# magicplan-webhook

Webhook receiver for MagicPlan exports that downloads exported files and uploads them into Dropbox.

## Purpose

MagicPlan can send a webhook when an export is generated. This service accepts that webhook, validates the request, downloads the exported files from the URLs in the payload, and uploads them to Dropbox.

There are two related implementations on this machine:

- This repo: a simpler Railway-deployable webhook receiver.
- `/Users/chadbaker/OpenWork/Welcome/magicplan_webhook_server.py`: a newer working copy that attempts to match MagicPlan project titles to Trubilt job folders and route files into the expected `PICTURES/` and `PLANS/` locations.

If you are handing this off to another agent, start with this repo for deployment details and inspect the newer working copy for the latest Trubilt-specific folder-routing logic.

## Repo Location

- Local path: `/Users/chadbaker/git/magicplan-webhook`
- Deployed endpoint on file: `https://magicplan-webhook-production.up.railway.app/webhook`
- GitHub repo: `https://github.com/trubilt-construction/magicplan-webhook.git`

## Files

- `magicplan_webhook_server.py`: Flask webhook server (also hosts the `POST /pull/<project_id>` endpoint that runs the export server-side)
- `magicplan_export_mapped.py`: standalone MagicPlan-to-Dropbox export — paginated `/projects/<id>/files`, fuzzy folder match, idempotent upload (Reports → SCOPE OF WORK/, sketches → PLANS/, photos/videos → PICTURES/EXISTING CONDITIONS/). Imported by the webhook server's `/pull` endpoint.
- `magicplan_rename_photos.py`: local Playwright tool that scrapes the room labels from the MagicPlan cloud UI (which the API doesn't expose) and renames Dropbox photo/video files from UUIDs to `<Room> - NN.<ext>`. Run after `/pull` lands the files. See `README-room-label-photo-names.md`.
- `magicplan_room_map.py`: lower-level inspector that dumps photo/video attachment metadata to JSON and validates a manual room-map file. Useful for debugging or for a different rename strategy; `magicplan_rename_photos.py` is the end-to-end tool.
- `dropbox_upload.py`: Dropbox upload helper (refresh-token aware)
- `magicplan_client.py`: standalone MagicPlan API exploration client
- `register_webhook.py`: helper to get/set the workspace webhook URL
- `requirements.txt`: Python dependencies
- `Procfile`: gunicorn process command for Railway (with `--timeout 300 --workers 2` so `/pull` doesn't get killed mid-run)
- `railway.json`: Railway build/start config
- `Dockerfile`: containerized deployment

## How It Works

MagicPlan sends a `POST` to `/webhook` with form-encoded fields such as:

- `key`: MagicPlan API key
- `email`: user email
- `title`: project title
- `planid`: plan ID
- `project_id`: project ID
- `pdf`, `jpg0`, `jpg1`, `dxf0`, `png0`, `svg0`, etc.: downloadable file URLs

The server:

1. Validates the incoming `key`
2. Collects supported file URLs from the form payload
3. Downloads each file
4. Uploads each file to Dropbox
5. Returns an XML response back to MagicPlan

## How The Webhook Gets Registered

This repo does not have a `register-webhook` command, but there is existing local code that updates the MagicPlan workspace webhook URL through the MagicPlan API.

Source:

- `/Users/chadbaker/OpenWork/Welcome/run_integration.py:199`

That script sends a `PUT` to:

```text
https://cloud.magicplan.app/api/v2/workspace
```

with headers:

- `customer: <customer_id>`
- `key: <api_key>`
- `Content-Type: application/json`

and body:

```json
{
  "webhook_url": "https://your-public-host/webhook"
}
```

So the registration mechanism is:

1. Bring up a public HTTPS URL for this webhook service
2. Update the MagicPlan workspace via `PUT /api/v2/workspace`
3. MagicPlan then sends export notifications to that `webhook_url`

The current workspace note on disk says the webhook already on file was:

```text
https://magicplan-webhook-production.up.railway.app/webhook
```

See:

- `/Users/chadbaker/Library/Application Support/Claude/local-agent-mode-sessions/252c9365-73d5-4bd1-b1b5-c40d854e681b/481db4b8-1dee-47df-9815-d980077d0a31/local_16f72035-d5e6-4a9d-89f3-b69089557a6b/outputs/RESUME-1835-onslow.md:30`

### Example registration curl

```bash
curl -X PUT https://cloud.magicplan.app/api/v2/workspace \
  -H "customer: $MAGICPLAN_CUSTOMER" \
  -H "key: $MAGICPLAN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"webhook_url":"https://magicplan-webhook-production.up.railway.app/webhook"}'
```

### Registration helper script

Get current workspace config:

```bash
export MAGICPLAN_CUSTOMER="..."
export MAGICPLAN_API_KEY="..."
python3 register_webhook.py --get
```

Set the webhook URL:

```bash
export MAGICPLAN_CUSTOMER="..."
export MAGICPLAN_API_KEY="..."
python3 register_webhook.py --set https://magicplan-webhook-production.up.railway.app/webhook
```

### Verify current workspace config

```bash
curl https://cloud.magicplan.app/api/v2/workspace \
  -H "customer: $MAGICPLAN_CUSTOMER" \
  -H "key: $MAGICPLAN_API_KEY"
```

If `PUT /workspace` fails or the caller does not want to automate it, the fallback is to set the workspace webhook manually in the MagicPlan integrations UI.

## Current Behavior

### This repo

The version in this repo uploads into a generic Dropbox folder:

- `/magicplan_exports/<project_title>_<project_id_prefix>`

### Newer Trubilt-specific working copy

The newer copy at `/Users/chadbaker/OpenWork/Welcome/magicplan_webhook_server.py` adds Dropbox folder matching for Trubilt jobs:

- Base Dropbox job root: `/Trubilt/JOBS`
- Photos/videos: `PICTURES/EXISTING CONDITIONS/` if present, otherwise `PICTURES/`
- Plans/reports: `PLANS/`

It uses fuzzy matching between the MagicPlan project title and existing Dropbox job folders.

## Environment Variables

Required:

- `MAGICPLAN_API_KEY`: expected webhook key from MagicPlan
- `DROPBOX_ACCESS_TOKEN`: Dropbox API token used for uploads

Optional:

- `PORT`: web server port for deployed/container environments

## Important Security Note

Some local source files currently contain hardcoded credentials or fallback secrets. Treat those as compromised development artifacts, do not reuse them in new automation, and rotate them if they are still active.

Do not share:

- embedded Git remotes with tokens
- hardcoded API keys
- Dropbox access tokens

Use environment variables instead.

## Local Run

Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run locally:

```bash
export MAGICPLAN_API_KEY="..."
export DROPBOX_ACCESS_TOKEN="..."
python3 magicplan_webhook_server.py --port 5000
```

Server endpoints:

- `GET /`: basic status page
- `GET /health`: JSON health response
- `GET /test`: test/status page
- `POST /webhook`: MagicPlan webhook endpoint

Expected local webhook URL:

```text
http://localhost:5000/webhook
```

If you need MagicPlan to reach a local process, expose it with a tunnel such as:

```bash
ngrok http 5000
```

## Deploy

### Railway

This repo is already set up for Railway:

- `Procfile`: `web: gunicorn magicplan_webhook_server:app`
- `railway.json`: starts `gunicorn magicplan_webhook_server:app`

Set these environment variables in Railway:

- `MAGICPLAN_API_KEY`
- `DROPBOX_ACCESS_TOKEN`

### Docker

Build and run:

```bash
docker build -t magicplan-webhook .
docker run -p 8080:8080 \
  -e MAGICPLAN_API_KEY="..." \
  -e DROPBOX_ACCESS_TOKEN="..." \
  magicplan-webhook
```

Container entrypoint binds to port `8080`.

## Example curl

Health check:

```bash
curl https://magicplan-webhook-production.up.railway.app/health
```

Example webhook request:

```bash
curl -X POST https://magicplan-webhook-production.up.railway.app/webhook \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "key=$MAGICPLAN_API_KEY" \
  --data-urlencode "email=user@example.com" \
  --data-urlencode "title=1835 ONSLOW DR" \
  --data-urlencode "project_id=d506bcc1-63eb-4b14-b997-37c6989aef48" \
  --data-urlencode "pdf=https://example.com/export.pdf" \
  --data-urlencode "jpg0=https://example.com/photo0.jpg" \
  --data-urlencode "jpg1=https://example.com/photo1.jpg"
```

Expected success response:

```xml
<MagicPlanService><status>0</status><message>Files received and uploaded to Dropbox</message></MagicPlanService>
```

Some local variants return the shorter success message:

```xml
<MagicPlanService><status>0</status><message>Files received</message></MagicPlanService>
```

## Payload Shape

The webhook expects `application/x-www-form-urlencoded` input. Common fields:

- `key`
- `email`
- `title`
- `planid`
- `project_id`
- `pdf` or `pdf0`, `pdf1`
- `jpg0`, `jpg1`, ...
- `png0`, `png1`, ...
- `dxf0`, `dxf1`, ...
- `svg0`, `svg1`, ...

Only fields with HTTP URLs are downloaded.

## Dropbox Notes

The Dropbox helper uploads with:

- `mode=add`
- `autorename=true`

That means existing filenames are not overwritten. Duplicates will be auto-renamed by Dropbox.

## Trubilt Notes

For Trubilt's real workflow, the generic repo implementation is not the full story. The useful operational context also lives here:

- `/Users/chadbaker/OpenWork/Welcome/magicplan_webhook_server.py`
- `/Users/chadbaker/Dropbox/trubilt-magicplan-export.skill`
- `/Users/chadbaker/Library/Application Support/Claude/local-agent-mode-sessions/252c9365-73d5-4bd1-b1b5-c40d854e681b/481db4b8-1dee-47df-9815-d980077d0a31/local_16f72035-d5e6-4a9d-89f3-b69089557a6b/outputs/RESUME-1835-onslow.md`

That resume note also records:

- MagicPlan API base: `https://cloud.magicplan.app/api/v2`
- Workspace webhook on file: `https://magicplan-webhook-production.up.railway.app/webhook`
- Trubilt customer header value and workspace context used in earlier testing

Additional note:

- `README-room-label-photo-names.md` documents the current room-label situation for photo exports and the recommended next implementation step.

## Handoff For Another Agent

If another agent needs to continue work quickly:

1. Read this `README.md`
2. Read `magicplan_webhook_server.py` in this repo
3. Read `/Users/chadbaker/OpenWork/Welcome/magicplan_webhook_server.py`
4. Verify deploy health with `curl <deploy-url>/health`
5. Confirm `MAGICPLAN_API_KEY` and `DROPBOX_ACCESS_TOKEN` are set in the target environment
6. If the task is Trubilt-specific routing, prefer the newer working copy logic over the generic repo implementation

## Dependencies

From `requirements.txt`:

- `flask==3.0.0`
- `requests==2.31.0`
- `gunicorn==21.2.0`

## Known issues

### Fuzzy folder matcher can pick the wrong job folder

`find_matching_folder(address, folders, project_name)` in `magicplan_export_mapped.py` (and the same logic exposed via the server's `/test-match` endpoint) builds its search string as `"{address} {project_name}"` when address is set. That works fine when the address has a unique street name, but it falls down when the project name and address share *only* generic city/zip tokens with another folder name.

**Concrete failure that hit production on 2026-04-28:**

Project metadata:

- Name: `Gucciardini Meeting`
- Address: `307 Timothy Road, Jacksonville 28546`

Search string passed to the matcher: `"307 Timothy Road, Jacksonville 28546 Gucciardini Meeting"`.

For Dropbox folder `2119 NORTH DR, JACKSONVILLE 28540`, the matcher scored:

- Token presence: `jacksonville` (12 chars) → score = 12
- Sequence similarity: ~0.45 (long search string, both contain "jacksonville")
- Combined: `12 * 0.7 + 45 * 0.3 = 21.9`

For the correct folder `307 TIMOTHY RD`:

- Token presence: `307` (3) + `timothy` (7) = 10
- Sequence similarity: ~0.30 (long search string vs short folder name → similarity drops)
- Combined: `10 * 0.7 + 30 * 0.3 = 16`

`2119 NORTH DR, JACKSONVILLE 28540` won by ~6 points. `/pull` cheerfully uploaded all 90 files to the wrong folder.

**Mitigations in this repo:**

- **`magicplan_export_mapped.py` `find_matching_folder` was hardened** (commit following the 2026-04-28 incident): now uses the **street address only** (the part before the first comma — e.g. `"307 Timothy Road"` extracted from `"307 Timothy Road, Jacksonville 28546"`) as the matcher input. The project_name is ignored when an address is present, since project names contain noisy tokens (`Meeting`, `Apartments`) that don't appear in Dropbox folder names. Falls back to `project_name` only when address is missing or `"none"`. Threshold raised from 5 to 10, plus a new requirement that the winning folder beat the second-best by at least 3 points — this prevents a single shared city/zip token from deciding a close call. The change makes `/pull` safe to call without pre-flight.
- **`magicplan_rename_photos.py` was hardened** in parallel: (a) accepts a `--matched-folder` override flag that bypasses `/test-match` entirely, and (b) when no override is given, calls `/test-match` with `addr["street"]` instead of the project name. Same goal — street-only input bypasses city/zip noise.

The `/test-match` endpoint itself still uses the same hardened `find_matching_folder` under the hood (the server imports it from `magicplan_export_mapped`), so callers passing the street address get correct results from `/test-match` too. As a defence-in-depth habit, the trubilt-magicplan-export skill still pre-flights `/test-match` with the street-only address before firing `/pull`.
