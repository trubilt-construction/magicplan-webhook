#!/usr/bin/env python3
"""
Retroactively rename a MagicPlan project's exported photo/video files in
Dropbox with the room labels visible in cloud.magicplan.app.

Usage:
    # Preview the rename plan (default — does NOT touch Dropbox)
    python3 magicplan_rename_photos.py <project_id>

    # Actually rename the files
    python3 magicplan_rename_photos.py <project_id> --apply

Prereqs:
    pip install --break-system-packages playwright requests
    python3 -m playwright install chromium

What it does:
    1. Hits MagicPlan API /projects/<id>/files to enumerate every image/video
       file in the project. Captures: id, filename, filetype, symbol_id
       ('room' / 'plan' / None).
    2. Hits the magicplan-webhook /test-match to locate the matching Dropbox
       job folder.
    3. Launches Playwright (headed, persistent context) to navigate to
       cloud.magicplan.app's /photos/list. Overrides history.pushState to
       no-op, programmatically clicks every photo card, captures the would-be
       /photos/detail/<file_id> URL each click would have triggered.
    4. Joins the captures into a file_id -> room_label map, then composes
       a filename -> "<room> - NN.<ext>" rename plan.
    5. Prints the plan. If --apply is passed, performs the renames in the
       local Dropbox mount (the Dropbox client picks up renames and syncs
       them to the cloud — no Dropbox API needed for this step).

Auth:
    The script uses a persistent Playwright user-data-dir so MagicPlan login
    is reused between runs. First run will prompt you to sign in if the
    cookies aren't there yet.

Fallback room labels (per the README spec):
    - card-label is the project's own name -> "General"
    - symbol_instance.symbol_id is None    -> "Unassigned"
    - couldn't resolve at all              -> leave the UUID filename alone
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

import requests

MAGICPLAN_CUSTOMER = "60eedb08334e7"
MAGICPLAN_API_KEY = "6a980b647acdf33cebfd12ce20d908fc8099"
MAGICPLAN_API_BASE = "https://cloud.magicplan.app/api/v2"
MAGICPLAN_PHOTOS_URL = (
    "https://cloud.magicplan.app/estimator/projects/{pid}/photos/list"
)

WEBHOOK_HEALTH = "https://magicplan-webhook-production.up.railway.app/health"
WEBHOOK_TEST_MATCH = (
    "https://magicplan-webhook-production.up.railway.app/test-match"
)

DEFAULT_DROPBOX_BASE = Path("/Users/chadbaker/Dropbox/TRUBILT/JOBS")
PLAYWRIGHT_USER_DATA = Path.home() / ".opencode" / "playwright-magicplan"


# ---------------------------------------------------------------------------
# MagicPlan API
# ---------------------------------------------------------------------------

MP_HEADERS = {"customer": MAGICPLAN_CUSTOMER, "key": MAGICPLAN_API_KEY}


def get_project(project_id: str) -> dict:
    r = requests.get(
        f"{MAGICPLAN_API_BASE}/projects/{project_id}", headers=MP_HEADERS, timeout=15
    )
    r.raise_for_status()
    return r.json().get("data", {})


def get_project_files(project_id: str) -> list[dict]:
    """Paginated enumeration of every file the API returns for this project."""
    out = []
    page = 1
    while True:
        r = requests.get(
            f"{MAGICPLAN_API_BASE}/projects/{project_id}/files",
            headers=MP_HEADERS,
            params={"page": page},
            timeout=15,
        )
        r.raise_for_status()
        body = r.json()
        out.extend(body.get("data", []))
        if not body.get("page_info", {}).get("next_page"):
            break
        page += 1
    return out


def webhook_test_match(project_title: str) -> str | None:
    r = requests.get(
        WEBHOOK_TEST_MATCH, params={"project": project_title}, timeout=10
    )
    r.raise_for_status()
    return r.json().get("matched_folder")


# ---------------------------------------------------------------------------
# Playwright capture
# ---------------------------------------------------------------------------

CAPTURE_JS = r"""
async () => {
    const cards = Array.from(document.querySelectorAll('a[data-test="photo-card"]'));
    if (!cards.length) return { error: 'no_cards', count: 0 };

    // Snapshot labels BEFORE clicking (clicks may re-render and mutate text)
    const labels = cards.map(c => {
        const lines = (c.innerText || '').split('\n').map(s => s.trim()).filter(Boolean);
        return lines[lines.length - 1] || '';
    });

    // Hook history APIs to capture URLs without actually navigating
    const captured = [];
    const origPush = history.pushState;
    const origReplace = history.replaceState;
    history.pushState = function(state, title, url) {
        if (url) captured.push({ idx: window.__rmIdx, url: String(url) });
    };
    history.replaceState = function() { /* swallow */ };

    // First pass: click each card with a 50ms yield so Vue's router task queue
    // can drain between clicks. ~5–8s wall time for ~100 cards.
    async function clickPass(indices, yieldMs) {
        for (const i of indices) {
            window.__rmIdx = i;
            cards[i].click();
            await new Promise(r => setTimeout(r, yieldMs));
        }
    }

    function buildIdxToId() {
        const out = {};
        for (const c of captured) {
            const m = c.url.match(/\/photos\/detail\/([a-f0-9-]{36})/);
            if (m && !(c.idx in out)) out[c.idx] = m[1];
        }
        return out;
    }

    // Pass 1: all cards in DOM order, fast yield
    await clickPass(cards.map((_, i) => i), 50);

    // Up to 3 retry passes for any cards that didn't capture, with a longer
    // yield each time. Vue occasionally coalesces back-to-back clicks under
    // load (especially in daemon-launched Chromium); retrying with a slower
    // pace virtually always recovers them.
    for (let attempt = 1; attempt <= 3; attempt++) {
        const idxToId = buildIdxToId();
        const missing = cards.map((_, i) => i).filter(i => !idxToId[i]);
        if (missing.length === 0) break;
        await clickPass(missing, 100 * attempt);  // 100ms, 200ms, 300ms
    }

    // Restore
    history.pushState = origPush;
    history.replaceState = origReplace;
    delete window.__rmIdx;

    const idxToId = buildIdxToId();
    const result = labels.map((label, idx) => ({
        idx,
        label,
        file_id: idxToId[idx] || null,
    }));
    return {
        totalCards: cards.length,
        captures: captured.length,
        mapped: result.filter(r => r.file_id).length,
        rows: result,
    };
}
"""


def capture_room_map(project_id: str, headless: bool = False, seed: bool = False) -> list[dict]:
    """Drive Playwright through cloud.magicplan.app and return label rows.

    Uses an explicit storage_state.json to carry MagicPlan auth across
    runs (instead of Chromium's built-in cookie persistence which depends
    on macOS Keychain access — that breaks for LaunchAgent contexts).

    First-run flow: pass --seed (passed in via the `seed` arg). Launches
    a headed Chromium, navigates to MagicPlan, lets the user sign in,
    dumps the resulting cookies+localStorage to STATE_FILE, exits.

    Normal flow: loads STATE_FILE into a fresh non-persistent context.
    Works headed or headless, in user terminal or daemon context.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "ERROR: Playwright not installed. Run:\n"
            "  pip install playwright requests\n"
            "  python3 -m playwright install chromium",
            file=sys.stderr,
        )
        sys.exit(1)

    PLAYWRIGHT_USER_DATA.mkdir(parents=True, exist_ok=True)
    state_file = PLAYWRIGHT_USER_DATA / "state.json"
    photos_url = MAGICPLAN_PHOTOS_URL.format(pid=project_id)

    NORMAL_UA = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    )

    # --- Seed mode: first-time sign-in to populate state.json ---
    if seed:
        print(f"[playwright] seed mode: opening headed Chromium for sign-in...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            ctx = browser.new_context(viewport={"width": 1400, "height": 900})
            page = ctx.new_page()
            page.goto(photos_url, wait_until="domcontentloaded")
            print(
                f"[playwright] sign in to MagicPlan in the browser, navigate "
                f"until you see the photos list (or any logged-in page), then "
                f"come back here and press Enter."
            )
            input("Press Enter once you're signed in... ")
            ctx.storage_state(path=str(state_file))
            browser.close()
        print(f"[playwright] saved auth state to {state_file}")
        return []

    # --- Normal mode: load state.json and run the capture ---
    if not state_file.exists():
        print(
            f"ERROR: no auth state at {state_file}.\n"
            f"Run once with --seed to sign in:\n"
            f"  python3 {sys.argv[0]} {project_id} --seed",
            file=sys.stderr,
        )
        sys.exit(2)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
            ],
            ignore_default_args=["--enable-automation"] if headless else None,
        )
        ctx = browser.new_context(
            storage_state=str(state_file),
            viewport={"width": 1400, "height": 900},
            user_agent=NORMAL_UA if headless else None,
        )
        if headless:
            ctx.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', "
                "{get: () => undefined});"
            )
        page = ctx.new_page()
        page.goto(photos_url, wait_until="domcontentloaded")

        print(f"[playwright] waiting for photo cards to render (headless={headless})...")
        try:
            page.wait_for_selector('a[data-test="photo-card"]', timeout=30_000)
        except Exception:
            try:
                diag_url = page.url
                diag_title = page.title()
                diag_text = (page.inner_text("body") or "")[:300]
            except Exception:
                diag_url = diag_title = diag_text = "<unavailable>"
            print(
                f"[playwright] no photo cards after 30s.\n"
                f"  page url:   {diag_url}\n"
                f"  page title: {diag_title}\n"
                f"  page text:  {diag_text!r}\n"
                f"Auth state likely expired. Re-seed with:\n"
                f"  python3 {sys.argv[0]} {project_id} --seed",
                file=sys.stderr,
            )
            browser.close()
            sys.exit(2)

        # Give Vue a beat to finish rendering all cards
        page.wait_for_timeout(2_000)

        # Refresh state.json after every successful run so cookies stay current
        try:
            ctx.storage_state(path=str(state_file))
        except Exception:
            pass

        result = page.evaluate(CAPTURE_JS)
        browser.close()

    if isinstance(result, dict) and result.get("error") == "no_cards":
        print("ERROR: page reported no photo cards", file=sys.stderr)
        sys.exit(1)
    return result.get("rows", [])


