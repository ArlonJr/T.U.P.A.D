# ESP32 Facial Recognition Attendance Tracker

This project uses ESP32 and ESP32-CAM to create a facial recognition-based attendance tracking system.

## Hardware Requirements

- ESP32 38 Pins
- ESP32-CAM-CH340 USB Serial to Bluetooth and WIFI Camera Development Board

## Features

- Facial recognition for attendance tracking
- Attendance status: Present, Late, Absent
- Automatic removal (drop) after 3 absences

## Project Structure

- `/src` - ESP32 firmware code
- `/web` - Web interface for monitoring and managing attendance

## Setup Instructions

1. Install Arduino IDE and ESP32 board support
2. Install required libraries (see src/README.md)
3. Upload firmware to ESP32
4. Set up web server for the interface

## License

MIT
