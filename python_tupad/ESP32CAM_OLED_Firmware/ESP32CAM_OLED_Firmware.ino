#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "esp_http_server.h"
#include <SPI.h>
#include <MFRC522.h>
#include "esp_task_wdt.h" // Watchdog timer support
#include "esp_system.h"   // For system reset reason
#include <EEPROM.h>       // Add EEPROM library

// Disable watchdog by default - we'll only use it selectively
// #define WDT_TIMEOUT 20

// Global flag to indicate if RFID scanning is in progress
volatile bool rfid_scan_in_progress = false;

// Forward declarations
struct RfidCard;
struct RfidCard *findCardByUid(byte *uid, byte uidLength);
bool addNewCard(byte *uid, byte uidLength, const char *name);
bool handleRfidAttendance();

// Stream related constants
#define PART_BOUNDARY "123456789000000000000987654321"
static const char *_STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char *_STREAM_BOUNDARY = "\r\n--" PART_BOUNDARY "\r\n";
static const char *_STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

// Network identification
#define DEVICE_NAME "ESP32-CAM-Face-Recognition"
#define AP_SSID "ESP32-CAM-Face-Recognition"
#define AP_PASSWORD "12345678"

// Buzzer pin
#define BUZZER_PIN 2     // GPIO2 (built-in LED pin can be used for buzzer)
#define BUZZER_CHANNEL 0 // Use ledc channel 0

// JPEG encoding structure and function
typedef struct
{
    httpd_req_t *req;
    size_t len;
} jpg_chunking_t;

static size_t jpg_encode_stream(void *arg, size_t index, const void *data, size_t len)
{
    jpg_chunking_t *j = (jpg_chunking_t *)arg;
    if (!index)
    {
        j->len = 0;
    }
    if (httpd_resp_send_chunk(j->req, (const char *)data, len) != ESP_OK)
    {
        return 0;
    }
    j->len += len;
    return len;
}

// ===================
// Select camera model
// ===================
// #define CAMERA_MODEL_WROVER_KIT
// #define CAMERA_MODEL_ESP_EYE
// #define CAMERA_MODEL_M5STACK_PSRAM
// #define CAMERA_MODEL_M5STACK_V2_PSRAM
// #define CAMERA_MODEL_M5STACK_WIDE
// #define CAMERA_MODEL_M5STACK_ESP32CAM
// #define CAMERA_MODEL_M5STACK_UNITCAM
#define CAMERA_MODEL_AI_THINKER
// #define CAMERA_MODEL_TTGO_T_JOURNAL

#include "camera_pins.h"

// ===========================
// Enter your WiFi credentials
// ===========================
const char *ssid = "BATMAN HEADQUARTERS 2";
const char *password = "ETHANRANCE1213.";

// ===================
// OLED Display Setup
// ===================
#define SCREEN_WIDTH 128    // OLED display width, in pixels
#define SCREEN_HEIGHT 64    // OLED display height, in pixels
#define OLED_RESET -1       // Reset pin # (or -1 if sharing Arduino reset pin)
#define SCREEN_ADDRESS 0x3C // I2C address for most SSD1306 displays

// Define I2C pins for ESP32-CAM
#define I2C_SDA 14 // GPIO 14
#define I2C_SCL 15 // GPIO 15

// ===================
// RFID Reader Setup
// ===================
#define RFID_SS_PIN 13   // SDA pin connected to GPIO13
#define RFID_RST_PIN 3   // RST pin connected to GPIO3 (was GPIO4, which conflicts with white LED)
#define RFID_SCK_PIN 12  // SCK pin connected to GPIO12
#define RFID_MOSI_PIN 14 // MOSI pin - shared with I2C_SDA
#define RFID_MISO_PIN 15 // MISO pin - shared with I2C_SCL

MFRC522 rfid(RFID_SS_PIN, RFID_RST_PIN); // Create MFRC522 instance

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

WebServer server(80);

// Camera server implementation
httpd_handle_t camera_httpd = NULL;

// EEPROM configuration
#define EEPROM_SIZE 1024           // Size of EEPROM to use
#define EEPROM_START_ADDR 0        // Starting address for RFID data
#define EEPROM_MAGIC_NUMBER 0xAA55 // Magic number to verify valid data

// RFID Card structure with EEPROM support
struct RfidCard
{
    byte uid[4];   // UID of the RFID card
    char name[32]; // Name of the student
    bool active;   // Whether the card is active
};

// Array of known RFID cards
#define MAX_CARDS 10
struct RfidCard knownCards[MAX_CARDS];
int numKnownCards = 0;

// Flag to track if RFID has been properly initialized
bool rfid_initialized = false;

// Function to save RFID cards to EEPROM
bool saveRfidCardsToEEPROM()
{
    Serial.println("Saving RFID cards to EEPROM...");

    // Write magic number
    EEPROM.write(EEPROM_START_ADDR, (EEPROM_MAGIC_NUMBER >> 8) & 0xFF);
    EEPROM.write(EEPROM_START_ADDR + 1, EEPROM_MAGIC_NUMBER & 0xFF);

    // Write number of cards
    EEPROM.write(EEPROM_START_ADDR + 2, numKnownCards);

    // Write each card
    int addr = EEPROM_START_ADDR + 3;
    for (int i = 0; i < numKnownCards; i++)
    {
        // Write UID
        for (int j = 0; j < 4; j++)
        {
            EEPROM.write(addr++, knownCards[i].uid[j]);
        }

        // Write name (32 bytes)
        for (int j = 0; j < 32; j++)
        {
            EEPROM.write(addr++, knownCards[i].name[j]);
        }

        // Write active status
        EEPROM.write(addr++, knownCards[i].active ? 1 : 0);
    }

    // Commit changes
    bool success = EEPROM.commit();
    if (success)
    {
        Serial.println("RFID cards saved successfully");
    }
    else
    {
        Serial.println("Failed to save RFID cards");
    }
    return success;
}

