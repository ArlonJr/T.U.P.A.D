# Face Recognition Attendance System with ESP32-CAM

This project is developed as part of the Embedded Systems Laboratory at the Technological University of the Philippines. It implements an automated attendance system using face recognition technology and RFID integration.

## Project Overview

The system combines face recognition technology with RFID card scanning to create a robust attendance tracking solution. It features:

- Real-time face detection and recognition
- RFID card integration for backup authentication
- OLED display for user feedback
- Buzzer notifications for attendance status
- Automated attendance logging and reporting
- Database management for student records

## Hardware Components

- ESP32-CAM AI-Thinker module
- SSD1306 OLED display (128x64 pixels)
- MFRC522 RFID-RC522 module
- Active buzzer
- FTDI USB to TTL serial adapter
- Power supply and connecting wires

## Software Requirements

The project requires the following Python packages:

```
face-recognition==1.3.0
opencv-python
numpy
pandas
Pillow==8.0.1
dlib
```

For the complete list of dependencies, see `requirements.txt`.

## Project Structure

- `face_recognition_final.py` - Main face recognition and attendance system
- `db_utils.py` - Database management utilities
- `ESP32CAM_OLED_Firmware.ino` - ESP32-CAM firmware
- `ESP32CAM_OLED_Setup_Guide.md` - Hardware setup guide
- Various test and utility scripts for system components

## Setup Instructions

1. **Hardware Setup**

   - Follow the detailed wiring instructions in `ESP32CAM_OLED_Setup_Guide.md`
   - Connect all components according to the pinout diagram
   - Ensure proper power supply for all components

2. **Software Setup**

   - Install required Python packages: `pip install -r requirements.txt`
   - Upload the ESP32-CAM firmware using Arduino IDE
   - Configure WiFi settings in the firmware
   - Set up the database using the provided utilities

3. **System Configuration**
   - Add student faces to the recognition database
   - Configure RFID cards for student identification
   - Set up attendance rules and parameters

## Features

- **Face Recognition**

  - Real-time face detection and recognition
  - Multiple face detection support
  - Automatic attendance logging

- **RFID Integration**

  - Backup authentication method
  - Card registration system
  - Student identification

- **User Interface**

  - OLED display for status information
  - Audio feedback through buzzer
  - Attendance status indicators

- **Data Management**
  - SQLite database for attendance records
  - Student information management
  - Attendance reporting and export

## Usage

1. Start the main system:

   ```bash
   python face_recognition_final.py
   ```

2. The system will:

   - Initialize the camera and face recognition
   - Connect to the ESP32-CAM
   - Begin monitoring for faces and RFID cards
   - Log attendance automatically

3. View attendance reports:
   - Generated reports are saved as PNG files
   - Database can be queried for specific information

## Development and Testing

The project includes various test scripts for individual components:

- `test_buzzer.py` - Buzzer functionality testing
- `test_esp32cam.py` - Camera testing
- `rfid_test.py` - RFID reader testing
- `test_face_enhancement.py` - Face recognition testing

## Contributing

This project is part of the Embedded Systems Laboratory at TUP. For contributions or modifications, please contact the project maintainers.

## License

This project is developed for educational purposes at the Technological University of the Philippines.

## Acknowledgments

- Developed as part of the Embedded Systems Laboratory
- Technological University of the Philippines
- Project Advisors and Laboratory Instructors

