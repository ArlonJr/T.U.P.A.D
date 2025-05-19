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
    
    # Increase brightness significantly
    cl = cv2.add(cl, 30)
    
    # Merge channels back
    limg = cv2.merge((cl, a, b))
    
    # Convert back to BGR
    enhanced = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
    
    # More aggressive contrast enhancement
    alpha = 1.5
    beta = 25
    enhanced = cv2.convertScaleAbs(enhanced, alpha=alpha, beta=beta)
    
    # Apply gamma correction
    gamma = 1.5
    lookUpTable = np.empty((1,256), np.uint8)
    for i in range(256):
        lookUpTable[0,i] = np.clip(pow(i / 255.0, 1.0 / gamma) * 255.0, 0, 255)
    enhanced = cv2.LUT(enhanced, lookUpTable)
    
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

def main():
    print("Starting lighting test...")
    print("This script will help you test the effect of adding light sources")
    print("1. First, we'll show the camera view without additional lighting")
    print("2. Then you can use a flashlight, lamp, or phone light to illuminate the face")
    print("3. The script will try to detect faces in both conditions")
    
    input("Press Enter to start the test without additional lighting...")
    
    # Get image without flashlight
    print("Capturing image without additional lighting...")
    dark_img = get_image()
    if dark_img is None:
        print("Failed to get image!")
        return
    
    # Try to detect faces
    print("Detecting faces without additional lighting...")
    dark_small = cv2.resize(dark_img, (0, 0), fx=0.25, fy=0.25)
    dark_rgb = cv2.cvtColor(dark_small, cv2.COLOR_BGR2RGB)
    dark_faces = face_recognition.face_locations(dark_rgb)
    
    # Save dark image
    cv2.imwrite("dark_condition.jpg", dark_img)
    print(f"Found {len(dark_faces)} faces without additional lighting")
    
    # Mark faces on the dark image
    dark_with_faces = dark_img.copy()
    for (top, right, bottom, left) in dark_faces:
        # Scale back up
        top *= 4
        right *= 4
        bottom *= 4
        left *= 4
        
        cv2.rectangle(dark_with_faces, (left, top), (right, bottom), (0, 255, 0), 2)
    
    # Show dark image
    cv2.imshow("Without additional lighting", dark_with_faces)
    cv2.waitKey(1)
    
    # Now test with flashlight
    input("\nNow add your light source (flashlight, phone light, lamp, etc.)\nPosition it to illuminate the face, then press Enter...")
    
    # Get image with flashlight
    print("Capturing image with additional lighting...")
    light_img = get_image()
    if light_img is None:
        print("Failed to get image!")
        return
    
    # Try to detect faces
    print("Detecting faces with additional lighting...")
    light_small = cv2.resize(light_img, (0, 0), fx=0.25, fy=0.25)
    light_rgb = cv2.cvtColor(light_small, cv2.COLOR_BGR2RGB)
    light_faces = face_recognition.face_locations(light_rgb)
    
    # Save light image
    cv2.imwrite("light_condition.jpg", light_img)
    print(f"Found {len(light_faces)} faces with additional lighting")
    
    # Mark faces on the light image
    light_with_faces = light_img.copy()
    for (top, right, bottom, left) in light_faces:
        # Scale back up
        top *= 4
        right *= 4
        bottom *= 4
        left *= 4
        
        cv2.rectangle(light_with_faces, (left, top), (right, bottom), (0, 255, 0), 2)
    
    # Show the images side by side
    h1, w1 = dark_with_faces.shape[:2]
    h2, w2 = light_with_faces.shape[:2]
    
    # Ensure same size for comparison
    if (h1, w1) != (h2, w2):
        light_with_faces = cv2.resize(light_with_faces, (w1, h1))
    
    comparison = np.hstack((dark_with_faces, light_with_faces))
    cv2.imshow("Without light (left) vs With light (right)", comparison)
    cv2.imwrite("lighting_comparison.jpg", comparison)
    
    print("\nResults:")
    print(f"- Without additional lighting: {len(dark_faces)} faces detected")
    print(f"- With additional lighting: {len(light_faces)} faces detected")
    
    if len(light_faces) > len(dark_faces):
        print("\nConclusion: Additional lighting IMPROVED face detection!")
        print("Recommendation: Use a lamp, LED light, or flashlight to improve detection")
    elif len(light_faces) == len(dark_faces):
        if len(light_faces) > 0:
            print("\nConclusion: Both conditions detected faces, but lighting may improve reliability")
        else:
            print("\nConclusion: No faces detected in either condition")
            print("Try moving closer to the camera or improving the lighting further")
    else:
        print("\nConclusion: Unexpected result - fewer faces with lighting")
        print("This may be due to glare or reflections. Try adjusting the light angle.")
    
    print("\nSaved comparison as lighting_comparison.jpg")
    print("Press any key to exit...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main() 