import cv2
import numpy as np
import face_recognition
import requests
import time

# ESP32-CAM URL
base_url = 'http://192.168.0.156'
url = f'{base_url}/640x480.jpg'  # Change resolution as needed

# Function to enhance image brightness and contrast
def enhance_image(image):
    # Convert to LAB color space
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    
    # Split LAB channels
    l, a, b = cv2.split(lab)
    
    # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) to L channel
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    
    # Increase brightness
    cl = cv2.add(cl, 15)
    
    # Merge channels back
    limg = cv2.merge((cl, a, b))
    
    # Convert back to BGR
    enhanced = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
    
    # Additional contrast enhancement
    alpha = 1.2  # Contrast (1.0-3.0)
    beta = 10    # Brightness (0-100)
    enhanced = cv2.convertScaleAbs(enhanced, alpha=alpha, beta=beta)
    
    return enhanced

def get_image():
    try:
        img_resp = requests.get(url, timeout=5)
        if img_resp.status_code == 200:
            img_arr = np.array(bytearray(img_resp.content), dtype=np.uint8)
            img = cv2.imdecode(img_arr, -1)
            return img
        else:
            print(f"Failed to get image: {img_resp.status_code}")
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None

# Function to detect faces with various methods
def detect_faces(image):
    # Downscale for faster processing
    small_frame = cv2.resize(image, (0, 0), fx=0.25, fy=0.25)
    
    # Convert to RGB (face_recognition uses RGB)
    rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
    
    # Method 1: Standard HOG-based detection
    print("Trying standard HOG detection...")
    face_locations_hog = face_recognition.face_locations(rgb_small_frame)
    
    # Method 2: Enhanced image with HOG
    print("Trying enhanced image with HOG detection...")
    enhanced_small = enhance_image(small_frame)
    enhanced_rgb = cv2.cvtColor(enhanced_small, cv2.COLOR_BGR2RGB)
    face_locations_enhanced = face_recognition.face_locations(enhanced_rgb)
    
    # Method 3: Extra bright image for detection only
    print("Trying extra brightness for detection...")
    extra_bright = cv2.convertScaleAbs(rgb_small_frame, alpha=1.5, beta=50)
    face_locations_bright = face_recognition.face_locations(extra_bright)
    
    # Uncomment for CNN-based detection (very slow but more accurate)
    # print("Trying CNN detection...")
    # face_locations_cnn = face_recognition.face_locations(rgb_small_frame, model="cnn")
    
    return {
        "original": face_locations_hog,
        "enhanced": face_locations_enhanced,
        "bright": face_locations_bright,
        # "cnn": face_locations_cnn
    }

# Main function
def main():
    # Get original image
    print(f"Getting image from: {url}")
    original = get_image()
    
    if original is None:
        print("Failed to get image!")
        return
    
    # Create enhanced version
    enhanced = enhance_image(original)
    
    # Show the images side by side
    comparison = np.hstack((original, enhanced))
    cv2.imshow("Original vs Enhanced", comparison)
    cv2.waitKey(1)
    
    # Try to detect faces using different methods
    print("\nDetecting faces...")
    face_results = detect_faces(original)
    
    # Show results
    print("\nDetection Results:")
    for method, faces in face_results.items():
        print(f"- {method}: {len(faces)} faces found")
    
    # Mark faces on the images
    for method, face_locations in face_results.items():
        img_copy = enhanced.copy() if method == "enhanced" else original.copy()
        
        # Draw rectangles around faces
        for (top, right, bottom, left) in face_locations:
            # Scale back up face locations
            top *= 4
            right *= 4
            bottom *= 4
            left *= 4
            
            # Draw a box around the face
            cv2.rectangle(img_copy, (left, top), (right, bottom), (0, 255, 0), 2)
            
            # Draw a label with method name
            cv2.rectangle(img_copy, (left, bottom - 35), (right, bottom), (0, 255, 0), cv2.FILLED)
            cv2.putText(img_copy, method, (left + 6, bottom - 6), cv2.FONT_HERSHEY_DUPLEX, 1.0, (255, 255, 255), 1)
        
        # Display the resulting image
        cv2.imshow(f"Faces detected with {method}", img_copy)
    
    # Save comparison
    cv2.imwrite("face_detection_comparison.jpg", comparison)
    print("\nSaved face_detection_comparison.jpg")
    
    print("\nPress any key to exit...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main() 