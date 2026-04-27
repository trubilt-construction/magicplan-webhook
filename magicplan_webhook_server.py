#!/usr/bin/env python3
"""
MagicPlan Webhook Server
Receives export notifications from MagicPlan and uploads to Dropbox

Folder mapping:
- Photos/Videos → /Trubilt/JOBS/[Job]/PICTURES/EXISTING CONDITIONS/ (or PICTURES/ if subfolder doesn't exist)
- Plans/Reports → /Trubilt/JOBS/[Job]/PLANS/

Usage:
    python3 magicplan_webhook_server.py [--port 5000]
    
For public URL (required for MagicPlan to reach it):
    ngrok http 5000
"""

import os
import sys
import json
import re
import requests
from difflib import SequenceMatcher
from flask import Flask, request, Response
import logging

from dropbox_upload import get_access_token

# Allowed Dropbox path prefixes for /file endpoint (defence-in-depth: stops the
# endpoint from being abused as a generic Dropbox file reader if the auth token
# leaks).
FILE_FETCH_ALLOWED_PREFIXES = ("/TRUBILT/JOBS/", "/Trubilt/JOBS/")
# Origin allowed to fetch via /file (Handoff). Keep tight — single origin.
FILE_FETCH_ALLOW_ORIGIN = "https://app.handoff.ai"


def _file_fetch_cors_headers():
    return {
        "Access-Control-Allow-Origin": FILE_FETCH_ALLOW_ORIGIN,
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "X-Auth-Token, Content-Type",
        "Access-Control-Max-Age": "3600",
        "Vary": "Origin",
    }


def _file_fetch_response(body, status, mimetype="text/plain"):
    resp = Response(body, status=status, mimetype=mimetype)
    for k, v in _file_fetch_cors_headers().items():
        resp.headers[k] = v
    return resp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
DROPBOX_JOB_FOLDER = "/Trubilt/JOBS"

# Local-dev fallback: if DROPBOX_ACCESS_TOKEN env var isn't set and a token
# file exists, copy its contents into the env var so get_access_token() can
# pick it up below. The preferred config in production is the refresh-token
# flow (DROPBOX_REFRESH_TOKEN + DROPBOX_APP_KEY + DROPBOX_APP_SECRET).
if not os.environ.get("DROPBOX_ACCESS_TOKEN"):
    token_file = os.path.expanduser("~/.opencode/dropbox_token.txt")
    if os.path.exists(token_file):
        with open(token_file, 'r') as f:
            os.environ["DROPBOX_ACCESS_TOKEN"] = f.read().strip()

# Cache job folders to avoid repeated API calls
_job_folders_cache = None
_cache_time = 0
CACHE_DURATION = 300  # 5 minutes

