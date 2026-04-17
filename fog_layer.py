import json, time, sys, boto3
from datetime import datetime, timezone
from collections import deque
from awscrt import io, mqtt
from awsiot import mqtt_connection_builder
import config

io.init_logging(getattr(io.LogLevel, "Error"), "stderr")

sqs = boto3.client("sqs", region_name=config.AWS_REGION)
SQS_QUEUE_URL = config.SQS_QUEUE_URL

WINDOW = 6
bufs = {"thermal":deque(maxlen=WINDOW),"motion":deque(maxlen=WINDOW),"gps":deque(maxlen=WINDOW),"acoustic":deque(maxlen=WINDOW)}

def agg_thermal(b):
    ts=[r["smoothed_temperature_c"] for r in b]; irs=[r["smoothed_ir_intensity"] for r in b]
    return {"avg_temperature_c":round(sum(ts)/len(ts),2),"avg_ir_intensity":round(sum(irs)/len(irs),2),"max_ir_intensity":round(max(irs),2),"anomaly_count":sum(1 for r in b if r.get("anomaly")),"window_size":len(b)}

def agg_motion(b):
    det=sum(1 for r in b if r.get("motion_detected")); vs=[r["velocity_ms"] for r in b if r.get("motion_detected")]
    av=round(sum(vs)/len(vs),2) if vs else 0.0; thr=[r.get("threat_level","NONE") for r in b]
    mt="HIGH" if "HIGH" in thr else "MEDIUM" if "MEDIUM" in thr else "LOW" if "LOW" in thr else "NONE"
    return {"detection_rate":round(det/len(b),2),"avg_velocity_ms":av,"max_threat_level":mt,"detections_in_window":det,"window_size":len(b)}

def agg_gps(b):
    la=[r["latitude"] for r in b]; lo=[r["longitude"] for r in b]; sp=[r["speed_kmh"] for r in b]
    return {"avg_latitude":round(sum(la)/len(la),6),"avg_longitude":round(sum(lo)/len(lo),6),"avg_speed_kmh":round(sum(sp)/len(sp),2),"max_speed_kmh":round(max(sp),2),"all_in_zone":all(r.get("in_zone",True) for r in b),"window_size":len(b)}

def agg_acoustic(b):
    ds=[r["smoothed_decibel_level"] for r in b]
    return {"avg_decibel_level":round(sum(ds)/len(ds),2),"max_decibel_level":round(max(ds),2),"threat_sound_count":sum(1 for r in b if r.get("anomaly")),"classifications":list(set(r.get("classification","ambient") for r in b)),"window_size":len(b)}

AGGS={"thermal":agg_thermal,"motion":agg_motion,"gps":agg_gps,"acoustic":agg_acoustic}

print("[FOG] Connecting...", flush=True)
conn = mqtt_connection_builder.mtls_from_path(
    endpoint=config.ENDPOINT, cert_filepath=config.FOG_CERT,
    pri_key_filepath=config.FOG_KEY, ca_filepath=config.FOG_CA,
    client_id="fog-proc-node", clean_session=True, keep_alive_secs=60)
conn.connect().result()
print(f"[FOG] Connected. SQS: {SQS_QUEUE_URL}", flush=True)

def handler(topic, payload, **kwargs):
    try:
        d=json.loads(payload); s=d.get("sensor","unknown")
        if s not in bufs: return
        bufs[s].append(d)
        ag=AGGS[s](bufs[s])
        message = {"sensor":s,"timestamp":d["timestamp"],"device_id":d.get("device_id","unknown"),
                   "processed_at":d.get("processed_at",""),"fog_processed_at":datetime.now(timezone.utc).isoformat(),
                   "layer":"fog","edge_data":d,"aggregation":ag,"anomaly":d.get("anomaly",False)}
        sqs.send_message(QueueUrl=SQS_QUEUE_URL, MessageBody=json.dumps(message, default=str))
        conn.publish(topic=config.FOG_TOPIC, payload=json.dumps(message, default=str), qos=mqtt.QoS.AT_MOST_ONCE)
        a=" *** ANOMALY ***" if d.get("anomaly") else ""
        print(f"  [FOG] {s.upper()} -> SQS (window={ag.get('window_size',0)}){a}", flush=True)
    except Exception as e:
        print(f"  [FOG] ERR: {e}", flush=True)

conn.subscribe(topic="military/edge/#", qos=mqtt.QoS.AT_MOST_ONCE, callback=handler)[0].result()
print("[FOG] Subscribed to military/edge/#", flush=True)
print("[FOG] Waiting for edge data... Ctrl+C to stop\n", flush=True)

try:
    while True: time.sleep(1)
except KeyboardInterrupt:
    print("\n[FOG] Stopped.")