import requests
from bs4 import BeautifulSoup

# ESP32-CAM base URL
base_url = 'http://192.168.0.156'

print(f"Attempting to connect to ESP32-CAM main page at: {base_url}")

try:
    # Get the main index page
    response = requests.get(base_url, timeout=5)
    print(f"Response status code: {response.status_code}")
    
    if response.status_code == 200:
        print(f"Content length: {len(response.content)} bytes")
        print("\nFirst 1000 characters of the response:")
        print(response.text[:1000])
        
        # Try to parse HTML and find links
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            print("\nLinks found on the page:")
            for link in soup.find_all('a'):
                print(f"- {link.get('href')}: {link.text}")
        except Exception as e:
            print(f"Error parsing HTML: {e}")
    else:
        print(f"Failed to access main page: HTTP status code {response.status_code}")
        
except Exception as e:
    print(f"Error accessing ESP32-CAM: {e}")

# Try some common ESP32-CAM endpoints
endpoints = [
    '/',
    '/status',
    '/capture',
    '/stream',
    '/jpg',
    '/mjpeg',
]

print("\nTrying common ESP32-CAM endpoints:")
for endpoint in endpoints:
    url = base_url + endpoint
    try:
        response = requests.get(url, timeout=2)
        print(f"{url}: {response.status_code}")
    except Exception as e:
        print(f"{url}: Error - {e}") 