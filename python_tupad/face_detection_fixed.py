import cv2
import numpy as np
import face_recognition
import os
from datetime import datetime
import requests
import time

# Path for reference images
path = 'C:\python\image_folder'
# ESP32-CAM URL with correct format
url = 'http://192.168.0.156/640x480.jpg'  # Medium resolution

# Get Documents folder for attendance logging
docs_folder = os.path.join(os.path.expanduser("~"), "Documents")
attendance_file = os.path.join(docs_folder, 'ESP32CAM_Attendance.csv')

# Create Attendance file if it doesn't exist
if not os.path.isfile(attendance_file):
    try:
        with open(attendance_file, 'w') as f:
            f.write('Name,Time')
        print(f"Created attendance file at: {attendance_file}")
    except Exception as e:
        print(f"Could not create attendance file in Documents: {e}")
        # Fall back to current directory
        attendance_file = 'ESP32CAM_Attendance_Log.txt'
        with open(attendance_file, 'w') as f:
            f.write('Name,Time')
        print(f"Created fallback attendance file: {attendance_file}")

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
        else:
            print(f"Error loading image: {cl}")
    print(f"Loaded {len(images)} images successfully")
    print(f"Names: {classNames}")
else:
    print(f"WARNING: Reference images folder not found: {path}")
    print("Please create the folder and add face images for recognition")

# Function to enhance image for better face detection
def enhance_image(image):
    # Convert to LAB color space
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    
    # Split LAB channels
    l, a, b = cv2.split(lab)
    
    # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) to L channel
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    
    # Increase brightness significantly for dim environments
    cl = cv2.add(cl, 30)  # Increased from 15 to 30
    
    # Merge channels back
    limg = cv2.merge((cl, a, b))
    
    # Convert back to BGR
    enhanced = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
    
    # More aggressive contrast enhancement
    alpha = 1.5  # Increased from 1.2 to 1.5
    beta = 25    # Increased from 10 to 25
    enhanced = cv2.convertScaleAbs(enhanced, alpha=alpha, beta=beta)
    
    # Apply additional Gamma correction for very dark images
    gamma = 1.5
    lookUpTable = np.empty((1,256), np.uint8)
    for i in range(256):
        lookUpTable[0,i] = np.clip(pow(i / 255.0, 1.0 / gamma) * 255.0, 0, 255)
    enhanced = cv2.LUT(enhanced, lookUpTable)
    
    return enhanced

def findEncodings(images):
    encodeList = []
    for img in images:
        try:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            encode = face_recognition.face_encodings(img)[0]
            encodeList.append(encode)
        except Exception as e:
            print(f"Error encoding image: {e}")
    return encodeList

def markAttendance(name):
    global attendance_file
    try:
        # Read existing data
        nameList = []
        try:
            with open(attendance_file, 'r') as f:
                myDataList = f.readlines()
                for line in myDataList:
                    entry = line.split(',')
                    nameList.append(entry[0])
        except:
            myDataList = []
            
        # Check if name already exists in file
        if name not in nameList:
            now = datetime.now()
            dtString = now.strftime('%H:%M:%S')
            
            # Append to file
            with open(attendance_file, 'a') as f:
                f.write(f'\n{name},{dtString}')
            print(f"✓ Marked attendance for {name}")
    except Exception as e:
        print(f"Error in markAttendance: {e}")
        # Try one more time with current directory
        try:
            alt_file = "Attendance_backup.txt"
            with open(alt_file, 'a+') as f:
                f.write(f'\n{name},{datetime.now().strftime("%H:%M:%S")}')
            print(f"Marked attendance in backup file: {alt_file}")
        except:
            print("All attendance logging attempts failed")

# Function to get image from ESP32-CAM
def get_image_from_camera():
    try:
        img_resp = requests.get(url, timeout=5)
        if img_resp.status_code == 200:
            img_arr = np.array(bytearray(img_resp.content), dtype=np.uint8)
            img = cv2.imdecode(img_arr, -1)
            if img is None:
                print("Failed to decode image from ESP32-CAM")
                return False, None
                
            # Enhance the image for better face detection
            img = enhance_image(img)
            return True, img
        else:
            print(f"Failed to get image: HTTP status code {img_resp.status_code}")
            return False, None
    except Exception as e:
        print(f"Error accessing ESP32-CAM stream: {e}")
        return False, None

# Check if we have any images to use for recognition
if len(images) == 0:
    print("ERROR: No valid reference images found. Please add images to the folder.")
    exit()

# Encode known faces
print("Encoding reference faces...")
encodeListKnown = findEncodings(images)
print(f'Encoding complete. {len(encodeListKnown)} faces encoded.')

# Initialize with a test image
print("Testing camera connection...")
success, test_img = get_image_from_camera()
if success:
    print(f"Camera connection successful! Image dimensions: {test_img.shape}")
else:
    print("Camera connection failed! Please check your ESP32-CAM connection and URL.")
    print("Make sure the ESP32-CAM is powered on and has the correct IP address.")
    proceed = input("Do you want to continue anyway? (y/n): ")
    if proceed.lower() != 'y':
        exit()

# Main loop
print("Starting face recognition. Press 'q' to exit.")
while True:
    # Get image from ESP32-CAM
    success, img = get_image_from_camera()
    
    if not success:
        print(f"Failed to get image from ESP32-CAM at {url}. Retrying in 2 seconds...")
        time.sleep(2)
        continue
    
    # Ensure img is not None before processing
    if img is None:
        print("Image is None. Retrying...")
        time.sleep(2)
        continue
    
    # Process the image (scale down for faster processing)
    imgS = cv2.resize(img, (0, 0), None, 0.25, 0.25)
    imgS = cv2.cvtColor(imgS, cv2.COLOR_BGR2RGB)

    # Option 1: Standard HOG-based model (default, faster)
    facesCurFrame = face_recognition.face_locations(imgS)
    
    # If no faces found with standard method, try enhanced methods
    if len(facesCurFrame) == 0:
        print("No faces found with standard detection, trying enhanced methods...")
        
        # Try with increased brightness for detection
        detection_img = cv2.convertScaleAbs(imgS, alpha=1.8, beta=70)
        facesCurFrame = face_recognition.face_locations(detection_img)
    
    # If faces were found, display count
    if len(facesCurFrame) > 0:
        print(f"Found {len(facesCurFrame)} faces")
    
    # Get face encodings for the found faces
    encodesCurFrame = face_recognition.face_encodings(imgS, facesCurFrame)

    # Compare with known faces
    for encodeFace, faceLoc in zip(encodesCurFrame, facesCurFrame):
        matches = face_recognition.compare_faces(encodeListKnown, encodeFace)
        faceDis = face_recognition.face_distance(encodeListKnown, encodeFace)
        
        # If we have matches
        if len(faceDis) > 0:
            matchIndex = np.argmin(faceDis)
            
            if matches[matchIndex]:
                name = classNames[matchIndex].upper()
                
                # Mark face on image
                y1, x2, y2, x1 = faceLoc
                y1, x2, y2, x1 = y1 * 4, x2 * 4, y2 * 4, x1 * 4
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.rectangle(img, (x1, y2 - 35), (x2, y2), (0, 255, 0), cv2.FILLED)
                cv2.putText(img, name, (x1 + 6, y2 - 6), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 255, 255), 2)
                
                # Log attendance
                markAttendance(name)

    # Show the image with face recognition
    cv2.imshow('ESP32-CAM Face Recognition', img)
    
    # Press 'q' to exit
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
        
# Clean up
cv2.destroyAllWindows()
print(f"Attendance log saved to: {attendance_file}") 