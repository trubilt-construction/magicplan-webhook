#!/usr/bin/env python3
"""
Dropbox Uploader for magicplan exports
Handles file downloads and Dropbox uploads.

Authentication:
    Two modes are supported (refresh-token mode is preferred):

    1. Static access token (legacy, expires in ~4 hours):
           DROPBOX_ACCESS_TOKEN=sl....

    2. Refresh-token flow (recommended; access tokens are minted on demand):
           DROPBOX_APP_KEY=...
           DROPBOX_APP_SECRET=...
           DROPBOX_REFRESH_TOKEN=...

    The module-level get_access_token() returns a currently-valid access token
    using whichever mode is configured. When using refresh-token mode the
    access token is cached for its full TTL minus a 5-minute safety window.
"""

import os
import json
import time
import threading
import requests
from datetime import datetime
from urllib.parse import urlparse, unquote


# ---------------------------------------------------------------------------
# Token management
# ---------------------------------------------------------------------------

_token_lock = threading.Lock()
_token_cache = {"access_token": None, "expires_at": 0.0}


def _exchange_refresh_token(refresh_token, app_key, app_secret):
    """Mint a fresh short-lived access token from a refresh token."""
    response = requests.post(
        "https://api.dropbox.com/oauth2/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        auth=(app_key, app_secret),
        timeout=15,
    )
    if response.status_code != 200:
        raise Exception(
            f"Dropbox token refresh failed: "
            f"{response.status_code} - {response.text}"
        )
    return response.json()


def get_access_token():
    """Return a currently-valid Dropbox access token.

    Resolution order:
      1. If DROPBOX_REFRESH_TOKEN + DROPBOX_APP_KEY + DROPBOX_APP_SECRET are
         all set, use the refresh-token flow (with in-memory caching).
      2. Else fall back to the static DROPBOX_ACCESS_TOKEN env var.
      3. Else return an empty string.

    Raises on refresh failure.
    """
    refresh_token = os.environ.get("DROPBOX_REFRESH_TOKEN", "").strip()
    app_key = os.environ.get("DROPBOX_APP_KEY", "").strip()
    app_secret = os.environ.get("DROPBOX_APP_SECRET", "").strip()

    if refresh_token and app_key and app_secret:
        with _token_lock:
            now = time.time()
            cached = _token_cache.get("access_token")
            expires_at = _token_cache.get("expires_at", 0.0)
            # Refresh if missing or expiring within 5 minutes.
            if not cached or expires_at < now + 300:
                payload = _exchange_refresh_token(refresh_token, app_key, app_secret)
                _token_cache["access_token"] = payload["access_token"]
                _token_cache["expires_at"] = now + int(payload.get("expires_in", 14400))
            return _token_cache["access_token"]

    # Legacy static-token mode.
    return os.environ.get("DROPBOX_ACCESS_TOKEN", "").strip()


class DropboxUploader:
    """Dropbox API helper.

    Construction modes:
      - DropboxUploader()                    -- read auth from env (preferred)
      - DropboxUploader(access_token=token)  -- legacy static-token mode
    """

    def __init__(self, access_token=None):
        self._static_access_token = (access_token or "").strip() or None
        self.base_url = "https://api.dropboxapi.com/2"
        self.content_url = "https://content.dropboxapi.com/2"

    @property
    def access_token(self):
        """Currently-valid Dropbox access token (refreshed on demand)."""
        if self._static_access_token:
            return self._static_access_token
        return get_access_token()

    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
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

    def list_folder_recursive(self, dropbox_path):
        """List every file (recursively) under a Dropbox folder.

        Returns a list of {path, name, size} dicts. Folders are filtered out.
        Handles Dropbox's pagination via /files/list_folder/continue.

        Args:
            dropbox_path: Dropbox folder (e.g. /TRUBILT/JOBS/.../1835 ONSLOW DR)

        Raises:
            Exception on a non-200 response from Dropbox.
        """
        if not dropbox_path.startswith('/'):
            dropbox_path = '/' + dropbox_path

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        files = []
        cursor = None
        while True:
            if cursor is None:
                resp = requests.post(
                    f"{self.base_url}/files/list_folder",
                    headers=headers,
                    json={"path": dropbox_path, "recursive": True},
                    timeout=20,
                )
            else:
                resp = requests.post(
                    f"{self.base_url}/files/list_folder/continue",
                    headers=headers,
                    json={"cursor": cursor},
                    timeout=20,
                )
            if resp.status_code != 200:
                raise Exception(
                    f"Dropbox list_folder failed: {resp.status_code} - {resp.text}"
                )
            data = resp.json()
            for entry in data.get('entries', []):
                if entry.get('.tag') == 'file':
                    files.append({
                        'path': entry.get('path_display'),
                        'name': entry.get('name'),
                        'size': entry.get('size'),
                    })
            if not data.get('has_more'):
                break
            cursor = data.get('cursor')
        return files

    def download_file(self, dropbox_path):
        """Download a file's bytes from Dropbox.

        Args:
            dropbox_path: Full path in Dropbox (e.g. /TRUBILT/JOBS/.../file.pdf)

        Returns:
            (content_bytes, content_type_str)

        Raises:
            Exception on non-200 response.
        """
        if not dropbox_path.startswith('/'):
            dropbox_path = '/' + dropbox_path

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Dropbox-API-Arg": json.dumps({"path": dropbox_path}),
        }

        response = requests.post(
            f"{self.content_url}/files/download",
            headers=headers,
            stream=False,
        )

        if response.status_code != 200:
            raise Exception(
                f"Dropbox download failed: {response.status_code} - {response.text}"
            )

        ext = os.path.splitext(dropbox_path)[1].lower()
        content_type = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.pdf': 'application/pdf',
            '.mp4': 'video/mp4',
            '.mov': 'video/quicktime',
            '.heic': 'image/heic',
            '.txt': 'text/plain',
            '.dxf': 'application/dxf',
            '.svg': 'image/svg+xml',
            '.xml': 'application/xml',
            '.json': 'application/json',
        }.get(ext, 'application/octet-stream')

        return response.content, content_type


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
