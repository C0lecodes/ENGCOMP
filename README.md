# PillPath — Dispenser Demonstration

PillPath is a local demonstration portal for the UC Engineering Challenge. It manages a small fleet of ESP32 pill dispensers, provides a care-team dashboard, maintains a dose history, alerts when a dose remains **undispensed** for 30 minutes, and alerts when medication stock reaches its refill threshold.

## Run the Portal

Requires Python 3.10+ and uses only the Python standard library.

From the project directory, run:

```sh
python3 server.py
```

Then open:

```text
http://localhost:3000
```

Press **Reset demo** to return to the initial demonstration data.

To demonstrate a missed-dose alert, add a dose with a scheduled time more than 30 minutes in the past.

## Demonstrate with an ESP32

### 1. Open the project

Open the project folder in VS Code and install the **PlatformIO IDE** extension if it is not already installed.

### 2. Configure the ESP32

Open:

```text
src/main.cpp
```

Set the Wi-Fi credentials for your network.

Then change `SERVER_URL` to the IP address of the computer running the PillPath server. For example:

```cpp
#define SERVER_URL "http://192.156.1.100:3000"
```

The computer and ESP32 must be connected to the same local network.

### 3. Connect and upload

Attach a momentary button between **GPIO 18** and **GND**.

In PlatformIO:

1. Select **Upload** to upload the firmware.
2. Select **Monitor** to open the serial monitor.
3. Press the button to trigger a demonstration dispense.

### 4. Demonstration mode

`DEMO_WITHOUT_MOTORS` is set to `true` by default.

This allows the ESP32 to be demonstrated without motor hardware connected. When the button is pressed, the ESP32:

1. Requests the next pending dose.
2. Simulates the dispensing cycle.
3. Records the dispense with the PillPath server.
4. Decreases the medication stock.

## Hardware Mapping and Safety

The PlatformIO firmware reserves the following GPIO pins for the motor drivers:

| GPIO    | Function               |
| ------- | ---------------------- |
| GPIO 26 | Top barrel step        |
| GPIO 27 | Top barrel direction   |
| GPIO 32 | Lower barrel step      |
| GPIO 33 | Lower barrel direction |

Set:

```cpp
DEMO_WITHOUT_MOTORS
```

to `false` only after the motor hardware has been connected and the `stepMotor` counts have been calibrated for the final mechanical gearing.

For a physical prototype, add appropriate end stops and/or jam detection before operating the mechanism unattended.

### Important limitation

PillPath records a **device dispensing action**. It does not verify that a person actually received or swallowed a medication.

This project is a demonstration prototype and must not be used for clinical decisions or real medication management without appropriate security, authentication, encrypted communication, audit controls, privacy review, and validated hardware and sensors.

## API Endpoints

### `POST /api/device/heartbeat`

Updates the connection status of an ESP32 dispenser.

### `POST /api/device/dispense`

Records a pending dose as dispensed and decreases the corresponding medication stock.

### `GET /api/dashboard`

Returns dashboard data and evaluates the current alerts.

## Data Storage

Persistent demonstration data is stored in:

```text
data.json
```

The file is created automatically when the server first saves data.

## Project Structure

A typical project structure is:

```text
PillPath/
├── server.py
├── data.json
├── src/
│   └── main.cpp
└── ...
```

`data.json` is generated automatically and does not need to be created manually.
