import cv2
import numpy as np
import face_recognition
import os
from datetime import datetime, time
import requests
import time as tm
import sqlite3
import json
import socket
import subprocess
import threading
import pygame

# Initialize pygame mixer for sound effects
pygame.mixer.init()

# Check/create sounds directory
sounds_dir = './sounds'
if not os.path.exists(sounds_dir):
    os.makedirs(sounds_dir)
    print(f"Created sounds directory at {sounds_dir}")

# Generate simple beep sounds if they don't exist
def ensure_sound_files_exist():
    sound_files = {
        'beep_short.wav': 440,  # A4 tone
        'beep_long.wav': 261.63,  # C4 tone
        'beep_short_long.wav': 349.23  # F4 tone
    }
    
    try:
        from scipy.io import wavfile
        
        for filename, freq in sound_files.items():
            filepath = os.path.join(sounds_dir, filename)
            if not os.path.exists(filepath):
                # Generate a simple sine wave
                sample_rate = 44100
                duration = 0.2  # short beep duration
                if 'long' in filename:
                    duration = 0.6  # long beep duration
                
                t = np.linspace(0, duration, int(sample_rate * duration), False)
                wave = 0.5 * np.sin(2 * np.pi * freq * t)
                
                # If it's the combined sound, add a short beep followed by a long beep
                if filename == 'beep_short_long.wav':
                    t1 = np.linspace(0, 0.2, int(sample_rate * 0.2), False)
                    t2 = np.linspace(0, 0.6, int(sample_rate * 0.6), False)
                    wave1 = 0.5 * np.sin(2 * np.pi * 440 * t1)  # short beep
                    wave2 = 0.5 * np.sin(2 * np.pi * 261.63 * t2)  # long beep
                    
                    # Add a small pause between beeps
                    pause = np.zeros(int(sample_rate * 0.1))
                    wave = np.concatenate((wave1, pause, wave2))
                
                # Ensure the wave is in int16 format
                wave = (wave * 32767).astype(np.int16)
                
                # Write the WAV file
                wavfile.write(filepath, sample_rate, wave)
                print(f"Generated sound file: {filepath}")
    except ImportError:
        print("scipy not installed, cannot generate sound files")
        # Create empty files to prevent errors
        for filename in sound_files:
            filepath = os.path.join(sounds_dir, filename)
            if not os.path.exists(filepath):
                with open(filepath, 'wb') as f:
                    # Write a minimal valid WAV file header
                    f.write(bytes.fromhex('52494646' + '24000000' + '57415645' + '666d7420' + 
                                         '10000000' + '01000100' + '44ac0000' + '88580100' + 
                                         '02001000' + '64617461' + '00000000'))
                print(f"Created empty sound file: {filepath}")

# Try to ensure sound files exist
try:
    ensure_sound_files_exist()
except Exception as e:
    print(f"Warning: Could not create sound files: {e}")

# Path for reference images
path = 'C:\python\image_folder'

# ESP32-CAM IP address (confirmed working)
ESP32_IP = "192.168.0.156"
url = f'http://{ESP32_IP}/capture'  # Use /capture endpoint for single image
oled_url = f'http://{ESP32_IP}/oled'  # Endpoint for sending data to OLED
buzzer_url = f'http://{ESP32_IP}/buzzer'  # Endpoint for buzzer sounds

# Database file path
db_file = 'attendance.db'

# Time thresholds for attendance status
PRESENT_START = time(12, 20)
PRESENT_END = time(12, 35)
LATE_END = time(13, 50)

# Allowed weekdays: Monday (0), Thursday (3)
ALLOWED_DAYS = [0, 3, 5, 6]

# Variable to track if we're in a valid attendance time window
attendance_time_valid = False

# Variable to track if camera is available (default to False until tested)
camera_available = False

# Function to check if current time is within valid attendance window
def is_attendance_time_valid():
    current_datetime = datetime.now()
    current_time = current_datetime.time()
    current_day = current_datetime.weekday()
    
    # First check if it's an allowed day
    if current_day not in ALLOWED_DAYS:
        return False
    
    # Then check if time is within attendance window
    return PRESENT_START <= current_time <= LATE_END

# Function to find ESP32-CAM on the network
def find_esp32cam():
    """Try to find ESP32-CAM on the local network"""
    # Try common ESP32-CAM IP addresses
    common_ips = [
        '192.168.0.156',  # Default in code
        '192.168.1.100',  # Common default
        '192.168.4.1',    # ESP32 AP mode default
    ]
    
    # Get local network IP range
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        network_prefix = '.'.join(local_ip.split('.')[:3])
        
        # Add IP addresses from the local network range
        for i in range(1, 30):  # Only scan first 30 IPs to keep it fast
            ip = f"{network_prefix}.{i}"
            if ip not in common_ips:
                common_ips.append(ip)
    except Exception as e:
        print(f"Error determining local network: {e}")
    
    print("Scanning for ESP32-CAM...")
    for ip in common_ips:
        try:
            print(f"Trying {ip}...")
            response = requests.get(f"http://{ip}/", timeout=1)
            if response.status_code == 200:
                print(f"Found ESP32-CAM at {ip}")
                return ip
        except:
            pass
    
    print("Could not find ESP32-CAM automatically")
    return None

