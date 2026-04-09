import json, time, sys
from datetime import datetime, timezone
from collections import defaultdict
from awscrt import io, mqtt
from awsiot import mqtt_connection_builder
import config

io.init_logging(getattr(io.LogLevel, "Error"), "stderr")
ALPHA = 0.3
ema_state = defaultdict(lambda: None)

def ema(key, val):
    p = ema_state[key]
    if p is None: ema_state[key] = val; return val
    s = round(ALPHA * val + (1 - ALPHA) * p, 4); ema_state[key] = s; return s

def proc_thermal(r):
    t=r.get("temperature_c",0); ir=r.get("ir_intensity",0)
    if not (config.THERMAL_RANGE[0]<=t<=config.THERMAL_RANGE[1]): return None
    a=ir>70.0
    return {"sensor":"thermal","device_id":r["device_id"],"timestamp":r["timestamp"],"processed_at":datetime.now(timezone.utc).isoformat(),"layer":"edge","raw_temperature_c":t,"smoothed_temperature_c":ema("t_t",t),"raw_ir_intensity":ir,"smoothed_ir_intensity":ema("t_ir",ir),"heat_signature":r.get("heat_signature",False),"anomaly":a,"anomaly_reason":"High IR intensity detected" if a else "None"}

def proc_motion(r):
    v=r.get("velocity_ms",0)
    if not (config.MOTION_VELOCITY_RANGE[0]<=v<=config.MOTION_VELOCITY_RANGE[1]): return None
    d=r.get("motion_detected",False)
    if d and v<0.3: d=False; v=0.0
    tl="HIGH" if v>8 else "MEDIUM" if v>3 else "LOW" if d else "NONE"
    return {"sensor":"motion","device_id":r["device_id"],"timestamp":r["timestamp"],"processed_at":datetime.now(timezone.utc).isoformat(),"layer":"edge","motion_detected":d,"velocity_ms":round(v,2),"direction_deg":r.get("direction_deg",0),"threat_level":tl,"anomaly":tl=="HIGH","anomaly_reason":"Fast-moving object detected" if tl=="HIGH" else "None"}

def proc_gps(r):
    lat=r.get("latitude",0); lon=r.get("longitude",0)
    iz=config.GPS_LAT_RANGE[0]<=lat<=config.GPS_LAT_RANGE[1] and config.GPS_LON_RANGE[0]<=lon<=config.GPS_LON_RANGE[1]
    return {"sensor":"gps","device_id":r["device_id"],"timestamp":r["timestamp"],"processed_at":datetime.now(timezone.utc).isoformat(),"layer":"edge","latitude":lat,"longitude":lon,"altitude_m":ema("g_a",r.get("altitude_m",0)),"speed_kmh":r.get("speed_kmh",0),"in_zone":iz,"anomaly":not iz,"anomaly_reason":"Position outside operational zone" if not iz else "None"}

def proc_acoustic(r):
    db=r.get("decibel_level",0); cl=r.get("classification","ambient")
    if not (config.ACOUSTIC_DB_RANGE[0]<=db<=config.ACOUSTIC_DB_RANGE[1]): return None
    if db<20: cl="ambient"
    a=cl in {"gunshot","aircraft"}
    return {"sensor":"acoustic","device_id":r["device_id"],"timestamp":r["timestamp"],"processed_at":datetime.now(timezone.utc).isoformat(),"layer":"edge","raw_decibel_level":db,"smoothed_decibel_level":ema("a_db",db),"frequency_hz":r.get("frequency_hz",0),"classification":cl,"anomaly":a,"anomaly_reason":"Threat sound: "+cl if a else "None"}

TOPIC_MAP = {config.RAW_THERMAL:(proc_thermal,config.EDGE_THERMAL),config.RAW_MOTION:(proc_motion,config.EDGE_MOTION),config.RAW_GPS:(proc_gps,config.EDGE_GPS),config.RAW_ACOUSTIC:(proc_acoustic,config.EDGE_ACOUSTIC)}

print("[EDGE] Connecting...", flush=True)
conn = mqtt_connection_builder.mtls_from_path(
    endpoint=config.ENDPOINT, cert_filepath=config.EDGE_CERT,
    pri_key_filepath=config.EDGE_KEY, ca_filepath=config.EDGE_CA,
    client_id="edge-proc-node", clean_session=True, keep_alive_secs=60)
conn.connect().result()
print("[EDGE] Connected to AWS IoT Core", flush=True)

def handler(topic, payload, **kwargs):
    try:
        t=str(topic); r=json.loads(payload)
        if t not in TOPIC_MAP: return
        fn,out=TOPIC_MAP[t]; p=fn(r)
        if p is None: return
        conn.publish(topic=out, payload=json.dumps(p), qos=mqtt.QoS.AT_MOST_ONCE)
        a=" *** ANOMALY ***" if p.get("anomaly") else ""
        print(f"  [EDGE] {p['sensor'].upper()} -> {out}{a}", flush=True)
    except Exception as e:
        print(f"  [EDGE] ERR: {e}", flush=True)

conn.subscribe(topic="military/raw/#", qos=mqtt.QoS.AT_MOST_ONCE, callback=handler)[0].result()
print("[EDGE] Subscribed to military/raw/#", flush=True)
print("[EDGE] Waiting for sensor data... Ctrl+C to stop\n", flush=True)

try:
    while True: time.sleep(1)
except KeyboardInterrupt:
    print("\n[EDGE] Stopped.")