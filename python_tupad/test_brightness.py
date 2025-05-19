import requests
import cv2
import numpy as np
import time

# ESP32-CAM base URL
base_url = 'http://192.168.0.156'

# Camera control parameters to adjust
# Available parameters:
# - brightness: -2 to 2
# - contrast: -2 to 2
# - saturation: -2 to 2
# - special_effect: 0=none, 1=negative, 2=grayscale, 3=red, 4=green, 5=blue, 6=sepia
# - wb_mode: 0=auto, 1=sunny, 2=cloudy, 3=office, 4=home
# - awb: 0/1 auto white balance
# - awb_gain: 0/1 auto white balance gain
# - gainceiling: 0 to 6 (more gain for darker environments)

def adjust_camera(param, value):
    try:
        url = f"{base_url}/control?var={param}&val={value}"
        response = requests.get(url, timeout=2)
        print(f"Setting {param}={value}: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error setting {param}: {e}")
        return False

def get_image(resolution="640x480"):
    try:
        url = f"{base_url}/{resolution}.jpg"
        img_resp = requests.get(url, timeout=5)
        if img_resp.status_code == 200:
            img_arr = np.array(bytearray(img_resp.content), dtype=np.uint8)
            img = cv2.imdecode(img_arr, -1)
            return img
        else:
            print(f"Failed to get image: {img_resp.status_code}")
            return None
    except Exception as e:
        print(f"Error getting image: {e}")
        return None

# First get baseline image
print("Getting baseline image...")
baseline = get_image()
if baseline is not None:
    cv2.imwrite("baseline.jpg", baseline)
    print("Saved baseline.jpg")

# Increase brightness
print("\nAdjusting camera settings for better face detection...")

# Try to increase brightness
adjust_camera("brightness", 1)
time.sleep(0.5)

# Increase contrast
adjust_camera("contrast", 1)
time.sleep(0.5)

# Increase gain for low light
adjust_camera("gainceiling", 5)  # Higher gain for dark environments
time.sleep(0.5)

# Set white balance to auto
adjust_camera("awb", 1)
time.sleep(0.5)
adjust_camera("awb_gain", 1)
time.sleep(0.5)

# Get final image
print("\nGetting final image with adjusted settings...")
final = get_image()
if final is not None:
    cv2.imwrite("adjusted.jpg", final)
    print("Saved adjusted.jpg")
    
    # Display comparison
    if baseline is not None:
        comparison = np.hstack((baseline, final))
        cv2.imwrite("comparison.jpg", comparison)
        print("Saved comparison.jpg")
        
        cv2.imshow("Before (left) vs After (right)", comparison)
        print("Press any key to exit...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    
print("\nOptimal camera settings:")
print("1. Try these settings in your code first:")
print("   - brightness=1")
print("   - contrast=1")
print("   - gainceiling=5")
print("\n2. If still too dark, you can try further adjustments:")
print("   - brightness=2 (maximum)")
print("   - gainceiling=6 (maximum gain)")
print("\n3. If it's noisy/grainy, try reducing gain:")
print("   - gainceiling=3 or 4")

print("\nYou can add these settings to your face detection code.")
print("Check the comparison.jpg file to see the difference.") 