# ---------------------------------------------------------------------------
# Plan + rename
# ---------------------------------------------------------------------------

ROOM_LABEL_FALLBACKS = {
    "general_for_plan": "General",
    "unassigned": "Unassigned",
}


def normalize_label(card_label: str, project_name: str, symbol_id: str | None) -> str:
    """Map a raw card label to a usable room label per the README rules."""
    if not card_label:
        return ROOM_LABEL_FALLBACKS["unassigned"]
    if card_label.strip() == project_name.strip():
        return ROOM_LABEL_FALLBACKS["general_for_plan"]
    return card_label.strip()


def filename_safe(label: str) -> str:
    # Replace anything that's not alnum/space/dash/underscore with hyphen
    safe = re.sub(r"[^A-Za-z0-9 _\-]", "-", label).strip()
    return safe


def build_rename_plan(
    files: list[dict], rows: list[dict], project_name: str
) -> dict[str, str]:
    """Return a dict { current_filename: new_filename } for image/video files."""
    # Build file_id -> file metadata
    by_id = {f["id"]: f for f in files}

    # Pair each row with its file metadata
    plan: dict[str, str] = {}
    grouped = defaultdict(list)  # label -> [(file_id, filename, ext)]
    for row in rows:
        fid = row.get("file_id")
        if not fid:
            continue
        f = by_id.get(fid)
        if not f:
            continue
        filetype = f.get("filetype", "")
        if not (filetype.startswith("image/") or filetype.startswith("video/")):
            continue
        symbol_id = (
            (f.get("metadata") or {}).get("attached_to", {}).get("symbol_instance", {})
        ).get("symbol_id")
        label = normalize_label(row["label"], project_name, symbol_id)
        ext = os.path.splitext(f["filename"])[1].lower() or ""
        grouped[label].append((fid, f["filename"], ext))

    # Within each label, number sequentially in DOM order
    for label, items in grouped.items():
        for idx, (fid, filename, ext) in enumerate(items, start=1):
            new_name = f"{filename_safe(label)} - {idx:02d}{ext}"
            plan[filename] = new_name
    return plan


