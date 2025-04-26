/*
 * ESP32 Facial Recognition Attendance Tracker
 * Main program file
 */

// Include necessary libraries
#include <Wire.h>
#include <SPI.h>
#include <MFRC522.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <ESP32Servo.h>
#include <WiFi.h>
#include <DNSServer.h>
#include <WebServer.h>
#include <SPIFFS.h>
#include <ArduinoJson.h>
#include <RTClib.h>
#include "esp_camera.h"
#include "esp_http_server.h"
#include "esp_timer.h"
#include "img_converters.h"
#include "fb_gfx.h"
#include "driver/ledc.h"

// Include custom header files
#include "../include/facial_recognition.h"
#include "../include/rfid_reader.h"
#include "../include/attendance.h"
#include "../include/web_server.h"
#include "../include/display.h"
#include "../include/rtc.h"
#include "../include/door_control.h"

// Pin definitions
// ESP32 GPIO pins
#define BUZZER_PIN 12
#define SERVO_PIN 13

// RFID module pins
#define RFID_RST_PIN 22
#define RFID_SS_PIN  21

// OLED display pins
#define OLED_SDA 4
#define OLED_SCL 5
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

// Camera pins are defined in camera_config

// ESP32-CAM camera pins
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       19
#define Y4_GPIO_NUM       18
#define Y3_GPIO_NUM        5
#define Y2_GPIO_NUM        4
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// Initialize components
MFRC522 rfid(RFID_SS_PIN, RFID_RST_PIN);
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
Servo doorServo;
RTC_DS3231 rtc;
WebServer server(80);
DNSServer dnsServer;

// WiFi credentials
const char* ssid = "ESP32-Attendance";
const char* password = "attendancetracker";

// Time settings
const int classStartHour = 8;  // 8:00 AM
const int classStartMinute = 0;
const int lateThresholdMinutes = 15;  // Students arriving 15+ minutes late are marked as late
const int absentThresholdMinutes = 30;  // Students arriving 30+ minutes late are marked as absent
const int lockDoorHour = 17;   // 5:00 PM - lock door
const int endAttendanceHour = 9;  // Stop taking attendance at 9:00 AM

// Variables
bool isCameraInitialized = false;
bool isRtcInitialized = false;
bool isDoorLocked = false;
unsigned long lastDisplayUpdate = 0;
const unsigned long displayUpdateInterval = 5000;  // Update display every 5 seconds

void setup() {
  // Initialize serial communication
  Serial.begin(115200);
  Serial.println("Starting ESP32 Attendance System");
  
  // Initialize I2C bus
  Wire.begin(OLED_SDA, OLED_SCL);
  
  // Initialize SPIFFS
  if (!SPIFFS.begin(true)) {
    Serial.println("SPIFFS initialization failed!");
  } else {
    Serial.println("SPIFFS initialized successfully");
  }

  // Initialize display
  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("SSD1306 allocation failed");
  } else {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(WHITE);
    display.setCursor(0, 0);
    display.println("Initializing...");
    display.display();
    Serial.println("OLED initialized");
  }
  
  // Initialize RTC
  if (!rtc.begin()) {
    Serial.println("RTC initialization failed!");
  } else {
    isRtcInitialized = true;
    // Set RTC time if it's not running or lost power
    if (rtc.lostPower()) {
      Serial.println("RTC lost power, setting default time!");
      rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
    }
    Serial.println("RTC initialized");
  }
  
  // Initialize SPI bus and RFID reader
  SPI.begin();
  rfid.PCD_Init();
  Serial.println("RFID reader initialized");
  
  // Initialize servo motor
  doorServo.attach(SERVO_PIN);
  unlockDoor(); // Start with door unlocked
  Serial.println("Servo initialized");
  
  // Initialize buzzer
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  Serial.println("Buzzer initialized");
  
  // Initialize camera
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  
  // Configure camera image settings
  config.frame_size = FRAMESIZE_VGA;
  config.jpeg_quality = 12;
  config.fb_count = 1;
  
  // Initialize the camera
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera initialization failed with error 0x%x", err);
  } else {
    isCameraInitialized = true;
    Serial.println("Camera initialized successfully");
  }
  
  // Initialize WiFi in AP mode for the captive portal
  WiFi.softAP(ssid, password);
  Serial.println("WiFi AP started");
  Serial.print("IP address: ");
  Serial.println(WiFi.softAPIP());
  
  // Initialize DNS server for captive portal
  dnsServer.start(53, "*", WiFi.softAPIP());
  
  // Initialize web server
  setupWebServer();
  
  // Initialize attendance database
  initAttendanceDB();
  
  // Sound buzzer to indicate system is ready
  beep(1);
  
  // Show welcome message on display
  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("System Ready");
  display.println("Waiting for users");
  display.display();
  
  Serial.println("Setup complete");
}

