#ifndef CONFIG_H
#define CONFIG_H

// System configuration
#define SYSTEM_NAME "ESP32 Attendance Tracker"
#define SYSTEM_VERSION "1.0.0"

// Time settings
#define NTP_SERVER "pool.ntp.org"
#define GMT_OFFSET_SEC 0      // Adjust for your timezone (in seconds)
#define DAYLIGHT_OFFSET_SEC 0 // Daylight saving time offset (in seconds)

// Attendance settings
#define ATTENDANCE_START_HOUR 8
#define ATTENDANCE_START_MINUTE 0
#define LATE_THRESHOLD_MINUTES 15   // Minutes after start time to be marked late
#define ABSENT_THRESHOLD_MINUTES 30 // Minutes after start time to be marked absent
#define MAX_ABSENCES_BEFORE_DROP 3  // Number of absences before being dropped

// ESP32-CAM settings
#define ESP32CAM_BAUD_RATE 115200
#define ESP32CAM_RX_PIN 16 // ESP32 pin connected to CAM TX
#define ESP32CAM_TX_PIN 17 // ESP32 pin connected to CAM RX

// Face recognition settings
#define FACE_CONFIDENCE_THRESHOLD 0.7 // Minimum confidence level for face recognition (0-1)
#define FACE_DATABASE_PATH "/faces"   // Path in SPIFFS to store face data

// Web server settings
#define WEB_SERVER_PORT 80
#define MAX_JSON_DOCUMENT_SIZE 4096

#endif // CONFIG_H