// Function to load RFID cards from EEPROM
bool loadRfidCardsFromEEPROM()
{
    Serial.println("Loading RFID cards from EEPROM...");

    // Check magic number
    uint16_t magic = (EEPROM.read(EEPROM_START_ADDR) << 8) | EEPROM.read(EEPROM_START_ADDR + 1);
    if (magic != EEPROM_MAGIC_NUMBER)
    {
        Serial.println("No valid RFID data found in EEPROM");
        return false;
    }

    // Read number of cards
    numKnownCards = EEPROM.read(EEPROM_START_ADDR + 2);
    if (numKnownCards > MAX_CARDS)
    {
        Serial.println("Invalid number of cards in EEPROM");
        return false;
    }

    // Read each card
    int addr = EEPROM_START_ADDR + 3;
    for (int i = 0; i < numKnownCards; i++)
    {
        // Read UID
        for (int j = 0; j < 4; j++)
        {
            knownCards[i].uid[j] = EEPROM.read(addr++);
        }

        // Read name (32 bytes)
        for (int j = 0; j < 32; j++)
        {
            knownCards[i].name[j] = EEPROM.read(addr++);
        }

        // Read active status
        knownCards[i].active = EEPROM.read(addr++) == 1;

        // Print loaded card info
        Serial.print("Loaded card: ");
        Serial.print(knownCards[i].name);
        Serial.print(" (UID: ");
        for (int j = 0; j < 4; j++)
        {
            Serial.print(knownCards[i].uid[j] < 0x10 ? "0" : "");
            Serial.print(knownCards[i].uid[j], HEX);
            Serial.print(" ");
        }
        Serial.println(")");
    }

    Serial.printf("Loaded %d RFID cards from EEPROM\n", numKnownCards);
    return true;
}

// Function to safely initialize RFID
bool initRFID()
{
    Serial.println("Safe RFID Initialization...");

    // Already initialized? Skip.
    if (rfid_initialized)
    {
        Serial.println("RFID already initialized");
        return true;
    }

    // Temporarily suspend I2C to avoid conflicts
    Wire.end();
    delay(100); // Longer delay for stability

    // Set up SPI pins manually
    pinMode(RFID_SS_PIN, OUTPUT);
    pinMode(RFID_RST_PIN, OUTPUT);
    pinMode(RFID_SCK_PIN, OUTPUT);
    pinMode(RFID_MOSI_PIN, OUTPUT);
    pinMode(RFID_MISO_PIN, INPUT);

    // Manual reset sequence for better reliability
    digitalWrite(RFID_SS_PIN, HIGH);  // Deselect
    digitalWrite(RFID_RST_PIN, LOW);  // Reset the module
    delay(100);                       // Longer delay
    digitalWrite(RFID_RST_PIN, HIGH); // Release reset
    delay(100);                       // Longer delay

    // Initialize SPI at very low speed for stability
    SPI.begin(RFID_SCK_PIN, RFID_MISO_PIN, RFID_MOSI_PIN, RFID_SS_PIN);
    SPI.setFrequency(50000); // Super-low speed - 50kHz
    SPI.setDataMode(SPI_MODE0);

    // Try to initialize RFID with retries
    int retryCount = 0;
    const int maxRetries = 3;
    bool initSuccess = false;

    while (retryCount < maxRetries && !initSuccess)
    {
        Serial.printf("RFID init attempt %d/%d\n", retryCount + 1, maxRetries);

        rfid.PCD_Init();
        delay(200); // Longer delay between attempts

        // Check for working reader
        byte v = rfid.PCD_ReadRegister(MFRC522::VersionReg);
        if (v != 0x00 && v != 0xFF)
        {
            Serial.println("RFID init successful! Version: 0x" + String(v, HEX));
            initSuccess = true;
            break;
        }

        Serial.println("RFID init failed, retrying...");
        retryCount++;
        delay(200); // Delay before retry
    }

    if (!initSuccess)
    {
        Serial.println("RFID Init failed after all retries!");

        // Cleanup - shutdown SPI
        SPI.end();

        // Restart I2C for OLED
        Wire.begin(I2C_SDA, I2C_SCL);
        return false;
    }

    // Set antenna gain to maximum
    rfid.PCD_ClearRegisterBitMask(MFRC522::RFCfgReg, (0x07 << 4));
    rfid.PCD_SetRegisterBitMask(MFRC522::RFCfgReg, (0x07 << 4));

    // Initialization successful
    rfid_initialized = true;

    // Restart I2C for OLED
    SPI.end();  // End SPI first
    delay(100); // Longer delay
    Wire.begin(I2C_SDA, I2C_SCL);

    return true;
}

// Function to safely shutdown RFID
void deinitRFID()
{
    if (!rfid_initialized)
        return;

    Serial.println("Deinitializing RFID");
    rfid.PCD_AntennaOff();
    rfid.PCD_SoftPowerDown();
    SPI.end();
    rfid_initialized = false;

    // Reset pins to input mode
    pinMode(RFID_SS_PIN, INPUT);
    pinMode(RFID_RST_PIN, INPUT);
    pinMode(RFID_SCK_PIN, INPUT);
    pinMode(RFID_MOSI_PIN, INPUT);
    // MISO already input

    // Ensure I2C is running
    Wire.begin(I2C_SDA, I2C_SCL);
}

// Function to check if a card UID matches a known card
struct RfidCard *findCardByUid(byte *uid, byte uidLength)
{
    if (!uid || uidLength == 0)
    {
        Serial.println("Invalid UID in findCardByUid");
        return NULL;
    }

    Serial.print("Searching for card with UID: ");
    for (byte i = 0; i < uidLength; i++)
    {
        Serial.print(uid[i] < 0x10 ? " 0" : " ");
        Serial.print(uid[i], HEX);
    }
    Serial.println();

    for (int i = 0; i < numKnownCards; i++)
    {
        if (!knownCards[i].active)
        {
            continue;
        }

        bool match = true;
        for (byte j = 0; j < uidLength && j < 4; j++)
        {
            if (uid[j] != knownCards[i].uid[j])
            {
                match = false;
                break;
            }
        }
        if (match)
        {
            Serial.print("Found matching card for: ");
            Serial.println(knownCards[i].name);
            return &knownCards[i];
        }
    }

    Serial.println("No matching card found");
    return NULL;
}

// Update addNewCard function to save to EEPROM
bool addNewCard(byte *uid, byte uidLength, const char *name)
{
    if (!uid || uidLength == 0 || !name)
    {
        Serial.println("Invalid parameters in addNewCard");
        return false;
    }

    if (numKnownCards >= MAX_CARDS)
    {
        Serial.println("Cannot add more cards, array is full");
        return false;
    }

    // Check if card already exists
    if (findCardByUid(uid, uidLength) != NULL)
    {
        Serial.println("Card already exists");
        return false;
    }

    // Add new card
    for (byte i = 0; i < uidLength && i < 4; i++)
    {
        knownCards[numKnownCards].uid[i] = uid[i];
    }
    strncpy(knownCards[numKnownCards].name, name, 31);
    knownCards[numKnownCards].name[31] = '\0'; // Ensure null termination
    knownCards[numKnownCards].active = true;
    numKnownCards++;

    Serial.print("Added new card for: ");
    Serial.println(name);
    Serial.print("UID: ");
    for (byte i = 0; i < uidLength; i++)
    {
        Serial.print(uid[i] < 0x10 ? " 0" : " ");
        Serial.print(uid[i], HEX);
    }
    Serial.println();

    // Save to EEPROM
    return saveRfidCardsToEEPROM();
}

