import os
import sys
import uuid
import sqlite3
import base64
import bcrypt
import jwt
import json
import csv
import io
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS
from ultralytics import YOLO
from PIL import Image, ImageOps, ImageDraw, ImageFont

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()   # let PIL.Image.open() decode HEIC/HEIF uploads
except ImportError:
    pass

# Force unbuffered output so Railway logs show print() immediately
sys.stdout.reconfigure(line_buffering=True)

app = Flask(__name__)
CORS(app)

# Use Railway persistent volume if available, else local (for dev)
DATA_DIR      = "/app/data" if os.path.isdir("/app/data") else "."
UPLOAD_FOLDER = os.path.join(DATA_DIR, "uploads")
DB_PATH       = os.path.join(DATA_DIR, "mycelium.db")
SECRET_KEY    = os.environ.get("JWT_SECRET", "symbioframe_secret_key_2026_secure")   # JWT signing key
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
print(f"📁 Data directory: {DATA_DIR}", flush=True)

model = YOLO("best.pt")
print("✅ Model loaded")


# ══════════════════════════════════════════════════════════════════════════════
# Database
# ══════════════════════════════════════════════════════════════════════════════

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    # ── Migrate existing DB: add user_id columns if missing ───────────────
    for tbl, col in [
        ("detections",       "user_id INTEGER"),
        ("surface_readings", "user_id INTEGER"),
        ("env_readings",     "user_id INTEGER"),
        ("contributions",    "user_id INTEGER"),
        ("contributions",    "lat REAL"),
        ("contributions",    "lng REAL"),
    ]:
        try:
            conn.execute(f"ALTER TABLE {tbl} ADD COLUMN {col}")
            conn.commit()
            print(f"  ↳ Migrated: {tbl}.{col.split()[0]}")
        except Exception:
            pass  # Column already exists

    # ── Users ──────────────────────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    NOT NULL UNIQUE,
            password_hash TEXT    NOT NULL,
            created_at    TEXT    NOT NULL,
            is_admin      INTEGER DEFAULT 0
        )
    """)

    # ── Detections ─────────────────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS detections (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER REFERENCES users(id),
            sample_id        TEXT    NOT NULL,
            model_type       TEXT    DEFAULT 'pilot',
            timestamp        TEXT    NOT NULL,
            image_path       TEXT,
            yolo_state       TEXT,
            health_score     INTEGER,
            temp_c           REAL,
            env_humidity     REAL,
            surface_humidity REAL,
            delta_humidity   REAL,
            notes            TEXT
        )
    """)

    # ── Surface readings ───────────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS surface_readings (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER REFERENCES users(id),
            sample_id        TEXT NOT NULL,
            timestamp        TEXT NOT NULL,
            temp_c           REAL,
            surface_humidity REAL,
            pressure_hpa     REAL
        )
    """)

    # ── Env readings ───────────────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS env_readings (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER REFERENCES users(id),
            sample_id     TEXT NOT NULL,
            timestamp     TEXT NOT NULL,
            temp_c        REAL,
            env_humidity  REAL,
            pressure_hpa  REAL
        )
    """)

    # ── Contributions ──────────────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contributions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER REFERENCES users(id),
            timestamp     TEXT NOT NULL,
            contributor   TEXT DEFAULT 'anonymous',
            location      TEXT,
            lat           REAL,
            lng           REAL,
            image_path    TEXT NOT NULL,
            annotations   TEXT,
            mycelium_type TEXT,
            notes         TEXT,
            status        TEXT DEFAULT 'pending',
            roboflow_id   TEXT
        )
    """)

    # ── Samples (identity cards) ────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS samples (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL REFERENCES users(id),
            sample_id    TEXT    NOT NULL,
            name         TEXT,
            description  TEXT,
            cover_image  TEXT,
            created_at   TEXT    NOT NULL,
            UNIQUE(user_id, sample_id)
        )
    """)

    # ── Sample files (humidity maps, CloudCompare results, 3D scan models) ─
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sample_files (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            sample_id   TEXT    NOT NULL,
            file_type   TEXT    NOT NULL,
            timestamp   TEXT    NOT NULL,
            file_path   TEXT    NOT NULL,
            notes       TEXT,
            metadata    TEXT    DEFAULT '{}'
        )
    """)

    conn.commit()

    # ── Auto-migrate: back-fill samples from existing detections ───────────
    conn.execute("""
        INSERT OR IGNORE INTO samples (user_id, sample_id, created_at)
        SELECT user_id, sample_id, MIN(timestamp)
        FROM detections
        WHERE user_id IS NOT NULL AND sample_id IS NOT NULL AND sample_id != ''
          AND UPPER(sample_id) != 'QUICK-CHECK'
        GROUP BY user_id, sample_id
    """)
    conn.commit()
    print("✅ Samples + sample_files tables ready")

    # ── Migrations: add missing columns to existing tables ─────────────────
    # Safe: ALTER TABLE ADD COLUMN is ignored if column already exists via try/except
    migrations = [
        ("detections",       "user_id          INTEGER"),
        ("detections",       "state_areas      TEXT"),
        ("detections",       "score_breakdown  TEXT"),
        ("surface_readings", "user_id          INTEGER"),
        ("env_readings",     "user_id          INTEGER"),
        ("contributions",    "user_id          INTEGER"),
        ("contributions",    "lat              REAL"),
        ("contributions",    "lng              REAL"),
    ]
    for table, col_def in migrations:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
            conn.commit()
            print(f"  ↳ Migrated {table}: added {col_def.split()[0]}")
        except Exception:
            pass  # Column already exists — fine

    # ── Create / reset admin account (Kecen Yi) ────────────────────────────
    try:
        pw_hash = bcrypt.hashpw("yikecen".encode(), bcrypt.gensalt()).decode()
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", ("Kecen Yi",)
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO users (username, password_hash, created_at, is_admin) "
                "VALUES (?,?,?,1)",
                ("Kecen Yi", pw_hash, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            print("✅ Admin account created: Kecen Yi / symbioframe2026")
        else:
            # Always reset password hash on startup so it's always correct
            conn.execute(
                "UPDATE users SET password_hash=?, is_admin=1 WHERE username=?",
                (pw_hash, "Kecen Yi")
            )
            print("✅ Admin account refreshed: Kecen Yi")
        conn.commit()
    except Exception as e:
        print(f"⚠️  Admin account error: {e}")

    conn.close()
    print("✅ Database ready:", DB_PATH)


init_db()


# ══════════════════════════════════════════════════════════════════════════════
# Auth helpers
# ══════════════════════════════════════════════════════════════════════════════

def make_token(user_id, username, is_admin):
    payload = {
        "user_id":  user_id,
        "username": username,
        "is_admin": is_admin,
        "exp":      datetime.utcnow() + timedelta(days=30)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def decode_token(token):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except Exception:
        return None


def get_current_user():
    """Extract user from Authorization header. Returns dict or None."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return decode_token(auth[7:])
    return None


def require_auth(f):
    """Decorator: endpoint requires valid token."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"error": "Login required"}), 401
        return f(*args, **kwargs)
    return wrapper


def require_admin(f):
    """Decorator: endpoint requires admin token."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user or not user.get("is_admin"):
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return wrapper