# Function to verify if the device is an ESP32-CAM
def verify_esp32cam(ip):
    """Check if the device at the given IP is actually an ESP32-CAM with expected endpoints"""
    valid_endpoints = ["/", "/capture", "/stream"]
    found_endpoints = []
    
    try:
        # First check if any web server is responding
        print(f"Testing base endpoint: http://{ip}/")
        response = requests.get(f"http://{ip}/", timeout=2)
        response_text = response.text[:200]  # Get first 200 chars for analysis
        
        if response.status_code == 200:
            found_endpoints.append("/")
            print(f"Base endpoint / responded with 200 OK")
            print(f"Response headers: {dict(response.headers)}")
            print(f"Response text snippet: {response_text}")
            
            # Look for keywords in the response that suggest it's an ESP32-CAM
            if "ESP32" in response.text or "Camera" in response.text:
                print(f"Device at {ip} appears to be an ESP32-CAM (found keywords in response)")
            
            # Try to check other endpoints
            for endpoint in valid_endpoints[1:]:
                print(f"Testing endpoint: http://{ip}{endpoint}")
                try:
                    response = requests.get(f"http://{ip}{endpoint}", timeout=1)
                    if response.status_code == 200:
                        found_endpoints.append(endpoint)
                        content_type = response.headers.get('Content-Type', 'unknown')
                        content_length = len(response.content)
                        print(f"Found valid endpoint: {endpoint} (Content-Type: {content_type}, Length: {content_length})")
                        
                        # Check if it's really an image response
                        if 'image' in content_type or content_length > 5000:
                            print(f"  ✓ Endpoint {endpoint} appears to be a camera image endpoint")
                        else:
                            print(f"  ⚠️ Endpoint {endpoint} might not be returning camera images")
                    elif response.status_code == 404:
                        print(f"Endpoint {endpoint} returned 404 - not available")
                    else:
                        print(f"Endpoint {endpoint} returned status {response.status_code}")
                except Exception as e:
                    print(f"Error checking endpoint {endpoint}: {str(e)}")
                    
            # If we found multiple valid endpoints, it's likely our device
            if len(found_endpoints) >= 2:
                print(f"Device at {ip} is confirmed to be an ESP32-CAM (multiple valid endpoints)")
                return True
            
            # If only root endpoint works, ask user to confirm
            print(f"\nFound a web server at {ip}, but couldn't confirm it's an ESP32-CAM.")
            print(f"Available endpoints: {', '.join(found_endpoints)}")
            print("Possible issues:")
            print("1. The device is not an ESP32-CAM")
            print("2. The ESP32-CAM firmware doesn't support the expected endpoints")
            print("3. The device is behind a router/gateway that's intercepting requests")
            
            # Probe for alternative endpoints
            print("\nProbing for alternative endpoints...")
            alt_endpoints = ["/cam", "/camera", "/image", "/jpg", "/photo", "/still", "/snapshot", 
                          "/jpg/image.jpg", "/camera.jpg", "/capture.jpg", "/live"]
            working_endpoints = []
            
            for endpoint in alt_endpoints:
                print(f"Testing alternative endpoint: http://{ip}{endpoint}")
                try:
                    response = requests.get(f"http://{ip}{endpoint}", timeout=1)
                    content_type = response.headers.get('Content-Type', 'unknown')
                    
                    try:
                        content_length = len(response.content) if response.content else 0
                    except Exception:
                        content_length = 0
                        
                    print(f"  - Status: {response.status_code}, Content-Type: {content_type}, Size: {content_length} bytes")
                    
                    if response.status_code == 200:
                        # Check if it's an image by examining content type and size
                        if ('image' in content_type.lower() or content_length > 5000) and content_length > 0:
                            working_endpoints.append(endpoint)
                            print(f"  ✓ Found possible camera endpoint: {endpoint}")
                        else:
                            print(f"  ⚠️ Endpoint returned 200 but may not be an image ({content_type}, {content_length} bytes)")
                except Exception as e:
                    print(f"  ✗ Error: {str(e)}")
            
            if working_endpoints:
                print(f"\nFound possible camera endpoints: {', '.join(working_endpoints)}")
                # Ask user if they want to use any of these
                use_alt = input("Do you want to use one of these alternative endpoints? (y/n): ")
                if use_alt.lower() == 'y':
                    if len(working_endpoints) == 1:
                        new_endpoint = working_endpoints[0]
                    else:
                        for i, ep in enumerate(working_endpoints, 1):
                            print(f"{i}. {ep}")
                        choice = int(input("Enter the number of the endpoint to use: "))
                        if 1 <= choice <= len(working_endpoints):
                            new_endpoint = working_endpoints[choice-1]
                        else:
                            new_endpoint = None
                    
                    if new_endpoint:
                        global url
                        url = f"http://{ip}{new_endpoint}"
                        print(f"Updated camera URL to {url}")
                        return True
            
            confirm = input(f"Is this device at {ip} your ESP32-CAM? (y/n): ")
            return confirm.lower() == 'y'
    except Exception as e:
        print(f"Error verifying ESP32-CAM at {ip}: {str(e)}")
        return False
        
    return False

# Function to test and fix ESP32 connection
def test_and_fix_esp32_connection():
    global ESP32_IP, url, oled_url, buzzer_url
    
    print("\n--- Testing ESP32-CAM Connection ---")
    
    # Try current IP
    try:
        response = requests.get(f"http://{ESP32_IP}/", timeout=2)
        if response.status_code == 200:
            print(f"Found web server at {ESP32_IP}, verifying if it's an ESP32-CAM...")
            if verify_esp32cam(ESP32_IP):
                print(f"ESP32-CAM connection successful at {ESP32_IP}")
                return True
    except Exception as e:
        pass
    
    # If we reach here, connection failed. Try to find device
    print(f"Connection to ESP32-CAM at {ESP32_IP} failed")
    print("Searching for ESP32-CAM on the network...")
    
    new_ip = find_esp32cam()
    if new_ip:
        # Verify it's really an ESP32-CAM
        if verify_esp32cam(new_ip):
            # Update global variables
            ESP32_IP = new_ip
            url = f'http://{ESP32_IP}/capture'
            oled_url = f'http://{ESP32_IP}/oled'
            buzzer_url = f'http://{ESP32_IP}/buzzer'
            
            print(f"Updated ESP32-CAM IP to {ESP32_IP}")
            return True
    
    # If we reach here, device not found
    print("\nCouldn't connect to ESP32-CAM. Please check:")
    print("1. ESP32-CAM is powered on")
    print("2. ESP32-CAM is connected to the same network")
    print("3. IP address is correct")
    print("4. No firewall is blocking the connection")
    print("5. The ESP32-CAM firmware supports the required endpoints (/capture, /stream, etc.)")
    
    # Ask user for manual IP update
    print("\nDo you want to:")
    print("1. Continue without camera (face recognition disabled)")
    print("2. Enter a new IP address manually")
    print("3. Exit program")
    
    choice = input("Enter choice (1/2/3): ")
    
    if choice == '1':
        print("Continuing without camera. Face recognition will be disabled.")
        return False
    elif choice == '2':
        new_ip = input("Enter ESP32-CAM IP address: ")
        ESP32_IP = new_ip
        url = f'http://{ESP32_IP}/capture'
        oled_url = f'http://{ESP32_IP}/oled'
        buzzer_url = f'http://{ESP32_IP}/buzzer'
        print(f"Updated ESP32-CAM IP to {ESP32_IP}")
        
        # Check if user wants to test with a different endpoint
        change_endpoint = input("Do you want to change the capture endpoint? (y/n): ")
        if change_endpoint.lower() == 'y':
            new_endpoint = input("Enter new endpoint (default is /capture): ")
            if new_endpoint:
                url = f'http://{ESP32_IP}{new_endpoint}'
                print(f"Updated capture URL to {url}")
        
        return True
    else:
        print("Exiting program")
        exit()

