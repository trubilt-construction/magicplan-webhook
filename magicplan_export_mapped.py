#!/usr/bin/env python3
"""
MagicPlan to Dropbox Export - Matches by Address
Photos → /Trubilt Job Folders/[Job]/pictures/existing conditions/
Plans/Reports → /Trubilt Job Folders/[Job]/plans/
"""

import os
import sys
import json
import requests
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor, as_completed

from dropbox_upload import get_access_token

# Configuration
MAGICPLAN_CUSTOMER = "60eedb08334e7"
MAGICPLAN_API_KEY = "6a980b647acdf33cebfd12ce20d908fc8099"
DROPBOX_JOB_FOLDER = "/Trubilt/JOBS"

# Local-dev credential loading.
#
# Order of preference (matches dropbox_upload.get_access_token()):
#   1. DROPBOX_REFRESH_TOKEN + DROPBOX_APP_KEY + DROPBOX_APP_SECRET (auto-refreshing,
#      preferred). If not in env, try ~/.opencode/dropbox.env (KEY=value lines).
#   2. DROPBOX_ACCESS_TOKEN (legacy static, expires every ~4 hours).
#      If not in env, try ~/.opencode/dropbox_token.txt as a static-token file.
#
# This mirrors the auth pattern the Railway-deployed webhook server uses, so
# refreshing your local credentials means setting the same env vars Railway
# already has. Both fallback files live in ~/.opencode/ so they don't end up
# in shell rc files or the repo.

def _load_env_file_if_present(path):
    """Load KEY=value lines from a dotenv-style file into os.environ.
    Existing env vars are not overwritten."""
    if not os.path.exists(path):
        return
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


# 1. Refresh-token credentials (preferred): try env, then ~/.opencode/dropbox.env
if not (
    os.environ.get("DROPBOX_REFRESH_TOKEN")
    and os.environ.get("DROPBOX_APP_KEY")
    and os.environ.get("DROPBOX_APP_SECRET")
):
    _load_env_file_if_present(os.path.expanduser("~/.opencode/dropbox.env"))

# 2. Legacy static-token fallback: only used if refresh-token mode isn't configured.
if (
    not os.environ.get("DROPBOX_REFRESH_TOKEN")
    and not os.environ.get("DROPBOX_ACCESS_TOKEN")
):
    token_file = os.path.expanduser("~/.opencode/dropbox_token.txt")
    if os.path.exists(token_file):
        with open(token_file, "r") as f:
            os.environ["DROPBOX_ACCESS_TOKEN"] = f.read().strip()

HEADERS = {
    "customer": MAGICPLAN_CUSTOMER,
    "key": MAGICPLAN_API_KEY
}

def similarity(a, b):
    """Calculate string similarity"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def get_dropbox_folders(path):
    """Get folders in Dropbox path. Raises on Dropbox API failure so callers
    don't mistake an auth error for an empty folder."""
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json"
    }
    r = requests.post(
        "https://api.dropboxapi.com/2/files/list_folder",
        headers=headers,
        json={"path": path}
    )
    if r.status_code == 200:
        return [e['name'] for e in r.json().get('entries', []) if e['.tag'] == 'folder']
    raise RuntimeError(
        f"Dropbox list_folder failed for {path}: "
        f"HTTP {r.status_code} - {r.text[:300]}"
    )

