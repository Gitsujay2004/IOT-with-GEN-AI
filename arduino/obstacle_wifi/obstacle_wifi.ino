//Library Section

#include <WiFi.h>
#include <HTTPClient.h>

//Wifi Configuration

const char* WIFI_SSID  = "wifi-name";
const char* WIFI_PASS  = "wifi-password";
const char* SERVER_URL = "http://local ip address(ipv4)/api/sensor";

// ultrasonic pins

const int TRIG_PIN = 5;
const int ECHO_PIN = 18;

//distance configuration

const int  MIN_VALID_CM     = 2;
const int  MAX_RANGE_CM     = 200;
const int  CLEAR_PATH_VALUE = 999;
const unsigned long ECHO_TIMEOUT_US = 25000UL;
const int  SAMPLES          = 3;
const unsigned long SEND_INTERVAL_MS = 250;  //approximately every 250 milliseconds, the latest processed distance is sent to the backend
const unsigned long WIFI_TIMEOUT_MS  = 20000;   

WiFiClient wifiClient;
HTTPClient http; 
unsigned long lastSend = 0;

//distance measurement

long readDistanceOnce() {
  digitalWrite(TRIG_PIN, LOW);  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH); delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  unsigned long duration = pulseIn(ECHO_PIN, HIGH, ECHO_TIMEOUT_US);
  if (duration == 0) return 0;
  return (long)(duration * 0.0343 / 2.0);  //Distance = Time × Speed of Sound ÷ 2
}

//Filtering the Distance

//three readings are taken instead of using only one reading

long readDistanceFiltered() {                 
  long r[SAMPLES];
  for (int i = 0; i < SAMPLES; i++) { r[i] = readDistanceOnce(); delay(10); }
  for (int i = 0; i < SAMPLES - 1; i++)
    for (int j = i + 1; j < SAMPLES; j++)
      if (r[j] < r[i]) { long t = r[i]; r[i] = r[j]; r[j] = t; }
  return r[SAMPLES / 2];
}

//Processing the Distance


int processDistance(long d) {
  if (d <= MIN_VALID_CM || d > MAX_RANGE_CM) return CLEAR_PATH_VALUE;
  return (int)d;
}

// ---------- Wi-Fi ----------
void onWiFiEvent(WiFiEvent_t event, WiFiEventInfo_t info) {
  if (event == ARDUINO_EVENT_WIFI_STA_DISCONNECTED) {
    Serial.println("  [disconnect reason " + String(info.wifi_sta_disconnected.reason) + "]");
  }
}

void connectWiFi() {
  WiFi.disconnect(true, true);      // reset any previous attempt
  delay(500);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);

  // Scan first, so we can see if the network is visible at all
  Serial.println("Scanning networks...");
  int n = WiFi.scanNetworks();
  bool found = false;
  for (int i = 0; i < n; i++) {
    Serial.println("  " + WiFi.SSID(i) + "  (" + String(WiFi.RSSI(i)) +
                   " dBm, ch " + String(WiFi.channel(i)) + ")");
    if (WiFi.SSID(i) == String(WIFI_SSID)) found = true;
  }
  WiFi.scanDelete();
  if (n <= 0)      Serial.println("No networks seen at all (antenna or power problem)");
  else if (!found) Serial.println("'" + String(WIFI_SSID) + "' is NOT visible (5 GHz, hidden, out of range, or name typo)");

  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting to Wi-Fi");
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < WIFI_TIMEOUT_MS) {
    delay(500); Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nConnected. ESP32 IP: " + WiFi.localIP().toString());
    Serial.println("Sending data to: " + String(SERVER_URL));
  } else {
    Serial.println("\nFailed. Status code = " + String(WiFi.status()));
    WiFi.disconnect();
    delay(3000);
  }
}

// ---------- Send to FastAPI ----------

void sendDistance(int dist) {
  http.begin(wifiClient, SERVER_URL);
  http.setTimeout(1500);
  http.addHeader("Content-Type", "application/json");
  int code = http.POST("{\"distance\":" + String(dist) + "}");

  String line = "distance=" + String(dist) + "  HTTP=" + String(code);
  if (code < 0) line += "  (" + http.errorToString(code) + ")";
  Serial.println(line);
  http.end();
}

void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  WiFi.onEvent(onWiFiEvent);
  connectWiFi();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) { connectWiFi(); return; }
  if (millis() - lastSend >= SEND_INTERVAL_MS) {
    lastSend = millis();
    sendDistance(processDistance(readDistanceFiltered()));
  }
}