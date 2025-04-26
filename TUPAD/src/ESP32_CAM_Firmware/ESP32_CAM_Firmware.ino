/**
 * ESP32-CAM Firmware for Facial Recognition Attendance System
 * Uses ESP32-CAM with CH340 USB-to-Serial
 */

#include "esp_camera.h"
#include <WiFi.h>
#include "fd_forward.h"
#include "fr_forward.h"
#include "fr_flas
h.h"

// Camera model
// #define CAMERA_MODEL_WROVER_KIT // Has PSRAM
// #define CAMERA_MODEL_ESP_EYE // Has PSRAM
// #define CAMERA_MODEL_M5STACK_PSRAM // Has PSRAM
// #define CAMERA_MODEL_M5STACK_V2_PSRAM // M5Camera version B Has PSRAM
// #define CAMERA_MODEL_M5STACK_WIDE // Has PSRAM
// #define CAMERA_MODEL_M5STACK_ESP32CAM // No PSRAM
#define CAMERA_MODEL_AI_THINKER // Has PSRAM
// #define CAMERA_MODEL_TTGO_T_JOURNAL // No PSRAM

#include "camera_pins.h"

// Command codes from main ESP32
#define CMD_INIT 0x01
#define CMD_CAPTURE_FRAME 0x02
#define CMD_DETECT_FACE 0x03
#define CMD_TRAIN_FACE 0x04
#define CMD_RECOGNIZE_FACE 0x05
#define CMD_GET_FEATURES 0x06
#define CMD_RESET 0xFF

// Response codes to main ESP32
#define RESP_OK 0x01
#define RESP_ERROR 0x02
#define RESP_FACE_DETECTED 0x03
#define RESP_NO_FACE 0x04
#define RESP_FACE_TRAINED 0x05
#define RESP_FACE_RECOGNIZED 0x06
#define RESP_UNKNOWN_FACE 0x07
#define RESP_FEATURES_DATA 0x08

// Face recognition parameters
#define FACE_ID_SAVE_ADDR 0x00
#define ENROLL_CONFIRM_TIMES 5
#define FACE_MATCH_THRESHOLD 0.70

// Global variables
static face_id_list id_list = {0};
camera_fb_t *fb = NULL;
dl_matrix3du_t *image_matrix = NULL;
bool is_enrolling = false;

// Face recognition structures
static mtmn_config_t mtmn_config = {0};
static box_array_t *net_boxes = NULL;
static face_recognition_state_t recognition_state = FACE_REC_IDLE;

void setup()
{
    // Initialize serial
    Serial.begin(115200);
    Serial.setDebugOutput(true);
    Serial.println();

    // Configure camera
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

    // Enable PSRAM if available
    if (psramFound())
    {
        config.frame_size = FRAMESIZE_UXGA;
        config.jpeg_quality = 10;
        config.fb_count = 2;
    }
    else
    {
        config.frame_size = FRAMESIZE_SVGA;
        config.jpeg_quality = 12;
        config.fb_count = 1;
    }

    // Initialize camera
    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK)
    {
        Serial.printf("Camera init failed with error 0x%x", err);
        return;
    }

    // Configure face detection parameters
    mtmn_config.type = FAST;
    mtmn_config.min_face = 80;
    mtmn_config.pyramid = 0.707;
    mtmn_config.pyramid_times = 4;
    mtmn_config.p_threshold.score = 0.6;
    mtmn_config.p_threshold.nms = 0.7;
    mtmn_config.p_threshold.candidate_number = 20;
    mtmn_config.r_threshold.score = 0.7;
    mtmn_config.r_threshold.nms = 0.7;
    mtmn_config.r_threshold.candidate_number = 10;
    mtmn_config.o_threshold.score = 0.7;
    mtmn_config.o_threshold.nms = 0.7;
    mtmn_config.o_threshold.candidate_number = 1;

    // Load face recognition model
    face_id_init(&id_list, FACE_ID_SAVE_ADDR, ENROLL_CONFIRM_TIMES);

    Serial.println("ESP32-CAM initialized successfully");
}

