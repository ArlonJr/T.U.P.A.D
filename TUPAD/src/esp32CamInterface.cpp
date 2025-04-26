#include "esp32CamInterface.h"

ESP32CamInterface::ESP32CamInterface()
{
    bufferIndex = 0;
}

bool ESP32CamInterface::begin()
{
    // Initialize serial communication with ESP32-CAM
    camSerial = new HardwareSerial(2); // Use UART2
    camSerial->begin(ESP32CAM_BAUD_RATE, SERIAL_8N1, ESP32CAM_RX_PIN, ESP32CAM_TX_PIN);

    // Wait for ESP32-CAM to boot up
    delay(2000);

    // Send initialization command
    bool success = sendCommand(CMD_INIT);

    if (!success)
    {
        Serial.println("Failed to initialize ESP32-CAM");
        return false;
    }

    // Read response
    uint8_t responseCode;
    if (!readResponse(&responseCode) || responseCode != RESP_OK)
    {
        Serial.println("ESP32-CAM initialization failed");
        return false;
    }

    Serial.println("ESP32-CAM initialized successfully");
    return true;
}

bool ESP32CamInterface::dataAvailable()
{
    // Check if there's data available from ESP32-CAM
    if (camSerial->available() > 0)
    {
        // Check for face detection data
        uint8_t responseCode;
        if (readResponse(&responseCode))
        {
            return (responseCode == RESP_FACE_DETECTED || responseCode == RESP_FACE_RECOGNIZED);
        }
    }
    return false;
}

FaceData ESP32CamInterface::getFaceData()
{
    FaceData faceData;
    faceData.faceDetected = false;
    faceData.confidence = 0.0f;
    faceData.faceFeatures = nullptr;
    faceData.featuresSize = 0;

    // Request face features
    if (!sendCommand(CMD_GET_FEATURES))
    {
        return faceData;
    }

    // Read response
    uint8_t responseCode;
    uint8_t responseData[1024];
    size_t dataLen = 0;

    if (!readResponse(&responseCode, responseData, &dataLen))
    {
        return faceData;
    }

    // Process response
    if (responseCode == RESP_FEATURES_DATA)
    {
        parseFaceData(responseData, dataLen, &faceData);
    }

    return faceData;
}

bool ESP32CamInterface::captureFaceForTraining(String userId)
{
    // First, send the userId to the ESP32-CAM
    uint8_t idData[64];
    size_t idLen = userId.length();

    // Copy the string to the data buffer
    memcpy(idData, userId.c_str(), idLen);

    // Send training command with user ID
    if (!sendCommand(CMD_TRAIN_FACE, idData, idLen))
    {
        return false;
    }

    // Read response
    uint8_t responseCode;
    if (!readResponse(&responseCode))
    {
        return false;
    }

    // Check if training was successful
    return (responseCode == RESP_FACE_TRAINED);
}

bool ESP32CamInterface::resetCamera()
{
    // Send reset command
    if (!sendCommand(CMD_RESET))
    {
        return false;
    }

    // Read response
    uint8_t responseCode;
    if (!readResponse(&responseCode))
    {
        return false;
    }

    // Wait for ESP32-CAM to reset
    delay(2000);

    return (responseCode == RESP_OK);
}

bool ESP32CamInterface::sendCommand(uint8_t cmd, const uint8_t *data, size_t dataLen)
{
    // Command format: [CMD] [DATA_LENGTH] [DATA...]

    // Send command byte
    camSerial->write(cmd);

    // Send data length
    camSerial->write((uint8_t)dataLen);

    // Send data if any
    if (data && dataLen > 0)
    {
        camSerial->write(data, dataLen);
    }

    // Flush buffer
    camSerial->flush();

    return true;
}

bool ESP32CamInterface::readResponse(uint8_t *responseCode, uint8_t *data, size_t *dataLen)
{
    // Response format: [RESP_CODE] [DATA_LENGTH] [DATA...]

    // Wait for response with timeout
    unsigned long startTime = millis();
    while (camSerial->available() < 2)
    {
        if (millis() - startTime > 5000)
        {
            // Timeout after 5 seconds
            return false;
        }
        delay(10);
    }

    // Read response code
    *responseCode = camSerial->read();

    // Read data length
    uint8_t respDataLen = camSerial->read();

    // If caller wants data, read it
    if (data && dataLen)
    {
        // Wait for all data to arrive
        startTime = millis();
        while (camSerial->available() < respDataLen)
        {
            if (millis() - startTime > 5000)
            {
                // Timeout after 5 seconds
                return false;
            }
            delay(10);
        }

        // Read data
        for (size_t i = 0; i < respDataLen; i++)
        {
            if (i < 1024)
            { // Prevent buffer overflow
                data[i] = camSerial->read();
            }
            else
            {
                camSerial->read(); // Discard excess data
            }
        }

        // Return data length
        *dataLen = respDataLen;
    }
    else
    {
        // Discard any data
        for (size_t i = 0; i < respDataLen; i++)
        {
            camSerial->read();
        }
    }

    return true;
}

bool ESP32CamInterface::parseFaceData(uint8_t *data, size_t dataLen, FaceData *faceData)
{
    if (dataLen < sizeof(float))
    {
        return false;
    }

    // First 4 bytes are confidence
    memcpy(&faceData->confidence, data, sizeof(float));

    // Rest is feature data
    size_t featuresSize = dataLen - sizeof(float);

    // Allocate memory for features
    faceData->faceFeatures = (uint8_t *)malloc(featuresSize);
    if (!faceData->faceFeatures)
    {
        return false;
    }

    // Copy feature data
    memcpy(faceData->faceFeatures, data + sizeof(float), featuresSize);
    faceData->featuresSize = featuresSize;
    faceData->faceDetected = true;

    return true;
}