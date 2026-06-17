import os
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

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
DB_PATH       = "mycelium.db"
SECRET_KEY    = os.environ.get("JWT_SECRET", "symbioframe_secret_key_2026_secure")   # JWT signing key
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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

    conn.commit()

    # ── Migrations: add missing columns to existing tables ─────────────────
    # Safe: ALTER TABLE ADD COLUMN is ignored if column already exists via try/except
    migrations = [
        ("detections",       "user_id          INTEGER"),
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
        pw_hash = bcrypt.hashpw("symbioframe2026".encode(), bcrypt.gensalt()).decode()
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

def calc_health_score(detections, delta_humidity=None, sample_id=None, user_id=None):
    # Dimension 1: image (0-60)
    img_score = 60.0
    for d in detections:
        conf = d["confidence"] / 100
        name = d["class_name"]
        if name in ("contaminated", "contamination_risk"):
            img_score -= 20 * conf
        elif name in ("dry_aging", "dry_aged_mycelium", "aging"):
            img_score -= 12 * conf
        elif name == "exposed_substrate":
            img_score -= 8 * conf
    img_score = max(0.0, img_score)

    # Dimension 2: delta humidity (0-30)
    if delta_humidity is not None:
        dh = delta_humidity
        if 5 <= dh <= 25:
            hum_score = 30
        elif 0 <= dh < 5 or 25 < dh <= 35:
            hum_score = 20
        elif -10 <= dh < 0 or 35 < dh <= 50:
            hum_score = 10
        else:
            hum_score = 0
    else:
        hum_score = 15  # neutral if no sensor data

    # Dimension 3: trend (0-10)
    trend_score = 10
    if sample_id and user_id:
        try:
            conn = get_db()
            recent = conn.execute(
                "SELECT health_score FROM detections WHERE sample_id=? AND user_id=? "
                "AND health_score IS NOT NULL ORDER BY id DESC LIMIT 4",
                (sample_id, user_id)
            ).fetchall()
            conn.close()
            sc = [r[0] for r in recent]
            if len(sc) >= 3 and sc[0] < sc[1] and sc[1] < sc[2]:
                trend_score = 0
            elif len(sc) >= 2 and sc[0] < sc[1]:
                trend_score = 5
        except Exception:
            pass

    return max(0, min(100, round(img_score + hum_score + trend_score)))


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

    ext       = os.path.splitext(file.filename)[1].lower() or ".jpg"
    filename  = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(save_path)

    results = model(save_path, conf=0.1)  # Low threshold for small dataset
    result  = results[0]

    result_filename = f"result_{os.path.splitext(filename)[0]}.jpg"
    result_path     = os.path.join(UPLOAD_FOLDER, result_filename)
    result.save(filename=result_path)

    img_h, img_w = result.orig_shape[:2]
    img_area = img_w * img_h

    detections = []
    for box in result.boxes:
        class_id   = int(box.cls[0])
        class_name = model.names[class_id]
        confidence = round(float(box.conf[0]) * 100, 1)
        x1, y1, x2, y2 = [round(float(v), 1) for v in box.xyxy[0]]
        area_pct = round((x2-x1)*(y2-y1) / img_area * 100, 1)
        detections.append({
            "class_id":   class_id,
            "class_name": class_name,
            "confidence": confidence,
            "area_pct":   area_pct,
            "bbox": {"x1":x1,"y1":y1,"x2":x2,"y2":y2,
                     "width":round(x2-x1,1),"height":round(y2-y1,1)}
        })

    state_areas = {}
    for d in detections:
        n = d["class_name"]
        state_areas[n] = round(state_areas.get(n, 0) + d["area_pct"], 1)

    # Find sensing delta for this sample+date
    delta, surf_hum, env_hum, temp_c = find_sensing_delta(user_id, sample_id, timestamp)

    health_score = calc_health_score(detections, delta_humidity=delta,
                                     sample_id=sample_id, user_id=user_id)
    yolo_state   = main_state(detections)

    conn = get_db()
    conn.execute("""
        INSERT INTO detections
            (user_id, sample_id, model_type, timestamp, image_path,
             yolo_state, health_score, temp_c, env_humidity, surface_humidity,
             delta_humidity, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (user_id, sample_id, model_type, timestamp, filename,
          yolo_state, health_score, temp_c, env_hum, surf_hum, delta, notes))
    conn.commit()

    # Also try realtime pairing if 1-min reading was just done
    realtime_delta = try_compute_delta_realtime(sample_id, user_id, conn)
    if realtime_delta and delta is None:
        delta = realtime_delta
    conn.close()

    with open(result_path, "rb") as f:
        result_b64 = base64.b64encode(f.read()).decode()

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

    for row in reader:
        try:
            ts        = row.get("datetime", "").strip()
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

            if csv_type == "surface":
                # Accept both 6-col (no model_type) and 7-col (with model_type)
                surf_hum = float(row.get("surface_humidity") or row.get("surface_humid") or 0)
                temp_c   = float(row.get("temp_c") or 0)
                pressure = float(row.get("pressure_hpa") or 0)
                conn.execute("""
                    INSERT INTO surface_readings
                        (user_id, sample_id, timestamp, temp_c, surface_humidity, pressure_hpa)
                    VALUES (?,?,?,?,?,?)
                """, (user_id, sample_id, ts, temp_c, surf_hum, pressure))

            else:  # env
                env_hum  = float(row.get("env_humidity") or row.get("env_humid") or 0)
                temp_c   = float(row.get("temp_c") or 0)
                pressure = float(row.get("pressure_hpa") or 0)
                conn.execute("""
                    INSERT INTO env_readings
                        (user_id, sample_id, timestamp, temp_c, env_humidity, pressure_hpa)
                    VALUES (?,?,?,?,?,?)
                """, (user_id, sample_id, ts, temp_c, env_hum, pressure))

            inserted += 1
        except Exception:
            skipped += 1

    conn.commit()
    conn.close()

    return jsonify({
        "success":  True,
        "inserted": inserted,
        "skipped":  skipped,
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
@app.route("/samples", methods=["GET", "POST"])
@require_auth
def samples():
    user    = get_current_user()
    user_id = user["user_id"]
    conn    = get_db()

    if request.method == "GET":
        rows = conn.execute(
            "SELECT DISTINCT sample_id FROM detections WHERE user_id=? ORDER BY sample_id",
            (user_id,)
        ).fetchall()
        conn.close()
        return jsonify({"samples": [r[0] for r in rows]})
    else:
        data = request.get_json()
        sid  = (data.get("sample_id") or "").strip().upper().replace(" ", "-")
        conn.close()
        if not sid:
            return jsonify({"error": "sample_id required"}), 400
        return jsonify({"success": True, "sample_id": sid})


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
    import requests as req_lib

    upload_url = (
        f"https://api.roboflow.com/dataset/{ROBOFLOW_PROJECT}/upload"
        f"?api_key={ROBOFLOW_API_KEY}&name={image_filename}&split=train"
    )
    with open(image_path, "rb") as img_f:
        img_b64 = base64.b64encode(img_f.read()).decode()

    resp = req_lib.post(upload_url, json={"image": img_b64}, timeout=30)
    print(f"Roboflow response: {resp.status_code} {resp.text[:300]}")
    if resp.status_code not in (200, 201):
        raise Exception(f"Roboflow upload failed: {resp.status_code} {resp.text[:200]}")

    result   = resp.json()
    image_id = result.get("id") or result.get("imageId") or result.get("image", {}).get("id") or str(result)

    if annotations and image_id:
        ann_url = (
            f"https://api.roboflow.com/dataset/{ROBOFLOW_PROJECT}/annotate/{image_id}"
            f"?api_key={ROBOFLOW_API_KEY}"
        )
        rf_anns = [{"label": a["label"], "points": a["points"], "type": "polygon"} for a in annotations]
        req_lib.post(ann_url, json={"annotations": rf_anns}, timeout=15)

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

    ext       = os.path.splitext(file.filename)[1].lower() or ".jpg"
    filename  = f"contrib_{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(save_path)

    roboflow_id    = None
    roboflow_error = None
    try:
        roboflow_id = upload_to_roboflow(save_path, annotations, filename)
        print(f"✅ Roboflow upload success: {roboflow_id}")
    except Exception as e:
        roboflow_error = str(e)
        print(f"❌ Roboflow upload failed: {roboflow_error}")

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


# ── Contribution stats (global — for map display) ─────────────────────────────
@app.route("/contributions/stats", methods=["GET"])
def contribution_stats():
    conn     = get_db()
    total    = conn.execute("SELECT COUNT(*) FROM contributions").fetchone()[0]
    uploaded = conn.execute("SELECT COUNT(*) FROM contributions WHERE status='uploaded'").fetchone()[0]
    unknown  = conn.execute(
        "SELECT COUNT(*) FROM contributions WHERE location IS NULL OR location=''"
    ).fetchone()[0]

    # Named locations with lat/lng
    locations = conn.execute("""
        SELECT location, lat, lng, COUNT(*) as cnt
        FROM contributions
        WHERE location IS NOT NULL AND location != ''
        GROUP BY location ORDER BY cnt DESC LIMIT 50
    """).fetchall()

    recent = conn.execute("""
        SELECT timestamp, contributor, location, mycelium_type, status
        FROM contributions ORDER BY id DESC LIMIT 10
    """).fetchall()

    conn.close()
    return jsonify({
        "total":    total,
        "uploaded": uploaded,
        "unknown":  unknown,
        "locations": [{"location": r[0], "lat": r[1], "lng": r[2], "count": r[3]}
                      for r in locations],
        "recent":   [dict(r) for r in recent],
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


# ── Emergency: reset admin password (accessible without auth) ─────────────────
@app.route("/reset-admin", methods=["POST"])
def reset_admin():
    """Emergency endpoint — resets Kecen Yi password to symbioframe2026."""
    pw_hash = bcrypt.hashpw("symbioframe2026".encode(), bcrypt.gensalt()).decode()
    conn = get_db()
    conn.execute(
        "UPDATE users SET password_hash=?, is_admin=1 WHERE username=?",
        (pw_hash, "Kecen Yi")
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Admin password reset to symbioframe2026"})


# ── Launch ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 SYMBIO-FRAME backend starting on port {port}")
    app.run(debug=False, host="0.0.0.0", port=port)