// Improved buzzer implementation with direct pin control and louder sound
void tone(int pin, int frequency, int duration)
{
    // Use manual pulse generation instead of ledc functions
    long toggleCount = frequency * duration / 1000;
    long halfPeriod = 500000 / frequency; // in microseconds

    pinMode(pin, OUTPUT);

    // Generate the tone manually with higher amplitude
    for (long i = 0; i < toggleCount; i++)
    {
        digitalWrite(pin, HIGH);
        delayMicroseconds(halfPeriod);
        digitalWrite(pin, LOW);
        delayMicroseconds(halfPeriod);
    }
}

void playPresentSound()
{
    Serial.println("Playing PRESENT sound");
    // Happy sound for present - two high beeps with higher frequency
    tone(BUZZER_PIN, 2500, 200); // Increased frequency and duration
    delay(100);
    tone(BUZZER_PIN, 2500, 200); // Increased frequency and duration
    Serial.println("PRESENT sound completed");
}

void playLateSound()
{
    Serial.println("Playing LATE sound");
    // Warning sound for late - one long and one short beep with higher frequency
    tone(BUZZER_PIN, 2000, 400); // Increased frequency and duration
    delay(100);
    tone(BUZZER_PIN, 2000, 150); // Increased frequency and duration
    Serial.println("LATE sound completed");
}

void playAbsentSound()
{
    Serial.println("Playing ABSENT sound");
    // Error sound for absent - three short beeps with higher frequency
    for (int i = 0; i < 3; i++)
    {
        tone(BUZZER_PIN, 1500, 100); // Increased frequency and duration
        delay(100);                  // Increased delay between beeps
    }
    Serial.println("ABSENT sound completed");
}

void testBuzzer()
{
    Serial.println("TESTING BUZZER - you should hear 3 different patterns");

    Serial.println("1. Present pattern:");
    playPresentSound();
    delay(500);

    Serial.println("2. Late pattern:");
    playLateSound();
    delay(500);

    Serial.println("3. Absent pattern:");
    playAbsentSound();

    Serial.println("Buzzer test complete");
}

static esp_err_t capture_handler(httpd_req_t *req)
{
    camera_fb_t *fb = NULL;
    esp_err_t res = ESP_OK;
    int64_t fr_start = esp_timer_get_time();

    fb = esp_camera_fb_get();
    if (!fb)
    {
        Serial.println("Camera capture failed");
        httpd_resp_send_500(req);
        return ESP_FAIL;
    }

    httpd_resp_set_type(req, "image/jpeg");
    httpd_resp_set_hdr(req, "Content-Disposition", "inline; filename=capture.jpg");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");

    size_t fb_len = 0;
    if (fb->format == PIXFORMAT_JPEG)
    {
        fb_len = fb->len;
        res = httpd_resp_send(req, (const char *)fb->buf, fb->len);
    }
    else
    {
        jpg_chunking_t jchunk = {req, 0};
        res = frame2jpg_cb(fb, 80, jpg_encode_stream, &jchunk) ? ESP_OK : ESP_FAIL;
        httpd_resp_send_chunk(req, NULL, 0);
        fb_len = jchunk.len;
    }
    esp_camera_fb_return(fb);
    int64_t fr_end = esp_timer_get_time();
    Serial.printf("JPG: %uB %ums\n", (uint32_t)(fb_len), (uint32_t)((fr_end - fr_start) / 1000));
    return res;
}

static esp_err_t stream_handler(httpd_req_t *req)
{
    camera_fb_t *fb = NULL;
    esp_err_t res = ESP_OK;
    size_t _jpg_buf_len = 0;
    uint8_t *_jpg_buf = NULL;
    char *part_buf[64];

    res = httpd_resp_set_type(req, _STREAM_CONTENT_TYPE);
    if (res != ESP_OK)
    {
        return res;
    }

    while (true)
    {
        // Check if RFID scanning is in progress
        if (rfid_scan_in_progress)
        {
            // Send a placeholder/notification image or delay
            delay(100); // Just delay briefly - could send a placeholder image
            continue;   // Skip this frame and check again
        }

        fb = esp_camera_fb_get();
        if (!fb)
        {
            Serial.println("Camera capture failed");
            res = ESP_FAIL;
        }
        else
        {
            if (fb->format != PIXFORMAT_JPEG)
            {
                bool jpeg_converted = frame2jpg(fb, 80, &_jpg_buf, &_jpg_buf_len);
                esp_camera_fb_return(fb);
                fb = NULL;
                if (!jpeg_converted)
                {
                    Serial.println("JPEG compression failed");
                    res = ESP_FAIL;
                }
            }
            else
            {
                _jpg_buf_len = fb->len;
                _jpg_buf = fb->buf;
            }
        }
        if (res == ESP_OK)
        {
            res = httpd_resp_send_chunk(req, (const char *)_jpg_buf, _jpg_buf_len);
        }
        if (res == ESP_OK)
        {
            res = httpd_resp_send_chunk(req, _STREAM_BOUNDARY, strlen(_STREAM_BOUNDARY));
        }
        if (res == ESP_OK)
        {
            size_t hlen = snprintf((char *)part_buf, 64, _STREAM_PART, _jpg_buf_len);
            res = httpd_resp_send_chunk(req, (const char *)part_buf, hlen);
        }
        if (fb)
        {
            esp_camera_fb_return(fb);
            fb = NULL;
            _jpg_buf = NULL;
        }
        else if (_jpg_buf)
        {
            free(_jpg_buf);
            _jpg_buf = NULL;
        }
        if (res != ESP_OK)
        {
            break;
        }
    }

    return res;
}

// Buzzer endpoint handler
static esp_err_t buzzer_handler(httpd_req_t *req)
{
    char buf[100];
    int ret = httpd_req_recv(req, buf, sizeof(buf) - 1);
    if (ret <= 0)
    {
        Serial.println("Error receiving data for buzzer");
        return ESP_FAIL;
    }

    buf[ret] = '\0';

    Serial.print("Buzzer request received: ");
    Serial.println(buf);

    // Parse JSON
    DynamicJsonDocument doc(256);
    DeserializationError error = deserializeJson(doc, buf);

    if (error)
    {
        Serial.println("Error parsing JSON for buzzer");
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "Invalid JSON format");
        return ESP_FAIL;
    }

    // Get status
    const char *status = doc["status"];
    Serial.printf("Buzzer status received: %s\n", status);

    if (strcmp(status, "present") == 0)
    {
        playPresentSound();
    }
    else if (strcmp(status, "late") == 0)
    {
        playLateSound();
    }
    else if (strcmp(status, "absent") == 0)
    {
        playAbsentSound();
    }
    else if (strcmp(status, "test") == 0)
    {
        // For testing - test all patterns
        Serial.println("Testing all buzzer patterns");
        testBuzzer();
    }
    else
    {
        // Unknown status
        Serial.println("Unknown status received");
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "Unknown status");
        return ESP_FAIL;
    }

    httpd_resp_send(req, "Buzzer sound played", HTTPD_RESP_USE_STRLEN);
    return ESP_OK;
}

