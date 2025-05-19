import sqlite3
from datetime import datetime, timedelta

def init_test_database():
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    # Create students table if not exists
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE,
        status TEXT DEFAULT 'active',
        absent_count INTEGER DEFAULT 0,
        last_updated TEXT
    )
    ''')
    
    # Create attendance table if not exists
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY,
        student_name TEXT,
        date TEXT,
        time TEXT,
        status TEXT,
        method TEXT DEFAULT 'face',
        UNIQUE(student_name, date)
    )
    ''')
    
    # Add a test student if not exists
    cursor.execute("INSERT OR IGNORE INTO students (name, status, last_updated) VALUES (?, ?, ?)",
                  ('Test Student', 'active', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    
    conn.commit()
    conn.close()

def mark_absence(student_name, date):
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    # Record absence
    cursor.execute(
        "INSERT OR IGNORE INTO attendance (student_name, date, time, status) VALUES (?, ?, ?, ?)",
        (student_name, date, "00:00:00", "absent")
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

def mark_present(student_name, date):
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    # Record attendance
    cursor.execute(
        "INSERT OR IGNORE INTO attendance (student_name, date, time, status) VALUES (?, ?, ?, ?)",
        (student_name, date, datetime.now().strftime('%H:%M:%S'), "present")
    )
    
    conn.commit()
    conn.close()

def check_student_status(student_name):
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT name, status, absent_count 
        FROM students 
        WHERE name=?
    """, (student_name,))
    
    result = cursor.fetchone()
    if result:
        print(f"\nStudent Status:")
        print(f"Name: {result[0]}")
        print(f"Status: {result[1]}")
        print(f"Total Absences: {result[2]}")
    else:
        print(f"Student {student_name} not found")
    
    conn.close()

def simulate_absences():
    student_name = "Arlon Jr. T. Ylasco"
    print("\n=== Starting Absence Simulation ===")
    
    # Initialize database
    init_test_database()
    
    # Check initial status
    print("\nInitial Status:")
    check_student_status(student_name)
    
    # Simulate 3 absences (not necessarily consecutive)
    print("\nSimulating 3 absences...")
    for i in range(3):
        date = (datetime.now().replace(day=1) + timedelta(days=i*2)).strftime('%Y-%m-%d')  # Every other day
        mark_absence(student_name, date)
        print(f"\nAfter absence {i+1}:")
        check_student_status(student_name)
    
    # Try to mark present (should fail if dropped)
    print("\nTrying to mark present after being dropped...")
    date = datetime.now().strftime('%Y-%m-%d')
    mark_present(student_name, date)
    check_student_status(student_name)
    
    # Reactivate student
    print("\nReactivating student...")
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE students SET status='active', absent_count=0 WHERE name=?", (student_name,))
    conn.commit()
    conn.close()
    
    # Mark present after reactivation
    print("\nMarking present after reactivation...")
    mark_present(student_name, date)
    check_student_status(student_name)

if __name__ == "__main__":
    simulate_absences() 