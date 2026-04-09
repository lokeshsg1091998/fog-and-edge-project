"""
sensor_simulator.py — Edge / IoT Device Layer
Simulates four military-grade sensors and publishes raw readings
to AWS IoT Core via MQTT every PUBLISH_INTERVAL seconds.

Sensors:
  1. Thermal  — infrared temperature and heat-signature detection
  2. Motion   — PIR velocity and direction
  3. GPS      — latitude, longitude, altitude, speed
  4. Acoustic — decibel level, frequency, sound classification

Each sensor publishes on its own MQTT topic under military/raw/<type>.
"""

import time
import json
import math
import random
from datetime import datetime, timezone
from awscrt import io, mqtt
from awsiot import mqtt_connection_builder
import config

# ─── Logging (minimal in production, change to Debug for testing) ─
io.init_logging(getattr(io.LogLevel, "Fatal"), "stderr")

# ─── MQTT Connection Setup ────────────────────────────────────────
print("[SIMULATOR] Building MQTT connection...")
connection = mqtt_connection_builder.mtls_from_path(
    endpoint=config.ENDPOINT,
    cert_filepath=config.SENSOR_CERT,
    pri_key_filepath=config.SENSOR_KEY,
    ca_filepath=config.SENSOR_CA,
    client_id=config.SENSOR_CLIENT_ID,
    clean_session=True,
    keep_alive_secs=60,
)

print("[SIMULATOR] Connecting to AWS IoT Core...")
connect_future = connection.connect()
connect_future.result()
print("[SIMULATOR] Connected successfully.\n")

# ─── Stateful variables for realistic GPS drift ──────────────────
gps_lat = 53.3498    # Dublin starting coordinates
gps_lon = -6.2603
gps_alt = 45.0

# ─── Sensor Data Generators ──────────────────────────────────────

def generate_thermal():
    """Produce a raw thermal / IR reading."""
    ambient = round(random.gauss(22.0, 4.0), 2)
    heat_sig = random.random() < 0.25  # 25% chance of heat signature
    ir_intensity = round(random.uniform(60.0, 95.0) if heat_sig
                         else random.uniform(5.0, 40.0), 2)
    return {
        "sensor": "thermal",
        "device_id": config.SENSOR_CLIENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature_c": ambient,
        "heat_signature": heat_sig,
        "ir_intensity": ir_intensity,
    }


def generate_motion():
    """Produce a raw motion / PIR reading."""
    detected = random.random() < 0.30  # 30% chance of motion
    velocity = round(random.uniform(0.5, 12.0), 2) if detected else 0.0
    direction = round(random.uniform(0.0, 360.0), 1) if detected else 0.0
    return {
        "sensor": "motion",
        "device_id": config.SENSOR_CLIENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "motion_detected": detected,
        "velocity_ms": velocity,
        "direction_deg": direction,
    }


def generate_gps():
    """Produce a raw GPS fix with realistic drift."""
    global gps_lat, gps_lon, gps_alt
    gps_lat += random.gauss(0, 0.0003)
    gps_lon += random.gauss(0, 0.0003)
    gps_alt += random.gauss(0, 0.5)
    speed = round(random.uniform(0.0, 25.0), 2)
    return {
        "sensor": "gps",
        "device_id": config.SENSOR_CLIENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "latitude": round(gps_lat, 6),
        "longitude": round(gps_lon, 6),
        "altitude_m": round(gps_alt, 2),
        "speed_kmh": speed,
    }


def generate_acoustic():
    """Produce a raw acoustic reading with sound classification."""
    classifications = ["ambient", "footstep", "vehicle", "gunshot", "aircraft"]
    weights = [0.40, 0.25, 0.20, 0.05, 0.10]
    sound_class = random.choices(classifications, weights=weights, k=1)[0]

    db_map = {
        "ambient":  (10, 35),
        "footstep": (25, 55),
        "vehicle":  (55, 90),
        "gunshot":  (120, 150),
        "aircraft": (80, 115),
    }
    lo, hi = db_map[sound_class]
    decibels = round(random.uniform(lo, hi), 1)
    frequency = round(random.uniform(20.0, 8000.0), 1)

    return {
        "sensor": "acoustic",
        "device_id": config.SENSOR_CLIENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "decibel_level": decibels,
        "frequency_hz": frequency,
        "classification": sound_class,
    }


# ─── Topic Map ────────────────────────────────────────────────────
GENERATORS = {
    config.RAW_THERMAL:  generate_thermal,
    config.RAW_MOTION:   generate_motion,
    config.RAW_GPS:      generate_gps,
    config.RAW_ACOUSTIC: generate_acoustic,
}

# ─── Publishing Loop ─────────────────────────────────────────────

def publish_all():
    """Generate and publish one reading per sensor type."""
    for topic, gen_func in GENERATORS.items():
        payload = gen_func()
        msg = json.dumps(payload)
        future, _ = connection.publish(
            topic=topic, payload=msg, qos=mqtt.QoS.AT_LEAST_ONCE
        )
        future.result()
        print(f"  -> {topic}: {msg[:120]}")


if __name__ == "__main__":
    print(f"[SIMULATOR] Publishing 4 sensors every {config.PUBLISH_INTERVAL}s")
    print("[SIMULATOR] Press Ctrl+C to stop\n")
    try:
        while True:
            ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
            print(f"[{ts}] Publishing batch ──────────────────")
            publish_all()
            time.sleep(config.PUBLISH_INTERVAL)
    except KeyboardInterrupt:
        print("\n[SIMULATOR] Stopping...")
    finally:
        print("[SIMULATOR] Disconnecting...")
        try:
            connection.disconnect().result()
            print("[SIMULATOR] Disconnected.")
        except Exception as e:
            print(f"[SIMULATOR] Disconnect error: {e}")
