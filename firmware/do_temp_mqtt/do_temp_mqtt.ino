#include <Arduino.h>
#include <WiFiS3.h>
#include <ArduinoMqttClient.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include "arduino_secrets.h"  // <-- Ensure this file contains your WiFi & MQTT credentials

// --- WiFi Credentials ---
const char* ssid = SECRET_SSID;
const char* pass = SECRET_PASS;

// --- MQTT Broker Settings ---
const char* mqttBroker = SECRET_MQTT_BROKER;
const int mqttPort = SECRET_MQTT_PORT;
const char* mqttUsername = SECRET_MQTT_USERNAME;
const char* mqttPassword = SECRET_MQTT_PASSWORD;

// --- MQTT Topic ---
const char* doTopic = "test1/DO/Temp";

// --- Sensor Pin Definitions ---
#define DO_ANALOG_PIN A1
#define DS18B20_PIN   2  // Data pin for DS18B20 water temperature sensor

// --- ADC Settings ---
const int ADC_RESOLUTION_BITS = 14; // UNO R4 WiFi supports up to 14 bits (0–16383)

// --- Calibration Values (from calibration sketch 'P' command) ---
const long CAL_AIR_COUNTS = 6079;  // Replace with your measured air calibration
const long CAL_ZERO_COUNTS = 3633; // Replace with your measured zero calibration

// --- DFRobot DO Table (oxygen solubility in water, [0..40 °C]) ---
const uint16_t DO_Table[41] = {
  14460,14220,13820,13440,13090,12740,12420,12110,11810,11530,
  11260,11010,10770,10530,10300,10080,9860,9660,9460,9270,
  9080,8900,8730,8570,8410,8250,8110,7960,7820,7690,
  7560,7430,7300,7180,7070,6950,6840,6730,6630,6530,6410
};

// --- Global Variables ---
float currentTemperature_C = 0;
uint16_t adcRawReading = 0;
float doValue_mgL = 0;

// --- WiFi and MQTT ---
WiFiClient wifiClient;
MqttClient mqttClient(wifiClient);

// --- DS18B20 Setup ---
OneWire oneWire(DS18B20_PIN);
DallasTemperature sensors(&oneWire);

// --- Publish interval ---
const long publishInterval = 5000;
unsigned long lastPublishTime = 0;

/**
 * @brief Calculate DO (mg/L) using two-point calibration and temperature correction.
 */
float calculateDO_mgL(long counts, float temperature_c) {
  if (CAL_AIR_COUNTS <= CAL_ZERO_COUNTS) return -1; // invalid calibration

  int t = round(temperature_c);
  if (t < 0) t = 0;
  if (t > 40) t = 40;

  float sat_ugL = DO_Table[t];  // Oxygen solubility (µg/L)
  float do_mgL = (counts - CAL_ZERO_COUNTS) * ((sat_ugL / 1000.0) / (float)(CAL_AIR_COUNTS - CAL_ZERO_COUNTS));
  if (do_mgL < 0) do_mgL = 0;
  return do_mgL;
}

/**
 * @brief Read water temperature from DS18B20.
 */
float readTemperatureC_DS18B20() {
  sensors.requestTemperatures();
  float tC = sensors.getTempCByIndex(0);
  if (tC == DEVICE_DISCONNECTED_C) {
    Serial.println("DS18B20 read failed! Check wiring or pull-up resistor.");
    return currentTemperature_C > 0 ? currentTemperature_C : 25.0; // fallback to last or default
  }
  return tC;
}

/**
 * @brief Connect to WiFi.
 */
void connectToWiFi() {
  Serial.print("Connecting to SSID: ");
  Serial.println(ssid);
  while (WiFi.begin(ssid, pass) != WL_CONNECTED) {
    Serial.print(".");
    delay(500);
  }
  Serial.println("\nWiFi connected!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
}

/**
 * @brief Connect to MQTT broker.
 */
void connectToMqtt() {
  Serial.print("Connecting to MQTT broker: ");
  Serial.println(mqttBroker);

  if (strlen(mqttUsername) > 0) {
    mqttClient.setUsernamePassword(mqttUsername, mqttPassword);
  }

  while (!mqttClient.connect(mqttBroker, mqttPort)) {
    Serial.print("MQTT connect failed, code=");
    Serial.println(mqttClient.connectError());
    delay(2000);
  }
  Serial.println("Connected to MQTT broker!");
}

/**
 * @brief Setup function.
 */
void setup() {
  Serial.begin(115200);
  while (!Serial);

  analogReadResolution(ADC_RESOLUTION_BITS);

  sensors.begin();
  Serial.println("DS18B20 initialized.");

  if (WiFi.status() == WL_NO_MODULE) {
    Serial.println("No WiFi module detected!");
    while (true);
  }

  connectToWiFi();
  connectToMqtt();
}

/**
 * @brief Main loop.
 */
void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi lost. Reconnecting...");
    connectToWiFi();
  }

  if (!mqttClient.connected()) {
    Serial.println("MQTT lost. Reconnecting...");
    connectToMqtt();
  }

  mqttClient.poll();

  unsigned long currentMillis = millis();
  if (currentMillis - lastPublishTime >= publishInterval) {
    lastPublishTime = currentMillis;

    // --- Read sensors ---
    currentTemperature_C = readTemperatureC_DS18B20();
    adcRawReading = analogRead(DO_ANALOG_PIN);
    doValue_mgL = calculateDO_mgL(adcRawReading, currentTemperature_C);

    // --- Debug print ---
    Serial.print("Temp: "); Serial.print(currentTemperature_C, 2); Serial.print(" °C\t");
    Serial.print("ADC: "); Serial.print(adcRawReading); Serial.print("\t");
    Serial.print("DO: "); Serial.print(doValue_mgL, 2); Serial.println(" mg/L");

    // --- MQTT Payload ---
    String payload = "{";
    payload += "\"temperature_C\": " + String(currentTemperature_C, 2) + ",";
    payload += "\"do_mgL\": " + String(doValue_mgL, 2) + ",";
    payload += "\"raw_adc\": " + String(adcRawReading);
    payload += "}";

    mqttClient.beginMessage(doTopic);
    mqttClient.print(payload);
    if (mqttClient.endMessage()) {
      Serial.println("MQTT Publish OK");
    } else {
      Serial.println("MQTT Publish Failed!");
    }
  }
}