def similarity(a, b):
    """Calculate string similarity"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def get_dropbox_folders(path):
    """Get folders in Dropbox path"""
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
    return []

def find_matching_folder(search_text, folders):
    """Find the best matching folder for a project name/address"""
    if not search_text or not folders:
        return None
    
    search_parts = search_text.lower().replace(',', ' ').replace('-', ' ').split()
    
    best_match = None
    best_score = 0
    
    for folder in folders:
        folder_clean = folder.lower().replace('-', ' ').replace(',', ' ')
        
        score = 0
        for part in search_parts:
            if len(part) > 2 and part in folder_clean:
                score += len(part)
        
        text_similarity = similarity(search_text.lower(), folder.lower())
        total_score = score * 0.7 + text_similarity * 100 * 0.3
        
        if total_score > best_score:
            best_score = total_score
            best_match = folder
    
    if best_score > 5:
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

def create_folder(path):
    """Create a folder in Dropbox"""
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json"
    }
    requests.post(
        "https://api.dropboxapi.com/2/files/create_folder_v2",
        headers=headers,
        json={"path": path}
    )

def upload_to_dropbox(content, path):
    """Upload file to Dropbox"""
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/octet-stream",
        "Dropbox-API-Arg": json.dumps({
            "path": path,
            "mode": "add",
            "autorename": True
        })
    }
    r = requests.post(
        "https://content.dropboxapi.com/2/files/upload",
        headers=headers,
        data=content
    )
    return r.json()

def download_file(url):
    """Download a file from URL"""
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.content

def get_job_folders():
    """Get list of job folders (with caching)"""
    global _job_folders_cache, _cache_time
    import time
    
    if _job_folders_cache is None or time.time() - _cache_time > CACHE_DURATION:
        _job_folders_cache = get_dropbox_folders(DROPBOX_JOB_FOLDER)
        _cache_time = time.time()
        logger.info(f"Refreshed job folders cache: {len(_job_folders_cache)} folders")
    
    return _job_folders_cache

@app.route('/webhook', methods=['POST'])
def magicplan_webhook():
    """
    Receives MagicPlan export notifications.
    
    MagicPlan sends POST data with:
    - key: API key
    - email: User email
    - title: Project title
    - planid: Plan ID
    - project_id: Project ID
    - pdf, jpg0, jpg1, etc.: File URLs
    """
    try:
        # Parse form data
        data = request.form.to_dict()
        logger.info(f"Received webhook: title={data.get('title')}, project_id={data.get('project_id')}")
        
        # Validate API key
        expected_key = os.environ.get("MAGICPLAN_API_KEY", "6a980b647acdf33cebfd12ce20d908fc8099")
        if data.get('key') != expected_key:
            logger.warning(f"Invalid API key received")
            return Response('<status>1</status>', mimetype='text/xml'), 401
        
        # Extract project info
        project_title = data.get('title', 'Unknown Project')
        project_id = data.get('project_id', '')
        email = data.get('email', '')
        
        logger.info(f"Export received for: {project_title} (ID: {project_id})")
        
        # Find matching Dropbox folder
        folders = get_job_folders()
        matched_folder = find_matching_folder(project_title, folders)
        
        if not matched_folder:
            logger.warning(f"No matching folder found for: {project_title}")
            logger.info(f"Would upload to: /magicplan_exports/{project_title}")
            matched_folder = None
        else:
            logger.info(f"Matched to Dropbox folder: {matched_folder}")
        
        # Set destination paths
        if matched_folder:
            base_path = f"{DROPBOX_JOB_FOLDER}/{matched_folder}"
            pictures_base = f"{base_path}/PICTURES"
            plans_path = f"{base_path}/PLANS"
            
            # Check if EXISTING CONDITIONS subfolder exists
            existing_conditions_path = f"{pictures_base}/EXISTING CONDITIONS"
            if folder_exists(existing_conditions_path):
                pictures_path = existing_conditions_path
            else:
                pictures_path = pictures_base
        else:
            # Fallback to magicplan_exports
            base_path = f"/magicplan_exports/{project_title}"
            pictures_path = f"{base_path}/pictures"
            plans_path = f"{base_path}/plans"
        
        logger.info(f"Destination - Pictures: {pictures_path}")
        logger.info(f"Destination - Plans: {plans_path}")
        
        # Collect file URLs from webhook data
        files_to_download = []
        
        # Handle multiple file types
        file_patterns = [
            ('pdf', r'^pdf\d*$'),
            ('jpg', r'^jpg\d+$'),
            ('png', r'^png\d+$'),
            ('dxf', r'^dxf\d*$'),
            ('svg', r'^svg\d*$'),
        ]
        
        for key, pattern in file_patterns:
            # Check for single file (like 'pdf')
            if key in data and data[key] and data[key].startswith('http'):
                files_to_download.append((key, data[key]))
            
            # Check for numbered files (like 'jpg0', 'jpg1', etc.)
            for i in range(10):
                numbered_key = f"{key}{i}"
                if numbered_key in data and data[numbered_key] and data[numbered_key].startswith('http'):
                    files_to_download.append((numbered_key, data[numbered_key]))
        
        logger.info(f"Files to download: {[f[0] for f in files_to_download]}")
        
        # Download and upload to Dropbox
        if get_access_token():
            uploaded_photos = 0
            uploaded_plans = 0
            
            for file_key, url in files_to_download:
                try:
                    # Determine file type
                    is_image = re.match(r'^(jpg|png)\d*$', file_key, re.IGNORECASE)
                    is_video = 'video' in file_key.lower()
                    is_plan = file_key.lower().startswith(('pdf', 'dxf', 'svg'))
                    
                    # Set destination based on file type
                    if is_image or is_video:
                        dest_path = f"{pictures_path}/{file_key}_{project_id[:8]}"
                    else:
                        dest_path = f"{plans_path}/{file_key}_{project_id[:8]}"
                    
                    # Download and upload
                    content = download_file(url)
                    result = upload_to_dropbox(content, dest_path)
                    
                    if is_image or is_video:
                        uploaded_photos += 1
                    else:
                        uploaded_plans += 1
                    
                    logger.info(f"Uploaded {file_key}: {result.get('name', 'unknown')}")
                    
                except Exception as e:
                    logger.error(f"Failed to upload {file_key}: {e}")
            
            logger.info(f"Upload complete: {uploaded_photos} photos/videos, {uploaded_plans} plans")
        
        else:
            logger.warning("Dropbox auth not configured - files not uploaded")
        
        # Return success response
        return Response(
            '<MagicPlanService><status>0</status><message>Files received</message></MagicPlanService>',
            mimetype='text/xml'
        )
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        import traceback
        traceback.print_exc()
        return Response(
            f'<MagicPlanService><status>1</status><message>{str(e)}</message></MagicPlanService>',
            mimetype='text/xml'
        ), 500


@app.route('/file', methods=['GET', 'OPTIONS'])
def serve_dropbox_file():
    """Serve a Dropbox file's bytes to authenticated callers, with CORS for Handoff.

    Used by the Handoff page to fetch each captured file from Dropbox and
    upload it via Handoff's normal upload flow (DataTransfer + change event).

    Auth: shared secret in either the X-Auth-Token header or `token` query param,
    matched against the FILE_FETCH_TOKEN env var. The header is preferred so the
    secret stays out of server access logs.

    Path safety: the requested Dropbox path must start with /TRUBILT/JOBS/ (or
    /Trubilt/JOBS/) and must not contain "..". This stops the endpoint from
    being used to read arbitrary files in the linked Dropbox account if the
    token is ever exposed.
    """
    cors_headers = _file_fetch_cors_headers()

    # CORS preflight
    if request.method == 'OPTIONS':
        resp = Response('', status=204)
        for k, v in cors_headers.items():
            resp.headers[k] = v
        return resp

    # Auth
    expected_token = os.environ.get('FILE_FETCH_TOKEN', '').strip()
    if not expected_token:
        logger.error("/file called but FILE_FETCH_TOKEN is not set")
        return _file_fetch_response('Server not configured (FILE_FETCH_TOKEN missing)', 500)

    provided_token = request.headers.get('X-Auth-Token') or request.args.get('token') or ''
    if provided_token != expected_token:
        return _file_fetch_response('Unauthorized', 401)

    # Path
    dropbox_path = request.args.get('path', '')
    if not dropbox_path:
        return _file_fetch_response('Missing path parameter', 400)
    if '..' in dropbox_path or '\x00' in dropbox_path:
        return _file_fetch_response('Invalid path', 400)
    if not any(dropbox_path.startswith(p) for p in FILE_FETCH_ALLOWED_PREFIXES):
        return _file_fetch_response(
            'Path must be under /TRUBILT/JOBS/ or /Trubilt/JOBS/', 403
        )

    try:
        token = get_access_token()
    except Exception as e:
        logger.error(f"/file Dropbox auth failed: {e}")
        return _file_fetch_response('Dropbox auth failed on server', 500)
    if not token:
        return _file_fetch_response('Dropbox not configured on server', 500)

    try:
        from dropbox_upload import DropboxUploader
        uploader = DropboxUploader()
        content, content_type = uploader.download_file(dropbox_path)
    except Exception as e:
        logger.error(f"/file download failed for {dropbox_path}: {e}")
        return _file_fetch_response(f'Error: {e}', 502)

    resp = Response(content, status=200, mimetype=content_type)
    for k, v in cors_headers.items():
        resp.headers[k] = v
    # Caching off — the Handoff page fetches once per upload and we don't want
    # any intermediary caching the auth-gated bytes.
    resp.headers['Cache-Control'] = 'no-store'
    return resp


@app.route('/list', methods=['GET', 'OPTIONS'])
def list_dropbox_folder():
    """Return the list of files (recursively) under a Dropbox path.

    Used by the Handoff page uploader to discover what to upload for a given
    job folder, so the script doesn't need a hardcoded FILES list per job.

    Auth + path safety are identical to /file. Response is JSON:
        {"count": N, "files": [{"path", "name", "size", "type"}, ...]}
    """
    cors_headers = _file_fetch_cors_headers()

    if request.method == 'OPTIONS':
        resp = Response('', status=204)
        for k, v in cors_headers.items():
            resp.headers[k] = v
        return resp

    expected_token = os.environ.get('FILE_FETCH_TOKEN', '').strip()
    if not expected_token:
        logger.error("/list called but FILE_FETCH_TOKEN is not set")
        return _file_fetch_response('Server not configured (FILE_FETCH_TOKEN missing)', 500)

    provided_token = request.headers.get('X-Auth-Token') or request.args.get('token') or ''
    if provided_token != expected_token:
        return _file_fetch_response('Unauthorized', 401)

    dropbox_path = request.args.get('path', '')
    if not dropbox_path:
        return _file_fetch_response('Missing path parameter', 400)
    if '..' in dropbox_path or '\x00' in dropbox_path:
        return _file_fetch_response('Invalid path', 400)
    if not any(dropbox_path.startswith(p) for p in FILE_FETCH_ALLOWED_PREFIXES):
        return _file_fetch_response(
            'Path must be under /TRUBILT/JOBS/ or /Trubilt/JOBS/', 403
        )

    try:
        token = get_access_token()
    except Exception as e:
        logger.error(f"/list Dropbox auth failed: {e}")
        return _file_fetch_response('Dropbox auth failed on server', 500)
    if not token:
        return _file_fetch_response('Dropbox not configured on server', 500)

    try:
        from dropbox_upload import DropboxUploader
        uploader = DropboxUploader()
        files = uploader.list_folder_recursive(dropbox_path)
    except Exception as e:
        logger.error(f"/list listing failed for {dropbox_path}: {e}")
        return _file_fetch_response(f'Error: {e}', 502)

    # Annotate each file with a content-type guess so the uploader can pass it
    # straight into File() without doing the lookup itself.
    EXT_TO_TYPE = {
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
        '.heic': 'image/heic',
        '.pdf': 'application/pdf',
        '.mp4': 'video/mp4', '.mov': 'video/quicktime',
        '.txt': 'text/plain',
        '.dxf': 'application/dxf', '.svg': 'image/svg+xml',
        '.xml': 'application/xml', '.json': 'application/json',
    }
    for f in files:
        ext = os.path.splitext(f.get('name', ''))[1].lower()
        f['type'] = EXT_TO_TYPE.get(ext, 'application/octet-stream')

    body = json.dumps({'count': len(files), 'files': files})
    resp = Response(body, status=200, mimetype='application/json')
    for k, v in cors_headers.items():
        resp.headers[k] = v
    resp.headers['Cache-Control'] = 'no-store'
    return resp


@app.route('/pull/<project_id>', methods=['POST', 'OPTIONS'])
def pull_project(project_id):
    """Pull a MagicPlan project's full file set into the matching Dropbox job folder.

    Triggered by the trubilt-magicplan-export skill via Chrome MCP fetch — same
    underlying export logic as the magicplan_export_mapped.py CLI (we import its
    export_project). This exists so the skill doesn't need shell access on the
    user's machine.

    Auth: shared secret in `X-Auth-Token` header or `token` query param,
    matched against the FILE_FETCH_TOKEN env var (same secret as /file and /list).

    project_id safety: must look like a hyphen-and-hex UUID (no path traversal).

    Long-running: /pull can take 30+ seconds for projects with 100+ files. The
    Procfile bumps gunicorn --timeout to 300 to accommodate.

    Response (JSON): the dict returned by export_project (matched_folder, counts,
    failure_details, etc.) plus a `log` field with the captured stdout.
    """
    # CORS preflight (skill calls /pull from a same-origin Chrome tab navigated
    # to the Railway domain, so CORS isn't strictly needed — but be permissive
    # for any future cross-origin caller; the token gate is the actual auth).
    if request.method == 'OPTIONS':
        resp = Response('', status=204)
        origin = request.headers.get('Origin', '*')
        resp.headers['Access-Control-Allow-Origin'] = origin
        resp.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        resp.headers['Access-Control-Allow-Headers'] = 'X-Auth-Token, Content-Type'
        resp.headers['Vary'] = 'Origin'
        return resp

    # Auth
    expected_token = os.environ.get('FILE_FETCH_TOKEN', '').strip()
    if not expected_token:
        logger.error("/pull called but FILE_FETCH_TOKEN is not set")
        return Response('Server not configured (FILE_FETCH_TOKEN missing)', status=500)
    provided = request.headers.get('X-Auth-Token') or request.args.get('token') or ''
    if provided != expected_token:
        return Response('Unauthorized', status=401)

    # Path safety on project_id
    if not re.fullmatch(r'[a-fA-F0-9-]{8,64}', project_id):
        return Response(
            json.dumps({"ok": False, "error": "invalid_project_id"}),
            mimetype='application/json',
            status=400,
        )

    # Run export with stdout captured for the response 'log' field
    from io import StringIO
    from contextlib import redirect_stdout
    try:
        import magicplan_export_mapped
    except Exception as exc:
        logger.exception("/pull: failed to import magicplan_export_mapped")
        return Response(
            json.dumps({"ok": False, "error": f"import_failed: {exc}"}),
            mimetype='application/json',
            status=500,
        )

    buf = StringIO()
    try:
        with redirect_stdout(buf):
            result = magicplan_export_mapped.export_project(project_id)
    except Exception as exc:
        logger.exception(f"/pull: export_project crashed for {project_id}")
        return Response(
            json.dumps({
                "ok": False,
                "error": str(exc),
                "log": buf.getvalue(),
            }),
            mimetype='application/json',
            status=500,
        )

    # export_project returns False if the matcher didn't find a folder (no upload attempted),
    # or a dict with the per-run summary.
    if result is False:
        body = {
            "ok": False,
            "error": "no_matching_folder",
            "log": buf.getvalue(),
        }
        return Response(json.dumps(body), mimetype='application/json', status=200)

    if isinstance(result, dict):
        result["log"] = buf.getvalue()
        return Response(json.dumps(result), mimetype='application/json', status=200)

    # Defensive: shouldn't happen but don't crash on unexpected shape
    return Response(
        json.dumps({"ok": False, "error": "unexpected_result_shape", "log": buf.getvalue()}),
        mimetype='application/json',
        status=500,
    )


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    try:
        configured = bool(get_access_token())
    except Exception:
        configured = False
    return {"status": "ok", "dropbox_configured": configured}

@app.route('/test', methods=['GET'])
def test_page():
    """Test page"""
    return """
    <html><body>
    <h1>MagicPlan Webhook Server</h1>
    <p>Server is running!</p>
    <p>Webhook URL: <code>/webhook</code></p>
    <ul>
        <li>Dropbox configured: {}</li>
        <li>Job folders: {}</li>
    </ul>
    </body></html>
    """.format(
        "Yes" if get_access_token() else "No",
        len(get_job_folders()) if get_access_token() else "N/A"
    )

@app.route('/test-match', methods=['GET'])
def test_match():
    """Test folder matching"""
    project_name = request.args.get('project', '')
    folders = get_job_folders()
    matched = find_matching_folder(project_name, folders)
    return {
        "project": project_name,
        "matched_folder": matched,
        "total_folders": len(folders)
    }

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='MagicPlan Webhook Server')
    parser.add_argument('--port', type=int, default=5000, help='Port to run on')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()
    
    print("="*60)
    print("MAGICPLAN WEBHOOK SERVER")
    print("="*60)
    print(f"Starting on port {args.port}...")
    print(f"Webhook URL: http://localhost:{args.port}/webhook")
    print(f"Dropbox: {'Configured' if get_access_token() else 'NOT CONFIGURED'}")
    print(f"Job folders: {len(get_job_folders()) if get_access_token() else 0}")
    print("")
    print("To expose to internet (for MagicPlan):")
    print(f"  ngrok http {args.port}")
    print("="*60)
    
    app.run(host='0.0.0.0', port=args.port, debug=args.debug)
