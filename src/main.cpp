/* PillPath ESP32 - PlatformIO firmware
   Reports a dispensing action. It does not prove medication ingestion.
   Set SERVER_URL to your computer's LAN address - never use localhost.
*/
#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

constexpr char WIFI_SSID[] = "Iphone13";
constexpr char WIFI_PASSWORD[] = "joinifyourafag";
// Laptop address while connected to the current iPhone hotspot.
constexpr char SERVER_URL[] = "http://172.20.10.11:3000";
constexpr char DEVICE_ID[] = "PILL-001";
constexpr int BUTTON_PIN = 18; // momentary button from GPIO 18 to GND
constexpr int STATUS_LED_PIN = 2; // onboard LED on common ESP32 DevKit boards
constexpr int TOP_STEP_PIN = 26, TOP_DIR_PIN = 27;
constexpr int LOWER_STEP_PIN = 32, LOWER_DIR_PIN = 33;
constexpr bool DEMO_WITHOUT_MOTORS = true; // set false only after connecting calibrated drivers
unsigned long lastHeartbeat = 0, lastPress = 0;
unsigned long lastWiFiAttempt = 0;
bool buttonWasDown = false;

void flashStatus(int flashes = 1) {
  for (int i = 0; i < flashes; i++) {
    digitalWrite(STATUS_LED_PIN, HIGH); delay(90);
    digitalWrite(STATUS_LED_PIN, LOW); delay(90);
  }
}

void stepMotor(int stepPin, int dirPin, int steps, bool forward = true) {
  digitalWrite(dirPin, forward);
  for (int i = 0; i < steps; i++) { digitalWrite(stepPin, HIGH); delayMicroseconds(800); digitalWrite(stepPin, LOW); delayMicroseconds(800); }
}
void runDispenseCycle() {
  if (DEMO_WITHOUT_MOTORS) { Serial.println("DEMO: dispense cycle accepted (motor outputs disabled)"); return; }
  // Calibrate counts to your mechanism: top aligns one pill with the base hole; lower advances one pocket.
  stepMotor(TOP_STEP_PIN, TOP_DIR_PIN, 200); delay(250);
  stepMotor(LOWER_STEP_PIN, LOWER_DIR_PIN, 100); delay(250);
}
bool postJson(const String& route, JsonDocument& document) {
  if (WiFi.status() != WL_CONNECTED) { Serial.println("SERVER: Wi-Fi is disconnected."); return false; }
  HTTPClient http; http.begin(String(SERVER_URL) + route); http.addHeader("Content-Type", "application/json");
  String text; serializeJson(document, text); int status = http.POST(text); http.end();
  Serial.printf("SERVER: POST %s returned HTTP %d\n", route.c_str(), status);
  return status >= 200 && status < 300;
}
void heartbeat() { Serial.println("STATUS: Sending heartbeat..."); JsonDocument doc; doc["deviceId"] = DEVICE_ID; doc["patient"] = "Margaret Wilson"; postJson("/api/device/heartbeat", doc); }
void startWiFi() {
  Serial.printf("WIFI: Trying network '%s'...\n", WIFI_SSID);
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  lastWiFiAttempt = millis();
}
String nextDoseId() {
  if (WiFi.status() != WL_CONNECTED) { Serial.println("SERVER: Cannot look up dose; Wi-Fi is disconnected."); return ""; }
  Serial.println("SERVER: Looking up next pending dose...");
  HTTPClient http; http.begin(String(SERVER_URL) + "/api/device/next-dose?deviceId=" + DEVICE_ID); int status = http.GET();
  if (status != 200) { Serial.printf("SERVER: Dose lookup failed (HTTP %d).\n", status); http.end(); return ""; } JsonDocument doc; deserializeJson(doc, http.getString()); http.end();
  return doc["dose"]["id"].is<const char*>() ? String(doc["dose"]["id"].as<const char*>()) : "";
}
void handleButton() {
  Serial.println("BUTTON: Press detected.");
  flashStatus();
  const String doseId = nextDoseId();
  if (doseId.isEmpty()) { Serial.println("DISPENSE: No pending dose. Motor not moved."); flashStatus(2); return; }
  Serial.printf("DISPENSE: Authorised dose is %s. Starting cycle...\n", doseId.c_str());
  runDispenseCycle(); // A production design should add optical/jam confirmation before recording success.
  JsonDocument doc; doc["deviceId"] = DEVICE_ID; doc["doseId"] = doseId;
  if (postJson("/api/device/dispense", doc)) { Serial.println("DISPENSE: Recorded successfully."); flashStatus(3); }
  else { Serial.println("DISPENSE: Could not be recorded - check Wi-Fi/server."); flashStatus(2); }
}
void setup() {
  Serial.begin(115200); pinMode(BUTTON_PIN, INPUT_PULLUP); pinMode(STATUS_LED_PIN, OUTPUT); digitalWrite(STATUS_LED_PIN, LOW); pinMode(TOP_STEP_PIN, OUTPUT); pinMode(TOP_DIR_PIN, OUTPUT); pinMode(LOWER_STEP_PIN, OUTPUT); pinMode(LOWER_DIR_PIN, OUTPUT);
  Serial.println("\nPillPath starting. Press the GPIO 18 button to request a dispense.");
  WiFi.mode(WIFI_STA); // ESP32 supports 2.4 GHz Wi-Fi only.
  startWiFi(); // Do not block: button and LED feedback still work while Wi-Fi reconnects.
}
void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    static bool wasConnected = false;
    if (!wasConnected) { Serial.printf("WIFI: Connected. IP: %s\n", WiFi.localIP().toString().c_str()); heartbeat(); wasConnected = true; }
    if (millis() - lastHeartbeat > 60000) { heartbeat(); lastHeartbeat = millis(); }
  } else if (millis() - lastWiFiAttempt > 10000) {
    Serial.println("WIFI: Not connected. Retrying in background; button demo remains available.");
    startWiFi();
  }
  const bool buttonDown = digitalRead(BUTTON_PIN) == LOW;
  if (buttonDown && !buttonWasDown && millis() - lastPress > 80) { lastPress = millis(); handleButton(); }
  if (!buttonDown && buttonWasDown) Serial.println("BUTTON: Released.");
  buttonWasDown = buttonDown;
}
