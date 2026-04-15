#!/usr/bin/env python3
"""
Dropbox Uploader for magicplan exports
Handles file downloads and Dropbox uploads
"""

import os
import json
import requests
from datetime import datetime
from urllib.parse import urlparse, unquote

class DropboxUploader:
    def __init__(self, access_token):
        self.access_token = access_token
        self.base_url = "https://api.dropboxapi.com/2"
        self.content_url = "https://content.dropboxapi.com/2"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    
    def upload_from_url(self, url, dropbox_path, filename_prefix=""):
        """
        Download file from URL and upload to Dropbox
        
        Args:
            url: Source URL (can be S3 or other)
            dropbox_path: Destination folder in Dropbox
            filename_prefix: Optional prefix for filename
        
        Returns:
            Dropbox path of uploaded file
        """
        # Download the file
        response = requests.get(url)
        response.raise_for_status()
        content = response.content
        
        # Determine filename from URL
        parsed = urlparse(url)
        url_filename = unquote(os.path.basename(parsed.path))
        
        # Create destination filename
        if filename_prefix:
            ext = os.path.splitext(url_filename)[1]
            dest_filename = f"{filename_prefix}_{url_filename}"
        else:
            dest_filename = url_filename
        
        # Full Dropbox path
        full_path = f"{dropbox_path}/{dest_filename}"
        
        return self.upload_file(content, full_path, url_filename)
    
    def upload_file(self, content, dropbox_path, original_filename=""):
        """
        Upload file content to Dropbox
        
        Args:
            content: File content (bytes)
            dropbox_path: Full path in Dropbox (e.g., /folder/file.jpg)
            original_filename: Original filename for metadata
        
        Returns:
            Dropbox path of uploaded file
        """
        # Ensure path starts with /
        if not dropbox_path.startswith('/'):
            dropbox_path = '/' + dropbox_path
        
        # Determine content type
        ext = os.path.splitext(dropbox_path)[1].lower()
        content_type = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.pdf': 'application/pdf',
            '.dxf': 'application/dxf',
            '.svg': 'image/svg+xml',
            '.xml': 'application/xml',
            '.html': 'text/html',
            '.json': 'application/json',
            '.mp': 'application/octet-stream',
            '.ifc': 'application/octet-stream',
            '.usdz': 'application/octet-stream',
            '.obj': 'text/plain'
        }.get(ext, 'application/octet-stream')
        
        # Upload via Dropbox API
        dropbox_api_arg = json.dumps({
            "path": dropbox_path,
            "mode": "add",  # Add new file, don't overwrite
            "autorename": True,  # Auto-rename if exists
            "mute": False
        })
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/octet-stream",
            "Dropbox-API-Arg": dropbox_api_arg
        }
        
        response = requests.post(
            f"{self.content_url}/files/upload",
            headers=headers,
            data=content
        )
        
        if response.status_code != 200:
            raise Exception(f"Dropbox upload failed: {response.status_code} - {response.text}")
        
        result = response.json()
        return result.get('path_display', dropbox_path)
    
    def create_folder(self, path):
        """Create a folder in Dropbox"""
        if not path.startswith('/'):
            path = '/' + path
        
        data = json.dumps({
            "path": path,
            "autorename": False
        })
        
        response = requests.post(
            f"{self.base_url}/files/create_folder_v2",
            headers=self.headers,
            data=data
        )
        
        return response.json()
    
    def list_folder(self, path="/"):
        """List contents of a Dropbox folder"""
        if not path.startswith('/'):
            path = '/' + path
        
        data = json.dumps({"path": path})
        
        response = requests.post(
            f"{self.base_url}/files/list_folder",
            headers=self.headers,
            data=data
        )
        
        return response.json()
    
    def get_link(self, path):
        """Get a sharing link for a file"""
        if not path.startswith('/'):
            path = '/' + path
        
        data = json.dumps({
            "path": path,
            "settings": {
                "requested_visibility": "public"
            }
        })
        
        response = requests.post(
            f"{self.base_url}/sharing/create_shared_link_with_settings",
            headers=self.headers,
            data=data
        )
        
        return response.json()


def main():
    # Test with a sample file if token is provided
    token = os.environ.get("DROPBOX_ACCESS_TOKEN")
    if not token:
        print("DROPBOX_ACCESS_TOKEN not set")
        print("Usage: DROPBOX_ACCESS_TOKEN=xxx python3 dropbox_upload.py")
        return
    
    uploader = DropboxUploader(token)
    
    # Test listing root folder
    print("Testing Dropbox connection...")
    result = uploader.list_folder("/")
    print(f"Root folder contains {len(result.get('entries', []))} items")
    print("Dropbox integration ready!")


if __name__ == "__main__":
    main()
