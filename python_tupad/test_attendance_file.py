import os
from datetime import datetime

def test_attendance_file_access():
    print("Testing Attendance.csv file access...")
    
    # Current directory file
    current_file = 'Attendance.csv'
    
    # Alternative files in current directory
    alt_current_file = 'Attendance_log.txt'
    
    # Temp directory file
    temp_dir = os.environ.get('TEMP', os.path.join(os.path.expanduser("~"), "AppData", "Local", "Temp"))
    temp_file = os.path.join(temp_dir, 'ESP32CAM_Attendance.csv')
    
    # Documents folder file
    docs_folder = os.path.join(os.path.expanduser("~"), "Documents")
    docs_file = os.path.join(docs_folder, 'ESP32CAM_Attendance.csv')
    
    # Desktop folder file
    desktop_folder = os.path.join(os.path.expanduser("~"), "Desktop")
    desktop_file = os.path.join(desktop_folder, 'ESP32CAM_Attendance.csv')
    
    # Test locations
    locations = [
        {"name": "Current directory", "path": current_file},
        {"name": "Alternative file in current dir", "path": alt_current_file},
        {"name": "Temp directory", "path": temp_file},
        {"name": "Documents folder", "path": docs_file},
        {"name": "Desktop folder", "path": desktop_file}
    ]
    
    print(f"Current working directory: {os.getcwd()}")
    print(f"Script location: {os.path.abspath(__file__)}")
    
    for location in locations:
        name = location["name"]
        path = location["path"]
        
        print(f"\nTesting {name}: {path}")
        
        # Check if directory exists
        directory = os.path.dirname(path)
        if directory:
            if os.path.exists(directory):
                print(f"Directory exists: {directory}")
            else:
                print(f"Directory doesn't exist: {directory}")
                try:
                    os.makedirs(directory, exist_ok=True)
                    print(f"Created directory: {directory}")
                except Exception as e:
                    print(f"Failed to create directory: {e}")
        
        # Test file creation
        try:
            with open(path, 'w') as f:
                f.write("Name,Time")
            print(f"✓ Successfully created file")
        except Exception as e:
            print(f"✗ Failed to create file: {e}")
            continue
            
        # Test file writing
        try:
            with open(path, 'a') as f:
                now = datetime.now()
                time_str = now.strftime('%H:%M:%S')
                f.write(f"\nTEST_USER,{time_str}")
            print(f"✓ Successfully wrote to file")
        except Exception as e:
            print(f"✗ Failed to write to file: {e}")
            continue
            
        # Test file reading
        try:
            with open(path, 'r') as f:
                content = f.read()
            print(f"✓ Successfully read file:")
            print(f"  Content: {content}")
        except Exception as e:
            print(f"✗ Failed to read file: {e}")
            
    print("\nTest completed. Use the location that shows all successful operations.")

if __name__ == "__main__":
    test_attendance_file_access() 