def find_matching_folder(address, folders, project_name=""):
    """Find the best matching folder for an address.

    Uses the project's street address (the part before the first comma) as the
    primary search text — that's what Dropbox folder names are based on. The
    project name is only used as a fallback when address is missing.

    Why not include the city/zip or project_name in the search text? Because
    folder names like ``307 TIMOTHY RD`` are short and don't contain city/zip
    tokens. When the search string includes ``Jacksonville 28546 Gucciardini
    Meeting``, every Jacksonville-area folder picks up a token-presence hit on
    "Jacksonville", and the longer search string drops the sequence-similarity
    score for the correct (short) folder. On 2026-04-28 that combination
    routed Gucciardini's 90 files to ``2119 NORTH DR, JACKSONVILLE 28540``
    instead of ``307 TIMOTHY RD``. See README.md "Known issues" for the full
    incident analysis.

    A street-only search ("307 Timothy Road" → tokens ``307`` + ``timothy``)
    matches the correct short folder cleanly and starves the wrong-address
    folders of any token hits.
    """
    # Prefer the street address only. Falls back to full address (which may be
    # all we have if the caller didn't pass a comma-separated form), then to
    # project_name when address is empty or literally "none".
    if address and address.lower() != "none":
        # Take the part before the first comma — typically just the street
        # ("307 Timothy Road" out of "307 Timothy Road, Jacksonville 28546").
        street_only = address.split(",", 1)[0].strip()
        search_text = street_only or address
    else:
        search_text = project_name

    if not search_text or not folders:
        return None

    # Clean up search text
    search_parts = search_text.lower().replace(',', ' ').replace('-', ' ').split()

    best_match = None
    best_score = 0
    second_best_score = 0

    for folder in folders:
        folder_clean = folder.lower().replace('-', ' ').replace(',', ' ')

        # Check each word
        score = 0
        matches = 0
        for part in search_parts:
            if len(part) > 2 and part in folder_clean:
                matches += 1
                score += len(part)  # Longer matches = higher score

        # Also check overall similarity
        text_similarity = similarity(search_text.lower(), folder.lower())

        # Combined score
        total_score = score * 0.7 + text_similarity * 100 * 0.3

        if total_score > best_score:
            second_best_score = best_score
            best_score = total_score
            best_match = folder
        elif total_score > second_best_score:
            second_best_score = total_score

    # Only return if confidence is reasonable AND the best beats the second-best
    # by a clear margin — close calls used to pick the wrong folder when the
    # winning margin was decided by city/zip tokens (e.g., "Jacksonville").
    if best_score > 10 and (best_score - second_best_score) >= 3:
        return best_match
    return None

def folder_exists(path):
    """Check if a folder exists in Dropbox"""
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json"
    }
    r = requests.post(
        "https://api.dropboxapi.com/2/files/get_metadata",
        headers=headers,
        json={"path": path}
    )
    return r.status_code == 200

def create_subfolders(parent_path, subfolders):
    """Create subfolders if they don't exist"""
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json"
    }
    
    for subfolder in subfolders:
        path = f"{parent_path}/{subfolder}"
        r = requests.post(
            "https://api.dropboxapi.com/2/files/create_folder_v2",
            headers=headers,
            json={"path": path}
        )
        # Ignore if already exists

def upload_to_dropbox(content, path, max_retries=4):
    """Upload file to Dropbox with retry-on-429.

    Dropbox responds with HTTP 429 (`too_many_write_operations`) under burst
    parallel writes and includes a `retry_after` hint (in seconds) we should
    honor. We retry up to `max_retries` times with exponential backoff floored
    at the server-suggested wait. Anything else non-200 raises so the caller
    counts it as a real failure.
    """
    import time as _t

    headers = {
        "Content-Type": "application/octet-stream",
        "Dropbox-API-Arg": json.dumps({
            "path": path,
            "mode": "add",
            "autorename": True,
        }),
    }

    attempt = 0
    while True:
        # Refresh the bearer per attempt so a long retry doesn't outlive the token.
        headers["Authorization"] = f"Bearer {get_access_token()}"
        r = requests.post(
            "https://content.dropboxapi.com/2/files/upload",
            headers=headers,
            data=content,
        )
        if r.status_code == 200:
            return r.json()

        # Honor 429 retry-after, with exponential backoff floor.
        if r.status_code == 429 and attempt < max_retries:
            try:
                body = r.json()
                hinted = int(
                    body.get("error", {}).get("retry_after")
                    or body.get("retry_after")
                    or 1
                )
            except Exception:
                hinted = 1
            backoff = max(hinted, 2 ** attempt)
            _t.sleep(backoff)
            attempt += 1
            continue

        raise RuntimeError(
            f"Dropbox upload failed for {path}: HTTP {r.status_code} - {r.text[:300]}"
        )


