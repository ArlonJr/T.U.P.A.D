#ifndef ESP32_CAM_INTERFACE_H
#define ESP32_CAM_INTERFACE_H

#include <Arduino.h>
#include <HardwareSerial.h>
#include "config.h"
#include "attendanceManager.h"

// Command codes for communication with ESP32-CAM
#define CMD_INIT 0x01
#define CMD_CAPTURE_FRAME 0x02
#define CMD_DETECT_FACE 0x03
#define CMD_TRAIN_FACE 0x04
#define CMD_RECOGNIZE_FACE 0x05
#define CMD_GET_FEATURES 0x06
#define CMD_RESET 0xFF

// Response codes from ESP32-CAM
#define RESP_OK 0x01
#define RESP_ERROR 0x02
#define RESP_FACE_DETECTED 0x03
#define RESP_NO_FACE 0x04
#define RESP_FACE_TRAINED 0x05
#define RESP_FACE_RECOGNIZED 0x06
#define RESP_UNKNOWN_FACE 0x07
#define RESP_FEATURES_DATA 0x08

class ESP32CamInterface
{
public:
    ESP32CamInterface();

    // Initialize serial communication with ESP32-CAM
    bool begin();

    // Check if data is available from the camera
    bool dataAvailable();

    // Get face data from the camera
    FaceData getFaceData();

    // Capture and train a face
    bool captureFaceForTraining(String userId);

    // Reset the camera
    bool resetCamera();

private:
    // Serial port for communication with ESP32-CAM
    HardwareSerial *camSerial;

    // Buffer for incoming data
    uint8_t buffer[1024];
    int bufferIndex;

    // Send a command to the camera
    bool sendCommand(uint8_t cmd, const uint8_t *data = nullptr, size_t dataLen = 0);

    // Read a response from the camera
    bool readResponse(uint8_t *responseCode, uint8_t *data = nullptr, size_t *dataLen = nullptr);

    // Parse face data from response
    bool parseFaceData(uint8_t *data, size_t dataLen, FaceData *faceData);
};

#endif // ESP32_CAM_INTERFACE_H