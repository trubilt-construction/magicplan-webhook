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

# Configuration
MAGICPLAN_CUSTOMER = "60eedb08334e7"
MAGICPLAN_API_KEY = "6a980b647acdf33cebfd12ce20d908fc8099"
DROPBOX_JOB_FOLDER = "/Trubilt/JOBS"

DROPBOX_TOKEN = os.environ.get("DROPBOX_ACCESS_TOKEN", "")
if not DROPBOX_TOKEN:
    token_file = os.path.expanduser("~/.opencode/dropbox_token.txt")
    if os.path.exists(token_file):
        with open(token_file, 'r') as f:
            DROPBOX_TOKEN = f.read().strip()

HEADERS = {
    "customer": MAGICPLAN_CUSTOMER,
    "key": MAGICPLAN_API_KEY
}

def similarity(a, b):
    """Calculate string similarity"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def get_dropbox_folders(path):
    """Get folders in Dropbox path"""
    headers = {
        "Authorization": f"Bearer {DROPBOX_TOKEN}",
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

def find_matching_folder(address, folders, project_name=""):
    """Find the best matching folder for an address"""
    # Prefer project_name if address is empty/useless
    search_text = project_name if not address or address.lower() == "none" else f"{address} {project_name}"
    if not search_text or not folders:
        return None
    
    # Clean up search text
    search_parts = search_text.lower().replace(',', ' ').replace('-', ' ').split()
    
    best_match = None
    best_score = 0
    
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
            best_score = total_score
            best_match = folder
    
    # Only return if confidence is reasonable
    if best_score > 5:
        return best_match
    return None

def folder_exists(path):
    """Check if a folder exists in Dropbox"""
    headers = {
        "Authorization": f"Bearer {DROPBOX_TOKEN}",
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
        "Authorization": f"Bearer {DROPBOX_TOKEN}",
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

def upload_to_dropbox(content, path):
    """Upload file to Dropbox"""
    headers = {
        "Authorization": f"Bearer {DROPBOX_TOKEN}",
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
    
    # Check if EXISTING CONDITIONS subfolder exists, otherwise use PICTURES directly
    existing_conditions_path = f"{pictures_base}/EXISTING CONDITIONS"
    if folder_exists(existing_conditions_path):
        pictures_path = existing_conditions_path
        print(f"\n2. Using existing EXISTING CONDITIONS subfolder")
    else:
        pictures_path = pictures_base
        print(f"\n2. No EXISTING CONDITIONS folder - using PICTURES directly")
    
    print(f"   Pictures → {pictures_path}")
    print(f"   Plans    → {plans_path}")
    
    # Get files
    print(f"\n3. Fetching files from MagicPlan...")
    files = get_project_files(project_id)
    print(f"   Found {len(files)} files")
    
    # Prepare upload tasks
    upload_tasks = []
    for f in files:
        filename = f['filename']
        file_url = f['file']['url']
        filetype = f['filetype']
        
        # Determine destination
        if 'image' in filetype or 'video' in filetype:
            dest_path = f"{pictures_path}/{filename}"
            file_type = "photo/video"
        elif any(ext in filename.lower() for ext in ['.pdf', '.dxf', '.jpg', '.jpeg', '.png', '.svg']):
            dest_path = f"{plans_path}/{filename}"
            file_type = "plan/sketch"
        else:
            dest_path = f"{plans_path}/{filename}"
            file_type = "file"
        
        upload_tasks.append((filename, file_url, dest_path, file_type))
    
    # Upload with parallel threads
    print(f"\n4. Uploading files (parallel)...")
    uploaded_photos = 0
    uploaded_plans = 0
    skipped = 0
    completed = 0
    
    def upload_file(task):
        filename, file_url, dest_path, file_type = task
        try:
            content = download_file(file_url)
            upload_to_dropbox(content, dest_path)
            return ('success', file_type, filename)
        except Exception as e:
            return ('error', file_type, filename, str(e))
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(upload_file, task): task for task in upload_tasks}
        for future in as_completed(futures):
            result = future.result()
            completed += 1
            if result[0] == 'success':
                if 'photo' in result[1] or 'video' in result[1]:
                    uploaded_photos += 1
                else:
                    uploaded_plans += 1
                if completed % 20 == 0:
                    print(f"   Progress: {completed}/{len(files)} files")
            else:
                skipped += 1
                print(f"   ❌ {result[2]}: {result[3]}")
    
    print(f"\n{'='*60}")
    print(f"✅ EXPORT COMPLETE!")
    print(f"   Photos/Videos → {uploaded_photos}")
    print(f"   Plans/Files  → {uploaded_plans}")
    if skipped > 0:
        print(f"   Skipped       → {skipped}")
    print(f"   Location: {base_path}")
    print(f"{'='*60}")
    
    return True

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
    if not DROPBOX_TOKEN:
        print("ERROR: Dropbox token not found!")
        sys.exit(1)
    
    if len(sys.argv) < 2:
        list_projects()
        return
    
    if sys.argv[1] in ['--list', '-l']:
        list_projects()
        return
    
    project_id = sys.argv[1]
    success = export_project(project_id)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
