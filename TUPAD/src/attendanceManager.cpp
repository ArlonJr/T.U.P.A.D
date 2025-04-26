#include "attendanceManager.h"

AttendanceManager::AttendanceManager()
{
    usersFilePath = "/users.json";
    attendanceFilePath = "/attendance.json";
}

bool AttendanceManager::begin()
{
    // Configure time
    configTime(GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC, NTP_SERVER);

    // Load saved data from SPIFFS
    bool loadedUsers = loadUsersFromFile();
    bool loadedAttendance = loadAttendanceFromFile();

    // Create initial files if they don't exist
    if (!loadedUsers)
    {
        saveUsersToFile();
    }

    if (!loadedAttendance)
    {
        saveAttendanceToFile();
    }

    return true;
}

bool AttendanceManager::addUser(String userId, String name)
{
    // Check if user already exists
    for (auto &user : users)
    {
        if (user.id == userId)
        {
            return false; // User already exists
        }
    }

    // Create new user
    UserData newUser;
    newUser.id = userId;
    newUser.name = name;
    newUser.absenceCount = 0;
    newUser.isDropped = false;

    // Add to users vector
    users.push_back(newUser);

    // Save to file
    return saveUsersToFile();
}

bool AttendanceManager::removeUser(String userId)
{
    for (auto it = users.begin(); it != users.end(); ++it)
    {
        if (it->id == userId)
        {
            users.erase(it);
            return saveUsersToFile();
        }
    }
    return false; // User not found
}

UserData *AttendanceManager::getUserData(String userId)
{
    for (auto &user : users)
    {
        if (user.id == userId)
        {
            return &user;
        }
    }
    return nullptr; // User not found
}

bool AttendanceManager::addFaceData(String userId, FaceData faceData)
{
    // Check if user exists
    UserData *user = getUserData(userId);
    if (!user)
    {
        return false; // User not found
    }

    // Save face data to file
    return saveFaceDataToFile(userId, faceData);
}

String AttendanceManager::identifyUser(FaceData faceData)
{
    if (!faceData.faceDetected || faceData.confidence < FACE_CONFIDENCE_THRESHOLD)
    {
        return ""; // No face or low confidence
    }

    float bestMatch = 0;
    String bestMatchId = "";

    // Compare with all users
    for (auto &user : users)
    {
        // Skip dropped users
        if (user.isDropped)
        {
            continue;
        }

        // Load user's face data
        FaceData userData;
        if (loadFaceDataFromFile(user.id, &userData))
        {
            // Compare features
            float similarity = 0;
            if (compareFeatures(faceData.faceFeatures, userData.faceFeatures, userData.featuresSize))
            {
                if (similarity > bestMatch && similarity >= FACE_CONFIDENCE_THRESHOLD)
                {
                    bestMatch = similarity;
                    bestMatchId = user.id;
                }
            }

            // Free allocated memory
            if (userData.faceFeatures)
            {
                free(userData.faceFeatures);
            }
        }
    }

    return bestMatchId;
}

bool AttendanceManager::markAttendance(String userId)
{
    // Check if user exists and is not dropped
    UserData *user = getUserData(userId);
    if (!user || user->isDropped)
    {
        return false;
    }

    // Get current time
    time_t now = getCurrentTime();

    // Check if already marked for today
    time_t today = getStartOfDay(now);
    for (auto &record : attendanceRecords)
    {
        if (record.userId == userId && getStartOfDay(record.timestamp) == today)
        {
            return true; // Already marked for today
        }
    }

    // Determine attendance status
    AttendanceStatus status = PRESENT;

    // Get current hour and minute
    struct tm timeinfo;
    localtime_r(&now, &timeinfo);
    int currentHour = timeinfo.tm_hour;
    int currentMinute = timeinfo.tm_min;

    // Convert to minutes since midnight
    int currentTimeMinutes = currentHour * 60 + currentMinute;
    int attendanceStartMinutes = ATTENDANCE_START_HOUR * 60 + ATTENDANCE_START_MINUTE;

    // Check if late
    if (currentTimeMinutes > attendanceStartMinutes + LATE_THRESHOLD_MINUTES)
    {
        status = LATE;
    }

    // Check if absent
    if (currentTimeMinutes > attendanceStartMinutes + ABSENT_THRESHOLD_MINUTES)
    {
        status = ABSENT;

        // Increment absence count
        user->absenceCount++;

        // Check if dropped
        if (user->absenceCount >= MAX_ABSENCES_BEFORE_DROP)
        {
            user->isDropped = true;
        }

        // Save user data
        saveUsersToFile();
    }

    // Create attendance record
    AttendanceRecord record;
    record.userId = userId;
    record.timestamp = now;
    record.status = status;

    // Add to records vector
    attendanceRecords.push_back(record);

    // Save to file
    return saveAttendanceToFile();
}

