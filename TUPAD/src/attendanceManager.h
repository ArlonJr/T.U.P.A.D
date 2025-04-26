#ifndef ATTENDANCE_MANAGER_H
#define ATTENDANCE_MANAGER_H

#include <Arduino.h>
#include <ArduinoJson.h>
#include <SPIFFS.h>
#include <time.h>
#include "config.h"

// Attendance status enumeration
enum AttendanceStatus
{
    NONE,
    PRESENT,
    LATE,
    ABSENT,
    DROPPED
};

// User data structure
struct UserData
{
    String id;
    String name;
    int absenceCount;
    bool isDropped;
};

// Attendance record structure
struct AttendanceRecord
{
    String userId;
    time_t timestamp;
    AttendanceStatus status;
};

// Face data structure received from ESP32-CAM
struct FaceData
{
    bool faceDetected;
    float confidence;
    uint8_t *faceFeatures;
    size_t featuresSize;
};

class AttendanceManager
{
public:
    AttendanceManager();

    // Initialize the attendance manager
    bool begin();

    // User management
    bool addUser(String userId, String name);
    bool removeUser(String userId);
    UserData *getUserData(String userId);

    // Face recognition
    bool addFaceData(String userId, FaceData faceData);
    String identifyUser(FaceData faceData);

    // Attendance management
    bool markAttendance(String userId);
    void processScheduledStatusChanges();
    AttendanceStatus getUserAttendanceStatus(String userId, time_t date);

    // Data export
    String getAttendanceJSON();
    String getUsersJSON();

private:
    // File operations
    bool saveUsersToFile();
    bool loadUsersFromFile();
    bool saveAttendanceToFile();
    bool loadAttendanceFromFile();
    bool saveFaceDataToFile(String userId, FaceData faceData);
    bool loadFaceDataFromFile(String userId, FaceData *faceData);

    // Utility functions
    time_t getCurrentTime();
    time_t getStartOfDay(time_t timestamp);
    bool compareFeatures(uint8_t *features1, uint8_t *features2, size_t size);

    // Data storage
    std::vector<UserData> users;
    std::vector<AttendanceRecord> attendanceRecords;
    String usersFilePath;
    String attendanceFilePath;
};

#endif // ATTENDANCE_MANAGER_H