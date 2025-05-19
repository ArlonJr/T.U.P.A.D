import cv2
import numpy as np
import requests
import time

# ESP32-CAM URL
url = 'http://192.168.0.156/cam-hi.jpg'

print(f"Attempting to connect to ESP32-CAM at: {url}")

# Try to get an image
try:
    img_resp = requests.get(url, timeout=5)
    print(f"Response status code: {img_resp.status_code}")
    print(f"Response headers: {img_resp.headers}")
    
    if img_resp.status_code == 200:
        print(f"Content length: {len(img_resp.content)} bytes")
        img_arr = np.array(bytearray(img_resp.content), dtype=np.uint8)
        img = cv2.imdecode(img_arr, -1)
        
        if img is not None:
            print(f"Successfully decoded image. Dimensions: {img.shape}")
            
            # Display the image
            cv2.imshow('ESP32-CAM Test', img)
            print("Press any key to exit...")
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        else:
            print("Failed to decode image - received data is not a valid image")
    else:
        print(f"Failed to get image: HTTP status code {img_resp.status_code}")
        
except Exception as e:
    print(f"Error accessing ESP32-CAM: {e}")

# Try alternative URLs if the main one fails
alternative_urls = [
    'http://192.168.0.156/cam.jpg',
    'http://192.168.0.156/cam-lo.jpg',
    'http://192.168.0.156/snapshot.jpg',
    'http://192.168.0.156:81/stream'
]

for alt_url in alternative_urls:
    print(f"\nTrying alternative URL: {alt_url}")
    try:
        img_resp = requests.get(alt_url, timeout=2)
        print(f"Response status code: {img_resp.status_code}")
        if img_resp.status_code == 200:
            print("Connection successful!")
    except Exception as e:
        print(f"Error: {e}") 