// Handle RFID card detection for attendance
bool handleRfidAttendance()
{
    if (!rfid_initialized)
    {
        Serial.println("RFID not initialized for attendance");
        return false;
    }

    // Check if RFID reader detected a card
    if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial())
    {
        return false;
    }

    // Get card UID
    byte uidLength = rfid.uid.size;
    byte uid[10]; // Maximum UID size
    for (byte i = 0; i < uidLength; i++)
    {
        uid[i] = rfid.uid.uidByte[i];
    }

    // Print UID for debugging
    Serial.print("Card detected! UID: ");
    for (byte i = 0; i < uidLength; i++)
    {
        Serial.print(uid[i] < 0x10 ? " 0" : " ");
        Serial.print(uid[i], HEX);
    }
    Serial.println();

    // Find card in known cards
    Serial.println("Finding card in known cards");
    struct RfidCard *card = findCardByUid(uid, uidLength);
    if (card != NULL)
    {
        // Card found - mark attendance
        Serial.print("Recognized card for: ");
        Serial.println(card->name);

        // Display on OLED
        display.clearDisplay();
        display.setCursor(0, 0);
        display.println("RFID Attendance");
        display.println(card->name);
        display.println("Marked PRESENT");
        display.println(WiFi.localIP().toString());
        display.display();

        // Play success sound
        playPresentSound();

        rfid.PICC_HaltA();      // Halt PICC
        rfid.PCD_StopCrypto1(); // Stop encryption on PCD
        return true;
    }
    else
    {
        // Unknown card
        Serial.println("Unknown card");

        // Display on OLED
        display.clearDisplay();
        display.setCursor(0, 0);
        display.println("Unknown RFID Card");
        display.println("Card not registered");
        display.println("Please register first");
        display.display();

        // Play error sound
        playAbsentSound();

        rfid.PICC_HaltA();      // Halt PICC
        rfid.PCD_StopCrypto1(); // Stop encryption on PCD
        return false;
    }
}

// Add RFID endpoint for managing cards
static esp_err_t rfid_handler(httpd_req_t *req)
{
    char buf[1024];
    int ret = httpd_req_recv(req, buf, sizeof(buf) - 1);
    if (ret <= 0)
    {
        Serial.println("Error receiving data for RFID management");
        return ESP_FAIL;
    }

    buf[ret] = '\0';
    Serial.print("RFID management request received: ");
    Serial.println(buf);

    // Parse JSON
    DynamicJsonDocument doc(1024);
    DeserializationError error = deserializeJson(doc, buf);

    if (error)
    {
        Serial.println("Error parsing JSON for RFID management");
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "Invalid JSON format");
        return ESP_FAIL;
    }

    // Get action
    const char *action = doc["action"];
    if (!action)
    {
        Serial.println("No action specified");
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "No action specified");
        return ESP_FAIL;
    }

    // Handle different actions
    if (strcmp(action, "add") == 0)
    {
        // Add new card
        const char *name = doc["name"];
        JsonArray uidArray = doc["uid"];

        if (!name || uidArray.size() == 0)
        {
            Serial.println("Missing name or UID");
            httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "Missing name or UID");
            return ESP_FAIL;
        }

        byte uid[4];
        for (size_t i = 0; i < min((size_t)4, uidArray.size()); i++)
        {
            uid[i] = uidArray[i];
        }

        bool success = addNewCard(uid, min((size_t)4, uidArray.size()), name);

        if (success)
        {
            httpd_resp_send(req, "Card added successfully", HTTPD_RESP_USE_STRLEN);
            return ESP_OK;
        }
        else
        {
            httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "Failed to add card");
            return ESP_FAIL;
        }
    }
    else if (strcmp(action, "remove") == 0)
    {
        // Remove a card
        JsonArray uidArray = doc["uid"];
        if (uidArray.size() == 0)
        {
            Serial.println("Missing UID");
            httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "Missing UID");
            return ESP_FAIL;
        }

        byte uid[4];
        for (size_t i = 0; i < min((size_t)4, uidArray.size()); i++)
        {
            uid[i] = uidArray[i];
        }

        struct RfidCard *card = findCardByUid(uid, min((size_t)4, uidArray.size()));
        if (card)
        {
            card->active = false;
            httpd_resp_send(req, "Card deactivated", HTTPD_RESP_USE_STRLEN);
            return ESP_OK;
        }
        else
        {
            httpd_resp_send_err(req, HTTPD_404_NOT_FOUND, "Card not found");
            return ESP_FAIL;
        }
    }
    else if (strcmp(action, "list") == 0)
    {
        // List all cards
        DynamicJsonDocument response(2048);
        JsonArray cards = response.createNestedArray("cards");

        for (int i = 0; i < numKnownCards; i++)
        {
            if (knownCards[i].active)
            {
                JsonObject card = cards.createNestedObject();
                card["name"] = knownCards[i].name;
                JsonArray cardUid = card.createNestedArray("uid");
                for (int j = 0; j < 4; j++)
                {
                    cardUid.add(knownCards[i].uid[j]);
                }
            }
        }

        String responseStr;
        serializeJson(response, responseStr);
        httpd_resp_set_type(req, "application/json");
        httpd_resp_send(req, responseStr.c_str(), responseStr.length());
        return ESP_OK;
    }
    else if (strcmp(action, "scan") == 0)
    {
        // Request to read current card from reader
        if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial())
        {
            httpd_resp_send_err(req, HTTPD_404_NOT_FOUND, "No card present");
            return ESP_FAIL;
        }

        DynamicJsonDocument response(256);
        JsonArray cardUid = response.createNestedArray("uid");
        for (byte i = 0; i < rfid.uid.size; i++)
        {
            cardUid.add(rfid.uid.uidByte[i]);
        }

        String responseStr;
        serializeJson(response, responseStr);
        httpd_resp_set_type(req, "application/json");
        httpd_resp_send(req, responseStr.c_str(), responseStr.length());

        rfid.PICC_HaltA();
        rfid.PCD_StopCrypto1();
        return ESP_OK;
    }
    else
    {
        Serial.println("Unknown action");
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "Unknown action");
        return ESP_FAIL;
    }
}