# Function to send data to OLED display with improved error handling
def update_oled_display(text_lines, clear=False, show_smiley=False):
    """Send data to OLED display with improved error handling"""
    
    # If camera is not available, just log the message but don't try to send
    if not camera_available:
        print(f"OLED update skipped (camera not available): {text_lines}")
        return False
        
    try:
        # print(f"Updating OLED display with {len(text_lines)} lines")
        
        # Add smiley face if requested
        if show_smiley:
            # Add smiley bitmap at the end
            text_lines.append(":)")  # Add smiley at the bottom
        
        payload = {
            'clear': clear,
            'lines': text_lines[:4]  # Limit to 4 lines for small OLED displays
        }
        
        response = requests.post(oled_url, json=payload, timeout=2)
        
        if response.status_code == 200:
            # print("OLED display updated successfully")
            return True
        else:
            print(f"Failed to update OLED display. HTTP status code: {response.status_code}")
            print(f"Response content: {response.text}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to ESP32-CAM OLED endpoint at {oled_url}")
        return False
    except requests.exceptions.Timeout:
        print("Error: OLED update request timed out")
        return False
    except Exception as e:
        print(f"Unexpected error updating OLED: {str(e)}")
        return False

# Function to get image from ESP32-CAM with improved error handling
def get_image_from_camera():
    if not camera_available:
        print("Cannot get image - camera not available")
        return False, None
        
    try:
        # print(f"Attempting to get image from {url}")
        img_resp = requests.get(url, timeout=5)
        
        if img_resp.status_code == 200:
            # print("Successfully received image from camera")
            img_arr = np.array(bytearray(img_resp.content), dtype=np.uint8)
            img = cv2.imdecode(img_arr, -1)
            
            if img is None:
                print("Error: Failed to decode image from ESP32-CAM")
                return False, None
            
            # Flip the image upside down
            img = cv2.flip(img, -1)  # -1 means flip both horizontally and vertically
                
            # print(f"Image dimensions: {img.shape}")
            return True, img
        else:
            print(f"Error: Failed to get image. HTTP status code: {img_resp.status_code}")
            print(f"Response content: {img_resp.text[:200]}")  # Print first 200 chars of response
            print("\nAvailable endpoints:")
            print("1. /capture - Get single image")
            print("2. /stream - Get video stream")
            print("3. /oled - Control OLED display")
            return False, None
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to ESP32-CAM at {ESP32_IP}")
        print("Please check:")
        print("1. ESP32-CAM is powered on")
        print("2. ESP32-CAM is connected to the same network")
        print("3. No firewall is blocking the connection")
        return False, None
    except requests.exceptions.Timeout:
        print("Error: Request timed out. Camera might be busy or not responding")
        return False, None
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return False, None

