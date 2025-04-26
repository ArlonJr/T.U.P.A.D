# Hardware Connection Instructions

This guide explains how to connect the ESP32 and ESP32-CAM-CH340 components for the Facial Recognition Attendance Tracker system.

## Components

1. ESP32 38-Pin Development Board
2. ESP32-CAM-CH340 with USB Serial to Bluetooth and WiFi Camera Development Board

## Wiring Diagram

Connect the following pins between the ESP32 and ESP32-CAM:

| ESP32 Pin | ESP32-CAM Pin | Function                                        |
| --------- | ------------- | ----------------------------------------------- |
| GPIO16    | U0T (TX)      | RX for serial communication                     |
| GPIO17    | U0R (RX)      | TX for serial communication                     |
| GND       | GND           | Common ground                                   |
| 5V        | 5V            | Power supply (when not using USB for ESP32-CAM) |

## ESP32-CAM Connection Notes

The ESP32-CAM-CH340 module has built-in USB for programming and communication. You have two options for setup:

1. **Development/Programming Mode:**

   - Connect the ESP32-CAM to your computer via USB
   - Connect the ESP32 to your computer via USB
   - Both devices can be programmed separately

2. **Deployment Mode:**
   - Program both devices first
   - Power the ESP32 with a suitable power supply
   - Connect the ESP32-CAM to the ESP32 as shown in the wiring diagram above
   - The ESP32 will provide power and communication to the ESP32-CAM

## Power Requirements

- ESP32 requires 5V input (USB or external power supply)
- ESP32-CAM can be powered through its USB port or through the 5V pin from the ESP32
- When using facial recognition, it's recommended to use a stable power supply capable of providing at least 1A

## Programming Sequence

1. Program the ESP32-CAM with the firmware in `/src/ESP32_CAM_Firmware/`
2. Program the ESP32 with the main controller code in `/src/`
3. After programming, connect the devices according to the wiring diagram

## Testing the Connection

1. When connected properly and powered on, the ESP32 will establish communication with the ESP32-CAM automatically
2. The blue LED on the ESP32-CAM will flash briefly during initialization
3. You can access the web interface by connecting to the ESP32's WiFi AP or through your local network if you've configured it to connect to your WiFi

## Troubleshooting

If you encounter communication issues between the ESP32 and ESP32-CAM:

1. Check all wire connections are secure
2. Verify both devices have the correct firmware uploaded
3. Make sure both devices are receiving sufficient power
4. Check the serial monitor for debugging information
5. Try resetting both devices by pressing their respective reset buttons

## Camera Positioning

For optimal facial recognition performance:

1. Position the camera at eye level
2. Ensure adequate, even lighting on faces (avoid backlighting)
3. Mount the camera securely to prevent movement
4. Optimal distance for face detection is approximately 30-80cm from the camera
