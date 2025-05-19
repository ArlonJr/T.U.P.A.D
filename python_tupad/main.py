import sqlite3
from datetime import datetime

def mark_absence(student_name):
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    # Record absence
    date = datetime.now().strftime('%Y-%m-%d')
    cursor.execute(
        "INSERT OR IGNORE INTO attendance (student_name, date, time, status) VALUES (?, ?, ?, ?)",
        (student_name, date, datetime.now().strftime('%H:%M:%S'), "absent")
    )
    
    # Increment absent count
    cursor.execute("""
        UPDATE students 
        SET absent_count = absent_count + 1
        WHERE name=?
    """, (student_name,))
    
    # Check if student should be dropped (3 total absences)
    cursor.execute("SELECT absent_count FROM students WHERE name=?", (student_name,))
    absent_count = cursor.fetchone()[0]
    
    if absent_count >= 3:
        cursor.execute("UPDATE students SET status='dropped' WHERE name=?", (student_name,))
        print(f"Student {student_name} has been dropped due to {absent_count} total absences")
    
    conn.commit()
    conn.close()

def mark_present(student_name):
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    # Record attendance
    date = datetime.now().strftime('%Y-%m-%d')
    cursor.execute(
        "INSERT OR IGNORE INTO attendance (student_name, date, time, status) VALUES (?, ?, ?, ?)",
        (student_name, date, datetime.now().strftime('%H:%M:%S'), "present")
    )
    
    conn.commit()
    conn.close() 