def list_folder_filenames(path):
    """Return a set of filenames (not paths) directly inside a Dropbox folder.

    Used for idempotency — the export loop skips any file whose target name is
    already present at the destination, so re-runs don't create (1)/(2) dupes.
    Returns an empty set if the folder doesn't exist (Dropbox 409). Raises on
    any other non-200 so we don't silently treat a real failure as 'empty folder'.
    """
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json",
    }
    names = set()
    cursor = None
    while True:
        if cursor is None:
            r = requests.post(
                "https://api.dropboxapi.com/2/files/list_folder",
                headers=headers,
                json={"path": path, "recursive": False},
                timeout=20,
            )
        else:
            r = requests.post(
                "https://api.dropboxapi.com/2/files/list_folder/continue",
                headers=headers,
                json={"cursor": cursor},
                timeout=20,
            )
        if r.status_code == 409:
            # Path not found — treat as empty folder (will be created on first upload).
            return names
        if r.status_code != 200:
            raise RuntimeError(
                f"Dropbox list_folder failed for {path}: HTTP {r.status_code} - {r.text[:300]}"
            )
        body = r.json()
        for entry in body.get("entries", []):
            if entry.get(".tag") == "file":
                names.add(entry.get("name"))
        if not body.get("has_more"):
            break
        cursor = body.get("cursor")
    return names

def download_file(url):
    """Download a file from URL"""
    r = requests.get(url)
    r.raise_for_status()
    return r.content

def get_projects(limit=50):
    r = requests.get(
        f"https://cloud.magicplan.app/api/v2/projects",
        headers=HEADERS,
        params={"limit": limit}
    )
    return r.json().get('data', [])

def get_project(project_id):
    r = requests.get(
        f"https://cloud.magicplan.app/api/v2/projects/{project_id}",
        headers=HEADERS
    )
    return r.json().get('data', {})

def get_project_files(project_id):
    """Get all files for a project (handles pagination)"""
    all_files = []
    page = 1
    
    while True:
        r = requests.get(
            f"https://cloud.magicplan.app/api/v2/projects/{project_id}/files",
            headers=HEADERS,
            params={"page": page}
        )
        data = r.json()
        all_files.extend(data.get('data', []))
        
        # Check if there are more pages
        page_info = data.get('page_info', {})
        if not page_info.get('next_page'):
            break
        page += 1
    
    return all_files

