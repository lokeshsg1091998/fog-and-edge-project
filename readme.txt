================================================================================
  MILITARY IoT SENSOR NETWORK — SETUP & INSTALLATION GUIDE
  Fog and Edge Computing (H9FECC) — CA Project
================================================================================

PROJECT OVERVIEW
----------------
This project implements a 3-layer military IoT surveillance architecture:

  Layer 1 — EDGE (sensor_simulator.py)
    Simulates 4 military sensors (thermal, motion, GPS, acoustic).
    Publishes raw JSON payloads to AWS IoT Core via MQTT every 10 seconds.

  Layer 2 — EDGE PROCESSING (edge_layer.py)
    Subscribes to raw sensor topics from Layer 1.
    Performs real-time filtering: range validation, noise smoothing (EMA),
    and anomaly flagging. Publishes cleaned data on separate MQTT topics.

  Layer 3 — FOG (fog_layer.py)
    Subscribes to edge-processed topics from Layer 2.
    Performs higher-level aggregation: rolling-window averages,
    cross-sensor correlation, threat classification.
    Stores results in Amazon DynamoDB.

  Cloud Backend — Dashboard (dashboard/)
    Flask web application deployed on AWS Elastic Beanstalk.
    Reads from DynamoDB and renders a real-time military command dashboard
    with live sensor cards, line charts, and event logging.


MQTT DATA FLOW
--------------
  sensor_simulator.py  --(publishes)--> military/raw/{sensor_type}
          |
  edge_layer.py        --(subscribes)-- military/raw/#
          |                --(publishes)--> military/edge/{sensor_type}
          |
  fog_layer.py         --(subscribes)-- military/edge/#
          |                --(publishes)--> military/fog/processed
          |                --(writes)-----> DynamoDB: MilitarySensorData
          |
  Dashboard (EBS)      --(reads)-------> DynamoDB: MilitarySensorData


FILE STRUCTURE
--------------
  military-iot-project/
  |-- config.py                  Shared settings (endpoint, topics, certs)
  |-- sensor_simulator.py        Edge/IoT layer — raw sensor data generator
  |-- edge_layer.py              Edge processing — filtering & validation
  |-- fog_layer.py               Fog layer — aggregation & DynamoDB storage
  |-- MilitarySensorPolicy.json  IoT policy template
  |-- requirements.txt           Python dependencies for sensor scripts
  |-- certs/                     AWS IoT certificates (you add these)
  |-- dashboard/
      |-- application.py         Flask app (EBS entry point)
      |-- requirements.txt       Dashboard dependencies
      |-- templates/
      |   |-- index.html         Military-themed dashboard UI
      |-- .ebextensions/
          |-- 01_env.config      EBS environment configuration


================================================================================
  STEP-BY-STEP SETUP INSTRUCTIONS
================================================================================


STEP 1 — OPEN AWS CLOUD9 IDE
-----------------------------
1.  Log in to AWS Academy Learner Lab. Click "Start Lab". Wait for the
    green circle. Click "AWS" to open the Management Console.

2.  In the console search bar, type "Cloud9" and open the Cloud9 service.

3.  Click "Create environment".
      - Name: military-iot-project
      - Instance type: t3.small (or t2.micro if budget is tight)
      - Platform: Amazon Linux 2023
      - Timeout: 4 hours
      - Connection: AWS Systems Manager (SSM)
    Click "Create".

4.  Wait 2-3 minutes. Click "Open" next to your new environment.

5.  In the Cloud9 terminal, verify Python:
      python3 --version
    Expected output: Python 3.9+ (any 3.x version is fine).


STEP 2 — UPLOAD PROJECT FILES TO CLOUD9
----------------------------------------
1.  In Cloud9, go to File menu → Upload Local Files.

2.  Upload all the project files. Or use the terminal:
      mkdir ~/environment/military-iot-project
      cd ~/environment/military-iot-project

3.  Create the directory structure:
      mkdir -p certs dashboard/templates dashboard/.ebextensions

4.  Copy each file to the correct location (or drag-and-drop in Cloud9
    file tree). Final structure should match FILE STRUCTURE above.


STEP 3 — INSTALL PYTHON DEPENDENCIES
-------------------------------------
1.  In the Cloud9 terminal:
      cd ~/environment/military-iot-project

2.  Create a virtual environment:
      python3 -m venv venv
      source venv/bin/activate

3.  Upgrade pip:
      pip install --upgrade pip