void loop() {
  // Handle captive portal DNS and web server
  dnsServer.processNextRequest();
  server.handleClient();
  
  // Get current time from RTC
  DateTime now;
  if (isRtcInitialized) {
    now = rtc.now();
  }
  
  // Check if it's time to lock the door
  if (isRtcInitialized && !isDoorLocked && now.hour() >= lockDoorHour) {
    lockDoor();
    isDoorLocked = true;
    Serial.println("Door locked for the day");
    beep(2);
  }
  
  // Check if we should still take attendance
  bool takeAttendance = true;
  if (isRtcInitialized && now.hour() >= endAttendanceHour) {
    takeAttendance = false;
  }
  
  // Process facial recognition if camera is working and we're still taking attendance
  if (isCameraInitialized && takeAttendance) {
    String recognizedPerson = recognizeFace();
    if (recognizedPerson != "") {
      processAttendance(recognizedPerson, "FACE");
    }
  }
  
  // Check for RFID card if we're still taking attendance
  if (takeAttendance && rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
    String cardID = getCardIDString();
    String user = getUserByRFID(cardID);
    if (user != "") {
      processAttendance(user, "RFID");
    } else {
      // Unknown card
      Serial.println("Unknown RFID card detected");
      display.clearDisplay();
      display.setCursor(0, 0);
      display.println("Unknown Card");
      display.println("Please register");
      display.display();
      beep(3); // 3 beeps for unknown card
    }
    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
  }
  
  // Update display with current status periodically
  if (millis() - lastDisplayUpdate > displayUpdateInterval) {
    updateDisplay(now);
    lastDisplayUpdate = millis();
  }
  
  delay(100); // Small delay to prevent CPU hogging
}

// Get RFID card ID as a string
String getCardIDString() {
  String cardID = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    cardID += (rfid.uid.uidByte[i] < 0x10 ? "0" : "");
    cardID += String(rfid.uid.uidByte[i], HEX);
  }
  cardID.toUpperCase();
  return cardID;
}

// Update the OLED display with current status
void updateDisplay(DateTime now) {
  display.clearDisplay();
  display.setCursor(0, 0);
  
  // Show current time
  if (isRtcInitialized) {
    display.print(now.year(), DEC);
    display.print('/');
    display.print(now.month(), DEC);
    display.print('/');
    display.print(now.day(), DEC);
    display.print(' ');
    display.print(now.hour(), DEC);
    display.print(':');
    if (now.minute() < 10) display.print('0');
    display.print(now.minute(), DEC);
    display.print(':');
    if (now.second() < 10) display.print('0');
    display.println(now.second(), DEC);
  } else {
    display.println("RTC not available");
  }
  
  // Show attendance status
  display.println("Attendance Status:");
  display.print("Present: ");
  display.println(getPresentCount());
  display.print("Late: ");
  display.println(getLateCount());
  display.print("Absent: ");
  display.println(getAbsentCount());
  
  display.display();
}

// Sound the buzzer
void beep(int times) {
  for (int i = 0; i < times; i++) {
    digitalWrite(BUZZER_PIN, HIGH);
    delay(200);
    digitalWrite(BUZZER_PIN, LOW);
    if (i < times - 1) {
      delay(200);
    }
  }
}

// Lock the door using servo motor
void lockDoor() {
  doorServo.write(0); // Adjust angle as needed for your setup
  Serial.println("Door locked");
}

// Unlock the door using servo motor
void unlockDoor() {
  doorServo.write(90); // Adjust angle as needed for your setup
  Serial.println("Door unlocked");
} 