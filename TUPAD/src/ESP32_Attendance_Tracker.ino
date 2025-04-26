/**
 * ESP32 Facial Recognition Attendance Tracker
 * Main controller code for ESP32 38-pin board
 */

#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>
#include <SPIFFS.h>
#include "config.h"
#include "attendanceManager.h"
#include "esp32CamInterface.h"

// WiFi credentials
const char *ssid = "YOUR_WIFI_SSID";
const char *password = "YOUR_WIFI_PASSWORD";

// Create web server
WebServer server(80);

// Initialize the attendance manager
AttendanceManager attendanceManager;

// Initialize ESP32-CAM interface
ESP32CamInterface camInterface;

void setup()
{
    Serial.begin(115200);
    Serial.println("Starting ESP32 Attendance Tracker...");

    // Initialize file system
    if (!SPIFFS.begin(true))
    {
        Serial.println("SPIFFS initialization failed!");
        return;
    }

    // Connect to WiFi
    WiFi.begin(ssid, password);
    Serial.print("Connecting to WiFi");
    while (WiFi.status() != WL_CONNECTED)
    {
        delay(500);
        Serial.print(".");
    }
    Serial.println();
    Serial.print("Connected to WiFi, IP address: ");
    Serial.println(WiFi.localIP());

    // Setup ESP32-CAM connection
    camInterface.begin();

    // Initialize attendance manager
    attendanceManager.begin();

    // Setup server routes
    setupServerRoutes();

    // Start server
    server.begin();
    Serial.println("HTTP server started");
}

void loop()
{
    server.handleClient();

    // Process any incoming camera data
    if (camInterface.dataAvailable())
    {
        // Get the face data from camera
        FaceData faceData = camInterface.getFaceData();

        // Process attendance
        if (faceData.faceDetected)
        {
            String userId = attendanceManager.identifyUser(faceData);
            if (userId != "")
            {
                attendanceManager.markAttendance(userId);
                Serial.println("Attendance marked for user: " + userId);
            }
            else
            {
                Serial.println("Unknown face detected");
            }
        }
    }

    // Handle any scheduled attendance status changes (e.g., marking people as late after a certain time)
    attendanceManager.processScheduledStatusChanges();

    delay(100);
}

void setupServerRoutes()
{
    // API endpoint to get attendance data
    server.on("/api/attendance", HTTP_GET, []()
              {
    String attendanceData = attendanceManager.getAttendanceJSON();
    server.send(200, "application/json", attendanceData); });

    // API endpoint to add a new user
    server.on("/api/users", HTTP_POST, []()
              {
    if (server.hasArg("plain")) {
      String body = server.arg("plain");
      DynamicJsonDocument doc(1024);
      DeserializationError error = deserializeJson(doc, body);
      
      if (!error) {
        String name = doc["name"];
        String id = doc["id"];
        bool success = attendanceManager.addUser(id, name);
        
        if (success) {
          server.send(200, "application/json", "{\"status\":\"success\",\"message\":\"User added\"}");
        } else {
          server.send(400, "application/json", "{\"status\":\"error\",\"message\":\"Failed to add user\"}");
        }
      } else {
        server.send(400, "application/json", "{\"status\":\"error\",\"message\":\"Invalid JSON\"}");
      }
    } });

    // API endpoint to capture face for training
    server.on("/api/capture-face", HTTP_POST, []()
              {
    if (server.hasArg("plain")) {
      String body = server.arg("plain");
      DynamicJsonDocument doc(1024);
      DeserializationError error = deserializeJson(doc, body);
      
      if (!error) {
        String userId = doc["userId"];
        bool success = false;
        
        // Request face capture from ESP32-CAM
        if (camInterface.captureFaceForTraining(userId)) {
          success = true;
        }
        
        if (success) {
          server.send(200, "application/json", "{\"status\":\"success\",\"message\":\"Face captured\"}");
        } else {
          server.send(400, "application/json", "{\"status\":\"error\",\"message\":\"Failed to capture face\"}");
        }
      } else {
        server.send(400, "application/json", "{\"status\":\"error\",\"message\":\"Invalid JSON\"}");
      }
    } });

    // Serve static files for web interface
    server.onNotFound([]()
                      {
    if (!handleFileRead(server.uri())) {
      server.send(404, "text/plain", "File Not Found");
    } });
}

bool handleFileRead(String path)
{
    Serial.println("handleFileRead: " + path);
    if (path.endsWith("/"))
    {
        path += "index.html";
    }

    String contentType = getContentType(path);
    if (SPIFFS.exists(path))
    {
        File file = SPIFFS.open(path, "r");
        server.streamFile(file, contentType);
        file.close();
        return true;
    }
    return false;
}

String getContentType(String filename)
{
    if (filename.endsWith(".html"))
        return "text/html";
    else if (filename.endsWith(".css"))
        return "text/css";
    else if (filename.endsWith(".js"))
        return "application/javascript";
    else if (filename.endsWith(".ico"))
        return "image/x-icon";
    else if (filename.endsWith(".json"))
        return "application/json";
    return "text/plain";
}