# ══════════════════════════════════════════════════════════════════════════════
# Auth endpoints
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/auth/register", methods=["POST"])
def register():
    data     = request.get_json()
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?,?,?)",
            (username, pw_hash, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        row = conn.execute("SELECT id, is_admin FROM users WHERE username=?", (username,)).fetchone()
        conn.close()
        token = make_token(row["id"], username, bool(row["is_admin"]))
        return jsonify({"success": True, "token": token, "username": username, "is_admin": bool(row["is_admin"])})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Username already taken"}), 409


@app.route("/auth/login", methods=["POST"])
def login():
    data     = request.get_json()
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    conn = get_db()
    row  = conn.execute(
        "SELECT id, password_hash, is_admin FROM users WHERE username=?", (username,)
    ).fetchone()
    conn.close()

    if not row or not bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
        return jsonify({"error": "Invalid username or password"}), 401

    token = make_token(row["id"], username, bool(row["is_admin"]))
    return jsonify({
        "success":  True,
        "token":    token,
        "username": username,
        "is_admin": bool(row["is_admin"])
    })


@app.route("/auth/me", methods=["GET"])
@require_auth
def me():
    user = get_current_user()
    return jsonify({"username": user["username"], "is_admin": user["is_admin"]})


# ══════════════════════════════════════════════════════════════════════════════
# Scoring logic
# ══════════════════════════════════════════════════════════════════════════════

def calc_health_score(detections, delta_humidity=None, sample_id=None, user_id=None,
                      img_total_pixels=None, state_areas=None):
    # Dimension 1: image (0-60)
    # Primary path: use class area percentages from state_areas
    if state_areas:
        contamination_pct = state_areas.get("contamination_risk", 0) / 100
        dry_aged_pct      = state_areas.get("dry_aged_mycelium",  0) / 100
        exposed_pct       = state_areas.get("exposed_substrate",  0) / 100
        penalty_pts = contamination_pct * 80 + exposed_pct * 60 + dry_aged_pct * 40
        img_score = round(max(10.0, 60 - penalty_pts))
    else:
        # Fallback: per-detection conf × area_ratio (old records / no state_areas)
        img_score = 60.0
        for d in detections:
            conf = d["confidence"] / 100
            name = d["class_name"]
            area_ratio = min(1.0, d.get("area_pixels", 0) / img_total_pixels) if img_total_pixels else 1.0
            if name in ("contaminated", "contamination_risk"):
                img_score -= 30 * conf * area_ratio
            elif name in ("dry_aging", "dry_aged_mycelium", "aging"):
                img_score -= 15 * conf * area_ratio
            elif name == "exposed_substrate":
                img_score -= 25 * conf * area_ratio
        img_score = round(max(0.0, img_score))

    # Dimension 2: delta humidity (0-30); None = no sensor data
    # |ΔRH| < 5 → 30, 5-15 → linear, > 15 → 0
    if delta_humidity is not None:
        abs_dh = abs(delta_humidity)
        if abs_dh < 5:
            hum_score = 30
        elif abs_dh <= 15:
            hum_score = round(30 * (15 - abs_dh) / 10)
        else:
            hum_score = 0
    else:
        hum_score = None

    # Dimension 3: trend (0-10)
    # Compare newest vs oldest among last 3 previous scores:
    # delta >= -3 (stable/rising) → 10, -10 to -3 (slight drop) → 5, < -10 → 0
    trend_score = 10
    if sample_id and user_id:
        try:
            conn = get_db()
            recent = conn.execute(
                "SELECT health_score FROM detections WHERE sample_id=? AND user_id=? "
                "AND health_score IS NOT NULL ORDER BY id DESC LIMIT 3",
                (sample_id, user_id)
            ).fetchall()
            conn.close()
            sc = [r[0] for r in recent]
            if len(sc) >= 2:
                delta_sc = sc[0] - sc[-1]   # newest vs oldest in fetched window
                if delta_sc < -10:
                    trend_score = 0
                elif delta_sc < -3:
                    trend_score = 5
        except Exception:
            pass

    # Compute total
    # Without humidity: scale (img + trend) / 70 → 100
    # With humidity:    img + hum + trend (max 100)
    has_humidity = hum_score is not None
    if has_humidity:
        total = max(0, min(100, img_score + hum_score + trend_score))
    else:
        total = max(0, min(100, round((img_score + trend_score) / 70 * 100)))

    return {
        "total":        total,
        "img":          img_score,
        "hum":          hum_score,   # None if no humidity data
        "trend":        trend_score,
        "has_humidity": has_humidity,
    }


def main_state(detections):
    if not detections:
        return "healthy_mycelium"
    return max(detections, key=lambda d: d["confidence"])["class_name"]


def find_sensing_delta(user_id, sample_id, timestamp_str):
    """
    Find best delta_humidity for a given sample + date.
    Looks in surface_readings and env_readings for the same user+sample+date,
    returns average delta across matched pairs.
    """
    try:
        date_str = timestamp_str[:10]  # "YYYY-MM-DD"
        conn = get_db()

        surf = conn.execute("""
            SELECT AVG(surface_humidity) as avg_s, AVG(temp_c) as avg_t
            FROM surface_readings
            WHERE user_id=? AND sample_id=?
              AND DATE(timestamp)=?
        """, (user_id, sample_id, date_str)).fetchone()

        env = conn.execute("""
            SELECT AVG(env_humidity) as avg_e
            FROM env_readings
            WHERE user_id=? AND sample_id=?
              AND DATE(timestamp)=?
        """, (user_id, sample_id, date_str)).fetchone()

        conn.close()

        if surf["avg_s"] and env["avg_e"]:
            delta = round(surf["avg_s"] - env["avg_e"], 1)
            return delta, round(surf["avg_s"], 1), round(env["avg_e"], 1), round(surf["avg_t"] or 0, 1)
    except Exception:
        pass
    return None, None, None, None


def try_compute_delta_realtime(sample_id, user_id, conn):
    """For 1-min reading: pair readings from last 10 minutes."""
    surface = conn.execute("""
        SELECT AVG(surface_humidity) as avg_s, AVG(temp_c) as avg_t
        FROM surface_readings
        WHERE sample_id=? AND user_id=?
          AND timestamp >= datetime('now', '-10 minutes')
    """, (sample_id, user_id)).fetchone()

    env = conn.execute("""
        SELECT AVG(env_humidity) as avg_e
        FROM env_readings
        WHERE sample_id=? AND user_id=?
          AND timestamp >= datetime('now', '-10 minutes')
    """, (sample_id, user_id)).fetchone()

    if surface["avg_s"] and env["avg_e"]:
        delta = round(surface["avg_s"] - env["avg_e"], 1)
        conn.execute("""
            UPDATE detections
            SET surface_humidity = ?,
                env_humidity     = ?,
                delta_humidity   = ?,
                temp_c           = COALESCE(temp_c, ?)
            WHERE sample_id=? AND user_id=?
              AND id = (SELECT MAX(id) FROM detections WHERE sample_id=? AND user_id=?)
        """, (round(surface["avg_s"], 1), round(env["avg_e"], 1),
              delta, round(surface["avg_t"] or 0, 1),
              sample_id, user_id, sample_id, user_id))
        conn.commit()
        return delta
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Core endpoints
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/", methods=["GET"])
def index():
    from flask import send_from_directory
    return send_from_directory(".", "dashboard_v3.html")

@app.route("/api/status", methods=["GET"])
def status():
    return jsonify({"status": "ok", "message": "SYMBIO-FRAME backend running 🍄"})


# ── Shared image upload preprocessing (used by /detect and /contribute) ───────
MAX_UPLOAD_DIM = 1280   # longest side, px — keeps memory bounded and stays detailed enough for annotation/training

def load_normalized_image(file_storage, max_dim=MAX_UPLOAD_DIM):
    """Decode an uploaded image file (jpg/png/webp/heic/... via PIL+pillow-heif),
    correct EXIF rotation, convert to RGB, and downscale so the longest side
    does not exceed max_dim. Returns a PIL.Image in RGB mode.
    Raises ValueError if the file cannot be decoded as an image."""
    try:
        img = Image.open(file_storage.stream)
        img.load()
    except Exception as e:
        raise ValueError(f"Unsupported or corrupted image file: {e}")

    try:
        img = ImageOps.exif_transpose(img)   # match the orientation browsers display (and annotations are drawn against)
    except Exception:
        pass

    if img.mode != "RGB":
        img = img.convert("RGB")

    w, h = img.size
    longest = max(w, h)
    if longest > max_dim:
        scale = max_dim / longest
        img = img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)

    return img