void loop()
{
    if (Serial.available() >= 2)
    {
        uint8_t cmd = Serial.read();
        uint8_t dataLen = Serial.read();

        // Buffer for incoming data
        uint8_t data[64];

        // Read data if any
        if (dataLen > 0)
        {
            // Wait for all data to arrive
            unsigned long startTime = millis();
            while (Serial.available() < dataLen)
            {
                if (millis() - startTime > 5000)
                {
                    // Timeout after 5 seconds
                    return;
                }
                delay(10);
            }

            // Read data
            for (uint8_t i = 0; i < dataLen && i < sizeof(data); i++)
            {
                data[i] = Serial.read();
            }
        }

        // Process command
        switch (cmd)
        {
        case CMD_INIT:
            handleInit();
            break;
        case CMD_CAPTURE_FRAME:
            handleCaptureFrame();
            break;
        case CMD_DETECT_FACE:
            handleDetectFace();
            break;
        case CMD_TRAIN_FACE:
            handleTrainFace(data, dataLen);
            break;
        case CMD_RECOGNIZE_FACE:
            handleRecognizeFace();
            break;
        case CMD_GET_FEATURES:
            handleGetFeatures();
            break;
        case CMD_RESET:
            handleReset();
            break;
        default:
            // Unknown command
            sendResponse(RESP_ERROR, nullptr, 0);
            break;
        }
    }

    // Periodic face detection (when not processing a command)
    static unsigned long lastDetectionTime = 0;
    if (millis() - lastDetectionTime > 1000)
    { // Check for faces every second
        detectAndRecognizeFace();
        lastDetectionTime = millis();
    }
}

void handleInit()
{
    // Initialize camera if needed
    sendResponse(RESP_OK, nullptr, 0);
}

void handleCaptureFrame()
{
    // Capture a frame from the camera
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb)
    {
        sendResponse(RESP_ERROR, nullptr, 0);
        return;
    }

    // Free the frame buffer
    esp_camera_fb_return(fb);

    sendResponse(RESP_OK, nullptr, 0);
}

void handleDetectFace()
{
    // Capture a frame
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb)
    {
        sendResponse(RESP_ERROR, nullptr, 0);
        return;
    }

    // Convert frame to RGB565 format for face detection
    dl_matrix3du_t *image_matrix = dl_matrix3du_alloc(1, fb->width, fb->height, 3);
    if (!image_matrix)
    {
        esp_camera_fb_return(fb);
        sendResponse(RESP_ERROR, nullptr, 0);
        return;
    }

    // Convert jpeg to RGB
    bool jpeg_converted = fmt2rgb888(fb->buf, fb->len, fb->format, image_matrix->item);
    esp_camera_fb_return(fb);

    if (!jpeg_converted)
    {
        dl_matrix3du_free(image_matrix);
        sendResponse(RESP_ERROR, nullptr, 0);
        return;
    }

    // Detect faces
    box_array_t *boxes = face_detect(image_matrix, &mtmn_config);

    if (boxes)
    {
        // Face detected
        sendResponse(RESP_FACE_DETECTED, nullptr, 0);
        free(boxes);
    }
    else
    {
        // No face detected
        sendResponse(RESP_NO_FACE, nullptr, 0);
    }

    dl_matrix3du_free(image_matrix);
}