def apply_renames(folder: Path, plan: dict[str, str], dry_run: bool) -> dict:
    """Rename files in `folder` according to `plan`. Returns a stats dict."""
    stats = {"renamed": 0, "skipped_missing": 0, "skipped_existing": 0, "errors": 0}
    for old, new in plan.items():
        src = folder / old
        dst = folder / new
        if not src.exists():
            stats["skipped_missing"] += 1
            continue
        if dst.exists() and src != dst:
            stats["skipped_existing"] += 1
            continue
        if dry_run:
            continue
        try:
            src.rename(dst)
            stats["renamed"] += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR renaming {old} -> {new}: {exc}", file=sys.stderr)
            stats["errors"] += 1
    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply MagicPlan room labels to a Dropbox job folder")
    parser.add_argument("project_id", help="MagicPlan project UUID")
    parser.add_argument(
        "--dropbox-base",
        default=str(DEFAULT_DROPBOX_BASE),
        help=f"Dropbox JOBS root (default: {DEFAULT_DROPBOX_BASE})",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually rename files (default is dry-run preview)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Playwright in headless mode (no Chromium window). Requires "
             "auth state in ~/.opencode/playwright-magicplan/state.json (seed first).",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="One-time setup: open a headed Chromium, let the user sign in to "
             "MagicPlan, save the resulting cookies+localStorage to "
             "~/.opencode/playwright-magicplan/state.json. The daemon and "
             "subsequent runs use that state file (no Keychain involvement).",
    )
    args = parser.parse_args()

    print(f"[magicplan] fetching project metadata for {args.project_id}...")
    project = get_project(args.project_id)
    project_name = project.get("name", "?")
    print(f"           name: {project_name}")
    addr = project.get("address", {})
    print(f"           address: {addr.get('street','?')}, {addr.get('city','?')} {addr.get('postal_code','')}")

    print("[magicplan] enumerating project files...")
    files = get_project_files(args.project_id)
    by_filetype = defaultdict(int)
    for f in files:
        by_filetype[f.get("filetype", "?")] += 1
    print(f"           total: {len(files)} files {dict(by_filetype)}")

    print(f"[webhook] resolving Dropbox folder via /test-match...")
    matched = webhook_test_match(project_name)
    if not matched:
        print(f"           ERROR: no matched folder for project '{project_name}'", file=sys.stderr)
        return 2
    print(f"           matched: {matched}")

    job_folder = Path(args.dropbox_base) / matched
    photos_folder = job_folder / "PICTURES" / "EXISTING CONDITIONS"
    if not photos_folder.is_dir():
        photos_folder = job_folder / "PICTURES"
    print(f"           target folder: {photos_folder}")
    if not photos_folder.is_dir():
        print(f"           ERROR: folder doesn't exist", file=sys.stderr)
        return 2

    if args.seed:
        # Seed mode: just capture auth state and exit (no rename plan needed).
        capture_room_map(args.project_id, seed=True)
        print(
            "[seed] done. You can now run the script normally (with or without "
            "--apply, with or without --headless)."
        )
        return 0

    print(f"[playwright] capturing room labels from cloud.magicplan.app (headless={args.headless})...")
    rows = capture_room_map(args.project_id, headless=args.headless)
    mapped = sum(1 for r in rows if r.get("file_id"))
    print(f"             cards: {len(rows)}, mapped to file_id: {mapped}")
    if mapped == 0:
        print("             ERROR: nothing captured. Aborting before any rename.", file=sys.stderr)
        return 3

    print("[plan] building rename plan...")
    plan = build_rename_plan(files, rows, project_name)
    if not plan:
        print("       no renames computed (no image/video files matched).")
        return 0

    # Group plan entries by target room label for human-readable output
    grouped_print = defaultdict(list)
    for old, new in plan.items():
        # Reverse-lookup label from new name (strip " - NN.<ext>")
        m = re.match(r"^(.*?) - \d+\.[A-Za-z0-9]+$", new)
        label = m.group(1) if m else new
        grouped_print[label].append((old, new))

    print(f"\n[plan] {len(plan)} files would be renamed (in {photos_folder.name}):")
    for label in sorted(grouped_print):
        items = grouped_print[label]
        print(f"  {label}: {len(items)}")
        for old, new in items[:2]:
            print(f"    {old}  ->  {new}")
        if len(items) > 2:
            print(f"    ... and {len(items) - 2} more")

    print()
    if not args.apply:
        print("(dry-run; pass --apply to actually rename the files)")
        return 0

    print("[apply] performing renames...")
    stats = apply_renames(photos_folder, plan, dry_run=False)
    print(
        f"        renamed: {stats['renamed']}  "
        f"skipped (already-renamed/dest-exists): {stats['skipped_existing']}  "
        f"skipped (source missing): {stats['skipped_missing']}  "
        f"errors: {stats['errors']}"
    )
    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
