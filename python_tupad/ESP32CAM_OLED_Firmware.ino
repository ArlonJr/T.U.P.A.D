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
    .handler = rfid_handler,
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