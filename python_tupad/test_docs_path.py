import os
import traceback
from datetime import datetime

# Try to create and write to a file in Documents folder
try:
    # Get Documents folder path
    docs_folder = os.path.join(os.path.expanduser("~"), "Documents")
    print(f"Documents folder path: {docs_folder}")
    print(f"Does it exist? {os.path.exists(docs_folder)}")
    
    # Create test file path
    test_file = os.path.join(docs_folder, "ESP32CAM_test.csv")
    print(f"Test file path: {test_file}")
    
    # Try to write to the file
    print("Attempting to write to file...")
    with open(test_file, 'w') as f:
        f.write("Name,Time")
    print("Successfully created file!")
    
    # Append to the file
    with open(test_file, 'a') as f:
        now = datetime.now()
        time_str = now.strftime('%H:%M:%S')
        f.write(f"\nTEST_USER,{time_str}")
    print("Successfully appended to file!")
    
    # Read the file
    with open(test_file, 'r') as f:
        content = f.read()
    print(f"File contents: {content}")
    
    print("\nSUCCESS! You can use the Documents folder for attendance logging.")
    print(f"Full path: {test_file}")
    
except Exception as e:
    print(f"ERROR: {e}")
    print("\nDetailed error information:")
    traceback.print_exc()
    
    # Try desktop instead
    try:
        print("\nTrying Desktop folder instead...")
        desktop_folder = os.path.join(os.path.expanduser("~"), "Desktop")
        print(f"Desktop folder path: {desktop_folder}")
        
        if os.path.exists(desktop_folder):
            test_file = os.path.join(desktop_folder, "ESP32CAM_test.csv")
            with open(test_file, 'w') as f:
                f.write("Name,Time")
            print(f"Successfully wrote to Desktop: {test_file}")
        else:
            print(f"Desktop folder doesn't exist at {desktop_folder}")
    except Exception as e2:
        print(f"Desktop attempt also failed: {e2}")
        
        # Try current directory with different file name
        try:
            print("\nTrying current directory with different filename...")
            test_file = "ESP32CAM_Attendance_Log.txt"  # use txt extension as it might have fewer restrictions
            with open(test_file, 'w') as f:
                f.write("Name,Time")
            print(f"Successfully wrote to current directory: {test_file}")
            print(f"Full path: {os.path.abspath(test_file)}")
        except Exception as e3:
            print(f"All attempts failed: {e3}")
            print("You may need to run the program as administrator.") 