# ── Detection result rendering (custom overlay, no YOLO default plot) ─────────
DETECTION_COLORS = {
    "healthy_mycelium":   (40, 160, 70),    # green
    "dry_aged_mycelium":  (240, 195, 25),   # yellow
    "contamination_risk": (128, 0, 128),    # purple
    "exposed_substrate":  (220, 50, 50),   # red
}
LEGEND_ORDER = ["healthy_mycelium", "dry_aged_mycelium", "contamination_risk", "exposed_substrate"]
LEGEND_LABELS = {
    "healthy_mycelium":   "Healthy",
    "dry_aged_mycelium":  "Dry / aged",
    "contamination_risk": "Contamination risk",
    "exposed_substrate":  "Exposed substrate",
}

def render_detection_image(base_img, result):
    """Draw translucent class-colored mask overlays (boxes as fallback when a
    detection has no mask) on base_img, then append a legend strip below.
    No text is drawn on the photo itself — only the legend names it."""
    base    = base_img.convert("RGB")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)

    mask_polys = result.masks.xy if result.masks is not None else None
    if result.boxes is not None:
        for i, box in enumerate(result.boxes):
            try:
                class_name = model.names[int(box.cls[0])]
            except Exception:
                continue
            color = DETECTION_COLORS.get(class_name, (150, 150, 150))
            poly  = mask_polys[i] if mask_polys is not None and i < len(mask_polys) else None
            if poly is not None and len(poly) >= 3:
                draw.polygon([tuple(p) for p in poly], fill=color + (90,), outline=color + (255,), width=3)
            else:
                x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]
                draw.rectangle([x1, y1, x2, y2], fill=color + (90,), outline=color + (255,), width=3)

    composited = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
    return _add_legend_strip(composited)