// Add RFID attendance endpoint
static esp_err_t rfid_attendance_handler(httpd_req_t *req)
{
    Serial.println("RFID attendance request received");

    // Set scan in progress flag to pause camera
    rfid_scan_in_progress = true;

    // Update OLED to indicate scanning for attendance
    display.clearDisplay();
    display.setCursor(0, 0);
    display.println("RFID Attendance");
    display.println("Place card for");
    display.println("attendance...");
    display.display();

    // Initialize RFID - safely
    if (!initRFID())
    {
        // Failed to initialize
        Serial.println("RFID init failed - aborting attendance");
        display.clearDisplay();
        display.setCursor(0, 0);
        display.println("RFID ERROR");
        display.println("Failed to init");
        display.println("reader. Check");
        display.println("wiring!");
        display.display();

        // Clear scan flag
        rfid_scan_in_progress = false;

        httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "RFID reader init failed");
        return ESP_FAIL;
    }

    // Try to detect a card with a short timeout (5 seconds max)
    bool card_found = false;
    byte card_uid[10];
    byte card_uid_size = 0;

    Serial.println("Scanning for attendance card...");
    unsigned long start_time = millis();
    const unsigned long timeout = 5000; // 5 seconds timeout for attendance

    // Re-initialize SPI for RFID reading
    SPI.begin(RFID_SCK_PIN, RFID_MISO_PIN, RFID_MOSI_PIN, RFID_SS_PIN);
    SPI.setFrequency(50000); // Very low 50KHz for maximum reliability
    SPI.setDataMode(SPI_MODE0);

    // Try to detect card
    while (millis() - start_time < timeout)
    {
        // Simple approach - just try to find and read a card
        if (rfid.PICC_IsNewCardPresent())
        {
            // Card detected - try to read it
            if (rfid.PICC_ReadCardSerial())
            {
                Serial.println("Attendance card detected!");

                // Safely copy UID
                card_uid_size = rfid.uid.size > 10 ? 10 : rfid.uid.size;
                memcpy(card_uid, rfid.uid.uidByte, card_uid_size);
                card_found = true;

                // Halt the card
                rfid.PICC_HaltA();
                rfid.PCD_StopCrypto1();
                break;
            }
        }

        // Update display every 500ms
        if (millis() % 500 < 50)
        {
            display.setCursor(0, 40);
            display.print("Waiting");
            for (int i = 0; i < ((millis() / 500) % 4); i++)
            {
                display.print(".");
            }
            display.display();
        }

        // Small delay to prevent hogging CPU
        delay(50);
    }

    // Always safely shut down RFID
    deinitRFID();

    if (!card_found)
    {
        Serial.println("No attendance card found after timeout");
        display.clearDisplay();
        display.setCursor(0, 0);
        display.println("No card found");
        display.println("Attendance");
        display.println("marking canceled");
        display.display();

        // Clear scan flag before returning
        rfid_scan_in_progress = false;

        httpd_resp_send_err(req, HTTPD_404_NOT_FOUND, "No card present for attendance");
        return ESP_FAIL;
    }

    // Find card in known cards
    struct RfidCard *card = findCardByUid(card_uid, card_uid_size);
    if (card != NULL)
    {
        // Card found - mark attendance
        Serial.print("Attendance marked for: ");
        Serial.println(card->name);

        // Display on OLED
        display.clearDisplay();
        display.setCursor(0, 0);
        display.println("RFID Attendance");
        display.println(card->name);
        display.println("Marked PRESENT");
        display.println(WiFi.localIP().toString());
        display.display();

        // Play success sound
        playPresentSound();

        // Send success response
        httpd_resp_send(req, "Attendance marked successfully", HTTPD_RESP_USE_STRLEN);
    }
    else
    {
        // Unknown card
        Serial.println("Unknown card used for attendance");

        // Display on OLED
        display.clearDisplay();
        display.setCursor(0, 0);
        display.println("Unknown Card");
        display.println("Card not registered");
        display.println("Please register first");
        display.display();

        // Play error sound
        playAbsentSound();

        // Report error
        httpd_resp_send_err(req, HTTPD_404_NOT_FOUND, "Unknown card - cannot mark attendance");

        // Clear scan flag to resume camera operations
        rfid_scan_in_progress = false;
        return ESP_FAIL;
    }

    // Give user time to read the result before resuming camera
    delay(2000);

    // Clear scan flag to resume camera operations
    rfid_scan_in_progress = false;
    return ESP_OK;
}

