import cv2
import numpy as np
import face_recognition
import os
from datetime import datetime
import requests
import time

# from PIL import ImageGrab

path = 'C:\python\image_folder'
# Updated URL format based on ESP32-CAM WifiCam firmware
# Choose a resolution that balances quality and performance
# Lower resolution is faster but less accurate, higher resolution is more accurate but slower
url = 'http://192.168.0.156/640x480.jpg'  # Medium resolution
# url = 'http://192.168.0.156/320x240.jpg'  # Low resolution (faster)
# url = 'http://192.168.0.156/1280x720.jpg'  # High resolution (more accurate)

images = []
classNames = []
myList = os.listdir(path)
print(myList)
for cl in myList:
    curImg = cv2.imread(f'{path}/{cl}')
    images.append(curImg)
    classNames.append(os.path.splitext(cl)[0])
print(classNames)

# Check if the image folder is empty
if len(images) == 0:
    print("ERROR: No images found in the folder. Please add reference face images.")
    print(f"Add JPG images of faces to: {path}")
    exit()

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

# Get Documents folder for attendance logging
docs_folder = os.path.join(os.path.expanduser("~"), "Documents")
attendance_file = os.path.join(docs_folder, 'ESP32CAM_Attendance.csv')

def markAttendance(name):
    global attendance_file  # Make the variable accessible inside the function
    try:
        # Make sure Documents folder exists
        if not os.path.exists(docs_folder):
            try:
                os.makedirs(docs_folder, exist_ok=True)
            except Exception as e:
                print(f"Cannot create Documents folder: {e}")
                # Fall back to current directory
                global attendance_file  # Declare again to be sure
                attendance_file = 'ESP32CAM_Attendance_Log.txt'
        
        # Check if file exists, if not create it with header
        if not os.path.isfile(attendance_file):
            with open(attendance_file, 'w') as f:
                f.write('Name,Time')
            print(f"Created attendance file at: {attendance_file}")
        
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
            print(f"Marked attendance for {name}")
    except Exception as e:
        print(f"Error in markAttendance: {e}")
        # Don't attempt alternative locations - we've already identified Documents works

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

# Function to enhance image brightness and contrast
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

# Initialize with a test image
print("Testing camera connection...")
success, test_img = get_image_from_camera()
if success:
    print(f"Camera connection successful! Image dimensions: {test_img.shape}")
else:
    print("Camera connection failed! Please check your ESP32-CAM connection and URL.")
    print("You can run test_esp32cam_resolutions.py to find valid resolutions.")

encodeListKnown = findEncodings(images)
print('Encoding Complete')

# Use ESP32-CAM instead of webcam
# cap = cv2.VideoCapture(0)

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
    
    # Save a copy of the original image for display
    original_img = img.copy()
    
    # Process the image
    imgS = cv2.resize(img, (0, 0), None, 0.25, 0.25)
    imgS = cv2.cvtColor(imgS, cv2.COLOR_BGR2RGB)

    # Try different face detection models/parameters for better detection in dim lighting
    # Option 1: Standard HOG-based model (default, faster but less accurate in dim light)
    facesCurFrame = face_recognition.face_locations(imgS)
    
    # If no faces found with standard method, try alternative methods
    if len(facesCurFrame) == 0:
        print("No faces found with standard detection, trying enhanced methods...")
        
        # Option 2: Try with increased brightness for detection
        detection_img = cv2.convertScaleAbs(imgS, alpha=1.8, beta=70)  # Very aggressive enhancement just for detection
        facesCurFrame = face_recognition.face_locations(detection_img)
        
        # Option 3: Try with different model parameter (CPU intensive)
        if len(facesCurFrame) == 0 and len(encodeListKnown) > 0:
            print("Still no faces found, trying with lower tolerance...")
            # Use a more aggressive approach with the first face as reference
            # This might help in very dim conditions
            face_locations = []
            face_encodings = face_recognition.face_encodings(detection_img)
            
            if len(face_encodings) > 0:
                # Compare with known faces with lower threshold
                for face_encoding in face_encodings:
                    matches = face_recognition.compare_faces(encodeListKnown, face_encoding, tolerance=0.7)  # Higher tolerance (default is 0.6)
                    if True in matches:
                        # We found a match, get its face location
                        for i, match in enumerate(matches):
                            if match:
                                # Manually create a face location since we know there's a match
                                # This is an estimate based on center of image
                                h, w = imgS.shape[:2]
                                face_locations.append((int(h*0.25), int(w*0.75), int(h*0.75), int(w*0.25)))
                                break
                
                facesCurFrame = face_locations
    
    # Print number of faces found
    if len(facesCurFrame) > 0:
        print(f"Found {len(facesCurFrame)} faces")
    
    encodesCurFrame = face_recognition.face_encodings(imgS, facesCurFrame)

    for encodeFace, faceLoc in zip(encodesCurFrame, facesCurFrame):
        matches = face_recognition.compare_faces(encodeListKnown, encodeFace)
        faceDis = face_recognition.face_distance(encodeListKnown, encodeFace)
# print(faceDis)
        matchIndex = np.argmin(faceDis)

        if matches[matchIndex]:
            name = classNames[matchIndex].upper()
# print(name)
            y1, x2, y2, x1 = faceLoc
            y1, x2, y2, x1 = y1 * 4, x2 * 4, y2 * 4, x1 * 4
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.rectangle(img, (x1, y2 - 35), (x2, y2), (0, 255, 0), cv2.FILLED)
            cv2.putText(img, name, (x1 + 6, y2 - 6), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 255, 255), 2)
            markAttendance(name)

    cv2.imshow('ESP32-CAM', img)
    
    # Press 'q' to exit
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
        
cv2.destroyAllWindows()
