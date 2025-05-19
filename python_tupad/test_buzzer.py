import requests
import time
import socket
import subprocess
import sys

def verify_ip(ip):
    """Check if an IP address is reachable"""
    try:
        # Try to ping the IP (works on most platforms)
        print(f"Pinging {ip}...")
        
        # Use different ping parameters based on platform
        param = '-n' if sys.platform.lower() == 'win32' else '-c'
        command = ['ping', param, '1', ip]
        
        # Run the ping command
        return subprocess.call(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
    except:
        return False

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
        
        # Add a few IPs from local network range
        for i in range(1, 10):
            common_ips.append(f"{network_prefix}.{i}")
    except:
        pass
    
    print("Checking common ESP32-CAM IP addresses...")
    
    for ip in common_ips:
        if verify_ip(ip):
            try:
                print(f"Found device at {ip}, checking for ESP32-CAM...")
                response = requests.get(f"http://{ip}/", timeout=1)
                if response.status_code == 200:
                    print(f"Found ESP32-CAM at {ip}")
                    return ip
            except:
                continue
    
    return None

# ESP32-CAM IP address
ESP32_IP = "192.168.0.156"  # Default IP

# Check connectivity and update IP if needed
if not verify_ip(ESP32_IP):
    print(f"Could not connect to ESP32-CAM at {ESP32_IP}")
    found_ip = find_esp32cam()
    
    if found_ip:
        ESP32_IP = found_ip
        print(f"Using discovered IP: {ESP32_IP}")
    else:
        print("Could not find ESP32-CAM automatically")
        custom_ip = input("Enter ESP32-CAM IP address manually: ")
        if custom_ip.strip():
            ESP32_IP = custom_ip.strip()

buzzer_url = f'http://{ESP32_IP}/buzzer'

def test_buzzer():
    print(f"Testing buzzer at {buzzer_url}")
    
    # Test each status
    statuses = ["present", "late", "absent", "test"]
    
    for status in statuses:
        print(f"\nTesting '{status}' sound...")
        try:
            print(f"Sending request to {buzzer_url}")
            response = requests.post(buzzer_url, json={"status": status}, timeout=5)
            print(f"Response status code: {response.status_code}")
            print(f"Response content: {response.text}")
            
            if response.status_code == 200:
                print(f"Successfully played {status} sound")
            else:
                print(f"Failed to play {status} sound")
                
            # Wait between sounds
            time.sleep(2)
            
        except requests.exceptions.ConnectionError:
            print(f"Connection error: Could not connect to ESP32-CAM at {buzzer_url}")
            print("Please check if ESP32-CAM is powered on and connected to the network")
            return
        except requests.exceptions.Timeout:
            print("Timeout error: ESP32-CAM did not respond in time")
            return
        except Exception as e:
            print(f"Error: {str(e)}")
            return

if __name__ == "__main__":
    test_buzzer() 