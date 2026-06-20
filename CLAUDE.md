# CLAUDE.md — SYMBIO-FRAME Mycelium Health Monitor

Project guidance for Claude Code. Read this before making changes.

## What this project is

A web-based mycelium health monitoring system for an MArch thesis (RC7, Bartlett / UCL). Users upload photos of wood–mycelium composite specimens; a custom YOLO model detects surface health states and the backend combines this with humidity data to produce a 0–100 health score and a short-term decay forecast. Visitors can also contribute labelled images that feed a shared training dataset.

- **Live site:** https://web-production-77f82.up.railway.app
- **Admin panel:** https://web-production-77f82.up.railway.app/admin
- **Local project folder:** `C:\Users\16691\Desktop\Mycelium`

## Tech stack

- **Backend:** Flask (single file, `app.py`), SQLite, JWT auth (PyJWT), bcrypt
- **Frontend:** single-page `dashboard_v3.html` (vanilla JS, Chart.js, Leaflet) + `admin.html`
- **ML:** Ultralytics YOLO, model file `best.pt` (segment model, detect-mode trained)
- **Sensors:** `sensor_surface.py` (ESP32 COM7, surface humidity), `sensor_env.py` (ESP32 COM4, environment humidity)
- **Deploy:** Railway, auto-deploys from GitHub `master` branch on push. Built via `Dockerfile` (python:3.11-slim).

## File map

| File | Role |
|------|------|
| `app.py` | Flask backend — all routes, auth, scoring, Roboflow upload |
| `dashboard_v3.html` | Main user-facing single-page app (served at `/`) |
| `admin.html` | Password-protected admin panel (served at `/admin`) |
| `best.pt` | Trained YOLO weights (~5 MB, committed to git) |
| `sensor_surface.py` / `sensor_env.py` | Local sensor capture scripts (not run on server) |
| `Dockerfile` | Railway build definition |
| `requirements.txt` | flask, flask-cors, ultralytics, bcrypt, PyJWT, requests |
| `Procfile` | `web: python app.py` |

## Critical conventions — do not break these

### YOLO classes (must stay exactly these four, matching Roboflow)
```
healthy_mycelium, dry_aged_mycelium, contamination_risk, exposed_substrate
```
There is **no** `over_wet_risk` class — it was removed. Any code referencing it is stale.

### Health score (0–100)
- Image component (0–60): subtract per detection — contamination_risk −20×conf, dry_aged −12×conf, exposed_substrate −8×conf
- Delta humidity component (0–30): based on surface−environment humidity difference
- Trend component (0–10): based on recent score direction

### Persistence (IMPORTANT)
Database and uploads live on a Railway **volume** mounted at `/app/data`:
```python
DATA_DIR = "/app/data" if os.path.isdir("/app/data") else "."
UPLOAD_FOLDER = os.path.join(DATA_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "mycelium.db")
```
Never hardcode `mycelium.db` or `uploads/` back to the project root — that would make data reset on every deploy.

### Deployment essentials (these were hard-won — keep them)
- `app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))` — Railway injects `PORT`; `debug=True` causes 502s.
- `/` serves `dashboard_v3.html` via `send_from_directory`, not JSON.
- Frontend `const API` must point to the Railway domain, not `127.0.0.1`.
- `print(..., flush=True)` for anything you need to see in Railway logs (output is otherwise buffered).

### Frontend auth + uploads
- `authFetch()` must NOT set `Content-Type` when the body is `FormData` — the browser sets the multipart boundary itself. Setting it manually breaks `/detect`, `/contribute`, `/upload-csv`.
- Token stored in `localStorage`; guests can browse and contribute anonymously; upload/analyse and private timeline require login.

### Roboflow upload (Contribute feature)
Images are POSTed to Roboflow as **base64 in the raw request body** with `Content-Type: application/x-www-form-urlencoded`. Sending base64 inside a JSON field returns 500. Workspace `myceliummonitor`, project `mycelium-detection`. API key is in `app.py` (do not print it in responses).

### Admin
- Admin account: username `Kecen Yi` (created/refreshed on startup, `is_admin=1`).
- `/admin/images`, `/admin/users`, `/admin/detections`, `/admin/download-all` (ZIP) require an admin JWT.
- `/reset-admin` (POST) is an emergency password-reset endpoint.

## Common tasks

### Deploy a change
```bash
git add <files>
git commit -m "message"
git push        # Railway auto-deploys from master
```

### Update the model
Replace `best.pt`, then commit and push. Retraining is done in Google Colab (T4 GPU) from a Roboflow YOLOv8-format export — train detect mode (`yolo11n.pt`), not seg, because the dataset mixes bbox and polygon annotations.

### Run sensors locally (optional)
Set `SEND_TO_DB = True` and paste the auth token into `AUTH_TOKEN` in the sensor script; otherwise it logs to CSV only.

## Working style (author preference)
- The author wants Claude to triple-check and self-verify code (syntax + logic) **before** outputting, not after.
- Validate JS with `node --check` and Python with `py_compile` before presenting any change.
- One change set at a time; confirm it works before moving on.
- Respond in Chinese.