4.  Install the sensor/edge/fog dependencies:
      pip install -r requirements.txt

5.  Verify installation:
      python3 -c "from awscrt import mqtt; print('awsiotsdk OK')"
      python3 -c "import boto3; print('boto3 OK')"


STEP 4 — ENABLE AWS IoT CORE
-----------------------------
1.  In the AWS Management Console, search for "IoT Core" and open it.

2.  If it is your first time, you will see a "Get started" page. Click it.
    IoT Core does not require any special enabling — it is available
    by default in your account.

3.  On the left sidebar, check you can see:
      - Manage → All devices → Things
      - Security → Policies
      - Test → MQTT test client
      - Settings (at the very bottom of the sidebar)

4.  Click "Settings" (bottom of left sidebar). Copy your "Device data
    endpoint". It looks like:
      a1b2c3d4e5f6g7-ats.iot.us-east-1.amazonaws.com
    You will paste this into config.py in the next step.


STEP 5 — CREATE THREE IoT THINGS
---------------------------------
You need 3 separate things (one per layer) each with its own certificate.

THING 1: military-sensor-sim
.............................
1.  IoT Core → Manage → All devices → Things → "Create things".
2.  Select "Create single thing" → Next.
3.  Thing name: military-sensor-sim
4.  Leave all other fields as default → Next.
5.  Auto-generate a new certificate (recommended) → Next.
6.  Skip policy for now → "Create thing".
7.  IMPORTANT: A download dialog appears. Download ALL 5 files:
      - xxxxxxxxxx-certificate.pem.crt
      - xxxxxxxxxx-private.pem.key
      - xxxxxxxxxx-public.pem.key
      - AmazonRootCA1.pem
      - AmazonRootCA3.pem
8.  Rename the certificate and key files for clarity:
      sensor-certificate.pem.crt
      sensor-private.pem.key
9.  Upload these to the certs/ folder in Cloud9.

THING 2: military-edge-node
............................
10. Repeat steps 1-8 with thing name: military-edge-node
11. Rename downloaded files:
      edge-certificate.pem.crt
      edge-private.pem.key
12. Upload to certs/ in Cloud9. (Reuse the same AmazonRootCA1.pem.)

THING 3: military-fog-node
...........................
13. Repeat steps 1-8 with thing name: military-fog-node
14. Rename downloaded files:
      fog-certificate.pem.crt
      fog-private.pem.key
15. Upload to certs/ in Cloud9.

After this step, your certs/ folder should contain:
  certs/
  |-- sensor-certificate.pem.crt
  |-- sensor-private.pem.key
  |-- edge-certificate.pem.crt
  |-- edge-private.pem.key
  |-- fog-certificate.pem.crt
  |-- fog-private.pem.key
  |-- AmazonRootCA1.pem


STEP 6 — CREATE AND ATTACH IoT POLICY
--------------------------------------
1.  IoT Core → Security → Policies → "Create policy".
2.  Policy name: MilitarySensorPolicy
3.  Click "JSON" view in the policy editor.
4.  Open MilitarySensorPolicy.json from the project files. Copy its content.
5.  Paste it into the editor.
6.  Replace YOUR_ACCOUNT_ID with your actual AWS account ID.
    To find your account ID:
      - Look at the top-right of the console (Account ID: 1234-5678-9012)
      - Or run in Cloud9 terminal: aws sts get-caller-identity --query Account --output text
    Remove dashes from the number if any.
7.  Click "Create".

8.  Now attach this policy to ALL THREE things' certificates:
    For EACH thing (military-sensor-sim, military-edge-node, military-fog-node):
      a. IoT Core → Manage → Things → click the thing name
      b. Click the "Certificates" tab
      c. Click the certificate ID (long hex string)
      d. Click the "Policies" tab
      e. Click "Attach policies"
      f. Select "MilitarySensorPolicy" → "Attach policies"


STEP 7 — UPDATE config.py
--------------------------
1.  Open config.py in Cloud9.

2.  Replace the ENDPOINT value with your endpoint from Step 4:
      ENDPOINT = "a1b2c3d4e5f6g7-ats.iot.us-east-1.amazonaws.com"

3.  Verify the certificate filenames match what you saved in certs/:
      SENSOR_CERT = "certs/sensor-certificate.pem.crt"
      SENSOR_KEY  = "certs/sensor-private.pem.key"
      (same for EDGE and FOG paths)

