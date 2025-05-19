# ESP32-CAM Face Recognition Attendance System

This system uses an ESP32-CAM to perform face recognition-based attendance tracking with automatic status marking (present, late, absent) and persistent record keeping in a SQLite database.

## Features

- Face detection and recognition using ESP32-CAM
- Enhanced image processing for dim lighting conditions
- Automatic status tracking:
  - **Present**: If detected before the morning threshold time
  - **Late**: If detected after the morning threshold but before noon
  - **Absent**: If not detected by end of day
- Student tracking:
  - Students are marked as "dropped" after 3 absences
  - Dropped students are no longer recognized by the system
  - Students can be reactivated through the database utility
- Database storage of all attendance records
- Utility scripts for managing attendance data

## Requirements

- ESP32-CAM with appropriate firmware
- Python 3.6+
- Required Python libraries:
  ```
  pip install opencv-python numpy face-recognition requests sqlite3 pandas matplotlib tabulate
  ```

## Setup

1. **Install Dependencies:**

   ```bash
   pip install opencv-python numpy face-recognition requests sqlite3 pandas matplotlib tabulate
   ```

2. **Reference Images:**

   - Create a folder called `image_folder` in the script directory
   - Add clear face images of each person to be recognized
   - Name each image file with the person's name (e.g., `john.jpg`)

3. **ESP32-CAM Setup:**

   - Configure your ESP32-CAM with the appropriate firmware
   - Make sure it's accessible on your network
   - Update the `url` variable in `face_recognition_final.py` with your ESP32-CAM's IP address and port

4. **Configuration:**
   - Edit time thresholds in `face_recognition_final.py` if needed:
     ```python
     PRESENT_TIME_THRESHOLD = time(9, 0)  # 9:00 AM - Present if before this time
     LATE_TIME_THRESHOLD = time(12, 0)    # 12:00 PM - Late if before this time, absent after
     ```

## Usage

1. **Run the Face Recognition System:**

   ```bash
   python face_recognition_final.py
   ```

2. **Key Commands During Operation:**

   - `q`: Quit the program
   - `a`: Process absent students immediately
   - `r`: Refresh student encodings (e.g., after adding new students)

3. **End of Day Processing:**

   - Run the following to mark absent students (can be scheduled):
     ```bash
     python mark_absent.py
     ```

4. **Database Management:**

   ```bash
   # View all students and their status
   python db_utils.py students

   # View attendance for today
   python db_utils.py attendance

   # View attendance for a specific date
   python db_utils.py attendance 2023-10-15

   # Reset absent count for a student
   python db_utils.py reset john

   # Reactivate a dropped student
   python db_utils.py reactivate john

   # Export attendance data (default: last 30 days)
   python db_utils.py export

   # Generate attendance report with visualization
   python db_utils.py report
   ```

## How It Works

1. **Initialization:**

   - The system loads reference images and encodes them
   - It creates/connects to the SQLite database
   - New students from the image folder are added to the database

2. **Face Recognition:**

   - The system captures images from the ESP32-CAM
   - It enhances the image for better face detection in dim lighting
   - Faces are detected, recognized and compared with known faces
   - If a match is found and the student is active, attendance is recorded

3. **Attendance Recording:**

   - Each person is recorded only once per day
   - Status (present/late/absent) is determined by the time of detection
   - All records are stored in the SQLite database

4. **Absence Processing:**
   - At the end of the day, the `mark_absent.py` script marks all non-attending students as absent
   - Absent count is incremented for each absent student
   - Students with 3 or more absences are marked as "dropped"
   - Dropped students are no longer recognized (but can be reactivated)

## Troubleshooting

- **Camera Connection Issues:**

  - Verify your ESP32-CAM IP address is correct
  - Check that the camera is powered on and connected to your network
  - Try accessing the camera stream directly in a browser

- **Face Detection Issues:**

  - Ensure adequate lighting in the environment
  - Make sure reference photos are clear and well-lit
  - Try different resolutions by changing the URL in the code

- **Database Issues:**
  - If database errors occur, check file permissions
  - Use database utilities to view and manage records

## File Structure

- `face_recognition_final.py` - Main face recognition and attendance system
- `db_utils.py` - Database management utilities
- `mark_absent.py` - End-of-day absent student processing
- `attendance.db` - SQLite database with attendance records
- `image_folder/` - Directory containing reference face images