void handleTrainFace(uint8_t *data, uint8_t dataLen)
{
    // Extract user ID from data
    char userId[64] = {0};
    if (dataLen > 0)
    {
        memcpy(userId, data, dataLen);
    }
    else
    {
        // No user ID provided
        sendResponse(RESP_ERROR, nullptr, 0);
        return;
    }

    // Convert user ID to integer (for internal face ID)
    int faceId = atoi(userId);

    // Start face enrollment process
    is_enrolling = true;
    recognition_state = FACE_REC_ENROLLING;

    // Capture a frame
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb)
    {
        sendResponse(RESP_ERROR, nullptr, 0);
        is_enrolling = false;
        recognition_state = FACE_REC_IDLE;
        return;
    }

    // Convert frame to RGB565 format
    dl_matrix3du_t *image_matrix = dl_matrix3du_alloc(1, fb->width, fb->height, 3);
    if (!image_matrix)
    {
        esp_camera_fb_return(fb);
        sendResponse(RESP_ERROR, nullptr, 0);
        is_enrolling = false;
        recognition_state = FACE_REC_IDLE;
        return;
    }

    // Convert jpeg to RGB
    bool jpeg_converted = fmt2rgb888(fb->buf, fb->len, fb->format, image_matrix->item);
    esp_camera_fb_return(fb);

    if (!jpeg_converted)
    {
        dl_matrix3du_free(image_matrix);
        sendResponse(RESP_ERROR, nullptr, 0);
        is_enrolling = false;
        recognition_state = FACE_REC_IDLE;
        return;
    }

    // Detect faces
    box_array_t *boxes = face_detect(image_matrix, &mtmn_config);

    if (!boxes)
    {
        dl_matrix3du_free(image_matrix);
        sendResponse(RESP_NO_FACE, nullptr, 0);
        is_enrolling = false;
        recognition_state = FACE_REC_IDLE;
        return;
    }

    // Align face
    dl_matrix3du_t *aligned_face = dl_matrix3du_alloc(1, FACE_WIDTH, FACE_HEIGHT, 3);
    if (!aligned_face)
    {
        dl_matrix3du_free(image_matrix);
        free(boxes);
        sendResponse(RESP_ERROR, nullptr, 0);
        is_enrolling = false;
        recognition_state = FACE_REC_IDLE;
        return;
    }

    // Get the largest face
    int maxArea = 0;
    int selectedBox = -1;
    for (int i = 0; i < boxes->len; i++)
    {
        int area = (boxes->box[i].box_p[2] - boxes->box[i].box_p[0]) * (boxes->box[i].box_p[3] - boxes->box[i].box_p[1]);
        if (area > maxArea)
        {
            maxArea = area;
            selectedBox = i;
        }
    }

    if (selectedBox < 0)
    {
        dl_matrix3du_free(aligned_face);
        dl_matrix3du_free(image_matrix);
        free(boxes);
        sendResponse(RESP_ERROR, nullptr, 0);
        is_enrolling = false;
        recognition_state = FACE_REC_IDLE;
        return;
    }

    if (!align_face(boxes->box[selectedBox].landmark, image_matrix, aligned_face))
    {
        dl_matrix3du_free(aligned_face);
        dl_matrix3du_free(image_matrix);
        free(boxes);
        sendResponse(RESP_ERROR, nullptr, 0);
        is_enrolling = false;
        recognition_state = FACE_REC_IDLE;
        return;
    }

    // Extract face features
    face_id_node_t face_id_node;
    if (!get_face_id(aligned_face, &face_id_node))
    {
        dl_matrix3du_free(aligned_face);
        dl_matrix3du_free(image_matrix);
        free(boxes);
        sendResponse(RESP_ERROR, nullptr, 0);
        is_enrolling = false;
        recognition_state = FACE_REC_IDLE;
        return;
    }

    // Enroll face
    if (face_id_node.id >= 0)
    {
        // Delete previous enrollment with same ID if exists
        face_id_delete_by_id(&id_list, faceId);
    }

    // Add new face
    face_id_node.id = faceId;
    face_id_add_to_list(&id_list, &face_id_node);

    // Save to flash
    if (!face_id_save(&id_list, FACE_ID_SAVE_ADDR))
    {
        dl_matrix3du_free(aligned_face);
        dl_matrix3du_free(image_matrix);
        free(boxes);
        sendResponse(RESP_ERROR, nullptr, 0);
        is_enrolling = false;
        recognition_state = FACE_REC_IDLE;
        return;
    }

    // Clean up
    dl_matrix3du_free(aligned_face);
    dl_matrix3du_free(image_matrix);
    free(boxes);

    // Enrollment successful
    is_enrolling = false;
    recognition_state = FACE_REC_IDLE;
    sendResponse(RESP_FACE_TRAINED, nullptr, 0);
}