# Create a fallback image for when the camera is not available
def create_status_image(message1="Camera Not Available", message2=None, message3=None):
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(img, message1, (80, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    
    if message2:
        cv2.putText(img, message2, (80, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    
    if message3:
        cv2.putText(img, message3, (80, 280), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    
    # Add instructions and time display
    cv2.putText(img, "Press 'q' to exit or 'r' to retry connection", (80, 360), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
    
    # Add current time
    current_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if is_attendance_time_valid():
        attendance_status = "ATTENDANCE VALID"
        color = (0, 255, 0)  # Green for valid attendance time
    else:
        attendance_status = "OUTSIDE ATTENDANCE HOURS"
        color = (0, 165, 255)  # Orange for outside hours
    
    cv2.putText(img, current_time_str, (80, 400), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    cv2.putText(img, attendance_status, (80, 430), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    
    return img

# Function to play buzzer sound based on attendance status
def play_buzzer_sound(status):
    """Play different sounds based on attendance status"""
    try:
        status = status.lower() if status else ""
        
        # Only play sound on ESP32-CAM, not locally
        if camera_available:
            try:
                print(f"Sending buzzer command to ESP32-CAM at {buzzer_url}")
                print(f"Status: {status}")
                response = requests.post(buzzer_url, json={"status": status}, timeout=2)
                print(f"Buzzer response status code: {response.status_code}")
                print(f"Buzzer response content: {response.text}")
                if response.status_code != 200:
                    print(f"Failed to play buzzer sound on ESP32-CAM: {response.status_code}")
                    print(f"Response content: {response.text}")
            except requests.exceptions.ConnectionError:
                print(f"Connection error: Could not connect to ESP32-CAM at {buzzer_url}")
                print("Please check if ESP32-CAM is powered on and connected to the network")
            except requests.exceptions.Timeout:
                print("Timeout error: ESP32-CAM did not respond in time")
            except Exception as e:
                print(f"Error playing buzzer sound on ESP32-CAM: {str(e)}")
    except Exception as e:
        print(f"Sound error: {e}")

# Function to test buzzer directly
def test_buzzer_direct():
    """Test each buzzer sound pattern directly"""
    print("Testing buzzer directly...")
    
    try:
        # Test local sounds first
        print("Testing local sound playback...")
        play_buzzer_sound("present")
        tm.sleep(1)
        play_buzzer_sound("late")
        tm.sleep(1)
        play_buzzer_sound("absent")
        tm.sleep(1)
        
        # Only try ESP32 buzzer if camera is available
        if camera_available:
            print("Testing ESP32-CAM buzzer...")
            for status in ["present", "late", "absent"]:
                print(f"Testing '{status}' sound...")
                try:
                    response = requests.post(buzzer_url, json={"status": status}, timeout=5)
                    print(f"Response: {response.status_code} - {response.text}")
                    tm.sleep(1.5)  # Wait for sound to complete
                except Exception as e:
                    print(f"Error: {str(e)}")
    except Exception as e:
        print(f"Buzzer test error: {e}")
    
    print("Buzzer test complete")

# Try to ensure ESP32-CAM connection is working
camera_available = test_and_fix_esp32_connection()

# Initialize database
def init_database():
    conn = None
    try:
        conn = sqlite3.connect(db_file, timeout=20)  # Add timeout to prevent locks
        cursor = conn.cursor()
        
        # Create students table if not exists
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE,
            image_path TEXT,
            status TEXT DEFAULT 'active',
            absent_count INTEGER DEFAULT 0,
            consecutive_absences INTEGER DEFAULT 0,
            last_updated TEXT
        )
        ''')
        
        # Create attendance table if not exists
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY,
            student_name TEXT,
            date TEXT,
            time TEXT,
            status TEXT,
            method TEXT DEFAULT 'face',
            UNIQUE(student_name, date)
        )
        ''')
        
        # Create RFID cards table if not exists
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS rfid_cards (
            id INTEGER PRIMARY KEY,
            card_uid TEXT UNIQUE,
            student_name TEXT,
            active BOOLEAN DEFAULT 1,
            FOREIGN KEY (student_name) REFERENCES students(name)
        )
        ''')
        
        # Check if consecutive_absences column exists in students table
        cursor.execute("PRAGMA table_info(students)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Add consecutive_absences column if it doesn't exist
        if 'consecutive_absences' not in columns:
            print("Adding consecutive_absences column to students table...")
            cursor.execute('ALTER TABLE students ADD COLUMN consecutive_absences INTEGER DEFAULT 0')
        
        # Check if method column exists in attendance table
        cursor.execute("PRAGMA table_info(attendance)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Add method column if it doesn't exist
        if 'method' not in columns:
            print("Adding method column to attendance table...")
            cursor.execute('ALTER TABLE attendance ADD COLUMN method TEXT DEFAULT "face"')
        
        conn.commit()
        print("Database initialized successfully")
        
        # Add all students from image_folder to the database if they don't exist
        if os.path.exists(path):
            for filename in os.listdir(path):
                if filename.endswith(('.jpg', '.jpeg', '.png', '.jfif')):
                    name = os.path.splitext(filename)[0]
                    image_path = os.path.join(path, filename)
                    
                    # Check if student exists
                    cursor.execute("SELECT id FROM students WHERE name=?", (name,))
                    if cursor.fetchone() is None:
                        # Add student to database
                        cursor.execute(
                            "INSERT INTO students (name, image_path, status, last_updated) VALUES (?, ?, ?, ?)",
                            (name, image_path, 'active', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                        )
                        print(f"Added student: {name}")
            
            conn.commit()
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

# Function to link RFID card with student
def link_rfid_card(student_name, card_uid):
    """Link an RFID card with an existing student"""
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Check if student exists
        cursor.execute("SELECT id FROM students WHERE name=?", (student_name,))
        if cursor.fetchone() is None:
            print(f"Student {student_name} not found")
            return False
            
        # Check if card is already registered
        cursor.execute("SELECT student_name FROM rfid_cards WHERE card_uid=?", (card_uid,))
        existing = cursor.fetchone()
        if existing:
            if existing[0] == student_name:
                print(f"Card already linked to {student_name}")
                return True
            else:
                print(f"Card already linked to another student: {existing[0]}")
                return False
        
        # Link card to student
        cursor.execute(
            "INSERT INTO rfid_cards (card_uid, student_name) VALUES (?, ?)",
            (card_uid, student_name)
        )
        conn.commit()
        print(f"Linked RFID card {card_uid} to {student_name}")
        return True
        
    except sqlite3.Error as e:
        print(f"Database error linking RFID card: {e}")
        return False
    finally:
        if conn:
            conn.close()

# Function to get student name from RFID card
def get_student_from_rfid(card_uid):
    """Get student name associated with an RFID card"""
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT student_name FROM rfid_cards WHERE card_uid=? AND active=1",
            (card_uid,)
        )
        result = cursor.fetchone()
        
        if result:
            return result[0]
        return None
        
    except sqlite3.Error as e:
        print(f"Database error getting student from RFID: {e}")
        return None
    finally:
        if conn:
            conn.close()

# Update markAttendance to handle database locks
def markAttendance(name, method="face"):
    conn = None
    try:
        # Check if we're in a valid attendance time window
        if not is_attendance_time_valid():
            print(f"Attendance not recorded for {name} - outside valid hours")
            return "Outside attendance hours"
            
        current_datetime = datetime.now()
        current_time = current_datetime.time()
        current_date = current_datetime.strftime('%Y-%m-%d')
        
        # Set status based on time
        status = "Unknown"
        if PRESENT_START <= current_time <= PRESENT_END:
            status = "Present"
        elif PRESENT_END < current_time <= LATE_END:
            status = "Late"
        else:
            return "Outside attendance hours"
        
        # Connect to database with timeout and retry logic
        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            try:
                conn = sqlite3.connect(db_file, timeout=20)
                cursor = conn.cursor()
                
                # First check if student is active
                cursor.execute("SELECT status FROM students WHERE name=?", (name,))
                student_result = cursor.fetchone()
                
                if not student_result:
                    print(f"Student {name} not found in database")
                    return "Student not found"
                    
                if student_result[0] != 'active':
                    print(f"Student {name} is not active (status: {student_result[0]})")
                    return "Student not active"
                
                # Check if this student already has an attendance record for today
                cursor.execute(
                    "SELECT status FROM attendance WHERE student_name=? AND date=?", 
                    (name, current_date)
                )
                result = cursor.fetchone()
                
                if result:
                    # Already recorded today, don't update
                    print(f"{name} already marked as {result[0]} for today ({current_date})")
                    return None
                else:
                    # Record new attendance
                    cursor.execute(
                        "INSERT INTO attendance (student_name, date, time, status, method) VALUES (?, ?, ?, ?, ?)",
                        (name, current_date, current_datetime.strftime('%H:%M:%S'), status, method)
                    )
                    
                    # Reset absence count for this student if they're present
                    if status in ["Present", "Late"]:
                        cursor.execute(
                            "UPDATE students SET consecutive_absences = 0 WHERE name = ?",
                            (name,)
                        )
                    
                    conn.commit()
                    print(f"Marked {name} as {status} at {current_datetime.strftime('%H:%M:%S')} using {method}")
                    return status
                    
            except sqlite3.Error as e:
                retry_count += 1
                if retry_count < max_retries:
                    print(f"Database error (attempt {retry_count}/{max_retries}): {e}")
                    tm.sleep(1)  # Use tm.sleep instead of time.sleep
                else:
                    print(f"Error in markAttendance after {max_retries} attempts: {e}")
                    return "Error"
            finally:
                if conn:
                    conn.close()
                    conn = None
                    
    except Exception as e:
        print(f"Unexpected error in markAttendance: {e}")
        return "Error"
    finally:
        if conn:
            conn.close()

# Update markRfidAttendance to use the new database functions
def markRfidAttendance(studentName):
    try:
        # Check if we're in a valid attendance time window
        if not is_attendance_time_valid():
            print(f"RFID attendance not recorded for {studentName} - outside valid hours")
            update_oled_display([
                "RFID Attendance",
                studentName,
                "Outside valid hours",
                datetime.now().strftime('%H:%M:%S')
            ])
            return "Outside attendance hours"
            
        # Mark attendance using the common function
        status = markAttendance(studentName, method="rfid")
        
        if status:
            # Update OLED with attendance confirmation
            update_oled_display([
                "RFID Attendance",
                studentName,
                f"Status: {status}",
                datetime.now().strftime('%H:%M:%S')
            ])
            
            # Play appropriate sound for attendance status
            play_buzzer_sound(status)
            
        return status
    except Exception as e:
        print(f"Error in markRfidAttendance: {e}")
        update_oled_display([
            "RFID Error",
            "Database issue",
            str(e)[:16],
            datetime.now().strftime('%H:%M:%S')
        ])
        return "Error"

# Initialize database
init_database()

# Attendance file in current directory (simplest approach) - for backwards compatibility
attendance_file = 'Attendance.txt'

# Create Attendance file if it doesn't exist (for backwards compatibility)
if not os.path.isfile(attendance_file):
    with open(attendance_file, 'w') as f:
        f.write('Name,Time')
    print(f"Created attendance file: {attendance_file}")

# Initialize with a test image
print("Testing camera connection...")
if camera_available:
    success, test_img = get_image_from_camera()
    if success:
        print(f"Camera connection successful! Image dimensions: {test_img.shape}")
    else:
        print("Camera connection failed on test! Check ESP32-CAM settings.")
        camera_available = False
else:
    print("Camera not available, continuing without face recognition capability.")

# Test buzzer functionality at startup
print("Testing buzzer connection...")
test_buzzer_direct()

# Main loop - modified to use active students
print("Starting face recognition. Press 'q' to exit, 'a' to process absences, 'r' to refresh encodings.")
print("Press 'd' to toggle detailed display on OLED, 'c' to clear OLED, 's' to show stats.")
print("Press 'f' to scan RFID card, 'l' to list RFID cards, 'n' to add new RFID card.")
print(f"Valid attendance window: {PRESENT_START.strftime('%H:%M')} - {LATE_END.strftime('%H:%M')} on days {ALLOWED_DAYS}")

# Load reference images
images = []
classNames = []
if os.path.exists(path):
    myList = os.listdir(path)
    print(f"Loading {len(myList)} reference images...")
    for cl in myList:
        curImg = cv2.imread(f'{path}/{cl}')
        if curImg is not None:
            images.append(curImg)
            classNames.append(os.path.splitext(cl)[0])
    print(f"Loaded {len(images)} images successfully")
    print(f"Names: {classNames}")
else:
    print(f"WARNING: Reference images folder not found: {path}")
    print("Please create the folder and add face images for recognition")

# Function to find face encodings with stricter matching
def findEncodings(images, names):
    """
    Create face encodings for the provided images.
    Only encode faces for active students.
    """
    encodeList = []
    activeNames = []
    
    # Connect to database to check student status
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    for i, (img, name) in enumerate(zip(images, names)):
        try:
            # Check if student is active
            cursor.execute("SELECT status FROM students WHERE name=?", (name,))
            result = cursor.fetchone()
            
            if result and result[0] == 'active':
                # Only encode active students
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                # Get all face encodings in the image
                face_encodings = face_recognition.face_encodings(img)
                if face_encodings:
                    # Use the first face found in the reference image
                    encodeList.append(face_encodings[0])
                    activeNames.append(name)
                    print(f"Encoded {name} (active)")
                else:
                    print(f"No face found in reference image for {name}")
            else:
                print(f"Skipping {name} (not active)")
        except Exception as e:
            print(f"Error encoding image for {name}: {e}")
    
    conn.close()
    return encodeList, activeNames

# Update process_absent_students to handle database locks
def process_absent_students():
    """Process students who were absent today and update their absent count"""
    conn = None
    try:
        # Connect to database with timeout
        conn = sqlite3.connect(db_file, timeout=20)
        cursor = conn.cursor()
        
        # Get current date
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # Get all active students
        cursor.execute("SELECT name FROM students WHERE status='active'")
        active_students = cursor.fetchall()
        
        # Get students who attended today
        cursor.execute("SELECT student_name FROM attendance WHERE date=?", (current_date,))
        attended_students = [record[0] for record in cursor.fetchall()]
        
        # Process absent students
        for student in active_students:
            name = student[0]
            if name not in attended_students:
                # Student was absent today
                print(f"Student {name} was absent today")
                
                # Record absence
                cursor.execute(
                    "INSERT OR IGNORE INTO attendance (student_name, date, time, status) VALUES (?, ?, ?, ?)",
                    (name, current_date, "00:00:00", "absent")
                )
                
                # Increment absent count and consecutive absences
                cursor.execute("""
                    UPDATE students 
                    SET absent_count = absent_count + 1,
                        consecutive_absences = consecutive_absences + 1 
                    WHERE name=?
                """, (name,))
                
                # Check if student should be dropped
                cursor.execute("SELECT consecutive_absences FROM students WHERE name=?", (name,))
                consecutive_absences = cursor.fetchone()[0]
                
                if consecutive_absences >= 3:
                    # Mark student as dropped
                    cursor.execute("UPDATE students SET status='dropped' WHERE name=?", (name,))
                    print(f"Student {name} has been dropped due to {consecutive_absences} consecutive absences")
        
        conn.commit()
        
    except sqlite3.Error as e:
        print(f"Database error processing absences: {e}")
    finally:
        if conn:
            conn.close()

# Check if we have any images to use for recognition
if len(images) == 0:
    print("ERROR: No valid reference images found. Please add images to the folder.")
    exit()

# Encode known faces (only active students)
print("Encoding reference faces...")
encodeListKnown, activeClassNames = findEncodings(images, classNames)
print(f'Encoding complete. {len(encodeListKnown)} active faces encoded.')

# Update OLED display on startup
print("Initializing OLED display...")
update_oled_display(["Face Recognition", "System Starting...", f"{len(encodeListKnown)} faces", "encoded"], clear=True)

# Initialize display toggle state
detailed_display = True  # Start with detailed display enabled
running = True
last_capture_time = 0
capture_interval = 0.5  # 500ms between captures
last_face_time = 0
face_display_interval = 2  # Show face info for 2 seconds
connection_retry_count = 0
max_retry_count = 5  # Maximum number of retries before trying to fix connection

# Clear OLED display on startup
update_oled_display(["Face Recognition", "System Starting...", f"{len(encodeListKnown)} faces", "encoded"], clear=True)

while running:
    current_time = tm.time()
    
    # Check if we're in a valid attendance time window
    attendance_time_valid = is_attendance_time_valid()
    
    # If camera is not available, show status image but continue running
    if not camera_available:
        # Update status image every 1 second
        if current_time - last_capture_time >= 1.0:
            last_capture_time = current_time
            
            if attendance_time_valid:
                timeframe_msg = f"Valid attendance: {PRESENT_START.strftime('%H:%M')} - {LATE_END.strftime('%H:%M')}"
            else:
                timeframe_msg = "Outside attendance hours"
                
            img = create_status_image(
                "Camera Not Available", 
                f"ESP32-CAM at {ESP32_IP} not responding",
                timeframe_msg
            )
            cv2.imshow('ESP32-CAM Face Recognition', img)
    
    # Only capture new image if enough time has passed and camera is available
    elif current_time - last_capture_time >= capture_interval:
        # Get image from ESP32-CAM
        success, img = get_image_from_camera()
        last_capture_time = current_time
        
        if not success:
            print(f"Failed to get image from ESP32-CAM at {url}. Retrying...")
            connection_retry_count += 1
            
            if connection_retry_count >= max_retry_count:
                print(f"Multiple connection failures ({connection_retry_count}). Attempting to fix connection...")
                camera_available = test_and_fix_esp32_connection()
                connection_retry_count = 0
                if not camera_available:
                    print("Camera connection could not be fixed. Continuing without camera.")
                    # Create a blank image to show error message
                    img = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.putText(img, "ESP32-CAM not available", (80, 220), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                    cv2.putText(img, "Press 'q' to exit or 'r' to retry", (80, 260), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                    cv2.imshow('ESP32-CAM Face Recognition', img)
            
            tm.sleep(2)
            continue
        
        # Ensure img is not None before processing
        if img is None:
            print("Image is None. Retrying...")
            tm.sleep(2)
            continue
        
        # Process the image (scale down for faster processing)
        imgS = cv2.resize(img, (0, 0), None, 0.25, 0.25)
        imgS = cv2.cvtColor(imgS, cv2.COLOR_BGR2RGB)

        # Standard HOG-based model
        facesCurFrame = face_recognition.face_locations(imgS)
        
        # If faces were found, display count
        face_count = len(facesCurFrame)
        if face_count > 0:
            print(f"Found {face_count} faces")
            last_face_time = current_time
        
        # Get face encodings for the found faces
        encodesCurFrame = face_recognition.face_encodings(imgS, facesCurFrame)

        # Initialize recognized names for this frame
        recognized_names = []
        recognized_statuses = []
        
        # Initialize newly_recognized list outside the if block
        newly_recognized = []  # Track newly recognized faces for buzzer
        
        # Only attempt to mark attendance if in valid time window
        if attendance_time_valid:
            # Compare with known faces (active students only)
            for encodeFace, faceLoc in zip(encodesCurFrame, facesCurFrame):
                # Use face_distance to get the actual distance values
                face_distances = face_recognition.face_distance(encodeListKnown, encodeFace)
                
                # Only consider it a match if the distance is very small (more strict matching)
                if len(face_distances) > 0:
                    matchIndex = np.argmin(face_distances)
                    min_distance = face_distances[matchIndex]
                    
                    # Only match if the distance is very small (more strict threshold)
                    if min_distance < 0.4:  # Lower threshold for stricter matching
                        name = activeClassNames[matchIndex].upper()
                        recognized_names.append(activeClassNames[matchIndex])
                        
                        # Get current attendance status from database
                        conn = sqlite3.connect(db_file)
                        cursor = conn.cursor()
                        current_date = datetime.now().strftime('%Y-%m-%d')
                        cursor.execute(
                            "SELECT status FROM attendance WHERE student_name=? AND date=?", 
                            (activeClassNames[matchIndex], current_date)
                        )
                        result = cursor.fetchone()
                        previously_recorded = result is not None
                        
                        status = result[0] if result else "Not recorded"
                        # Simplify status messages
                        if "too late" in status.lower():
                            status = "Absent"
                        elif "too early" in status.lower():
                            status = "Absent"
                        recognized_statuses.append(status)
                        conn.close()
                        
                        # Mark face on image
                        y1, x2, y2, x1 = faceLoc
                        y1, x2, y2, x1 = y1 * 4, x2 * 4, y2 * 4, x1 * 4
                        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.rectangle(img, (x1, y2 - 35), (x2, y2), (0, 255, 0), cv2.FILLED)
                        cv2.putText(img, f"{name}", (x1 + 6, y2 - 6), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 255, 255), 2)
                        cv2.putText(img, f"Status: {status}", (x1 + 6, y2 + 20), cv2.FONT_HERSHEY_COMPLEX, 0.5, (255, 255, 255), 1)
                        
                        # Track if this is a newly recognized person to trigger buzzer
                        new_status = markAttendance(activeClassNames[matchIndex])
                        if new_status and not previously_recorded:
                            print(f"New attendance recorded for {activeClassNames[matchIndex]} with status: {new_status}")
                            # Play buzzer sound
                            play_buzzer_sound(new_status)
                            # Add a small delay to ensure sound is played
                            tm.sleep(0.1)
                            newly_recognized.append((activeClassNames[matchIndex], new_status))
                        elif new_status:
                            print(f"Attendance already recorded for {activeClassNames[matchIndex]} with status: {status}")
                        else:
                            print(f"No new attendance recorded for {activeClassNames[matchIndex]}")
                    else:
                        # Face found but not matching any known face closely enough
                        y1, x2, y2, x1 = faceLoc
                        y1, x2, y2, x1 = y1 * 4, x2 * 4, y2 * 4, x1 * 4
                        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)  # Red rectangle for unknown face
                        cv2.rectangle(img, (x1, y2 - 35), (x2, y2), (0, 0, 255), cv2.FILLED)
                        cv2.putText(img, "Unknown", (x1 + 6, y2 - 6), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 255, 255), 2)
                        cv2.putText(img, f"Distance: {min_distance:.2f}", (x1 + 6, y2 + 20), cv2.FONT_HERSHEY_COMPLEX, 0.5, (255, 255, 255), 1)
        else:
            # If not in valid time window, just mark faces for display purposes
            for encodeFace, faceLoc in zip(encodesCurFrame, facesCurFrame):
                matches = face_recognition.compare_faces(encodeListKnown, encodeFace)
                faceDis = face_recognition.face_distance(encodeListKnown, encodeFace)
                
                # If we have matches and active students
                if len(faceDis) > 0:
                    matchIndex = np.argmin(faceDis)
                    
                    if matches[matchIndex]:
                        name = activeClassNames[matchIndex].upper()
                        recognized_names.append(activeClassNames[matchIndex])
                        recognized_statuses.append("Outside attendance hours")
                        
                        # Mark face on image
                        y1, x2, y2, x1 = faceLoc
                        y1, x2, y2, x1 = y1 * 4, x2 * 4, y2 * 4, x1 * 4
                        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 165, 0), 2)  # Orange color for outside hours
                        cv2.rectangle(img, (x1, y2 - 35), (x2, y2), (255, 165, 0), cv2.FILLED)
                        cv2.putText(img, f"{name}", (x1 + 6, y2 - 6), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 255, 255), 2)
                        cv2.putText(img, "Outside attendance hours", (x1 + 6, y2 + 20), cv2.FONT_HERSHEY_COMPLEX, 0.5, (255, 255, 255), 1)
            
            # If outside the valid time window, add info on the image
            current_time_str = datetime.now().strftime('%H:%M:%S')
            cv2.putText(img, f"NO ATTENDANCE: {current_time_str}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.putText(img, f"Valid hours: {PRESENT_START.strftime('%H:%M')} - {LATE_END.strftime('%H:%M')}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        # Play buzzer sound for any newly recognized individuals
        for name, status in newly_recognized:
            print(f"New recognition: {name} with status {status}")
            play_buzzer_sound(status)
            # Add a small delay to ensure sound is played
            tm.sleep(0.1)
        
        # Update OLED display based on face detection
        if recognized_names and (current_time - last_face_time < face_display_interval):
            # Prepare display text with name and status
            current_time_str = datetime.now().strftime('%H:%M:%S')
            current_date_str = datetime.now().strftime('%Y-%m-%d')
            oled_lines = []
            
            # Add first recognized person's info
            if len(recognized_names) > 0:
                oled_lines.append(f"{recognized_names[0]}")
                if attendance_time_valid:
                    oled_lines.append(f"{recognized_statuses[0]}")
                else:
                    oled_lines.append("Outside valid hours")
                oled_lines.append(f"{current_time_str}")
                oled_lines.append(f"{current_date_str}")
            
            # Update OLED with smiley face
            update_oled_display(oled_lines, show_smiley=attendance_time_valid)
        elif face_count > 0 and not recognized_names and (current_time - last_face_time < face_display_interval):
            # Update OLED for unrecognized faces
            update_oled_display([
                "Unknown face",
                datetime.now().strftime('%H:%M:%S'),
                datetime.now().strftime('%Y-%m-%d'),
                "No match found"
            ])
        elif current_time - last_face_time >= face_display_interval:
            # Show default status when no recent faces
            if attendance_time_valid:
                update_oled_display([
                    "Face Recognition",
                    "System Ready",
                    f"{len(encodeListKnown)} faces",
                    "in database"
                ])
            else:
                update_oled_display([
                    "Outside Valid Hours",
                    f"{PRESENT_START.strftime('%H:%M')} - {LATE_END.strftime('%H:%M')}",
                    "Attendance not",
                    "being recorded"
                ])
        
        # Show the image with face recognition
        cv2.imshow('ESP32-CAM Face Recognition', img)
    
    # Handle key presses with a longer wait time
    key = cv2.waitKey(100) & 0xFF  # Wait 100ms for key press
    if key != 255:  # If a key was pressed
        print(f"Key pressed: {chr(key)}")
        if key == ord('q'):
            print("Quitting...")
            update_oled_display(["System", "Shutting down...", "Goodbye!", ""], clear=True)
            running = False
        elif key == ord('a'):
            # Process absences - only allow this after the valid attendance window
            current_datetime = datetime.now()
            current_time = current_datetime.time()
            
            if current_time <= LATE_END:
                print(f"Cannot process absences until after {LATE_END.strftime('%H:%M')}.")
                update_oled_display([
                    "Cannot process",
                    "absences yet",
                    f"Wait until after",
                    f"{LATE_END.strftime('%H:%M')}"
                ])
            else:
                # Process absences for today
                print("Processing absent students...")
                process_absent_students()
                update_oled_display([
                    "Absences Processed",
                    "Students marked",
                    "as absent",
                    datetime.now().strftime('%H:%M:%S')
                ])
        elif key == ord('r'):
            print("Attempting to reconnect to camera and refresh encodings...")
            # Try to fix camera connection first
            camera_available = test_and_fix_esp32_connection()
            if camera_available:
                update_oled_display(["Refreshing", "student database", "Please wait...", ""])
                # Refresh encodings if camera is available
                encodeListKnown, activeClassNames = findEncodings(images, classNames)
                print(f'Re-encoding complete. {len(encodeListKnown)} active faces encoded.')
                update_oled_display(["Refresh complete", f"{len(encodeListKnown)} faces", "encoded", ""])
            else:
                update_oled_display(["Camera unavailable", "Continuing without", "face recognition", ""])
        elif key == ord('d'):
            detailed_display = not detailed_display
            if detailed_display:
                update_oled_display(["Detailed display", "ENABLED", "", ""])
            else:
                update_oled_display(["Detailed display", "DISABLED", "", ""])
        elif key == ord('c'):
            print("Clearing OLED display...")
            update_oled_display([], clear=True)
        elif key == ord('s'):
            print("Showing system stats...")
            # Get current date and time
            current_date = datetime.now().strftime('%Y-%m-%d')
            current_time = datetime.now().strftime('%H:%M:%S')
            
            # Connect to database to get attendance stats
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM attendance WHERE date=? AND status='present'", (current_date,))
            present_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM attendance WHERE date=? AND status='late'", (current_date,))
            late_count = cursor.fetchone()[0]
            conn.close()
            
            # Update OLED with stats
            update_oled_display([
                f"Date: {current_date}",
                f"Time: {current_time}",
                f"Present: {present_count}",
                f"Late: {late_count}"
            ])
        elif key == ord('f'):
            print("Scanning RFID card...")
            if camera_available:
                # Get student name from RFID scan
                try:
                    # Try to get student name from ESP32-CAM
                    response = requests.get(f'http://{ESP32_IP}/rfid/scan', timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        if 'name' in data:
                            student_name = data['name']
                            markRfidAttendance(student_name)
                        else:
                            print("No student name found in RFID response")
                            update_oled_display([
                                "RFID Error",
                                "No student name",
                                "found",
                                "Try again"
                            ])
                    else:
                        print(f"RFID scan failed with status code: {response.status_code}")
                        update_oled_display([
                            "RFID Error",
                            f"Status: {response.status_code}",
                            "Check ESP32-CAM",
                            "firmware"
                        ])
                except Exception as e:
                    print(f"Error scanning RFID card: {e}")
                    update_oled_display([
                        "RFID Error",
                        "Connection failed",
                        str(e)[:16],
                        "Try again"
                    ])
            else:
                print("Cannot scan RFID - ESP32-CAM not available")
                img = create_status_image(
                    "RFID Not Available", 
                    "ESP32-CAM connection required", 
                    "Press 'r' to reconnect camera"
                )
                cv2.imshow('ESP32-CAM Face Recognition', img)
        elif key == ord('l'):
            print("Listing RFID cards...")
            if camera_available:
                try:
                    # Get list of registered RFID cards from ESP32-CAM
                    response = requests.get(f'http://{ESP32_IP}/rfid/list', timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        if 'cards' in data and data['cards']:
                            print("Registered RFID cards:")
                            for i, card in enumerate(data['cards']):
                                print(f"{i+1}. {card.get('name', 'Unknown')} - {card.get('uid', 'No ID')}")
                            
                            # Display first few cards on OLED
                            cards = data['cards'][:4]  # Limit to 4 cards for OLED display
                            oled_lines = ["RFID Cards:"]
                            for card in cards:
                                oled_lines.append(f"{card.get('name', 'Unknown')}")
                            update_oled_display(oled_lines)
                        else:
                            print("No RFID cards registered")
                            update_oled_display([
                                "No RFID Cards",
                                "Registered",
                                "Use 'n' to add",
                                "new cards"
                            ])
                    else:
                        print(f"Failed to list RFID cards. Status code: {response.status_code}")
                        update_oled_display([
                            "RFID Error",
                            f"Status: {response.status_code}",
                            "Check ESP32-CAM",
                            "firmware"
                        ])
                except Exception as e:
                    print(f"Error listing RFID cards: {e}")
                    update_oled_display([
                        "RFID Error",
                        "Connection failed",
                        str(e)[:16],
                        "Try again"
                    ])
            else:
                print("Cannot list RFID cards - ESP32-CAM not available")
                img = create_status_image(
                    "RFID Not Available", 
                    "ESP32-CAM connection required", 
                    "Press 'r' to reconnect camera"
                )
                cv2.imshow('ESP32-CAM Face Recognition', img)
        elif key == ord('n'):
            print("Adding new RFID card...")
            if camera_available:
                try:
                    # First, get the student name
                    student_name = input("Enter student name: ")
                    if not student_name:
                        print("No student name provided")
                        update_oled_display([
                            "Add RFID Card",
                            "No name provided",
                            "Operation",
                            "cancelled"
                        ])
                        continue
                    
                    # Then, scan the RFID card
                    print(f"Please scan RFID card for {student_name}...")
                    update_oled_display([
                        "Add RFID Card",
                        f"Scan card for:",
                        student_name,
                        "Waiting..."
                    ])
                    
                    # First scan to get the UID
                    scan_response = requests.get(f'http://{ESP32_IP}/rfid/scan', timeout=10)
                    if scan_response.status_code != 200:
                        print("Failed to scan RFID card")
                        update_oled_display([
                            "RFID Error",
                            "Scan failed",
                            "Try again",
                            ""
                        ])
                        continue
                    
                    scan_data = scan_response.json()
                    if 'uid' not in scan_data:
                        print("No UID in scan response")
                        update_oled_display([
                            "RFID Error",
                            "No UID found",
                            "Try again",
                            ""
                        ])
                        continue
                    
                    # Register the card with the ESP32-CAM
                    register_data = {
                        'action': 'add',
                        'name': student_name,
                        'uid': scan_data['uid']
                    }
                    
                    response = requests.post(
                        f'http://{ESP32_IP}/rfid',
                        json=register_data,
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        print(f"RFID card registered for {student_name}")
                        update_oled_display([
                            "RFID Card Added",
                            f"For: {student_name}",
                            "Success!",
                            ""
                        ])
                    else:
                        print(f"Failed to register RFID card. Status code: {response.status_code}")
                        update_oled_display([
                            "RFID Error",
                            f"Status: {response.status_code}",
                            "Check ESP32-CAM",
                            "firmware"
                        ])
                except Exception as e:
                    print(f"Error adding RFID card: {e}")
                    update_oled_display([
                        "RFID Error",
                        "Connection failed",
                        str(e)[:16],
                        "Try again"
                    ])
            else:
                print("Cannot add RFID cards - ESP32-CAM not available")
                img = create_status_image(
                    "RFID Not Available", 
                    "ESP32-CAM connection required", 
                    "Press 'r' to reconnect camera"
                )
                cv2.imshow('ESP32-CAM Face Recognition', img)
        elif key == ord('k'):
            print("Linking RFID card to student...")
            if camera_available:
                try:
                    # First, get the student name
                    student_name = input("Enter student name to link card: ")
                    if not student_name:
                        print("No student name provided")
                        update_oled_display([
                            "Link RFID Card",
                            "No name provided",
                            "Operation",
                            "cancelled"
                        ])
                        continue
                    
                    # Then, scan the RFID card
                    print(f"Please scan RFID card for {student_name}...")
                    update_oled_display([
                        "Link RFID Card",
                        f"Scan card for:",
                        student_name,
                        "Waiting..."
                    ])
                    
                    # Scan to get the UID
                    scan_response = requests.get(f'http://{ESP32_IP}/rfid/scan', timeout=10)
                    if scan_response.status_code != 200:
                        print("Failed to scan RFID card")
                        update_oled_display([
                            "RFID Error",
                            "Scan failed",
                            "Try again",
                            ""
                        ])
                        continue
                    
                    scan_data = scan_response.json()
                    if 'uid' not in scan_data:
                        print("No UID in scan response")
                        update_oled_display([
                            "RFID Error",
                            "No UID found",
                            "Try again",
                            ""
                        ])
                        continue
                    
                    # Convert UID array to string
                    card_uid = '-'.join([f"{b:02x}" for b in scan_data['uid']])
                    
                    # Link the card to the student
                    if link_rfid_card(student_name, card_uid):
                        print(f"RFID card linked to {student_name}")
                        update_oled_display([
                            "RFID Card Linked",
                            f"To: {student_name}",
                            "Success!",
                            ""
                        ])
                    else:
                        print("Failed to link RFID card")
                        update_oled_display([
                            "RFID Error",
                            "Link failed",
                            "Check student name",
                            "and try again"
                        ])
                except Exception as e:
                    print(f"Error linking RFID card: {e}")
                    update_oled_display([
                        "RFID Error",
                        "Connection failed",
                        str(e)[:16],
                        "Try again"
                    ])
            else:
                print("Cannot link RFID cards - ESP32-CAM not available")
                img = create_status_image(
                    "RFID Not Available", 
                    "ESP32-CAM connection required", 
                    "Press 'r' to reconnect camera"
                )
                cv2.imshow('ESP32-CAM Face Recognition', img)

# Clean up
cv2.destroyAllWindows()
print("Program ended")

# Function to mark attendance with RFID
def mark_rfid_attendance():
    """Mark attendance using RFID reader"""
    if not camera_available:
        print("Cannot mark RFID attendance - ESP32-CAM not available")
        update_oled_display([
            "RFID Unavailable", 
            "Camera not connected",
            "Reconnect ESP32-CAM",
            "Try again"
        ])
        return False
        
    rfid_attendance_url = f'http://{ESP32_IP}/rfid/scan'
    
    try:
        print("Checking for RFID attendance...")
        response = requests.get(rfid_attendance_url, timeout=5)
        
        if response.status_code == 200:
            print("RFID scan successful")
            
            # Get student name from the response
            try:
                data = response.json()
                if 'name' in data:
                    student_name = data['name']
                    attendance_status = markRfidAttendance(student_name)
                    if attendance_status:
                        print(f"RFID attendance recorded for {student_name} with status: {attendance_status}")
                        return True
                    else:
                        print(f"No new attendance recorded for {student_name}")
                        return False
                else:
                    print("No student name found in RFID response")
                    update_oled_display([
                        "RFID Error", 
                        "No student name",
                        "found",
                        "Try again"
                    ])
                    return False
            except Exception as e:
                print(f"Error parsing RFID response: {str(e)}")
                update_oled_display([
                    "RFID Error", 
                    "Invalid response",
                    str(e)[:16],
                    "Try again"
                ])
                return False
        else:
            print(f"Failed to scan RFID. Status code: {response.status_code}")
            update_oled_display([
                "RFID Error", 
                f"Status: {response.status_code}",
                "Check ESP32-CAM",
                "firmware"
            ])
            return False
    except Exception as e:
        print(f"Error with RFID scan: {str(e)}")
        update_oled_display([
            "RFID Error", 
            "Connection failed",
            str(e)[:16],
            "Check connection"
        ])
        return False
 
