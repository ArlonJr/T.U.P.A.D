# ESP32-CAM with OLED Display Integration Guide

This guide explains how to set up the complete face recognition attendance system with ESP32-CAM, including OLED display, buzzer, and RFID reader.

## Components Required

- ESP32-CAM AI-Thinker module
- SSD1306 OLED display (128x64 pixels, I2C interface)
- MFRC522 RFID-RC522 module
- Active buzzer (5V)
- FTDI USB to TTL serial adapter (for programming)
- Jumper wires
- Breadboard (optional, for prototyping)
- 5V power supply

## Wiring Diagram

### ESP32-CAM Pinout Reference

```
                  +------+
             GND |*      | GND
              5V |*      | GPIO16
        GPIO12/D |*      | GPIO0
        GPIO13/D |*      | GPIO15/SCL
        GPIO15/D |*      | GPIO14/SDA
        GPIO14/D |*      | GPIO2
        GPIO2/D  |*      | GPIO4
             3V3 |*      | RX
              TX |*      | UOT
                  +------+
```

### Complete System Connections

| Component Pin              | ESP32-CAM Pin | Description  |
| -------------------------- | ------------- | ------------ |
| **OLED Display (SSD1306)** |               |              |
| VCC                        | 5V or 3.3V    | Power supply |
| GND                        | GND           | Ground       |
| SCL                        | GPIO15        | I2C Clock    |
| SDA                        | GPIO14        | I2C Data     |
| **RFID-RC522**             |               |              |
| SDA                        | GPIO13        | SPI Data     |
| SCK                        | GPIO14        | SPI Clock    |
| MOSI                       | GPIO15        | SPI MOSI     |
| MISO                       | GPIO12        | SPI MISO     |
| GND                        | GND           | Ground       |
| RST                        | GPIO4         | Reset        |
| 3.3V                       | 3.3V          | Power supply |
| **Buzzer**                 |               |              |
| Positive (+)               | GPIO2         | Signal       |
| Negative (-)               | GND           | Ground       |
| **FTDI Programmer**        |               |              |
| TX                         | RX            | Serial TX    |
| RX                         | TX            | Serial RX    |
| VCC                        | 5V            | Power supply |
| GND                        | GND           | Ground       |

### Programming Connection (FTDI)

Connect the FTDI programmer as follows:

| FTDI Pin | ESP32-CAM Pin |
| -------- | ------------- |
| TX       | RX            |
| RX       | TX            |
| VCC      | 5V            |
| GND      | GND           |

**Important**: Before uploading code, you must connect GPIO0 to GND to put the ESP32-CAM in programming mode.

## Software Setup

1. Install the required libraries in Arduino IDE:

   - ESP32 board support
   - Adafruit SSD1306
   - Adafruit GFX
   - ArduinoJson
   - MFRC522 (for RFID)

2. Upload the `ESP32CAM_OLED_Firmware.ino` sketch to your ESP32-CAM.

3. Make the following adjustments in the code:
   - Set your WiFi SSID and password
   - Verify the I2C pins match your wiring (default: SDA=GPIO14, SCL=GPIO15)
   - Verify the SPI pins for RFID (default: SDA=GPIO13, SCK=GPIO14, MOSI=GPIO15, MISO=GPIO12, RST=GPIO4)
   - Verify the buzzer pin (default: GPIO2)
   - Make sure camera model is set correctly (default: AI_THINKER)

## Installation Steps

1. **Connect all components** to the ESP32-CAM as specified in the wiring diagram.

2. **Programming mode:**

   - Connect GPIO0 to GND
   - Connect FTDI adapter to ESP32-CAM
   - Connect FTDI to computer USB port
   - Select the correct board and port in Arduino IDE
   - Upload the firmware

3. **Normal operation mode:**

   - Disconnect GPIO0 from GND
   - Cycle power to the ESP32-CAM
   - The OLED should show the startup sequence
   - The buzzer should make a test sound
   - The RFID reader should initialize

4. **Verify connectivity:**
   - The OLED should display the IP address once connected
   - Use this IP address in your Python face recognition code
   - Test the buzzer by sending a test command
   - Test the RFID reader by scanning a card

## Troubleshooting

- **Display not initializing**: Check I2C connections and power
- **Camera not working**: Check that the camera flex cable is properly seated
- **WiFi connection failing**: Verify credentials in the code
- **Can't program ESP32-CAM**: Ensure GPIO0 is connected to GND during upload
- **Buzzer not working**: Check GPIO2 connection and power supply
- **RFID reader not responding**: Verify SPI connections and power supply

## Customizing the Display

The ESP32-CAM firmware exposes HTTP endpoints for controlling different components:

### OLED Display Control

```json
POST /oled
{
  "clear": false,
  "lines": ["Line 1", "Line 2", "Line 3", "Line 4"]
}
```

### Buzzer Control

```json
POST /buzzer
{
  "status": "present" | "late" | "absent" | "test"
}
```

### RFID Control

```json
GET /rfid/scan
POST /rfid
{
  "action": "add",
  "name": "Student Name",
  "uid": "card-uid"
}
```

## Additional Notes

- The OLED display I2C lines (SDA/SCL) use GPIO14 and GPIO15, which are available pins on the ESP32-CAM that don't interfere with the camera functionality.
- The RFID reader uses SPI communication, which shares some pins with the I2C bus. Make sure to use the correct pins as specified.
- The buzzer is connected to GPIO2, which is also the built-in LED pin. This allows for both visual and audio feedback.
- The SSD1306 can run on either 3.3V or 5V, but most modules are designed for 3.3V logic.
- If you're having issues with any component, ensure you're using a stable power supply. USB power from a computer might not be sufficient.
- The ESP32-CAM has limited current output capability, so if you're experiencing stability issues, consider using an external power supply for all components.