4.  Save the file.


STEP 8 — CREATE DYNAMODB TABLE
-------------------------------
1.  In the AWS Console, search for "DynamoDB" and open it.

2.  Click "Create table".
      - Table name: MilitarySensorData
      - Partition key: sensor_type (String)
      - Sort key: timestamp (String)
      - Table settings: Default settings
    Click "Create table".

3.  Wait until the status shows "Active" (about 30 seconds).

4.  Verify the table exists in Cloud9 terminal:
      aws dynamodb describe-table --table-name MilitarySensorData --query "Table.TableStatus"
    Expected output: "ACTIVE"


STEP 9 — TEST THE FULL PIPELINE
--------------------------------
You will open 3 terminal tabs in Cloud9 and run each layer separately.

TERMINAL 1 — Fog Layer (start this FIRST so it is ready to receive)
.....................................................................
1.  In Cloud9, click the "+" icon next to the terminal tab → New Terminal.
2.  Run:
      cd ~/environment/military-iot-project
      source venv/bin/activate
      python3 fog_layer.py

3.  You should see:
      [FOG] Building MQTT connection...
      [FOG] Connecting to AWS IoT Core...
      [FOG] Connected successfully.
      [FOG] Subscribing to edge-processed topics...
      [FOG] Fog layer is running. Waiting for edge data...

TERMINAL 2 — Edge Layer (start this SECOND)
............................................
4.  Open another terminal tab.
5.  Run:
      cd ~/environment/military-iot-project
      source venv/bin/activate
      python3 edge_layer.py

6.  You should see:
      [EDGE] Edge layer is running. Waiting for sensor data...

TERMINAL 3 — Sensor Simulator (start this LAST)
................................................
7.  Open another terminal tab.
8.  Run:
      cd ~/environment/military-iot-project
      source venv/bin/activate
      python3 sensor_simulator.py

9.  You should see data publishing every 10 seconds:
      [SIMULATOR] Publishing 4 sensors every 10s
      [12:00:00] Publishing batch ──────────────────
        -> military/raw/thermal: {"sensor":"thermal",...}
        -> military/raw/motion: ...
        -> military/raw/gps: ...
        -> military/raw/acoustic: ...

10. Switch to Terminal 2 (edge). You should see processing logs:
      [EDGE] THERMAL → military/edge/thermal
      [EDGE] MOTION → military/edge/motion
      [EDGE] GPS → military/edge/gps
      [EDGE] ACOUSTIC → military/edge/acoustic

11. Switch to Terminal 1 (fog). You should see storage logs:
      [FOG] THERMAL stored & aggregated (window=1)
      [FOG] MOTION stored & aggregated (window=1)
      ...

12. Verify data landed in DynamoDB. In the AWS Console:
      DynamoDB → Tables → MilitarySensorData → "Explore table items"
    You should see records appearing.

13. Also verify in IoT Core MQTT test client:
      IoT Core → Test → MQTT test client
      Subscribe to topic: military/#
    You should see messages flowing.


STEP 10 — DEPLOY DASHBOARD TO ELASTIC BEANSTALK
-------------------------------------------------
1.  In the AWS Console, search for "Elastic Beanstalk" and open it.

2.  If this is your first time, click "Create application".
    Otherwise click "Create environment".

3.  Fill in:
      - Application name: military-dashboard
      - Environment name: military-dashboard-env
      - Platform: Python
      - Platform branch: Python 3.9 running on 64bit Amazon Linux 2023
        (or the latest available)
      - Platform version: latest

4.  Under "Application code", select "Upload your code".

5.  First, create a zip of the dashboard folder. In Cloud9 terminal:
      cd ~/environment/military-iot-project/dashboard
      zip -r ~/environment/dashboard-deploy.zip . -x ".*"

6.  Download the zip: In Cloud9, right-click dashboard-deploy.zip
    in the file tree → Download.

7.  Back in the Elastic Beanstalk console, click "Choose file" and
    upload dashboard-deploy.zip.

8.  Click "Configure more options" (or scroll to see presets).

9.  IMPORTANT — IAM Role for DynamoDB access:
      Under "Security", make sure the instance profile/role has
      DynamoDB read permissions. In Learner Lab, the default
      LabInstanceProfile usually has sufficient permissions. If not:
        a. Go to IAM → Roles → find the EB instance role
        b. Attach the policy: AmazonDynamoDBReadOnlyAccess

