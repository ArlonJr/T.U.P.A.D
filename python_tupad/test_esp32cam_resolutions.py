import requests
import cv2
import numpy as np

# ESP32-CAM base URL
base_url = 'http://192.168.0.156'

# Try to get the resolutions.csv file
try:
    response = requests.get(f"{base_url}/resolutions.csv", timeout=5)
    if response.status_code == 200:
        resolutions = response.text.strip().split('\n')
        print(f"Available resolutions: {resolutions}")
        
        # Try each resolution with JPG format
        for resolution in resolutions:
            url = f"{base_url}/{resolution}.jpg"
            print(f"\nTrying URL: {url}")
            try:
                img_resp = requests.get(url, timeout=5)
                if img_resp.status_code == 200:
                    print(f"Success! Content length: {len(img_resp.content)} bytes")
                    
                    # Try to decode the image
                    img_arr = np.array(bytearray(img_resp.content), dtype=np.uint8)
                    img = cv2.imdecode(img_arr, -1)
                    
                    if img is not None:
                        print(f"Successfully decoded image. Dimensions: {img.shape}")
                        # Save the image
                        cv2.imwrite(f"{resolution}.jpg", img)
                        print(f"Saved image as {resolution}.jpg")
                    else:
                        print("Failed to decode image data")
                else:
                    print(f"Failed with status code: {img_resp.status_code}")
            except Exception as e:
                print(f"Error: {e}")
    else:
        print(f"Failed to get resolutions.csv: {response.status_code}")
except Exception as e:
    print(f"Error accessing resolutions: {e}")
    
    # Try some common resolutions
    common_resolutions = [
        "QQVGA", "QVGA", "VGA", "SVGA", "XGA", "SXGA", "UXGA", 
        "96x96", "160x120", "176x144", "240x176", "240x240", 
        "320x240", "400x296", "480x320", "640x480", "800x600", 
        "1024x768", "1280x720", "1280x1024", "1600x1200"
    ]
    
    print("\nTrying common resolutions:")
    for resolution in common_resolutions:
        url = f"{base_url}/{resolution}.jpg"
        try:
            response = requests.get(url, timeout=2)
            print(f"{url}: {response.status_code}")
            if response.status_code == 200:
                print(f"Found valid resolution: {resolution}")
                
                # Try to decode and save the image
                img_arr = np.array(bytearray(response.content), dtype=np.uint8)
                img = cv2.imdecode(img_arr, -1)
                if img is not None:
                    print(f"Successfully decoded image. Dimensions: {img.shape}")
                    cv2.imwrite(f"{resolution}.jpg", img)
                    print(f"Saved image as {resolution}.jpg")
        except Exception as e:
            pass  # Skip errors to make output cleaner 