def export_project(project_id):
    """Export project files to correct Dropbox locations"""
    
    # Get project details
    project = get_project(project_id)
    project_name = project.get('name', 'Unknown')
    address = project.get('address', {})
    street = address.get('street', '')
    city = address.get('city', '')
    postal = address.get('postal_code', '')
    
    full_address = f"{street}, {city} {postal}".strip()
    
    print(f"\n{'='*60}")
    print(f"Project: {project_name}")
    print(f"Address: {full_address}")
    print(f"{'='*60}")
    
    # Get list of job folders from Dropbox
    print(f"\n1. Looking for matching folder in {DROPBOX_JOB_FOLDER}...")
    folders = get_dropbox_folders(DROPBOX_JOB_FOLDER)
    print(f"   Found {len(folders)} folders")
    
    # Find matching folder (using project name if address is empty)
    matched_folder = find_matching_folder(full_address, folders, project_name)
    
    if not matched_folder:
        print(f"\n❌ No matching folder found in Dropbox!")
        print(f"   Available folders:")
        for f in folders[:10]:
            print(f"   - {f}")
        if len(folders) > 10:
            print(f"   ... and {len(folders) - 10} more")
        return False
    
    print(f"   ✅ Matched to: {matched_folder}")
    
    # Set destination paths
    base_path = f"{DROPBOX_JOB_FOLDER}/{matched_folder}"
    pictures_base = f"{base_path}/PICTURES"
    plans_path = f"{base_path}/PLANS"
    scope_of_work_path = f"{base_path}/SCOPE OF WORK"

    # Check if EXISTING CONDITIONS subfolder exists, otherwise use PICTURES directly
    existing_conditions_path = f"{pictures_base}/EXISTING CONDITIONS"
    if folder_exists(existing_conditions_path):
        pictures_path = existing_conditions_path
        print(f"\n2. Using existing EXISTING CONDITIONS subfolder")
    else:
        pictures_path = pictures_base
        print(f"\n2. No EXISTING CONDITIONS folder - using PICTURES directly")

    print(f"   Pictures      → {pictures_path}")
    print(f"   Plans         → {plans_path}")
    print(f"   Scope of Work → {scope_of_work_path}  (Report PDFs)")
    
    # Get files
    print(f"\n3. Fetching files from MagicPlan...")
    files = get_project_files(project_id)
    print(f"   Found {len(files)} files")

    # Idempotency: list what's already in each destination so we don't re-upload
    # files that landed on a prior run (autorename would have created (1)/(2) dupes).
    print(f"\n3a. Checking what's already in Dropbox at the destinations...")
    existing_pictures = list_folder_filenames(pictures_path)
    existing_plans = list_folder_filenames(plans_path)
    existing_scope = list_folder_filenames(scope_of_work_path)
    print(f"   Pictures destination already has:      {len(existing_pictures)} files")
    print(f"   Plans destination already has:         {len(existing_plans)} files")
    print(f"   Scope of Work destination already has: {len(existing_scope)} files")

    # Prepare upload tasks (skip anything already present)
    upload_tasks = []
    pre_skipped_pictures = 0
    pre_skipped_plans = 0
    pre_skipped_scope = 0
    for f in files:
        filename = f['filename']
        file_url = f['file']['url']
        filetype = f['filetype']
        name_lower = filename.lower()

        # Determine destination based on filetype + filename hints.
        # Routing rules:
        #   * Images / videos        → pictures_path
        #   * PDFs containing "report" → scope_of_work_path
        #     (MagicPlan exports the project report as "<project> Report.pdf";
        #      Trubilt's convention is to keep the scope-narrative document
        #      separate from the floor plan drawings.)
        #   * Other PDFs / DXF / SVG → plans_path
        #   * Anything else (rare)   → plans_path
        if 'image' in filetype or 'video' in filetype:
            dest_path = f"{pictures_path}/{filename}"
            file_type = "photo/video"
            already = filename in existing_pictures
        elif name_lower.endswith('.pdf') and 'report' in name_lower:
            dest_path = f"{scope_of_work_path}/{filename}"
            file_type = "scope/report"
            already = filename in existing_scope
        elif any(ext in name_lower for ext in ['.pdf', '.dxf', '.jpg', '.jpeg', '.png', '.svg']):
            dest_path = f"{plans_path}/{filename}"
            file_type = "plan/sketch"
            already = filename in existing_plans
        else:
            dest_path = f"{plans_path}/{filename}"
            file_type = "file"
            already = filename in existing_plans

        if already:
            if 'photo' in file_type or 'video' in file_type:
                pre_skipped_pictures += 1
            elif 'scope' in file_type:
                pre_skipped_scope += 1
            else:
                pre_skipped_plans += 1
            continue

        upload_tasks.append((filename, file_url, dest_path, file_type))

    if pre_skipped_pictures or pre_skipped_plans or pre_skipped_scope:
        print(f"   Already present, skipping: {pre_skipped_pictures} photos/videos, "
              f"{pre_skipped_plans} plans, {pre_skipped_scope} scope/reports")
    print(f"   Will upload: {len(upload_tasks)} new files")

    # Upload with parallel threads
    print(f"\n4. Uploading files (parallel)...")
    uploaded_photos = 0
    uploaded_plans = 0
    uploaded_scope = 0
    failed = 0
    failure_details = []
    completed = 0

    def upload_file(task):
        filename, file_url, dest_path, file_type = task
        try:
            content = download_file(file_url)
            upload_to_dropbox(content, dest_path)
            return ('success', file_type, filename)
        except Exception as e:
            return ('error', file_type, filename, str(e))

    if upload_tasks:
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(upload_file, task): task for task in upload_tasks}
            for future in as_completed(futures):
                result = future.result()
                completed += 1
                if result[0] == 'success':
                    if 'photo' in result[1] or 'video' in result[1]:
                        uploaded_photos += 1
                    elif 'scope' in result[1]:
                        uploaded_scope += 1
                    else:
                        uploaded_plans += 1
                    if completed % 20 == 0:
                        print(f"   Progress: {completed}/{len(upload_tasks)} files")
                else:
                    failed += 1
                    failure_details.append({"filename": result[2], "error": result[3]})
                    print(f"   ❌ {result[2]}: {result[3]}")
    else:
        print(f"   (nothing to upload — all files already present)")

    print(f"\n{'='*60}")
    print(f"✅ EXPORT COMPLETE!")
    print(f"   Newly uploaded:   {uploaded_photos} photos/videos, {uploaded_plans} plans, {uploaded_scope} scope/reports")
    print(f"   Already present:  {pre_skipped_pictures} photos/videos, {pre_skipped_plans} plans, {pre_skipped_scope} scope/reports")
    if failed > 0:
        print(f"   Failed:           {failed} (see ❌ lines above)")
    print(f"   Location: {base_path}")
    print(f"{'='*60}")

    return {
        "ok": failed == 0,
        "matched_folder": matched_folder,
        "base_path": base_path,
        "destinations": {
            "pictures": pictures_path,
            "plans": plans_path,
            "scope_of_work": scope_of_work_path,
        },
        "newly_uploaded": {
            "photos_videos": uploaded_photos,
            "plans": uploaded_plans,
            "scope_reports": uploaded_scope,
        },
        "already_present": {
            "photos_videos": pre_skipped_pictures,
            "plans": pre_skipped_plans,
            "scope_reports": pre_skipped_scope,
        },
        "failed": failed,
        "failure_details": failure_details,
        "total_files_in_project": len(files),
    }