// Add RFID scan handler - GET request to scan for a card
static esp_err_t rfid_scan_handler(httpd_req_t *req)
{
    Serial.println("RFID scan request received");

    // Set scan in progress flag to pause camera
    rfid_scan_in_progress = true;

    // Set headers for JSON response
    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");

    // Update OLED to indicate scanning
    display.clearDisplay();
    display.setCursor(0, 0);
    display.println("RFID SCAN");
    display.println("Place card on");
    display.println("the reader...");
    display.display();

    // Initialize RFID - safely
    if (!initRFID())
    {
        // Failed to initialize
        Serial.println("RFID init failed - aborting scan");
        display.clearDisplay();
        display.setCursor(0, 0);
        display.println("RFID ERROR");
        display.println("Failed to init");
        display.println("reader. Check");
        display.println("wiring!");
        display.display();

        // Clear scan flag
        rfid_scan_in_progress = false;

        // Send error response
        DynamicJsonDocument errorResponse(256);
        errorResponse["error"] = "RFID reader init failed";
        String errorStr;
        serializeJson(errorResponse, errorStr);
        httpd_resp_send(req, errorStr.c_str(), errorStr.length());
        return ESP_OK;
    }

    // Try to detect a card with a longer timeout (5 seconds max)
    bool card_found = false;
    byte card_uid[10];
    byte card_uid_size = 0;

    Serial.println("Scanning for card...");
    unsigned long start_time = millis();
    const unsigned long timeout = 5000; // 5 seconds timeout

    // Re-initialize SPI for RFID reading
    SPI.begin(RFID_SCK_PIN, RFID_MISO_PIN, RFID_MOSI_PIN, RFID_SS_PIN);
    SPI.setFrequency(50000); // Very low 50KHz for maximum reliability
    SPI.setDataMode(SPI_MODE0);

    // Try to detect card
    while (millis() - start_time < timeout)
    {
        // Only use the simple detection method - less error-prone
        if (rfid.PICC_IsNewCardPresent())
        {
            // Card detected - try to read it
            if (rfid.PICC_ReadCardSerial())
            {
                Serial.println("Card detected and read successfully!");

                // Safely copy UID
                card_uid_size = rfid.uid.size > 10 ? 10 : rfid.uid.size;
                memcpy(card_uid, rfid.uid.uidByte, card_uid_size);
                card_found = true;

                // Halt the card
                rfid.PICC_HaltA();
                rfid.PCD_StopCrypto1();
                break;
            }
        }

        // Update display every 500ms
        if (millis() % 500 < 50)
        {
            display.setCursor(0, 40);
            display.print("Scanning");
            for (int i = 0; i < ((millis() / 500) % 4); i++)
            {
                display.print(".");
            }
            display.display();
        }

        // Small delay to prevent hogging CPU
        delay(50);
    }

    // Always safely shut down RFID
    deinitRFID();

    // Create response JSON
    DynamicJsonDocument response(256);

    // Check if we found a card
    if (!card_found)
    {
        Serial.println("No card found after timeout");
        display.clearDisplay();
        display.setCursor(0, 0);
        display.println("No card found");
        display.println("Scan canceled");
        display.display();

        // Clear scan flag before returning
        rfid_scan_in_progress = false;

        response["error"] = "No card present";
        String responseStr;
        serializeJson(response, responseStr);
        httpd_resp_send(req, responseStr.c_str(), responseStr.length());
        return ESP_OK;
    }

    // Card detected - create JSON response
    JsonArray cardUid = response.createNestedArray("uid");
    for (byte i = 0; i < card_uid_size; i++)
    {
        cardUid.add(card_uid[i]);
    }

    // Print UID for debugging
    Serial.print("Card detected! UID: ");
    for (byte i = 0; i < card_uid_size; i++)
    {
        Serial.print(card_uid[i] < 0x10 ? " 0" : " ");
        Serial.print(card_uid[i], HEX);
    }
    Serial.println();

    // Check if this is a known card
    struct RfidCard *card = findCardByUid(card_uid, card_uid_size);
    if (card != NULL)
    {
        Serial.print("Known card: ");
        Serial.println(card->name);

        // Add card details to response
        response["name"] = card->name;
        response["known"] = true;
        response["status"] = "registered";

        // Update OLED
        display.clearDisplay();
        display.setCursor(0, 0);
        display.println("Card Found!");
        display.println(card->name);
        display.println("Known card");

        // Play success sound
        playPresentSound();
    }
    else
    {
        Serial.println("Unknown card");

        // Add unknown card status to response
        response["known"] = false;
        response["status"] = "unknown";

        // Update OLED
        display.clearDisplay();
        display.setCursor(0, 0);
        display.println("Card Found!");
        display.println("UID: ");
        for (byte i = 0; i < card_uid_size; i++)
        {
            display.print(card_uid[i] < 0x10 ? "0" : "");
            display.print(card_uid[i], HEX);
            display.print(" ");
        }
        display.println("\nUnknown card");

        // Play error sound
        playAbsentSound();
    }
    display.display();

    // Send response
    String responseStr;
    serializeJson(response, responseStr);
    Serial.print("Sending response: ");
    Serial.println(responseStr);
    httpd_resp_send(req, responseStr.c_str(), responseStr.length());

    // Clear scan flag to resume camera operations
    rfid_scan_in_progress = false;

    return ESP_OK;
}

// Add a simple GET handler for testing the OLED endpoint
static esp_err_t handleOledGetRequest(httpd_req_t *req)
{
    Serial.println("OLED GET request received");

    // Send a simple test message to the OLED
    display.clearDisplay();
    display.setCursor(0, 0);
    display.println("Test Message");
    display.println("GET Request");
    display.println("Received");
    display.display();

    httpd_resp_send(req, "OLED test message displayed", HTTPD_RESP_USE_STRLEN);
    return ESP_OK;
}

// Update the OLED POST request handler
static esp_err_t handleOledRequest(httpd_req_t *req)
{
    Serial.println("OLED POST request received");

    // Check if we have a body
    size_t buf_len = req->content_len;
    if (buf_len > 1024)
    {
        Serial.println("Request body too large");
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "Request body too large");
        return ESP_FAIL;
    }

    char buf[1024];
    int ret = httpd_req_recv(req, buf, buf_len);
    if (ret <= 0)
    {
        Serial.println("Error receiving request body");
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "Error receiving request body");
        return ESP_FAIL;
    }

    Serial.printf("Received data: %s\n", buf);

    // Parse JSON
    DynamicJsonDocument doc(1024);
    DeserializationError error = deserializeJson(doc, buf);

    if (error)
    {
        Serial.println("Error parsing JSON");
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "Invalid JSON format");
        return ESP_FAIL;
    }

    // Clear display if requested
    bool clearDisplay = doc["clear"] | false;
    if (clearDisplay)
    {
        Serial.println("Clearing display");
        display.clearDisplay();
        display.display();
        httpd_resp_send(req, "Display cleared", HTTPD_RESP_USE_STRLEN);
        return ESP_OK;
    }

    // Get text lines
    JsonArray lines = doc["lines"];
    if (lines.size() == 0)
    {
        Serial.println("No text lines provided");
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "No text lines provided");
        return ESP_FAIL;
    }

    // Update display
    Serial.println("Updating display");
    display.clearDisplay();
    display.setCursor(0, 0);

    int lineHeight = 10; // Approximate height for text size 1
    int y = 0;

    for (size_t i = 0; i < lines.size() && i < 6; i++)
    {
        String line = lines[i].as<String>();
        Serial.printf("Line %d: %s\n", i, line.c_str());
        display.setCursor(0, y);
        display.println(line);
        y += lineHeight;
    }

    display.display();
    httpd_resp_send(req, "Display updated", HTTPD_RESP_USE_STRLEN);
    return ESP_OK;
}

// Add RFID list handler - GET request to list all registered cards
static esp_err_t rfid_list_handler(httpd_req_t *req)
{
    Serial.println("RFID list request received");

    // Set headers for JSON response
    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");

    // Create JSON response with all active cards
    DynamicJsonDocument response(2048);
    JsonArray cards = response.createNestedArray("cards");

    for (int i = 0; i < numKnownCards; i++)
    {
        if (knownCards[i].active)
        {
            JsonObject card = cards.createNestedObject();
            card["name"] = knownCards[i].name;
            JsonArray cardUid = card.createNestedArray("uid");
            for (int j = 0; j < 4; j++)
            {
                cardUid.add(knownCards[i].uid[j]);
            }
        }
    }

    // Serialize to JSON
    String responseStr;
    serializeJson(response, responseStr);

    // Send response
    httpd_resp_send(req, responseStr.c_str(), responseStr.length());
    return ESP_OK;
}

