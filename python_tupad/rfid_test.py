import requests
import time
import json
import sys

# Configuration - change to match your ESP32CAM IP address
ESP32_IP = "192.168.0.156"  # Default IP, change if different
SCAN_ENDPOINT = f"http://{ESP32_IP}/rfid/scan"
RFID_ENDPOINT = f"http://{ESP32_IP}/rfid"
ATTENDANCE_ENDPOINT = f"http://{ESP32_IP}/rfid/attendance"

def get_ip_address():
    """Prompt user for the IP address if needed"""
    global ESP32_IP, SCAN_ENDPOINT, RFID_ENDPOINT, ATTENDANCE_ENDPOINT
    
    ip = input(f"Enter ESP32-CAM IP address [{ESP32_IP}]: ").strip()
    if ip:
        ESP32_IP = ip
        SCAN_ENDPOINT = f"http://{ESP32_IP}/rfid/scan"
        RFID_ENDPOINT = f"http://{ESP32_IP}/rfid"
        ATTENDANCE_ENDPOINT = f"http://{ESP32_IP}/rfid/attendance"
    
    print(f"Using ESP32-CAM at: {ESP32_IP}")

def scan_card():
    """Scan for an RFID card and return its details"""
    print("\n=== SCANNING RFID CARD ===")
    print("Please place a card on the reader...")
    
    try:
        print(f"Sending scan request to {SCAN_ENDPOINT}...")
        
        # Increase timeout for longer scanning time
        response = requests.get(SCAN_ENDPOINT, timeout=15)
        
        if response.status_code == 200:
            print("✓ Successfully received response from ESP32-CAM")
            
            try:
                data = response.json()
                uid = data.get('uid', [])
                uid_hex = ':'.join([f"{byte:02X}" for byte in uid])
                
                print(f"Card detected! UID: {uid_hex}")
                
                # Check if it's a known card
                if data.get('known', False):
                    print(f"This is a known card for: {data.get('name', 'Unknown')}")
                else:
                    print("This is an unknown card")
                    
                return data
            except json.JSONDecodeError:
                print("ERROR: Could not parse JSON response")
                print(f"Response content: {response.text[:200]}")
                return None
        elif response.status_code == 404:
            print("No card was detected during the scan period")
            print(f"Response: {response.text}")
            return None
        elif response.status_code == 500:
            print("ERROR: Internal server error on the ESP32-CAM")
            print(f"Response: {response.text}")
            print("\nPossible hardware issue with the RFID reader module.")
            print("Check the serial monitor on the ESP32-CAM for more details.")
            return None
        else:
            print(f"Scan failed with status code: {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except requests.exceptions.Timeout:
        print("ERROR: Request timed out")
        print("The ESP32-CAM didn't respond within the timeout period.")
        print("This could indicate:")
        print("1. The ESP32-CAM is not powered on")
        print("2. The RFID scanning process is taking too long")
        print("3. There's a network issue")
        return None
    except requests.exceptions.ConnectionError:
        print("ERROR: Connection error")
        print(f"Could not connect to {ESP32_IP}")
        print("Check that:")
        print("1. The ESP32-CAM is powered on")
        print("2. The IP address is correct")
        print("3. Both devices are on the same network")
        return None
    except Exception as e:
        print(f"ERROR: Unexpected error during scan: {str(e)}")
        return None

def add_card():
    """Add a new RFID card to the system"""
    print("\n=== ADDING NEW RFID CARD ===")
    
    # First scan the card
    card_data = scan_card()
    if not card_data or 'uid' not in card_data:
        print("Failed to get card data. Cannot add card.")
        return False
    
    # Get student name
    name = input("Enter student name for this card: ")
    if not name.strip():
        print("Name cannot be empty. Aborting.")
        return False
    
    # Add the card
    try:
        payload = {
            "action": "add",
            "name": name,
            "uid": card_data['uid']
        }
        
        print(f"Adding card for {name}...")
        response = requests.post(RFID_ENDPOINT, json=payload, timeout=5)
        
        if response.status_code == 200:
            print("Card added successfully!")
            print(f"Response: {response.text}")
            return True
        else:
            print(f"Failed to add card. Status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"Error adding card: {str(e)}")
        return False

def list_cards():
    """List all registered RFID cards"""
    print("\n=== LISTING REGISTERED CARDS ===")
    
    try:
        payload = {"action": "list"}
        response = requests.post(RFID_ENDPOINT, json=payload, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            cards = data.get('cards', [])
            
            if not cards:
                print("No registered cards found")
                return []
            
            print(f"Found {len(cards)} registered cards:")
            for i, card in enumerate(cards, 1):
                uid_hex = ':'.join([f"{byte:02X}" for byte in card['uid']])
                print(f"{i}. {card['name']} - UID: {uid_hex}")
            
            return cards
        else:
            print(f"Failed to list cards. Status code: {response.status_code}")
            print(f"Response: {response.text}")
            return []
    except Exception as e:
        print(f"Error listing cards: {str(e)}")
        return []

def mark_attendance():
    """Mark attendance using an RFID card"""
    print("\n=== MARKING ATTENDANCE WITH RFID ===")
    print("Please place a card on the reader...")
    
    try:
        response = requests.post(ATTENDANCE_ENDPOINT, timeout=10)
        
        if response.status_code == 200:
            print("Attendance marked successfully!")
            print(f"Response: {response.text}")
            return True
        else:
            print(f"Failed to mark attendance. Status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"Error marking attendance: {str(e)}")
        return False

def remove_card():
    """Remove/deactivate an RFID card"""
    print("\n=== REMOVING RFID CARD ===")
    
    # First, list all cards
    cards = list_cards()
    if not cards:
        return False
    
    # Ask which card to remove
    choice = input("Enter the number of the card to remove (or scan): ")
    
    if choice.lower() == 'scan':
        # Scan the card instead
        card_data = scan_card()
        if not card_data or 'uid' not in card_data:
            print("Failed to get card data. Cannot remove card.")
            return False
        
        uid = card_data['uid']
    else:
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(cards):
                print("Invalid selection.")
                return False
            
            uid = cards[idx]['uid']
        except ValueError:
            print("Invalid input. Please enter a number or 'scan'.")
            return False
    
    # Remove the card
    try:
        payload = {
            "action": "remove",
            "uid": uid
        }
        
        print("Removing card...")
        response = requests.post(RFID_ENDPOINT, json=payload, timeout=5)
        
        if response.status_code == 200:
            print("Card removed successfully!")
            print(f"Response: {response.text}")
            return True
        else:
            print(f"Failed to remove card. Status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"Error removing card: {str(e)}")
        return False

def show_menu():
    """Display the main menu"""
    print("\n=== RFID TEST MENU ===")
    print("1. Scan RFID Card")
    print("2. Add New Card")
    print("3. List Registered Cards")
    print("4. Mark Attendance")
    print("5. Remove Card")
    print("0. Exit")
    
    choice = input("Enter your choice: ")
    return choice

def main():
    """Main function"""
    get_ip_address()
    
    while True:
        choice = show_menu()
        
        if choice == '1':
            scan_card()
        elif choice == '2':
            add_card()
        elif choice == '3':
            list_cards()
        elif choice == '4':
            mark_attendance()
        elif choice == '5':
            remove_card()
        elif choice == '0':
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please try again.")
        
        # Pause before showing menu again
        input("\nPress Enter to continue...")

if __name__ == "__main__":
    main() 