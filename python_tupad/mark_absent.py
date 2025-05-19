import sqlite3
import os
from datetime import datetime

# Database file path
db_file = 'attendance.db'

def mark_absent_students():
    """
    Mark all active students who didn't attend today as absent
    Increment their absent count and check for drops
    
    This should be run at the end of the day (can be scheduled via cron/task scheduler)
    """
    print(f"=== Processing Absences for {datetime.now().strftime('%Y-%m-%d')} ===")
    
    if not os.path.exists(db_file):
        print(f"Database file {db_file} not found.")
        return
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Get current date
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # Get all active students
        cursor.execute("SELECT name FROM students WHERE status='active'")
        active_students = cursor.fetchall()
        
        if not active_students:
            print("No active students found in the database.")
            return
            
        print(f"Found {len(active_students)} active students")
        
        # Get students who attended today
        cursor.execute("SELECT student_name FROM attendance WHERE date=?", (current_date,))
        attended_students = [record[0] for record in cursor.fetchall()]
        
        print(f"{len(attended_students)} students already recorded for today")
        
        # Track absent students
        absent_count = 0
        dropped_count = 0
        
        # Process absent students
        for student in active_students:
            name = student[0]
            if name not in attended_students:
                # Student was absent today
                print(f"Student {name} is absent today")
                
                # Record absence
                cursor.execute(
                    "INSERT OR IGNORE INTO attendance (student_name, date, time, status) VALUES (?, ?, ?, ?)",
                    (name, current_date, "23:59:59", "absent")
                )
                
                # Increment absent count
                cursor.execute("UPDATE students SET absent_count = absent_count + 1 WHERE name=?", (name,))
                
                # Check if student should be dropped
                cursor.execute("SELECT absent_count FROM students WHERE name=?", (name,))
                absent_count_record = cursor.fetchone()
                
                if absent_count_record:
                    absent_count_value = absent_count_record[0]
                    print(f"Student {name} has {absent_count_value} absences")
                    
                    if absent_count_value >= 3:
                        # Mark student as dropped
                        cursor.execute("UPDATE students SET status='dropped' WHERE name=?", (name,))
                        print(f"Student {name} has been dropped due to {absent_count_value} absences")
                        dropped_count += 1
                        
                absent_count += 1
        
        conn.commit()
        
        print(f"\nSummary:")
        print(f"- Total active students: {len(active_students)}")
        print(f"- Students who attended: {len(attended_students)}")
        print(f"- Students marked absent: {absent_count}")
        print(f"- Students dropped: {dropped_count}")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

def reset_daily_records():
    """Reset attendance records for testing purposes (should not be used in production)"""
    if not os.path.exists(db_file):
        print(f"Database file {db_file} not found.")
        return
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Get current date
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # Delete today's records
        cursor.execute("DELETE FROM attendance WHERE date=?", (current_date,))
        conn.commit()
        
        print(f"Deleted all attendance records for {current_date}")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    import sys
    
    # Check for reset flag (for testing only)
    if len(sys.argv) > 1 and sys.argv[1] == '--reset':
        print("WARNING: Resetting today's attendance records!")
        reset_daily_records()
    else:
        # Run the main function to mark absent students
        mark_absent_students() 