void AttendanceManager::processScheduledStatusChanges()
{
    // Get current time
    time_t now = getCurrentTime();

    // Get current hour and minute
    struct tm timeinfo;
    localtime_r(&now, &timeinfo);
    int currentHour = timeinfo.tm_hour;
    int currentMinute = timeinfo.tm_min;

    // Convert to minutes since midnight
    int currentTimeMinutes = currentHour * 60 + currentMinute;
    int attendanceStartMinutes = ATTENDANCE_START_HOUR * 60 + ATTENDANCE_START_MINUTE;

    // Check if past absence threshold for today
    if (currentTimeMinutes > attendanceStartMinutes + ABSENT_THRESHOLD_MINUTES)
    {
        time_t today = getStartOfDay(now);

        // Check all non-dropped users
        for (auto &user : users)
        {
            if (user.isDropped)
            {
                continue;
            }

            // Check if user has attendance record for today
            bool hasRecord = false;
            for (auto &record : attendanceRecords)
            {
                if (record.userId == user.id && getStartOfDay(record.timestamp) == today)
                {
                    hasRecord = true;
                    break;
                }
            }

            // Mark absent if no record for today
            if (!hasRecord)
            {
                // Create absent record
                AttendanceRecord record;
                record.userId = user.id;
                record.timestamp = now;
                record.status = ABSENT;

                // Add to records vector
                attendanceRecords.push_back(record);

                // Increment absence count
                user.absenceCount++;

                // Check if dropped
                if (user.absenceCount >= MAX_ABSENCES_BEFORE_DROP)
                {
                    user.isDropped = true;
                }
            }
        }

        // Save changes
        saveUsersToFile();
        saveAttendanceToFile();
    }
}

AttendanceStatus AttendanceManager::getUserAttendanceStatus(String userId, time_t date)
{
    time_t dayStart = getStartOfDay(date);

    for (auto &record : attendanceRecords)
    {
        if (record.userId == userId && getStartOfDay(record.timestamp) == dayStart)
        {
            return record.status;
        }
    }

    return NONE; // No record found
}

String AttendanceManager::getAttendanceJSON()
{
    DynamicJsonDocument doc(MAX_JSON_DOCUMENT_SIZE);
    JsonArray array = doc.to<JsonArray>();

    for (auto &record : attendanceRecords)
    {
        JsonObject obj = array.createNestedObject();
        obj["userId"] = record.userId;
        obj["timestamp"] = record.timestamp;

        // Convert status enum to string
        String statusStr = "unknown";
        switch (record.status)
        {
        case PRESENT:
            statusStr = "present";
            break;
        case LATE:
            statusStr = "late";
            break;
        case ABSENT:
            statusStr = "absent";
            break;
        case DROPPED:
            statusStr = "dropped";
            break;
        default:
            statusStr = "unknown";
            break;
        }
        obj["status"] = statusStr;

        // Find user name
        UserData *user = getUserData(record.userId);
        if (user)
        {
            obj["name"] = user->name;
        }
    }

    String output;
    serializeJson(doc, output);
    return output;
}

String AttendanceManager::getUsersJSON()
{
    DynamicJsonDocument doc(MAX_JSON_DOCUMENT_SIZE);
    JsonArray array = doc.to<JsonArray>();

    for (auto &user : users)
    {
        JsonObject obj = array.createNestedObject();
        obj["id"] = user.id;
        obj["name"] = user.name;
        obj["absenceCount"] = user.absenceCount;
        obj["isDropped"] = user.isDropped;
    }

    String output;
    serializeJson(doc, output);
    return output;
}

bool AttendanceManager::saveUsersToFile()
{
    DynamicJsonDocument doc(MAX_JSON_DOCUMENT_SIZE);
    JsonArray array = doc.to<JsonArray>();

    for (auto &user : users)
    {
        JsonObject obj = array.createNestedObject();
        obj["id"] = user.id;
        obj["name"] = user.name;
        obj["absenceCount"] = user.absenceCount;
        obj["isDropped"] = user.isDropped;
    }

    File file = SPIFFS.open(usersFilePath, "w");
    if (!file)
    {
        return false;
    }

    serializeJson(doc, file);
    file.close();
    return true;
}

bool AttendanceManager::loadUsersFromFile()
{
    if (!SPIFFS.exists(usersFilePath))
    {
        return false;
    }

    File file = SPIFFS.open(usersFilePath, "r");
    if (!file)
    {
        return false;
    }

    DynamicJsonDocument doc(MAX_JSON_DOCUMENT_SIZE);
    DeserializationError error = deserializeJson(doc, file);
    file.close();

    if (error)
    {
        return false;
    }

    // Clear existing users
    users.clear();

    // Load users from JSON
    JsonArray array = doc.as<JsonArray>();
    for (JsonObject obj : array)
    {
        UserData user;
        user.id = obj["id"].as<String>();
        user.name = obj["name"].as<String>();
        user.absenceCount = obj["absenceCount"].as<int>();
        user.isDropped = obj["isDropped"].as<bool>();
        users.push_back(user);
    }

    return true;
}