def _add_legend_strip(img):
    legend_h = 54
    w, h     = img.size
    canvas   = Image.new("RGB", (w, h + legend_h), (250, 248, 244))
    canvas.paste(img, (0, 0))
    draw   = ImageDraw.Draw(canvas)
    font   = ImageFont.load_default(size=20)
    swatch = 16
    x = 16
    y = h + legend_h // 2
    for cls in LEGEND_ORDER:
        color = DETECTION_COLORS[cls]
        draw.rectangle([x, y - swatch // 2, x + swatch, y + swatch // 2], fill=color)
        label = LEGEND_LABELS[cls]
        draw.text((x + swatch + 6, y), label, fill=(60, 50, 40), font=font, anchor="lm")
        x += swatch + 6 + draw.textlength(label, font=font) + 26
    return canvas


# ── Detect ────────────────────────────────────────────────────────────────────
@app.route("/detect", methods=["POST"])
@require_auth
def detect():
    user = get_current_user()
    user_id = user["user_id"]

    if "image" not in request.files:
        return jsonify({"error": "No image provided"}), 400

    file       = request.files["image"]
    sample_id  = request.form.get("sample_id", "SAMPLE-1")
    notes      = request.form.get("notes", "")
    timestamp  = request.form.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    model_type = "main" if sample_id.startswith("WOOD") else "pilot"

    try:
        img = load_normalized_image(file)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    filename  = f"{uuid.uuid4().hex}.jpg"
    save_path = os.path.join(UPLOAD_FOLDER, filename)

    try:
        img.save(save_path, "JPEG", quality=90)

        results = model(save_path, conf=0.1)
        result  = results[0]

        result_filename = f"result_{os.path.splitext(filename)[0]}.jpg"
        result_path     = os.path.join(UPLOAD_FOLDER, result_filename)
        render_detection_image(img, result).save(result_path, "JPEG", quality=90)
        img_w, img_h = img.size
        img.close()

        detections = []
        state_pixel_counts = {}

        if result.masks is not None and result.boxes is not None:
            # Segmentation masks available — use real pixel area
            for box, mask in zip(result.boxes, result.masks.data):
                try:
                    class_id   = int(box.cls[0])
                    class_name = model.names[class_id]
                    confidence = round(float(box.conf[0]) * 100, 1)
                    x1, y1, x2, y2 = [round(float(v), 1) for v in box.xyxy[0]]
                    mask_pixels = float(mask.sum())
                    state_pixel_counts[class_name] = state_pixel_counts.get(class_name, 0) + mask_pixels
                    detections.append({
                        "class_id":    class_id,
                        "class_name":  class_name,
                        "confidence":  confidence,
                        "area_pixels": mask_pixels,
                        "bbox": {"x1":x1,"y1":y1,"x2":x2,"y2":y2,
                                 "width":round(x2-x1,1),"height":round(y2-y1,1)}
                    })
                except Exception as box_err:
                    print(f"Box parsing error: {box_err}")
                    continue
        elif result.boxes is not None:
            # Fallback: no masks, use bbox area
            for box in result.boxes:
                try:
                    class_id   = int(box.cls[0])
                    class_name = model.names[class_id]
                    confidence = round(float(box.conf[0]) * 100, 1)
                    x1, y1, x2, y2 = [round(float(v), 1) for v in box.xyxy[0]]
                    bbox_area = (x2 - x1) * (y2 - y1)
                    state_pixel_counts[class_name] = state_pixel_counts.get(class_name, 0) + bbox_area
                    detections.append({
                        "class_id":    class_id,
                        "class_name":  class_name,
                        "confidence":  confidence,
                        "area_pixels": bbox_area,
                        "bbox": {"x1":x1,"y1":y1,"x2":x2,"y2":y2,
                                 "width":round(x2-x1,1),"height":round(y2-y1,1)}
                    })
                except Exception as box_err:
                    print(f"Box parsing error: {box_err}")
                    continue

        total_pixels = sum(state_pixel_counts.values())
        state_areas = {k: round(v / total_pixels * 100, 1) for k, v in state_pixel_counts.items()} if total_pixels > 0 else {}

        # Find sensing delta for this sample+date
        delta, surf_hum, env_hum, temp_c = find_sensing_delta(user_id, sample_id, timestamp)

        score_result = calc_health_score(detections, delta_humidity=delta,
                                        sample_id=sample_id, user_id=user_id,
                                        img_total_pixels=img_w * img_h,
                                        state_areas=state_areas)
        health_score    = score_result["total"]
        score_breakdown = json.dumps(score_result)
        yolo_state      = main_state(detections)

        conn = get_db()
        # Only auto-create a sample record for real sample IDs, not Quick Check
        if sample_id and sample_id.upper() != 'QUICK-CHECK':
            conn.execute("""
                INSERT OR IGNORE INTO samples (user_id, sample_id, created_at)
                VALUES (?, ?, ?)
            """, (user_id, sample_id, timestamp))
        conn.execute("""
            INSERT INTO detections
                (user_id, sample_id, model_type, timestamp, image_path,
                 yolo_state, health_score, temp_c, env_humidity, surface_humidity,
                 delta_humidity, notes, state_areas, score_breakdown)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (user_id, sample_id, model_type, timestamp, filename,
              yolo_state, health_score, temp_c, env_hum, surf_hum, delta, notes,
              json.dumps(state_areas) if state_areas else None, score_breakdown))
        conn.commit()

        realtime_delta = try_compute_delta_realtime(sample_id, user_id, conn)
        if realtime_delta and delta is None:
            delta = realtime_delta
        conn.close()

        with open(result_path, "rb") as f:
            result_b64 = base64.b64encode(f.read()).decode()

        print(f"✅ Detection complete: {len(detections)} objects, score={health_score}, state={yolo_state}")

        return jsonify({
            "success":          True,
            "sample_id":        sample_id,
            "timestamp":        timestamp,
            "yolo_state":       yolo_state,
            "health_score":     health_score,
            "delta_humidity":   delta,
            "total_detections": len(detections),
            "state_areas":      state_areas,
            "detections":       detections,
            "result_image":     result_b64,
        })

    except Exception as e:
        import traceback
        print(f"❌ Detection error: {traceback.format_exc()}")
        # Clean up saved file on error
        if os.path.exists(save_path):
            try: os.remove(save_path)
            except: pass
        return jsonify({"success": False, "error": str(e)}), 500


# ── Surface sensor (1-min reading from ESP32) ─────────────────────────────────
@app.route("/surface", methods=["POST"])
@require_auth
def surface():
    user = get_current_user()
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON required"}), 400

    conn = get_db()
    conn.execute("""
        INSERT INTO surface_readings
            (user_id, sample_id, timestamp, temp_c, surface_humidity, pressure_hpa)
        VALUES (?,?,?,?,?,?)
    """, (user["user_id"], data.get("sample_id",""),
          datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
          data.get("temp_c"), data.get("surface_humidity"), data.get("pressure_hpa")))
    conn.commit()
    delta = try_compute_delta_realtime(data.get("sample_id",""), user["user_id"], conn)
    conn.close()
    return jsonify({"success": True, "delta_humidity": delta})


# ── Env sensor (1-min reading from ESP32) ─────────────────────────────────────
@app.route("/environment", methods=["POST"])
@require_auth
def environment():
    user = get_current_user()
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON required"}), 400

    conn = get_db()
    conn.execute("""
        INSERT INTO env_readings
            (user_id, sample_id, timestamp, temp_c, env_humidity, pressure_hpa)
        VALUES (?,?,?,?,?,?)
    """, (user["user_id"], data.get("sample_id",""),
          datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
          data.get("temp_c"), data.get("env_humidity"), data.get("pressure_hpa")))
    conn.commit()
    delta = try_compute_delta_realtime(data.get("sample_id",""), user["user_id"], conn)
    conn.close()
    return jsonify({"success": True, "delta_humidity": delta})


# ── Upload CSV (surface or env) ───────────────────────────────────────────────
@app.route("/upload-csv", methods=["POST"])
@require_auth
def upload_csv():
    """
    Accept log_surface.csv or log_env.csv uploaded from the dashboard.
    csv_type: 'surface' or 'env'
    Columns accepted:
      surface: datetime, sample_id, [model_type ignored], time_ms, temp_c, surface_humidity, pressure_hpa
      env:     datetime, sample_id, time_ms, temp_c, env_humidity, pressure_hpa
    """
    user    = get_current_user()
    user_id = user["user_id"]

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    csv_type = request.form.get("csv_type", "").lower()
    if csv_type not in ("surface", "env"):
        return jsonify({"error": "csv_type must be 'surface' or 'env'"}), 400

    file_content = request.files["file"].read().decode("utf-8-sig", errors="ignore")
    reader       = csv.DictReader(io.StringIO(file_content))

    inserted = 0
    skipped  = 0
    conn     = get_db()

    affected_samples = set()

    for row in reader:
        try:
            # Accept both 'datetime' and 'timestamp' column names
            ts        = (row.get("datetime") or row.get("timestamp") or "").strip()
            sample_id = row.get("sample_id", "").strip()
            if not ts or not sample_id:
                skipped += 1
                continue

            # Normalise datetime format
            for fmt in ("%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                try:
                    ts = datetime.strptime(ts, fmt).strftime("%Y-%m-%d %H:%M:%S")
                    break
                except ValueError:
                    continue

            # Accept 'temperature' as alias for 'temp_c', 'humidity' as alias for sensor humidity
            if csv_type == "surface":
                surf_hum = float(row.get("surface_humidity") or row.get("surface_humid")
                                 or row.get("humidity") or 0)
                temp_c   = float(row.get("temp_c") or row.get("temperature") or 0)
                pressure = float(row.get("pressure_hpa") or row.get("pressure") or 0)
                conn.execute("""
                    INSERT INTO surface_readings
                        (user_id, sample_id, timestamp, temp_c, surface_humidity, pressure_hpa)
                    VALUES (?,?,?,?,?,?)
                """, (user_id, sample_id, ts, temp_c, surf_hum, pressure))
            else:  # env
                env_hum  = float(row.get("env_humidity") or row.get("env_humid")
                                 or row.get("humidity") or 0)
                temp_c   = float(row.get("temp_c") or row.get("temperature") or 0)
                pressure = float(row.get("pressure_hpa") or row.get("pressure") or 0)
                conn.execute("""
                    INSERT INTO env_readings
                        (user_id, sample_id, timestamp, temp_c, env_humidity, pressure_hpa)
                    VALUES (?,?,?,?,?,?)
                """, (user_id, sample_id, ts, temp_c, env_hum, pressure))

            affected_samples.add(sample_id)
            inserted += 1
        except Exception:
            skipped += 1

    conn.commit()

    # Back-fill scores for detections that had no humidity data at detection time
    rescored = 0
    for sid in affected_samples:
        pending = conn.execute("""
            SELECT id, timestamp, score_breakdown, state_areas
            FROM detections
            WHERE user_id=? AND sample_id=? AND delta_humidity IS NULL
        """, (user_id, sid)).fetchall()
        for det in pending:
            delta, surf_h, env_h, temp_c = find_sensing_delta(user_id, sid, det["timestamp"])
            if delta is None:
                continue
            bd = None
            try:
                bd = json.loads(det["score_breakdown"]) if det["score_breakdown"] else None
            except Exception:
                pass
            new_total = None
            new_breakdown = None
            if bd:
                # Update hum component in existing breakdown
                abs_dh = abs(delta)
                if abs_dh < 5:
                    new_hum = 30
                elif abs_dh <= 15:
                    new_hum = round(30 * (15 - abs_dh) / 10)
                else:
                    new_hum = 0
                new_total = max(0, min(100, bd["img"] + new_hum + bd["trend"]))
                bd.update({"hum": new_hum, "has_humidity": True, "total": new_total})
                new_breakdown = json.dumps(bd)
            else:
                # Old record without score_breakdown — full rescore using state_areas
                sa = None
                try:
                    sa = json.loads(det["state_areas"]) if det["state_areas"] else None
                except Exception:
                    pass
                if sa:
                    sr = calc_health_score([], delta_humidity=delta,
                                          sample_id=sid, user_id=user_id, state_areas=sa)
                    new_total = sr["total"]
                    new_breakdown = json.dumps(sr)
            conn.execute("""
                UPDATE detections
                SET surface_humidity=?, env_humidity=?, delta_humidity=?, temp_c=COALESCE(temp_c,?)
                    {score_update}
                WHERE id=? AND user_id=?
            """.replace("{score_update}",
                        ", health_score=?, score_breakdown=?" if new_total is not None else ""),
                ([surf_h, env_h, delta, temp_c] +
                 ([new_total, new_breakdown] if new_total is not None else []) +
                 [det["id"], user_id]))
            rescored += 1

    conn.commit()
    conn.close()

    return jsonify({
        "success":  True,
        "inserted": inserted,
        "skipped":  skipped,
        "rescored": rescored,
        "csv_type": csv_type,
    })


# ── History (user-scoped) ─────────────────────────────────────────────────────
@app.route("/history", methods=["GET"])
@require_auth
def history():
    user      = get_current_user()
    user_id   = user["user_id"]
    sample_id = request.args.get("sample_id")
    limit     = int(request.args.get("limit", 50))

    where  = ["user_id = ?"]
    params = [user_id]
    if sample_id:
        where.append("sample_id = ?")
        params.append(sample_id)

    params.append(limit)
    conn = get_db()
    rows = conn.execute(
        f"SELECT * FROM detections WHERE {' AND '.join(where)} ORDER BY id DESC LIMIT ?",
        params
    ).fetchall()
    conn.close()

    records      = [dict(r) for r in reversed(rows)]
    state_counts = {}
    for r in records:
        s = r.get("yolo_state") or "unknown"
        state_counts[s] = state_counts.get(s, 0) + 1

    return jsonify({"count": len(records), "state_counts": state_counts, "records": records})


# ── Samples (user-scoped) ─────────────────────────────────────────────────────
def _try_delete_file(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as exc:
        print(f"File delete warning: {exc}", flush=True)


@app.route("/samples", methods=["GET", "POST"])
@require_auth
def samples():
    user    = get_current_user()
    user_id = user["user_id"]
    conn    = get_db()

    if request.method == "GET":
        rows = conn.execute("""
            SELECT s.sample_id, s.name, s.description, s.cover_image, s.created_at,
                   latest.timestamp    AS latest_ts,
                   latest.yolo_state   AS latest_state,
                   latest.health_score AS latest_score,
                   latest.image_path   AS latest_image_path
            FROM samples s
            LEFT JOIN detections latest ON latest.id = (
                SELECT id FROM detections
                WHERE user_id = s.user_id AND sample_id = s.sample_id
                ORDER BY id DESC LIMIT 1
            )
            WHERE s.user_id = ?
            ORDER BY COALESCE(latest.timestamp, s.created_at) DESC
        """, (user_id,)).fetchall()
        conn.close()
        return jsonify({"samples": [dict(r) for r in rows]})
    else:
        # Support both multipart/form-data (with cover image) and plain JSON
        cover_image_path = None
        if request.content_type and "multipart" in request.content_type:
            sid         = (request.form.get("sample_id") or "").strip().upper().replace(" ", "-")
            name        = (request.form.get("name") or "").strip() or None
            description = (request.form.get("description") or "").strip() or None
            cf = request.files.get("cover_image")
            if cf and cf.filename:
                ext = os.path.splitext(cf.filename)[1].lower() or ".jpg"
                cover_fname = f"cover_{uuid.uuid4().hex}{ext}"
                cf.save(os.path.join(UPLOAD_FOLDER, cover_fname))
                cover_image_path = cover_fname
        else:
            data        = request.get_json() or {}
            sid         = (data.get("sample_id") or "").strip().upper().replace(" ", "-")
            name        = (data.get("name") or "").strip() or None
            description = (data.get("description") or "").strip() or None

        if not sid:
            conn.close()
            return jsonify({"error": "sample_id required"}), 400
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            conn.execute("""
                INSERT INTO samples (user_id, sample_id, name, description, cover_image, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, sid, name, description, cover_image_path, now))
            conn.commit()
        except sqlite3.IntegrityError:
            pass  # Already exists — fine
        conn.close()
        return jsonify({"success": True, "sample_id": sid})


# ── Sample detail — full archive ──────────────────────────────────────────────
@app.route("/samples/<sample_id>", methods=["GET"])
@require_auth
def sample_detail(sample_id):
    user    = get_current_user()
    user_id = user["user_id"]
    conn    = get_db()

    meta = conn.execute(
        "SELECT * FROM samples WHERE user_id=? AND sample_id=?",
        (user_id, sample_id)
    ).fetchone()
    if not meta:
        conn.close()
        return jsonify({"error": "Sample not found"}), 404

    det_rows = conn.execute("""
        SELECT id, timestamp, yolo_state, health_score, image_path, notes,
               surface_humidity, env_humidity, delta_humidity, temp_c, state_areas, score_breakdown
        FROM detections
        WHERE user_id=? AND sample_id=?
        ORDER BY timestamp ASC
    """, (user_id, sample_id)).fetchall()

    file_rows = conn.execute("""
        SELECT id, file_type, timestamp, file_path, notes, metadata
        FROM sample_files
        WHERE user_id=? AND sample_id=?
        ORDER BY timestamp ASC
    """, (user_id, sample_id)).fetchall()
    conn.close()

    files_by_type = {"humidity_map": [], "cloudcompare": [], "scan_model": []}
    for row in file_rows:
        ft = row["file_type"]
        if ft in files_by_type:
            files_by_type[ft].append(dict(row))

    return jsonify({
        "sample":        dict(meta),
        "detections":    [dict(r) for r in det_rows],
        "humidity_maps": files_by_type["humidity_map"],
        "cloudcompare":  files_by_type["cloudcompare"],
        "scan_models":   files_by_type["scan_model"],
    })


# ── Sample delete ─────────────────────────────────────────────────────────────
@app.route("/samples/<sample_id>/delete", methods=["DELETE"])
@require_auth
def delete_sample(sample_id):
    user    = get_current_user()
    user_id = user["user_id"]
    conn    = get_db()

    row = conn.execute(
        "SELECT cover_image FROM samples WHERE sample_id = ? AND user_id = ?",
        (sample_id, user_id)
    ).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Sample not found or not yours"}), 404

    dets   = conn.execute(
        "SELECT image_path FROM detections WHERE sample_id = ? AND user_id = ?",
        (sample_id, user_id)
    ).fetchall()
    sfiles = conn.execute(
        "SELECT file_path FROM sample_files WHERE sample_id = ? AND user_id = ?",
        (sample_id, user_id)
    ).fetchall()

    conn.execute("DELETE FROM detections   WHERE sample_id = ? AND user_id = ?", (sample_id, user_id))
    conn.execute("DELETE FROM sample_files WHERE sample_id = ? AND user_id = ?", (sample_id, user_id))
    conn.execute("DELETE FROM samples      WHERE sample_id = ? AND user_id = ?", (sample_id, user_id))
    conn.commit()
    conn.close()

    if row["cover_image"]:
        _try_delete_file(os.path.join(UPLOAD_FOLDER, row["cover_image"]))
    for det in dets:
        if det["image_path"]:
            _try_delete_file(os.path.join(UPLOAD_FOLDER, det["image_path"]))
            stem = os.path.splitext(det["image_path"])[0]
            _try_delete_file(os.path.join(UPLOAD_FOLDER, f"result_{stem}.jpg"))
    for sf in sfiles:
        if sf["file_path"]:
            _try_delete_file(os.path.join(UPLOAD_FOLDER, sf["file_path"]))

    print(f"🗑 Deleted sample {sample_id} by user {user_id}", flush=True)
    return jsonify({"success": True})


# ── Detection — delete single record ──────────────────────────────────────────
@app.route("/detections/<int:det_id>", methods=["DELETE"])
@require_auth
def delete_detection(det_id):
    user    = get_current_user()
    user_id = user["user_id"]
    conn    = get_db()
    row = conn.execute(
        "SELECT image_path FROM detections WHERE id=? AND user_id=?",
        (det_id, user_id)
    ).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    conn.execute("DELETE FROM detections WHERE id=? AND user_id=?", (det_id, user_id))
    conn.commit()
    conn.close()
    if row["image_path"]:
        _try_delete_file(os.path.join(UPLOAD_FOLDER, row["image_path"]))
        stem = os.path.splitext(row["image_path"])[0]
        _try_delete_file(os.path.join(UPLOAD_FOLDER, f"result_{stem}.jpg"))
    return jsonify({"success": True})


# ── Sample file — delete single record ────────────────────────────────────────
@app.route("/sample-files/<int:file_id>", methods=["DELETE"])
@require_auth
def delete_sample_file_by_id(file_id):
    user    = get_current_user()
    user_id = user["user_id"]
    conn    = get_db()
    row = conn.execute(
        "SELECT file_path FROM sample_files WHERE id=? AND user_id=?",
        (file_id, user_id)
    ).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    conn.execute("DELETE FROM sample_files WHERE id=? AND user_id=?", (file_id, user_id))
    conn.commit()
    conn.close()
    if row["file_path"]:
        _try_delete_file(os.path.join(UPLOAD_FOLDER, row["file_path"]))
    return jsonify({"success": True})


# ── Sample files — upload ─────────────────────────────────────────────────────
@app.route("/sample-files", methods=["POST"])
@require_auth
def upload_sample_file():
    user    = get_current_user()
    user_id = user["user_id"]

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file      = request.files["file"]
    sample_id = request.form.get("sample_id", "").strip()
    file_type = request.form.get("file_type", "").strip()
    notes     = request.form.get("notes", "")
    metadata  = request.form.get("metadata", "{}")
    timestamp = request.form.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not sample_id:
        return jsonify({"error": "sample_id required"}), 400
    if file_type not in ("humidity_map", "cloudcompare", "scan_model"):
        return jsonify({"error": "file_type must be humidity_map, cloudcompare, or scan_model"}), 400

    try:
        json.loads(metadata)
    except Exception:
        metadata = "{}"

    ext       = os.path.splitext(file.filename)[1].lower() or ".bin"
    filename  = f"{file_type}_{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(save_path)

    conn = get_db()
    conn.execute("""
        INSERT OR IGNORE INTO samples (user_id, sample_id, created_at)
        VALUES (?, ?, ?)
    """, (user_id, sample_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.execute("""
        INSERT INTO sample_files
            (user_id, sample_id, file_type, timestamp, file_path, notes, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, sample_id, file_type, timestamp, filename, notes, metadata))
    conn.commit()
    conn.close()

    print(f"✅ Sample file uploaded: {file_type} / {filename}", flush=True)
    return jsonify({"success": True, "file_path": filename, "file_type": file_type})


# ── Sample files — list ───────────────────────────────────────────────────────
@app.route("/sample-files/<sample_id>", methods=["GET"])
@require_auth
def get_sample_files(sample_id):
    user      = get_current_user()
    user_id   = user["user_id"]
    file_type = request.args.get("type")
    conn      = get_db()

    if file_type:
        rows = conn.execute("""
            SELECT id, file_type, timestamp, file_path, notes, metadata
            FROM sample_files
            WHERE user_id=? AND sample_id=? AND file_type=?
            ORDER BY timestamp ASC
        """, (user_id, sample_id, file_type)).fetchall()
    else:
        rows = conn.execute("""
            SELECT id, file_type, timestamp, file_path, notes, metadata
            FROM sample_files
            WHERE user_id=? AND sample_id=?
            ORDER BY timestamp ASC
        """, (user_id, sample_id)).fetchall()
    conn.close()
    return jsonify({"files": [dict(r) for r in rows]})


# ── Sensor direct entry (legacy /sensor endpoint, now auth-gated) ─────────────
@app.route("/sensor", methods=["POST"])
@require_auth
def sensor():
    user = get_current_user()
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON required"}), 400

    sample_id   = data.get("sample_id", "")
    temp_c      = data.get("temp_c")
    env_hum     = data.get("env_humidity")
    surface_hum = data.get("surface_humidity")
    delta       = round(surface_hum - env_hum, 1) if (surface_hum and env_hum) else None

    conn = get_db()
    conn.execute("""
        UPDATE detections
        SET temp_c=?, env_humidity=?, surface_humidity=?, delta_humidity=?
        WHERE sample_id=? AND user_id=?
          AND id=(SELECT MAX(id) FROM detections WHERE sample_id=? AND user_id=?)
    """, (temp_c, env_hum, surface_hum, delta,
          sample_id, user["user_id"], sample_id, user["user_id"]))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "delta_humidity": delta})


# ── Serve images ──────────────────────────────────────────────────────────────
@app.route("/image/<path:filename>", methods=["GET"])
def serve_image(filename):
    from flask import send_from_directory
    return send_from_directory(UPLOAD_FOLDER, filename)


# ── Summary ───────────────────────────────────────────────────────────────────
@app.route("/summary", methods=["GET"])
@require_auth
def summary():
    user    = get_current_user()
    user_id = user["user_id"]
    conn    = get_db()
    total   = conn.execute("SELECT COUNT(*) FROM detections WHERE user_id=?", (user_id,)).fetchone()[0]
    latest  = conn.execute("SELECT * FROM detections WHERE user_id=? ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
    surf_n  = conn.execute("SELECT COUNT(*) FROM surface_readings WHERE user_id=?", (user_id,)).fetchone()[0]
    env_n   = conn.execute("SELECT COUNT(*) FROM env_readings WHERE user_id=?", (user_id,)).fetchone()[0]
    conn.close()
    return jsonify({
        "total_records":        total,
        "surface_raw_readings": surf_n,
        "env_raw_readings":     env_n,
        "latest_record":        dict(latest) if latest else None,
    })


# ══════════════════════════════════════════════════════════════════════════════
# Roboflow
# ══════════════════════════════════════════════════════════════════════════════

ROBOFLOW_API_KEY  = "fDrVj3xCLR7CJOd8P2Rf"
ROBOFLOW_PROJECT  = "mycelium-detection"


def upload_to_roboflow(image_path, annotations, image_filename):
    """Upload image to Roboflow using base64 as raw POST body (correct method)."""
    import requests as req_lib

    with open(image_path, "rb") as img_f:
        img_b64 = base64.b64encode(img_f.read()).decode("ascii")

    upload_url = (
        f"https://api.roboflow.com/dataset/{ROBOFLOW_PROJECT}/upload"
        f"?api_key={ROBOFLOW_API_KEY}&name={image_filename}&split=train"
    )

    # Roboflow expects base64 string as raw body with form-urlencoded content type
    resp = req_lib.post(
        upload_url,
        data=img_b64,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=60
    )
    print(f"Roboflow response: {resp.status_code} {resp.text[:300]}", flush=True)
    if resp.status_code not in (200, 201):
        raise Exception(f"Roboflow upload failed: {resp.status_code} {resp.text[:200]}")

    result   = resp.json()
    image_id = result.get("id") or result.get("imageId") or result.get("image", {}).get("id")

    # Upload annotations if present
    if annotations and image_id:
        try:
            # Build YOLO-format annotation text for polygon segments
            ann_lines = []
            label_map = {"healthy_mycelium":0, "dry_aged_mycelium":1,
                         "contamination_risk":2, "exposed_substrate":3}
            for a in annotations:
                cls_idx = label_map.get(a["label"], 0)
                pts = a.get("points", [])
                if len(pts) >= 3:
                    coords = " ".join(f"{p['x']:.6f} {p['y']:.6f}" for p in pts)
                    ann_lines.append(f"{cls_idx} {coords}")
            if ann_lines:
                ann_text = "\n".join(ann_lines)
                ann_url = (
                    f"https://api.roboflow.com/dataset/{ROBOFLOW_PROJECT}/annotate/{image_id}"
                    f"?api_key={ROBOFLOW_API_KEY}&name={image_filename}.txt"
                )
                ann_resp = req_lib.post(
                    ann_url,
                    data=ann_text,
                    headers={"Content-Type": "text/plain"},
                    timeout=30
                )
                print(f"Roboflow annotation response: {ann_resp.status_code} {ann_resp.text[:200]}", flush=True)
        except Exception as ann_err:
            print(f"Annotation upload error (image still uploaded): {ann_err}", flush=True)

    return image_id


# ── Contribute ────────────────────────────────────────────────────────────────
@app.route("/contribute", methods=["POST"])
def contribute():
    """Open to anonymous users too; logged-in users get user_id attached."""
    user    = get_current_user()
    user_id = user["user_id"] if user else None

    if "image" not in request.files:
        return jsonify({"error": "No image provided"}), 400

    file          = request.files["image"]
    contributor   = request.form.get("contributor", "anonymous")
    location      = request.form.get("location", "") or ""
    lat           = request.form.get("lat")
    lng           = request.form.get("lng")
    mycelium_type = request.form.get("mycelium_type", "")
    notes         = request.form.get("notes", "")
    annotations_str = request.form.get("annotations", "[]")
    timestamp     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # location = "" or None → treat as unknown
    location_clean = location.strip() if location.strip() else None

    try:
        annotations = json.loads(annotations_str)
    except Exception:
        annotations = []

    try:
        img = load_normalized_image(file)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    filename  = f"contrib_{uuid.uuid4().hex}.jpg"
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    img.save(save_path, "JPEG", quality=90)
    img.close()

    print(f"📥 Contribute received: {filename}, {len(annotations)} annotations", flush=True)
    roboflow_id    = None
    roboflow_error = None
    try:
        roboflow_id = upload_to_roboflow(save_path, annotations, filename)
        print(f"✅ Roboflow upload success: {roboflow_id}", flush=True)
    except Exception as e:
        roboflow_error = str(e)
        print(f"❌ Roboflow upload failed: {roboflow_error}", flush=True)

    conn = get_db()
    conn.execute("""
        INSERT INTO contributions
            (user_id, timestamp, contributor, location, lat, lng,
             image_path, annotations, mycelium_type, notes, status, roboflow_id)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (user_id, timestamp, contributor, location_clean,
          float(lat) if lat else None, float(lng) if lng else None,
          filename, annotations_str, mycelium_type, notes,
          "uploaded" if roboflow_id else "pending", roboflow_id))
    conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM contributions").fetchone()[0]
    conn.close()

    return jsonify({
        "success":             True,
        "roboflow_id":         roboflow_id,
        "roboflow_error":      roboflow_error,
        "total_contributions": total,
    })


# ── City coordinate fallback for contributions without stored lat/lng ──────────
# Used by /contributions/stats when a location group has NULL lat/lng.
# Keys are lowercase substrings to match against the location text.
CITY_FALLBACK = {
    # China
    "beijing": (39.9042, 116.4074),   "北京": (39.9042, 116.4074),
    "shanghai": (31.2304, 121.4737),  "上海": (31.2304, 121.4737),
    "chengdu": (30.5728, 104.0668),   "成都": (30.5728, 104.0668),
    "guangzhou": (23.1291, 113.2644), "广州": (23.1291, 113.2644),
    "shenzhen": (22.5431, 114.0579),  "深圳": (22.5431, 114.0579),
    "hangzhou": (30.2741, 120.1551),  "杭州": (30.2741, 120.1551),
    "wuhan": (30.5928, 114.3055),     "武汉": (30.5928, 114.3055),
    "nanjing": (32.0603, 118.7969),   "南京": (32.0603, 118.7969),
    "xian": (34.3416, 108.9398),      "西安": (34.3416, 108.9398),
    "chongqing": (29.4316, 106.9123), "重庆": (29.4316, 106.9123),
    "tianjin": (39.3434, 117.3616),   "天津": (39.3434, 117.3616),
    "hong kong": (22.3193, 114.1694), "香港": (22.3193, 114.1694),
    "taipei": (25.0330, 121.5654),    "台北": (25.0330, 121.5654),
    # UK / Europe
    "london": (51.5074, -0.1278),     "paris": (48.8566, 2.3522),
    "berlin": (52.5200, 13.4050),     "amsterdam": (52.3676, 4.9041),
    "barcelona": (41.3851, 2.1734),   "rome": (41.9028, 12.4964),
    "madrid": (40.4168, -3.7038),     "zurich": (47.3769, 8.5417),
    "vienna": (48.2082, 16.3738),     "stockholm": (59.3293, 18.0686),
    "edinburgh": (55.9533, -3.1883),  "manchester": (53.4808, -2.2426),
    # Americas
    "new york": (40.7128, -74.0060),  "los angeles": (34.0522, -118.2437),
    "chicago": (41.8781, -87.6298),   "toronto": (43.6532, -79.3832),
    "mexico city": (19.4326, -99.1332),
    "sao paulo": (-23.5505, -46.6333),
    # Asia-Pacific
    "tokyo": (35.6762, 139.6503),     "osaka": (34.6937, 135.5023),
    "seoul": (37.5665, 126.9780),     "singapore": (1.3521, 103.8198),
    "sydney": (-33.8688, 151.2093),   "melbourne": (-37.8136, 144.9631),
    # Middle East / Africa
    "dubai": (25.2048, 55.2708),      "istanbul": (41.0082, 28.9784),
    "cairo": (30.0444, 31.2357),
}


# ── Contribution stats (global — for map display) ─────────────────────────────
@app.route("/contributions/stats", methods=["GET"])
def contribution_stats():
    conn     = get_db()
    total    = conn.execute("SELECT COUNT(*) FROM contributions").fetchone()[0]
    uploaded = conn.execute("SELECT COUNT(*) FROM contributions WHERE status='uploaded'").fetchone()[0]
    unknown  = conn.execute(
        "SELECT COUNT(*) FROM contributions WHERE location IS NULL OR location=''"
    ).fetchone()[0]

    # Named locations — use AVG so mixed groups (some rows have lat/lng, some don't) still work
    rows = conn.execute("""
        SELECT location, AVG(lat) as lat, AVG(lng) as lng, COUNT(*) as cnt
        FROM contributions
        WHERE location IS NOT NULL AND location != ''
        GROUP BY location ORDER BY cnt DESC LIMIT 50
    """).fetchall()

    recent = conn.execute("""
        SELECT timestamp, contributor, location, mycelium_type, status
        FROM contributions ORDER BY id DESC LIMIT 10
    """).fetchall()

    conn.close()

    locations = []
    for r in rows:
        lat, lng = r["lat"], r["lng"]
        if lat is None or lng is None:
            loc_lower = (r["location"] or "").lower()
            for key, (fb_lat, fb_lng) in CITY_FALLBACK.items():
                if key in loc_lower:
                    lat, lng = fb_lat, fb_lng
                    break
        locations.append({"location": r["location"], "lat": lat, "lng": lng, "count": r["cnt"]})

    return jsonify({
        "total":     total,
        "uploaded":  uploaded,
        "unknown":   unknown,
        "locations": locations,
        "recent":    [dict(r) for r in recent],
    })


# ══════════════════════════════════════════════════════════════════════════════
# Admin endpoints
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/admin/users", methods=["GET"])
@require_admin
def admin_users():
    conn  = get_db()
    users = conn.execute(
        "SELECT id, username, created_at, is_admin FROM users ORDER BY id"
    ).fetchall()
    conn.close()
    return jsonify({"users": [dict(u) for u in users]})


@app.route("/admin/detections", methods=["GET"])
@require_admin
def admin_detections():
    """Admin sees all users' detections."""
    conn = get_db()
    rows = conn.execute("""
        SELECT d.*, u.username FROM detections d
        LEFT JOIN users u ON d.user_id = u.id
        ORDER BY d.id DESC LIMIT 200
    """).fetchall()
    conn.close()
    return jsonify({"records": [dict(r) for r in rows]})


@app.route("/admin/images", methods=["GET"])
@require_admin
def admin_images():
    """
    Returns all detection images not yet used in training.
    Admin uses this to review and export for Roboflow labeling.
    """
    conn = get_db()
    rows = conn.execute("""
        SELECT d.id, d.user_id, u.username, d.sample_id, d.timestamp,
               d.image_path, d.yolo_state, d.health_score
        FROM detections d
        LEFT JOIN users u ON d.user_id = u.id
        WHERE d.image_path IS NOT NULL
        ORDER BY d.id DESC
    """).fetchall()
    conn.close()
    return jsonify({"images": [dict(r) for r in rows]})


# ── Admin: download all detection images as ZIP ───────────────────────────────
@app.route("/admin/download-all", methods=["GET"])
@require_admin
def admin_download_all():
    """Bundle all detection images into a ZIP for the admin to download."""
    import zipfile
    from io import BytesIO
    from flask import send_file

    conn = get_db()
    rows = conn.execute("""
        SELECT d.image_path, d.sample_id, d.timestamp, d.yolo_state, u.username
        FROM detections d
        LEFT JOIN users u ON d.user_id = u.id
        WHERE d.image_path IS NOT NULL
        ORDER BY d.id DESC
    """).fetchall()
    conn.close()

    mem = BytesIO()
    with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in rows:
            img_path = os.path.join(UPLOAD_FOLDER, r["image_path"])
            if os.path.exists(img_path):
                # Name: username_sample_date_originalname.jpg
                safe_user = (r["username"] or "anon").replace(" ", "")
                safe_date = (r["timestamp"] or "")[:10]
                arcname = f"{safe_user}_{r['sample_id']}_{safe_date}_{r['image_path']}"
                zf.write(img_path, arcname)
    mem.seek(0)
    return send_file(mem, mimetype="application/zip",
                     as_attachment=True,
                     download_name="all_detection_images.zip")


# ── Admin: list all contributions ────────────────────────────────────────────
@app.route("/admin/contributions", methods=["GET"])
@require_admin
def admin_contributions():
    conn = get_db()
    rows = conn.execute("""
        SELECT c.id, c.contributor, c.location, c.timestamp,
               c.image_path, c.status, c.mycelium_type,
               u.username
        FROM contributions c
        LEFT JOIN users u ON c.user_id = u.id
        ORDER BY c.id DESC
    """).fetchall()
    conn.close()
    return jsonify({"contributions": [dict(r) for r in rows]})


# ── Admin: clear all detection records + image files ─────────────────────────
@app.route("/admin/clear-detections", methods=["POST"])
@require_admin
def admin_clear_detections():
    conn = get_db()
    img_rows = conn.execute(
        "SELECT image_path FROM detections WHERE image_path IS NOT NULL"
    ).fetchall()
    deleted_files = 0
    for row in img_rows:
        img_path = os.path.join(UPLOAD_FOLDER, row["image_path"])
        if os.path.exists(img_path):
            os.remove(img_path)
            deleted_files += 1
    count = conn.execute("SELECT COUNT(*) FROM detections").fetchone()[0]
    conn.execute("DELETE FROM detections")
    conn.commit()
    conn.close()
    print(f"🗑️ Admin cleared {count} detections, {deleted_files} image files removed", flush=True)
    return jsonify({"success": True, "deleted_records": count, "deleted_files": deleted_files})


# ── Admin page (HTML) ─────────────────────────────────────────────────────────
@app.route("/admin", methods=["GET"])
def admin_page():
    from flask import send_from_directory
    return send_from_directory(".", "admin.html")


# ── Emergency: reset admin password (accessible without auth) ─────────────────
@app.route("/reset-admin", methods=["POST"])
def reset_admin():
    """Emergency endpoint — resets Kecen Yi password to yikecen."""
    pw_hash = bcrypt.hashpw("yikecen".encode(), bcrypt.gensalt()).decode()
    conn = get_db()
    conn.execute(
        "UPDATE users SET password_hash=?, is_admin=1 WHERE username=?",
        (pw_hash, "Kecen Yi")
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Admin password reset to yikecen"})


# ── Launch ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 SYMBIO-FRAME backend starting on port {port}")
    app.run(debug=False, host="0.0.0.0", port=port)