10. Click "Create environment". Wait 5-8 minutes for deployment.

11. Once the health shows "Ok" (green), click the environment URL
    (something like: http://military-dashboard-env.us-east-1.elasticbeanstalk.com).

12. You should see the Military Sensor Command Dashboard with
    live data updating every 10 seconds.


ALTERNATIVE: Deploy via EB CLI in Cloud9
........................................
If you prefer command-line deployment:

1.  Install the EB CLI:
      pip install awsebcli

2.  Initialise:
      cd ~/environment/military-iot-project/dashboard
      eb init -p python-3.9 military-dashboard --region us-east-1

3.  Create and deploy:
      eb create military-dashboard-env

4.  Open in browser:
      eb open


STEP 11 — VERIFY EVERYTHING END-TO-END
---------------------------------------
1.  Make sure all 3 Python scripts are running in Cloud9 terminals
    (sensor_simulator.py, edge_layer.py, fog_layer.py).

2.  Open the Elastic Beanstalk dashboard URL in a browser.

3.  Confirm:
    [ ] Sensor cards show live values and update every 10 seconds
    [ ] Line charts show historical data points
    [ ] Anomaly events appear in the event log (red entries)
    [ ] Start/Stop button pauses and resumes the dashboard
    [ ] Individual sensor toggles enable/disable each sensor
    [ ] Auto-refresh toggle switches between 10s auto and manual

4.  In DynamoDB → Explore table items, confirm new records are
    being added continuously.

5.  In IoT Core → MQTT test client, subscribe to military/# and
    confirm messages from all three layers.


================================================================================
  HOW IT WORKS — EXPLANATION FOR YOUR LECTURER
================================================================================

HOW MQTT AUTO-GENERATES VALUES:
  The sensor_simulator.py script uses Python's random module to produce
  realistic sensor readings (Gaussian distributions for temperature,
  weighted random choices for acoustic classifications, GPS drift etc.).
  Every 10 seconds it publishes 4 JSON payloads — one per sensor — to
  AWS IoT Core via MQTT using mutual TLS authentication. The "auto
  generation" is a timed loop: time.sleep(10) followed by publish().

EDGE LAYER PROCESSING:
  edge_layer.py subscribes to the raw topics. When a message arrives,
  the callback function runs the appropriate processor:
    - Range validation: discard readings outside physical limits
    - Noise smoothing: exponential moving average (EMA) on numeric values
    - Anomaly flagging: threshold checks (e.g. IR > 70 = heat signature)
  The cleaned payload is republished to a separate topic.

FOG LAYER PROCESSING:
  fog_layer.py subscribes to the edge-processed topics. It maintains
  a rolling buffer (deque of size 6) per sensor. On each message:
    - The reading is added to the buffer
    - Aggregation is computed over the window (averages, max, counts)
    - Both the individual reading and the aggregation are stored in
      DynamoDB as a single record
  This demonstrates fog-level intelligence: aggregation, correlation,
  and persistent storage closer to the cloud.


================================================================================
  TROUBLESHOOTING
================================================================================

PROBLEM: "Connection refused" or timeout when running scripts
  - Check that the ENDPOINT in config.py matches your IoT Core endpoint.
  - Check that certificate filenames in config.py match actual filenames
    in the certs/ folder.
  - Ensure the policy is attached to ALL three certificates.

PROBLEM: "Access denied" or "not authorized"
  - The IoT policy may not be attached. Go to IoT Core → Security →
    Certificates → click your cert → Policies → Attach policies.
  - Make sure YOUR_ACCOUNT_ID is replaced in MilitarySensorPolicy.json.

PROBLEM: No data in DynamoDB
  - Check that the fog_layer.py terminal shows "stored & aggregated".
  - Verify the table name in DynamoDB matches config.py (MilitarySensorData).
  - If using Learner Lab, ensure the lab session is still active (green).

PROBLEM: Dashboard shows "--" for all values
  - Make sure all 3 scripts are running.
  - Wait at least 10 seconds for the first batch of data.
  - Check the browser console (F12) for API errors.
  - Make sure the EBS instance role has DynamoDB read permissions.

PROBLEM: Cloud9 terminal disconnects
  - Increase the idle timeout: Cloud9 → Preferences → AWS Settings →
    set auto-hibernation to 4 hours.
  - Consider running scripts with 'nohup' to survive disconnects:
      nohup python3 fog_layer.py > fog.log 2>&1 &

================================================================================