void startCameraServer()
{
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.server_port = 80;

    httpd_uri_t capture_uri = {
        .uri = "/capture",
        .method = HTTP_GET,
        .handler = capture_handler,
        .user_ctx = NULL};

    httpd_uri_t stream_uri = {
        .uri = "/stream",
        .method = HTTP_GET,
        .handler = stream_handler,
        .user_ctx = NULL};

    // Add OLED endpoint for GET requests (for testing)
    httpd_uri_t oled_get_uri = {
        .uri = "/oled",
        .method = HTTP_GET,
        .handler = handleOledGetRequest,
        .user_ctx = NULL};

    // Add OLED endpoint for POST requests
    httpd_uri_t oled_post_uri = {
        .uri = "/oled",
        .method = HTTP_POST,
        .handler = handleOledRequest,
        .user_ctx = NULL};

    // Add buzzer endpoint
    httpd_uri_t buzzer_uri = {
        .uri = "/buzzer",
        .method = HTTP_POST,
        .handler = buzzer_handler,
        .user_ctx = NULL};

    // Add RFID endpoint for managing cards
    httpd_uri_t rfid_uri = {
        .uri = "/rfid",
        .method = HTTP_POST,
        .handler = rfid_handler,
        .user_ctx = NULL};

    // Add RFID scan endpoint (GET method)
    httpd_uri_t rfid_scan_uri = {
        .uri = "/rfid/scan",
        .method = HTTP_GET,
        .handler = rfid_scan_handler,
        .user_ctx = NULL};

    // Add RFID list endpoint (GET method)
    httpd_uri_t rfid_list_uri = {
        .uri = "/rfid/list",
        .method = HTTP_GET,
        .handler = rfid_list_handler,
        .user_ctx = NULL};

    // Add RFID attendance endpoint
    httpd_uri_t rfid_attendance_uri = {
        .uri = "/rfid/attendance",
        .method = HTTP_POST,
        .handler = rfid_attendance_handler,
        .user_ctx = NULL};

    if (httpd_start(&camera_httpd, &config) == ESP_OK)
    {
        httpd_register_uri_handler(camera_httpd, &capture_uri);
        httpd_register_uri_handler(camera_httpd, &stream_uri);
        httpd_register_uri_handler(camera_httpd, &oled_get_uri);
        httpd_register_uri_handler(camera_httpd, &oled_post_uri);
        httpd_register_uri_handler(camera_httpd, &buzzer_uri);
        httpd_register_uri_handler(camera_httpd, &rfid_uri);
        httpd_register_uri_handler(camera_httpd, &rfid_scan_uri);
        httpd_register_uri_handler(camera_httpd, &rfid_list_uri);
        httpd_register_uri_handler(camera_httpd, &rfid_attendance_uri);
        Serial.println("HTTP server started with all endpoints");
        Serial.println("Available endpoints:");
        Serial.println("GET /capture - Get single image");
        Serial.println("GET /stream - Get video stream");
        Serial.println("GET /oled - Test OLED endpoint");
        Serial.println("POST /oled - Update OLED display");
        Serial.println("POST /buzzer - Activate buzzer for status");
        Serial.println("POST /rfid - Manage RFID cards");
        Serial.println("GET /rfid/scan - Scan RFID card");
        Serial.println("GET /rfid/list - List registered RFID cards");
        Serial.println("POST /rfid/attendance - Mark attendance with RFID");
    }
    else
    {
        Serial.println("Error starting HTTP server");
    }
}

void setupLedFlash(int pin);