void handleRecognizeFace()
{
    // We'll use the detectAndRecognizeFace function
    detectAndRecognizeFace();
}

void handleGetFeatures()
{
    // Capture a frame
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb)
    {
        sendResponse(RESP_ERROR, nullptr, 0);
        return;
    }

    // Convert frame to RGB565 format
    dl_matrix3du_t *image_matrix = dl_matrix3du_alloc(1, fb->width, fb->height, 3);
    if (!image_matrix)
    {
        esp_camera_fb_return(fb);
        sendResponse(RESP_ERROR, nullptr, 0);
        return;
    }

    // Convert jpeg to RGB
    bool jpeg_converted = fmt2rgb888(fb->buf, fb->len, fb->format, image_matrix->item);
    esp_camera_fb_return(fb);

    if (!jpeg_converted)
    {
        dl_matrix3du_free(image_matrix);
        sendResponse(RESP_ERROR, nullptr, 0);
        return;
    }

    // Detect faces
    box_array_t *boxes = face_detect(image_matrix, &mtmn_config);

    if (!boxes)
    {
        dl_matrix3du_free(image_matrix);
        sendResponse(RESP_NO_FACE, nullptr, 0);
        return;
    }

    // Align face
    dl_matrix3du_t *aligned_face = dl_matrix3du_alloc(1, FACE_WIDTH, FACE_HEIGHT, 3);
    if (!aligned_face)
    {
        dl_matrix3du_free(image_matrix);
        free(boxes);
        sendResponse(RESP_ERROR, nullptr, 0);
        return;
    }

    // Get the largest face
    int maxArea = 0;
    int selectedBox = -1;
    for (int i = 0; i < boxes->len; i++)
    {
        int area = (boxes->box[i].box_p[2] - boxes->box[i].box_p[0]) * (boxes->box[i].box_p[3] - boxes->box[i].box_p[1]);
        if (area > maxArea)
        {
            maxArea = area;
            selectedBox = i;
        }
    }

    if (selectedBox < 0)
    {
        dl_matrix3du_free(aligned_face);
        dl_matrix3du_free(image_matrix);
        free(boxes);
        sendResponse(RESP_ERROR, nullptr, 0);
        return;
    }

    if (!align_face(boxes->box[selectedBox].landmark, image_matrix, aligned_face))
    {
        dl_matrix3du_free(aligned_face);
        dl_matrix3du_free(image_matrix);
        free(boxes);
        sendResponse(RESP_ERROR, nullptr, 0);
        return;
    }

    // Extract face features
    face_id_node_t face_id_node;
    if (!get_face_id(aligned_face, &face_id_node))
    {
        dl_matrix3du_free(aligned_face);
        dl_matrix3du_free(image_matrix);
        free(boxes);
        sendResponse(RESP_ERROR, nullptr, 0);
        return;
    }

    // Prepare response data
    uint8_t responseData[512];
    float confidence = boxes->box[selectedBox].score;

    // Copy confidence
    memcpy(responseData, &confidence, sizeof(float));

    // Copy feature vector
    size_t featureSize = sizeof(face_id_node.descriptor) / sizeof(face_id_node.descriptor[0]);
    for (size_t i = 0; i < featureSize; i++)
    {
        float value = face_id_node.descriptor[i];
        memcpy(responseData + sizeof(float) + (i * sizeof(float)), &value, sizeof(float));
    }

    // Calculate total data size
    size_t totalSize = sizeof(float) + (featureSize * sizeof(float));

    // Send response with features data
    sendResponse(RESP_FEATURES_DATA, responseData, totalSize);

    // Clean up
    dl_matrix3du_free(aligned_face);
    dl_matrix3du_free(image_matrix);
    free(boxes);
}

