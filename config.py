import os

# AWS IoT Core Settings
ENDPOINT = "a1qoqkxc51qy4e-ats.iot.us-east-1.amazonaws.com"
AWS_REGION = "us-east-1"

# IoT Thing Client IDs 
SENSOR_CLIENT_ID = "military-sensor-sim"
EDGE_CLIENT_ID = "military-edge-node"
FOG_CLIENT_ID = "military-fog-node"

# Certificate Paths 
SENSOR_CERT = "certs/sensor-certificate.pem.crt"
SENSOR_KEY = "certs/sensor-private.pem.key"
SENSOR_CA = "certs/AmazonRootCA1.pem"

EDGE_CERT = "certs/edge-certificate.pem.crt"
EDGE_KEY = "certs/edge-private.pem.key"
EDGE_CA = "certs/AmazonRootCA1.pem"

FOG_CERT = "certs/fog-certificate.pem.crt"
FOG_KEY = "certs/fog-private.pem.key"
FOG_CA = "certs/AmazonRootCA1.pem"

#  MQTT Topics 
RAW_TOPIC_PREFIX = "military/raw"
RAW_THERMAL = f"{RAW_TOPIC_PREFIX}/thermal"
RAW_MOTION = f"{RAW_TOPIC_PREFIX}/motion"
RAW_GPS = f"{RAW_TOPIC_PREFIX}/gps"
RAW_ACOUSTIC = f"{RAW_TOPIC_PREFIX}/acoustic"

# Edge-processed data published by the edge layer
EDGE_TOPIC_PREFIX = "military/edge"
EDGE_THERMAL = f"{EDGE_TOPIC_PREFIX}/thermal"
EDGE_MOTION = f"{EDGE_TOPIC_PREFIX}/motion"
EDGE_GPS = f"{EDGE_TOPIC_PREFIX}/gps"
EDGE_ACOUSTIC = f"{EDGE_TOPIC_PREFIX}/acoustic"

# Fog-processed aggregated data
FOG_TOPIC = "military/fog/processed"

PUBLISH_INTERVAL = 10  # seconds between each sensor reading

# DynamoDB
DYNAMODB_TABLE = "MilitarySensorData"

# Sensor Ranges
THERMAL_RANGE = (-40.0, 80.0)       # Celsius
MOTION_VELOCITY_RANGE = (0.0, 50.0) # m/s
GPS_LAT_RANGE = (52.0, 56.0)        # Ireland latitude bounds
GPS_LON_RANGE = (-11.0, -5.0)       # Ireland longitude bounds
ACOUSTIC_DB_RANGE = (0.0, 160.0)    # Decibels

# SQS Queue 
SQS_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/875936663120/MilitarySensorQueue"

# API Gateway
API_GATEWAY_URL = "https://o34gmgxw3i.execute-api.us-east-1.amazonaws.com/production"