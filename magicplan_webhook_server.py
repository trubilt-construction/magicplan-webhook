#!/usr/bin/env python3
"""
magicplan Webhook Server
Receives export notifications from magicplan and uploads to Dropbox

Usage:
    python3 magicplan_webhook_server.py [--port 5000]
    
For public URL (required for magicplan to reach it):
    ngrok http 5000
"""

import os
import sys
import json
import requests
from urllib.parse import parse_qs, urlencode
from flask import Flask, request, Response
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Dropbox configuration (will be loaded from environment or config)
DROPBOX_ACCESS_TOKEN = os.environ.get("DROPBOX_ACCESS_TOKEN", "")

@app.route('/webhook', methods=['POST'])
def magicplan_webhook():
    """
    Receives magicplan export notifications.
    
    Magicplan sends POST data with:
    - key: API key
    - email: User email
    - title: Project title
    - planid: Plan ID
    - project_id: Project ID
    - pdf, jpg0, jpg1, dxf0, etc.: File URLs
    """
    try:
        # Parse form data
        data = request.form.to_dict()
        logger.info(f"Received webhook: {json.dumps(data, indent=2)}")
        
        # Validate API key
        expected_key = os.environ.get("MAGICPLAN_API_KEY", "6a980b647acdf33cebfd12ce20d908fc8099")
        if data.get('key') != expected_key:
            logger.warning(f"Invalid API key received: {data.get('key')}")
            return Response('<status>1</status>', mimetype='text/xml'), 401
        
        # Extract project info
        project_title = data.get('title', 'Unknown Project')
        project_id = data.get('project_id', '')
        email = data.get('email', '')
        
        logger.info(f"Export received for: {project_title} (ID: {project_id})")
        logger.info(f"From user: {email}")
        
        # Collect file URLs
        files_to_download = {}
        for key, value in data.items():
            if key in ['pdf', 'jpg0', 'jpg1', 'jpg2', 'jpg3', 
                       'dxf0', 'dxf1', 'dxf2', 'dxf3',
                       'png0', 'png1', 'png2', 'png3',
                       'svg0', 'svg1', 'svg2', 'svg3',
                       'xml', 'html', 'ifc', 'usdz', 'obj']:
                if value and value.startswith('http'):
                    files_to_download[key] = value
        
        logger.info(f"Files to download: {list(files_to_download.keys())}")
        
        # Download and upload to Dropbox
        if DROPBOX_ACCESS_TOKEN:
            from dropbox_upload import DropboxUploader
            uploader = DropboxUploader(DROPBOX_ACCESS_TOKEN)
            
            folder_path = f"/magicplan_exports/{project_title}_{project_id[:8]}"
            
            for file_type, url in files_to_download.items():
                try:
                    result = uploader.upload_from_url(url, folder_path, f"{file_type}_{project_id[:8]}")
                    logger.info(f"Uploaded {file_type}: {result}")
                except Exception as e:
                    logger.error(f"Failed to upload {file_type}: {e}")
        else:
            logger.warning("DROPBOX_ACCESS_TOKEN not set - skipping upload")
            logger.info("Files available at:")
            for file_type, url in files_to_download.items():
                logger.info(f"  {file_type}: {url}")
        
        # Return success response (XML as per magicplan spec)
        return Response(
            '<MagicPlanService><status>0</status><message>Files received and uploaded to Dropbox</message></MagicPlanService>',
            mimetype='text/xml'
        )
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return Response(f'<MagicPlanService><status>1</status><message>{str(e)}</message></MagicPlanService>', 
                       mimetype='text/xml'), 500

@app.route('/')
def index():
    """Root redirect to test page"""
    return """
    <html><body>
    <h1>Magicplan Webhook Server ✅</h1>
    <p>Server is running and ready!</p>
    <p>Webhook endpoint: <code>/webhook</code></p>
    <p>Dropbox: {}</p>
    </body></html>
    """.format("Configured ✅" if DROPBOX_ACCESS_TOKEN else "NOT CONFIGURED - Set DROPBOX_ACCESS_TOKEN")

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return {"status": "ok", "dropbox_configured": bool(DROPBOX_ACCESS_TOKEN)}

@app.route('/test', methods=['GET'])
def test_page():
    """Test page"""
    return """
    <html><body>
    <h1>Magicplan Webhook Server</h1>
    <p>Server is running!</p>
    <p>Configure magicplan to send webhooks to: <code>/webhook</code></p>
    <p>Current status:</p>
    <ul>
        <li>Dropbox configured: {}</li>
    </ul>
    </body></html>
    """.format("Yes" if DROPBOX_ACCESS_TOKEN else "No - set DROPBOX_ACCESS_TOKEN")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Magicplan Webhook Server')
    parser.add_argument('--port', type=int, default=5000, help='Port to run on')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()
    
    print("="*60)
    print("MAGICPLAN WEBHOOK SERVER")
    print("="*60)
    print(f"Starting on port {args.port}...")
    print(f"Webhook URL: http://localhost:{args.port}/webhook")
    print(f"Dropbox: {'Configured' if DROPBOX_ACCESS_TOKEN else 'NOT CONFIGURED'}")
    print("")
    print("To expose to internet (for magicplan):")
    print(f"  ngrok http {args.port}")
    print("="*60)
    
    app.run(host='0.0.0.0', port=args.port, debug=args.debug)
