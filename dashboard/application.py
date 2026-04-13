import os
import json
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import boto3
from boto3.dynamodb.conditions import Key
from flask import Flask, render_template, jsonify, request

application = Flask(__name__)

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "MilitarySensorData")

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
table = dynamodb.Table(TABLE_NAME)


def decimal_default(obj):
    if isinstance(obj, Decimal):
        f = float(obj)
        return int(f) if f == int(f) else f
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

@application.route("/")
def dashboard():
    return render_template("index.html")


@application.route("/api/sensor-data")
def get_sensor_data():

    sensor_type = request.args.get("sensor_type", "thermal")
    limit = int(request.args.get("limit", 30))

    try:
        response = table.query(
            KeyConditionExpression=Key("sensor_type").eq(sensor_type),
            ScanIndexForward=False,  # newest first
            Limit=limit,
        )
        items = response.get("Items", [])
        items.reverse()  # oldest to newest for charts
        return json.dumps({"data": items}, default=decimal_default)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@application.route("/api/latest")
def get_latest():
    sensors = ["thermal", "motion", "gps", "acoustic"]
    latest = {}

    for s in sensors:
        try:
            resp = table.query(
                KeyConditionExpression=Key("sensor_type").eq(s),
                ScanIndexForward=False,
                Limit=1,
            )
            items = resp.get("Items", [])
            latest[s] = items[0] if items else None
        except Exception as e:
            latest[s] = {"error": str(e)}

    return json.dumps(latest, default=decimal_default)


@application.route("/api/health")
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()})

if __name__ == "__main__":
    application.run(host="0.0.0.0", port=8080, debug=True)