void setup()
{
    Serial.begin(115200);
    Serial.setDebugOutput(true);
    Serial.println();
    Serial.println("Starting " DEVICE_NAME);

    // Initialize EEPROM
    EEPROM.begin(EEPROM_SIZE);
    Serial.println("EEPROM initialized");

    // Load saved RFID cards
    if (!loadRfidCardsFromEEPROM())
    {
        Serial.println("No saved RFID cards found or error loading them");
        // Initialize with empty array
        numKnownCards = 0;
    }

    // Print reset reason to help diagnose issues
    esp_reset_reason_t reset_reason = esp_reset_reason();
    Serial.print("Reset reason: ");
    switch (reset_reason)
    {
    case ESP_RST_POWERON:
        Serial.println("Power-on reset");
        break;
    case ESP_RST_EXT:
        Serial.println("External pin reset");
        break;
    case ESP_RST_SW:
        Serial.println("Software reset");
        break;
    case ESP_RST_PANIC:
        Serial.println("Exception/panic reset");
        break;
    case ESP_RST_INT_WDT:
        Serial.println("Interrupt watchdog reset");
        break;
    case ESP_RST_TASK_WDT:
        Serial.println("Task watchdog reset");
        break;
    case ESP_RST_WDT:
        Serial.println("Other watchdog reset");
        break;
    case ESP_RST_DEEPSLEEP:
        Serial.println("Exit from deep sleep");
        break;
    case ESP_RST_BROWNOUT:
        Serial.println("Brownout reset");
        break;
    case ESP_RST_SDIO:
        Serial.println("SDIO reset");
        break;
    default:
        Serial.println("Unknown reason");
    }

    // Disable task watchdog timer
    Serial.println("Disabling watchdog timer to prevent resets...");
    // We're not initializing the WDT at all - completely disabled

    // Turn off the ESP32-CAM white LED at startup
    pinMode(4, OUTPUT);
    digitalWrite(4, LOW);
    Serial.println("White LED turned off");

    // Initialize buzzer pin
    pinMode(BUZZER_PIN, OUTPUT);
    digitalWrite(BUZZER_PIN, LOW);
    Serial.println("Buzzer pin initialized");

    // Test the buzzer directly (without PWM) to check if pin is working
    Serial.println("Testing buzzer pin with direct digitalWrite:");
    for (int i = 0; i < 3; i++)
    {
        digitalWrite(BUZZER_PIN, HIGH);
        delay(200);
        digitalWrite(BUZZER_PIN, LOW);
        delay(200);
    }

    // Initialize I2C for OLED
    Wire.begin(I2C_SDA, I2C_SCL);

    // Initialize OLED display
    if (!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS))
    {
        Serial.println(F("SSD1306 allocation failed"));
        // Continue even if OLED fails - camera might still work
    }
    else
    {
        // Show initial display
        display.clearDisplay();
        display.setTextSize(1);
        display.setTextColor(SSD1306_WHITE);
        display.setCursor(0, 0);
        display.println(F(DEVICE_NAME));
        display.println(F("Starting up..."));
        display.display();
    }

    // Initialize camera first to avoid conflicts
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
    config.frame_size = FRAMESIZE_UXGA;
    config.pixel_format = PIXFORMAT_JPEG; // for streaming
    config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
    config.fb_location = CAMERA_FB_IN_PSRAM;
    config.jpeg_quality = 12;
    config.fb_count = 1;

    // if PSRAM IC present, init with UXGA resolution and higher JPEG quality
    if (psramFound())
    {
        config.jpeg_quality = 10;
        config.fb_count = 2;
        config.grab_mode = CAMERA_GRAB_LATEST;
    }
    else
    {
        // Limit the frame size when PSRAM is not available
        config.frame_size = FRAMESIZE_SVGA;
        config.fb_location = CAMERA_FB_IN_DRAM;
    }

    // Initialize the camera
    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK)
    {
        Serial.printf("Camera init failed with error 0x%x", err);
        // Update OLED with error
        display.clearDisplay();
        display.setCursor(0, 0);
        display.println(F("Camera Error!"));
        display.println(F("Init failed."));
        display.println(F("Check wiring."));
        display.display();
        return;
    }

    // Set initial camera parameters (lower resolution for faster streaming)
    sensor_t *s = esp_camera_sensor_get();
    s->set_framesize(s, FRAMESIZE_VGA); // UXGA|SXGA|XGA|SVGA|VGA|CIF|QVGA|HQVGA|QQVGA

    // Now initialize SPI for RFID - after camera is set up
    Serial.println("Initializing RFID module...");

    // First, temporarily release the I2C pins
    Wire.end();

    // Initialize RFID pins manually to ensure they're set correctly
    pinMode(RFID_SS_PIN, OUTPUT);
    pinMode(RFID_RST_PIN, OUTPUT);

    digitalWrite(RFID_SS_PIN, HIGH); // Ensure SS is HIGH (inactive) initially
    digitalWrite(RFID_RST_PIN, LOW); // Reset the RFID module
    delay(100);
    digitalWrite(RFID_RST_PIN, HIGH); // Release reset
    delay(100);

    // Initialize SPI for RFID reader with custom pins
    SPI.begin(RFID_SCK_PIN, RFID_MISO_PIN, RFID_MOSI_PIN, RFID_SS_PIN);
    SPI.setFrequency(100000); // Set SPI clock to 1MHz for reliability

    // Initialize RFID module
    rfid.PCD_Init();
    delay(50);

    // Try to verify RFID module is working by reading version
    byte v = rfid.PCD_ReadRegister(MFRC522::VersionReg);
    if (v == 0x00 || v == 0xFF)
    {
        Serial.println("WARNING: RFID reader version read failed! Check wiring.");
        display.clearDisplay();
        display.setCursor(0, 0);
        display.println("RFID Error!");
        display.println("Check wiring");
        display.println("Version: " + String(v, HEX));
        display.display();
        delay(2000);
    }
    else
    {
        Serial.print("RFID Reader Version: 0x");
        Serial.println(v, HEX);

        // Set antenna gain to max
        rfid.PCD_SetAntennaGain(MFRC522::RxGain_max);

        // Print RFID reader details
        Serial.println("RFID reader initialized");
        rfid.PCD_DumpVersionToSerial();
    }

    // Reinitialize I2C
    Wire.begin(I2C_SDA, I2C_SCL);

    // Ensure OLED is still working
    display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS);
    display.clearDisplay();
    display.setCursor(0, 0);
    display.println(F("RFID Ready!"));
    display.print(F("Ver: 0x"));
    display.println(String(v, HEX));
    display.display();

    // Test buzzer
    Serial.println("Testing buzzer at startup...");
    testBuzzer();

    // Try to connect to WiFi
    WiFi.begin(ssid, password);
    Serial.print("Connecting to WiFi");

    // Update OLED with WiFi connection status
    display.clearDisplay();
    display.setCursor(0, 0);
    display.println(F("Connecting to WiFi"));
    display.println(ssid);
    display.display();

    // Wait for connection
    int connectionAttempts = 0;
    while (WiFi.status() != WL_CONNECTED)
    {
        delay(500);
        Serial.print(".");
        display.print(".");
        display.display();
        connectionAttempts++;

        if (connectionAttempts > 20)
        { // Timeout after 10 seconds
            // If WiFi connection fails, start AP mode
            Serial.println("\nWiFi connection failed, starting AP mode");
            display.clearDisplay();
            display.setCursor(0, 0);
            display.println(F("WiFi Failed"));
            display.println(F("Starting AP"));
            display.println(F(AP_SSID));
            display.println(F(AP_PASSWORD));
            display.display();

            WiFi.mode(WIFI_AP);
            WiFi.softAP(AP_SSID, AP_PASSWORD);
            Serial.print("AP IP address: ");
            Serial.println(WiFi.softAPIP());
            break;
        }
    }

    if (WiFi.status() == WL_CONNECTED)
    {
        Serial.println("");
        Serial.print("Connected to ");
        Serial.println(ssid);
        Serial.print("IP address: ");
        Serial.println(WiFi.localIP());

        // Update OLED with IP address
        display.clearDisplay();
        display.setCursor(0, 0);
        display.println(F("WiFi Connected!"));
        display.println(WiFi.localIP().toString());
        display.println(F("Camera Ready"));
        display.display();
    }

    // Start camera server
    startCameraServer();

    // Add resolution info endpoint
    server.on("/resolutions.csv", HTTP_GET, []()
              {
    String resolutions = "QQVGA\nQVGA\nVGA\nSVGA\nXGA\nSXGA\nUXGA";
    server.send(200, "text/plain", resolutions); });

    // Start HTTP server
    server.begin();

    Serial.println("Camera server started");
    Serial.print("Camera Ready! Use 'http://");
    Serial.print(WiFi.localIP());
    Serial.println("' to connect");
}

void loop()
{
    static unsigned long lastDebugTime = 0;
    unsigned long currentMillis = millis();

    // Debug output every 10 seconds
    if (currentMillis - lastDebugTime >= 10000)
    {
        lastDebugTime = currentMillis;
        Serial.println("System running for " + String(currentMillis / 1000) + " seconds");
        Serial.print("Free heap: ");
        Serial.println(ESP.getFreeHeap());

        // Update OLED with system status
        display.clearDisplay();
        display.setCursor(0, 0);
        display.println("System Status:");
        display.print("Uptime: ");
        display.print(currentMillis / 1000);
        display.println("s");
        display.print("Free mem: ");
        display.print(ESP.getFreeHeap());
        display.println("B");
        display.print("IP: ");
        display.println(WiFi.localIP().toString());
        display.display();
    }

    server.handleClient();

    // Check for RFID cards but ONLY if they have been explicitly initialized
    static unsigned long lastRfidCheck = 0;

    // Only check RFID every 200ms and only if properly initialized
    if (currentMillis - lastRfidCheck >= 200 && rfid_initialized)
    {
        lastRfidCheck = currentMillis;

        // Handle RFID card detection with very basic approach
        if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial())
        {
            // Simple card detection - less error prone
            byte uidLength = rfid.uid.size;
            Serial.print("Card detected in loop! UID: ");
            for (byte i = 0; i < uidLength; i++)
            {
                Serial.print(rfid.uid.uidByte[i] < 0x10 ? " 0" : " ");
                Serial.print(rfid.uid.uidByte[i], HEX);
            }
            Serial.println();

            // Halt the card
            rfid.PICC_HaltA();
            rfid.PCD_StopCrypto1();
        }
    }

    // Small delay to prevent CPU hogging
    delay(10);
}
