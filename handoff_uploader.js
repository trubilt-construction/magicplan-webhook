/**
 * Handoff bulk uploader — runs in DevTools console on a Handoff project's Files tab.
 *
 * For any future Trubilt job, edit the two constants at the top of this script
 * and paste the whole file into the Console while you're on that project's
 * Files tab. The script asks the magicplan-webhook bridge for the file list
 * under JOB_PATH and uploads each one through Handoff's normal upload flow.
 *
 * Prereqs (set up once, permanent):
 *   - magicplan-webhook is deployed with /file + /list endpoints
 *   - FILE_FETCH_TOKEN, DROPBOX_REFRESH_TOKEN, DROPBOX_APP_KEY, DROPBOX_APP_SECRET set on Railway
 *
 * Usage:
 *   1. Open the Handoff project's Files tab in Chrome.
 *   2. DevTools (Cmd+Opt+J) → Console.
 *   3. Edit FILE_FETCH_TOKEN and JOB_PATH below, then paste the whole script.
 *   4. Press Enter. Watch progress in the Console.
 *   5. To stop early: window.__cwUploadStop = true
 */
(async () => {
  // ---- EDIT ME ----
  const FILE_FETCH_TOKEN = 'PASTE_YOUR_TOKEN_HERE';
  const JOB_PATH = '/TRUBILT/JOBS/<EDIT_THIS_TO_THE_DROPBOX_FOLDER_FOR_THIS_UNIT>';
  // -----------------

  const BASE = 'https://magicplan-webhook-production.up.railway.app';
  const PACING_MS = 1500; // delay between uploads so Handoff's queue keeps up

  if (FILE_FETCH_TOKEN === 'PASTE_YOUR_TOKEN_HERE') {
    console.error('Set FILE_FETCH_TOKEN before running.');
    return;
  }
  if (JOB_PATH.includes('<EDIT_THIS')) {
    console.error('Set JOB_PATH to the Dropbox folder for this unit before running.');
    return;
  }

  const input = document.querySelector('input[type="file"]');
  if (!input) {
    console.error('No file input found on this page. Are you on the Files tab of a Handoff project?');
    return;
  }

  // 1. Ask the bridge for the file list under JOB_PATH.
  console.log(`Fetching file list under ${JOB_PATH} ...`);
  let FILES;
  try {
    const listUrl = `${BASE}/list?token=${encodeURIComponent(FILE_FETCH_TOKEN)}&path=${encodeURIComponent(JOB_PATH)}`;
    const listResp = await fetch(listUrl);
    if (!listResp.ok) {
      console.error(`Failed to list files: HTTP ${listResp.status} — ${(await listResp.text()).slice(0, 300)}`);
      return;
    }
    const json = await listResp.json();
    FILES = json.files || [];
    if (FILES.length === 0) {
      console.error('No files found at that path. Check JOB_PATH.');
      return;
    }
    const totalMB = (FILES.reduce((a, f) => a + (f.size || 0), 0) / 1024 / 1024).toFixed(1);
    console.log(`Found ${FILES.length} files (total ${totalMB} MB).`);
  } catch (e) {
    console.error('Error fetching file list:', e);
    return;
  }

  // 2. Iterate uploads.
  console.log(`Starting upload. Stop early with: window.__cwUploadStop = true`);
  window.__cwUploadStatus = { ok: 0, fail: 0, total: FILES.length, current: null, errors: [], started: Date.now(), done: false };
  window.__cwUploadStop = false;
  let ok = 0, fail = 0;
  const t0 = Date.now();

  for (let i = 0; i < FILES.length; i++) {
    if (window.__cwUploadStop) { console.warn('Stopped by user.'); break; }
    const f = FILES[i];
    window.__cwUploadStatus.current = `[${i + 1}/${FILES.length}] ${f.name}`;
    const tag = `[${i + 1}/${FILES.length}]`;
    try {
      const fileUrl = `${BASE}/file?token=${encodeURIComponent(FILE_FETCH_TOKEN)}&path=${encodeURIComponent(f.path)}`;
      const resp = await fetch(fileUrl);
      if (!resp.ok) {
        const text = await resp.text().catch(() => '');
        console.error(`${tag} FAIL ${f.name}: HTTP ${resp.status} ${text.slice(0, 200)}`);
        fail++;
        window.__cwUploadStatus.fail = fail;
        window.__cwUploadStatus.errors.push({ name: f.name, status: resp.status });
        continue;
      }
      const blob = await resp.blob();
      const file = new File([blob], f.name, { type: f.type || 'application/octet-stream' });
      const dt = new DataTransfer();
      dt.items.add(file);
      const inp = document.querySelector('input[type="file"]');
      Object.defineProperty(inp, 'files', { value: dt.files, configurable: true });
      inp.dispatchEvent(new Event('input', { bubbles: true }));
      inp.dispatchEvent(new Event('change', { bubbles: true }));
      ok++;
      window.__cwUploadStatus.ok = ok;
      const elapsed = ((Date.now() - t0) / 1000).toFixed(0);
      console.log(`${tag} ✓ ${f.name} (${(blob.size / 1024).toFixed(0)} KB) — ok=${ok} fail=${fail} ${elapsed}s`);
    } catch (e) {
      fail++;
      window.__cwUploadStatus.fail = fail;
      window.__cwUploadStatus.errors.push({ name: f.name, err: String(e).slice(0, 200) });
      console.error(`${tag} ERROR ${f.name}:`, e);
    }
    await new Promise(r => setTimeout(r, PACING_MS));
  }

  window.__cwUploadStatus.done = true;
  window.__cwUploadStatus.elapsed = (Date.now() - t0) / 1000;
  const elapsed = ((Date.now() - t0) / 1000).toFixed(0);
  console.log(`DONE — ok=${ok} fail=${fail} in ${elapsed}s`);
})();