def list_projects():
    """List available projects"""
    print("\n" + "="*60)
    print("MAGICPLAN PROJECTS")
    print("="*60)
    
    projects = get_projects(limit=50)
    
    print(f"\n{'#':<3} {'Name':<40} {'Address':<35}")
    print("-" * 80)
    
    for i, p in enumerate(projects, 1):
        addr = p.get('address', {})
        street = addr.get('street', '')[:30]
        city = addr.get('city', '')[:20]
        print(f"{i:<3} {p['name'][:38]:<40} {street}, {city}")
    
    print(f"\nTo export: python3 magicplan_export_mapped.py [project_id]")

def main():
    try:
        token = get_access_token()
    except Exception as exc:
        print(f"ERROR: Dropbox auth failed: {exc}")
        print("Check DROPBOX_REFRESH_TOKEN + DROPBOX_APP_KEY + DROPBOX_APP_SECRET,")
        print("or DROPBOX_ACCESS_TOKEN, or ~/.opencode/dropbox_token.txt")
        sys.exit(1)
    if not token:
        print("ERROR: Dropbox token not found!")
        print("Set DROPBOX_REFRESH_TOKEN + DROPBOX_APP_KEY + DROPBOX_APP_SECRET")
        print("(refresh-token mode, recommended) or DROPBOX_ACCESS_TOKEN (legacy),")
        print("or place a static token in ~/.opencode/dropbox_token.txt")
        sys.exit(1)

    # Sanity-check the token actually works against Dropbox before doing real work.
    # Static access tokens expire every ~4 hours; we'd rather fail loudly here
    # than silently return [] and look like JOBS/ is empty.
    try:
        sanity = requests.post(
            "https://api.dropboxapi.com/2/files/list_folder",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"path": DROPBOX_JOB_FOLDER, "limit": 1},
            timeout=15,
        )
    except Exception as exc:
        print(f"ERROR: couldn't reach Dropbox API: {exc}")
        sys.exit(1)
    if sanity.status_code == 401:
        print("ERROR: Dropbox returned 401 (token expired or invalid).")
        print("Refresh your token. If you're using the static path:")
        print("  - regenerate a token in the Dropbox App Console")
        print("  - write it to ~/.opencode/dropbox_token.txt")
        print("If you'd rather not deal with this every 4 hours, set up refresh-token mode:")
        print("  DROPBOX_REFRESH_TOKEN, DROPBOX_APP_KEY, DROPBOX_APP_SECRET")
        sys.exit(1)
    if sanity.status_code != 200:
        print(f"ERROR: Dropbox sanity check failed: HTTP {sanity.status_code}")
        print(sanity.text[:500])
        sys.exit(1)
    
    if len(sys.argv) < 2:
        list_projects()
        return
    
    if sys.argv[1] in ['--list', '-l']:
        list_projects()
        return
    
    project_id = sys.argv[1]
    result = export_project(project_id)

    # export_project returns a dict (success-shaped) or False (matcher failed before any upload)
    if result is False or (isinstance(result, dict) and not result.get("ok", False)):
        sys.exit(1)

if __name__ == "__main__":
    main()