bool AttendanceManager::saveAttendanceToFile()
{
    DynamicJsonDocument doc(MAX_JSON_DOCUMENT_SIZE);
    JsonArray array = doc.to<JsonArray>();

    for (auto &record : attendanceRecords)
    {
        JsonObject obj = array.createNestedObject();
        obj["userId"] = record.userId;
        obj["timestamp"] = record.timestamp;
        obj["status"] = (int)record.status;
    }

    File file = SPIFFS.open(attendanceFilePath, "w");
    if (!file)
    {
        return false;
    }

    serializeJson(doc, file);
    file.close();
    return true;
}

bool AttendanceManager::loadAttendanceFromFile()
{
    if (!SPIFFS.exists(attendanceFilePath))
    {
        return false;
    }

    File file = SPIFFS.open(attendanceFilePath, "r");
    if (!file)
    {
        return false;
    }

    DynamicJsonDocument doc(MAX_JSON_DOCUMENT_SIZE);
    DeserializationError error = deserializeJson(doc, file);
    file.close();

    if (error)
    {
        return false;
    }

    // Clear existing records
    attendanceRecords.clear();

    // Load records from JSON
    JsonArray array = doc.as<JsonArray>();
    for (JsonObject obj : array)
    {
        AttendanceRecord record;
        record.userId = obj["userId"].as<String>();
        record.timestamp = obj["timestamp"].as<time_t>();
        record.status = (AttendanceStatus)obj["status"].as<int>();
        attendanceRecords.push_back(record);
    }

    return true;
}

bool AttendanceManager::saveFaceDataToFile(String userId, FaceData faceData)
{
    String filePath = String(FACE_DATABASE_PATH) + "/" + userId + ".bin";

    // Create directory if it doesn't exist
    if (!SPIFFS.exists(FACE_DATABASE_PATH))
    {
        SPIFFS.mkdir(FACE_DATABASE_PATH);
    }

    File file = SPIFFS.open(filePath, "w");
    if (!file)
    {
        return false;
    }

    // Write header
    file.write((uint8_t *)&faceData.confidence, sizeof(float));
    file.write((uint8_t *)&faceData.featuresSize, sizeof(size_t));

    // Write features data
    file.write(faceData.faceFeatures, faceData.featuresSize);

    file.close();
    return true;
}

bool AttendanceManager::loadFaceDataFromFile(String userId, FaceData *faceData)
{
    String filePath = String(FACE_DATABASE_PATH) + "/" + userId + ".bin";

    if (!SPIFFS.exists(filePath))
    {
        return false;
    }

    File file = SPIFFS.open(filePath, "r");
    if (!file)
    {
        return false;
    }

    // Read header
    file.read((uint8_t *)&faceData->confidence, sizeof(float));
    file.read((uint8_t *)&faceData->featuresSize, sizeof(size_t));

    // Allocate memory for features
    faceData->faceFeatures = (uint8_t *)malloc(faceData->featuresSize);
    if (!faceData->faceFeatures)
    {
        file.close();
        return false;
    }

    // Read features data
    file.read(faceData->faceFeatures, faceData->featuresSize);

    faceData->faceDetected = true;

    file.close();
    return true;
}

time_t AttendanceManager::getCurrentTime()
{
    time_t now;
    time(&now);
    return now;
}

time_t AttendanceManager::getStartOfDay(time_t timestamp)
{
    struct tm timeinfo;
    localtime_r(&timestamp, &timeinfo);

    // Set to beginning of day
    timeinfo.tm_hour = 0;
    timeinfo.tm_min = 0;
    timeinfo.tm_sec = 0;

    return mktime(&timeinfo);
}

bool AttendanceManager::compareFeatures(uint8_t *features1, uint8_t *features2, size_t size)
{
    // Simple Euclidean distance calculation
    float distance = 0.0f;

    // Assuming features are stored as float values
    float *f1 = (float *)features1;
    float *f2 = (float *)features2;
    size_t floatCount = size / sizeof(float);

    for (size_t i = 0; i < floatCount; i++)
    {
        float diff = f1[i] - f2[i];
        distance += diff * diff;
    }

    distance = sqrt(distance);

    // Convert distance to similarity score (0-1)
    float similarity = 1.0f - (distance / 100.0f); // Arbitrary scaling factor

    // Clamp to 0-1 range
    if (similarity < 0.0f)
        similarity = 0.0f;
    if (similarity > 1.0f)
        similarity = 1.0f;

    return similarity;
}