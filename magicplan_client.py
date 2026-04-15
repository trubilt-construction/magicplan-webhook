#!/usr/bin/env python3
"""
magicplan API Client
- Lists projects
- Gets project details
- Downloads files
- Prepares for Dropbox upload
"""

import requests
import json
import os
from datetime import datetime

# API Configuration
API_BASE = "https://cloud.magicplan.app/api/v2"
CUSTOMER_ID = "60eedb08334e7"
API_KEY = "6a980b647acdf33cebfd12ce20d908fc8099"

HEADERS = {
    "customer": CUSTOMER_ID,
    "key": API_KEY
}

class MagicPlanClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
    
    def get_workspace(self):
        """Get workspace info"""
        r = self.session.get(f"{API_BASE}/workspace")
        r.raise_for_status()
        return r.json()
    
    def get_projects(self, limit=10, page=1):
        """Get list of projects"""
        r = self.session.get(f"{API_BASE}/projects", params={"limit": limit, "page": page})
        r.raise_for_status()
        return r.json()
    
    def get_project(self, project_id):
        """Get single project details"""
        r = self.session.get(f"{API_BASE}/projects/{project_id}")
        r.raise_for_status()
        return r.json()
    
    def get_project_files(self, project_id, filetype=None):
        """Get files for a project"""
        params = {"project_id": project_id}
        if filetype:
            params["filetype"] = filetype
        r = self.session.get(f"{API_BASE}/projects/{project_id}/files", params=params)
        r.raise_for_status()
        return r.json()
    
    def download_file(self, file_url, output_path):
        """Download a file from URL"""
        r = requests.get(file_url)
        r.raise_for_status()
        with open(output_path, 'wb') as f:
            f.write(r.content)
        return output_path

def main():
    client = MagicPlanClient()
    
    print("="*60)
    print("MAGICPLAN API EXPLORATION")
    print("="*60)
    
    # 1. Get workspace info
    print("\n1. WORKSPACE INFO:")
    workspace = client.get_workspace()
    print(f"   Name: {workspace['data']['name']}")
    print(f"   Owner: {workspace['data']['owner']}")
    print(f"   Supported formats: {workspace['data']['formats']}")
    
    # 2. Get recent projects
    print("\n2. RECENT PROJECTS:")
    projects = client.get_projects(limit=5)
    for p in projects['data'][:5]:
        print(f"   - {p['name']} (ID: {p['id'][:20]}...)")
    
    # 3. Get detailed info for Emerald Isle project
    print("\n3. EMERALD ISLE PROJECT DETAILS:")
    project = client.get_project("99fc08a3-b2a4-4ca4-aec3-164591142f23")
    data = project['data']
    print(f"   Name: {data['name']}")
    print(f"   Address: {data['address']['street']}, {data['address']['city']}, {data['address']['postal_code']}")
    print(f"   Plan ID: {data['plan_id']}")
    print(f"   Created: {data['user_created']}")
    
    # 4. Get project files
    print("\n4. PROJECT FILES:")
    files = client.get_project_files("99fc08a3-b2a4-4ca4-aec3-164591142f23")
    print(f"   Total files: {len(files.get('data', []))}")
    for f in files.get('data', [])[:5]:
        print(f"   - {f['filename']} ({f['filetype']}, {f['file']['size']} bytes)")
    
    # 5. Show what we need for Dropbox integration
    print("\n" + "="*60)
    print("DROPB0X INTEGRATION REQUIREMENTS:")
    print("="*60)
    print("""
For exporting magicplan data to Dropbox, we have TWO options:

OPTION A: Webhook-based (Recommended for automatic export)
- Set up a webhook server to receive export notifications
- When user clicks "Export" in magicplan, webhook receives file URLs
- Download files and upload to Dropbox
- Requires: Public webhook URL + Flask/FastAPI server

OPTION B: API-based (Manual/polling approach)
- Use API to get existing images from projects
- Need to trigger PDF/DXF generation somehow
- Can be run on-demand or scheduled

Which approach would you prefer?
""")

if __name__ == "__main__":
    main()
