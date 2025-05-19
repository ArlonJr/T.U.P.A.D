import sqlite3
from datetime import datetime
import time

def force_drop_student(student_name):
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            conn = sqlite3.connect('attendance.db', timeout=20)
            cursor = conn.cursor()
            
            # Update student status to dropped
            cursor.execute("""
                UPDATE students 
                SET status = 'dropped', 
                    last_updated = ? 
                WHERE name = ?
            """, (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), student_name))
            
            conn.commit()
            print(f"Student {student_name} has been marked as dropped.")
            conn.close()
            return True
            
        except sqlite3.Error as e:
            print(f"Database error (attempt {retry_count + 1}/{max_retries}): {e}")
            retry_count += 1
            if retry_count < max_retries:
                print("Retrying in 2 seconds...")
                time.sleep(2)
            else:
                print("Failed to update after multiple attempts.")
                return False
        finally:
            if 'conn' in locals():
                conn.close()

# Drop the student
student_name = "Jarl Leander L. Madamba"
force_drop_student(student_name) 