void handleReset()
{
    // Reset face recognition
    face_id_init(&id_list, FACE_ID_SAVE_ADDR, ENROLL_CONFIRM_TIMES);

    sendResponse(RESP_OK, nullptr, 0);
}

void detectAndRecognizeFace()
{
    // Capture a frame
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb)
    {
        return;
    }

    // Convert frame to RGB565 format
    dl_matrix3du_t *image_matrix = dl_matrix3du_alloc(1, fb->width, fb->height, 3);
    if (!image_matrix)
    {
        esp_camera_fb_return(fb);
        return;
    }

    // Convert jpeg to RGB
    bool jpeg_converted = fmt2rgb888(fb->buf, fb->len, fb->format, image_matrix->item);
    esp_camera_fb_return(fb);

    if (!jpeg_converted)
    {
        dl_matrix3du_free(image_matrix);
        return;
    }

    // Detect faces
    box_array_t *boxes = face_detect(image_matrix, &mtmn_config);

    if (!boxes)
    {
        dl_matrix3du_free(image_matrix);
        return;
    }

    // Align face
    dl_matrix3du_t *aligned_face = dl_matrix3du_alloc(1, FACE_WIDTH, FACE_HEIGHT, 3);
    if (!aligned_face)
    {
        dl_matrix3du_free(image_matrix);
        free(boxes);
        return;
    }

    // Get the largest face
    int maxArea = 0;
    int selectedBox = -1;
    for (int i = 0; i < boxes->len; i++)
    {
        int area = (boxes->box[i].box_p[2] - boxes->box[i].box_p[0]) * (boxes->box[i].box_p[3] - boxes->box[i].box_p[1]);
        if (area > maxArea)
        {
            maxArea = area;
            selectedBox = i;
        }
    }

    if (selectedBox < 0)
    {
        dl_matrix3du_free(aligned_face);
        dl_matrix3du_free(image_matrix);
        free(boxes);
        return;
    }

    if (!align_face(boxes->box[selectedBox].landmark, image_matrix, aligned_face))
    {
        dl_matrix3du_free(aligned_face);
        dl_matrix3du_free(image_matrix);
        free(boxes);
        return;
    }

    // Extract face features
    face_id_node_t face_id_node;
    if (!get_face_id(aligned_face, &face_id_node))
    {
        dl_matrix3du_free(aligned_face);
        dl_matrix3du_free(image_matrix);
        free(boxes);
        return;
    }

    // Recognize face
    int matched_id = recognize_face(&id_list, &face_id_node);

    // Prepare response based on recognition
    if (matched_id >= 0)
    {
        // Convert matched ID to string
        char idStr[10];
        sprintf(idStr, "%d", matched_id);

        // Send recognized face response
        sendResponse(RESP_FACE_RECOGNIZED, (uint8_t *)idStr, strlen(idStr));
    }
    else
    {
        // Send unknown face response
        sendResponse(RESP_UNKNOWN_FACE, nullptr, 0);
    }

    // Clean up
    dl_matrix3du_free(aligned_face);
    dl_matrix3du_free(image_matrix);
    free(boxes);
}

void sendResponse(uint8_t responseCode, const uint8_t *data, size_t dataLen)
{
    // Response format: [RESP_CODE] [DATA_LENGTH] [DATA...]

    // Send response code
    Serial.write(responseCode);

    // Send data length
    Serial.write((uint8_t)dataLen);

    // Send data if any
    if (data && dataLen > 0)
    {
        Serial.write(data, dataLen);
    }

    // Flush buffer
    Serial.flush();
}