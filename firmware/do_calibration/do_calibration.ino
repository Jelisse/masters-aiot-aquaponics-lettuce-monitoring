/* DFRobot Gravity DO (A1) + DS18B20 Water Temp Sensor
   UNO R4 WiFi friendly (sets 14-bit ADC if available)
   Serial commands:
     A -> capture AIR (100% sat) counts
     Z -> capture ZERO (0 mg/L) counts (optional)
     P -> print snippet to paste into code
*/

#include <Arduino.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// ----- USER CONFIG -----
#define DO_PIN      A1        // DFRobot DO analog pin
#define TEMP_PIN    2         // DS18B20 data pin (change as needed)
#define BAUDRATE    115200
// -----------------------

OneWire oneWire(TEMP_PIN);
DallasTemperature sensors(&oneWire);

// DFRobot's DO Table (oxygen solubility in water, [0..40 °C]) in µg/L
const uint16_t DO_Table[41] = {
  14460,14220,13820,13440,13090,12740,12420,12110,11810,11530,
  11260,11010,10770,10530,10300,10080,9860,9660,9460,9270,
  9080,8900,8730,8570,8410,8250,8110,7960,7820,7690,
  7560,7430,7300,7180,7070,6950,6840,6730,6630,6530,6410
};

// Global calibration values
long CAL_AIR_COUNTS = 0;
long CAL_ZERO_COUNTS = 0;

// Function to get DO saturation from table
float getDOSaturation_ugL(float tC) {
  int t = round(tC);
  if (t < 0) t = 0;
  if (t > 40) t = 40;
  return (float)DO_Table[t];
}

long readCountsAvg(uint16_t samples = 100, uint8_t delayMs = 5) {
  long sum = 0;
  for (uint16_t i = 0; i < samples; i++) {
    sum += analogRead(DO_PIN);
    delay(delayMs);
  }
  return sum / (long)samples;
}

void printHelp() {
  Serial.println(F("\nCommands:"));
  Serial.println(F("  A -> capture AIR counts (100% sat). Keep membrane moist in still air for 2-3 min then press A."));
  Serial.println(F("  Z -> capture ZERO counts (0 mg/L) in fresh Na2SO3 solution (optional)."));
  Serial.println(F("  P -> print snippet to paste into code."));
  Serial.println();
}

void setup() {
  Serial.begin(BAUDRATE);
  while (!Serial && millis() < 2000) {}
  sensors.begin();

  #if defined(ARDUINO_ARCH_RENESAS) || defined(ARDUINO_ARCH_SAMD) || defined(ARDUINO_ARCH_ESP32)
    analogReadResolution(14); // UNO R4 WiFi uses 14-bit ADC (0..16383)
  #endif

  pinMode(DO_PIN, INPUT);
  Serial.println(F("\n=== DFRobot DO sensor calibration (A1) + DS18B20 (pin 4) ==="));
  printHelp();
}

void loop() {
  if (Serial.available()) {
    char c = Serial.read();
    if (c == 'A' || c == 'a') {
      Serial.println(F("\n-- Capturing AIR (100% sat). Keep membrane moist in still air..."));
      delay(2000);
      CAL_AIR_COUNTS = readCountsAvg(200, 8);
      Serial.print(F("Captured AIR counts = ")); Serial.println(CAL_AIR_COUNTS);
    } else if (c == 'Z' || c == 'z') {
      Serial.println(F("\n-- Capturing ZERO (0 mg/L). Place in fresh Na2SO3 solution..."));
      delay(2000);
      CAL_ZERO_COUNTS = readCountsAvg(200, 8);
      Serial.print(F("Captured ZERO counts = ")); Serial.println(CAL_ZERO_COUNTS);
    } else if (c == 'P' || c == 'p') {
      Serial.println(F("\n// ---- Paste these into the top of your main sketch ----"));
      Serial.print(F("const long CAL_AIR_COUNTS = ")); Serial.print(CAL_AIR_COUNTS); Serial.println(F(";"));
      Serial.print(F("const long CAL_ZERO_COUNTS = ")); Serial.print(CAL_ZERO_COUNTS); Serial.println(F(";"));
      Serial.println(F("// -----------------------------------------------------\n"));
    } else {
      printHelp();
    }
  }

  // Read water temperature
  sensors.requestTemperatures();
  float tC = sensors.getTempCByIndex(0);
  if (tC == DEVICE_DISCONNECTED_C) {
    Serial.println(F("Warning: DS18B20 read failed. Check wiring."));
    delay(1200);
    return;
  }

  // Read DO analog counts (averaged)
  long counts = readCountsAvg(10, 6);

  // Compute DO mg/L only if AIR calibration available
  float DO_mgL = NAN;
  float percentSat = NAN;
  if (CAL_AIR_COUNTS > 0) {
    long zero = CAL_ZERO_COUNTS;
    long span = CAL_AIR_COUNTS - zero;
    if (span <= 0) span = 1;
    float sat_mgL = getDOSaturation_ugL(tC) / 1000.0;
    float delta = (float)(counts - zero);
    if (delta < 0) delta = 0;
    DO_mgL = delta * sat_mgL / (float)span;
    percentSat = (DO_mgL / sat_mgL) * 100.0;
  }

  // Print results
  Serial.print(F("Temp: ")); Serial.print(tC, 2); Serial.print(F(" °C  "));
  Serial.print(F("Counts: ")); Serial.print(counts);
  if (CAL_AIR_COUNTS > 0) {
    Serial.print(F("  DO: ")); Serial.print(DO_mgL, 2); Serial.print(F(" mg/L"));
    Serial.print(F("  (")); Serial.print(percentSat, 1); Serial.println(F("% sat)"));
  } else {
    Serial.println(F("  (press 'A' to capture AIR calibration)"));
  }

  delay(800);
}
