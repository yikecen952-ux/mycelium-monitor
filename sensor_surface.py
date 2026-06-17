"""
sensor_surface.py · Surface humidity collection
ESP32-A + BME280-A, COM7, placed on mycelium surface

Usage: python sensor_surface.py
Stop:  Ctrl+C
"""

import serial
import csv
import requests
from datetime import datetime
from pathlib import Path

# ══════════════════════════════════════════════════════
#  Change these before each session
# ══════════════════════════════════════════════════════
PORT       = "COM7"
SAMPLE_ID  = "MYC-A1"    # Which sample point today

SEND_TO_DB = False        # True  → also send to backend database (1-min reading mode)
                          # False → save to CSV only (independent data collection)

AUTH_TOKEN = ""           # Paste your login token here when SEND_TO_DB = True
                          # Get it from the website after logging in (Profile → Copy token)
# ══════════════════════════════════════════════════════

BAUD     = 115200
API      = "http://127.0.0.1:5000"
CSV_FILE = "log_surface.csv"


def init_csv():
    p = Path(CSV_FILE)
    if not p.exists():
        with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([
                "datetime", "sample_id",
                "time_ms", "temp_c", "surface_humidity", "pressure_hpa"
            ])
    return open(CSV_FILE, "a", newline="", encoding="utf-8-sig")


def send_surface(temp, surface_hum, pressure):
    if not SEND_TO_DB:
        return
    try:
        headers = {"Authorization": f"Bearer {AUTH_TOKEN}"} if AUTH_TOKEN else {}
        res = requests.post(f"{API}/surface", json={
            "sample_id":        SAMPLE_ID,
            "temp_c":           temp,
            "surface_humidity": surface_hum,
            "pressure_hpa":     pressure,
        }, headers=headers, timeout=5)
        data = res.json()
        if data.get("success"):
            delta = data.get("delta_humidity")
            print(f"  → DB saved | Δ humidity: {delta}%" if delta else "  → DB saved")
        else:
            print(f"  → Backend: {data}")
    except Exception as e:
        print(f"  → Cannot reach backend ({e}), data saved to CSV only")


print("=" * 50)
print(f"  Surface humidity  |  Sample: {SAMPLE_ID}")
print(f"  Port: {PORT}  |  CSV: {CSV_FILE}")
print(f"  Send to DB: {SEND_TO_DB}")
print("  Stop: Ctrl+C")
print("=" * 50 + "\n")

ser    = serial.Serial(PORT, BAUD, timeout=2)
f      = init_csv()
writer = csv.writer(f)

try:
    while True:
        line = ser.readline().decode(errors="ignore").strip()
        if not line:
            continue

        parts = line.split(",")
        if len(parts) != 4:
            continue

        if parts[0].lower() in ("datetime", "time_ms", "millis"):
            continue

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            time_ms  = parts[0]
            temp     = float(parts[1])
            surf_hum = float(parts[2])
            pressure = float(parts[3])
        except ValueError:
            continue

        # Save to CSV (always) — no model_type column
        writer.writerow([now, SAMPLE_ID, time_ms, temp, surf_hum, pressure])
        f.flush()

        print(f"[{now}] Temp {temp}°C | Surface humidity {surf_hum}% | Pressure {pressure}hPa")

        send_surface(temp, surf_hum, pressure)

except KeyboardInterrupt:
    print("\nCollection stopped")
finally:
    f.close()
    ser.close()
