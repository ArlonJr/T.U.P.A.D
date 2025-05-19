import sqlite3
import os
import sys
from datetime import datetime, timedelta
from tabulate import tabulate
import pandas as pd
import matplotlib.pyplot as plt

# Database file path
db_file = 'attendance.db'

def connect_db():
    """Connect to the SQLite database"""
    if not os.path.exists(db_file):
        print(f"Database file {db_file} not found.")
        return None
    
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        return None

def view_students():
    """Display all students and their status"""
    conn = connect_db()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, status, absent_count, last_updated 
            FROM students 
            ORDER BY status, name
        """)
        
        students = cursor.fetchall()
        
        if not students:
            print("No students found in the database.")
            return
        
        # Format data for display
        headers = ["ID", "Name", "Status", "Absent Count", "Last Updated"]
        print("\n" + tabulate(students, headers=headers, tablefmt="grid"))
        
        # Count by status
        cursor.execute("""
            SELECT status, COUNT(*) 
            FROM students 
            GROUP BY status
        """)
        status_counts = cursor.fetchall()
        
        print("\nStudent Status Summary:")
        for status, count in status_counts:
            print(f"- {status.title()}: {count}")
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()

def view_attendance(date=None):
    """Display attendance records for a specific date or today"""
    conn = connect_db()
    if not conn:
        return
    
    if not date:
        date = datetime.now().strftime('%Y-%m-%d')
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.student_name, a.time, a.status
            FROM attendance a
            JOIN students s ON a.student_name = s.name
            WHERE a.date = ? 
            ORDER BY a.time
        """, (date,))
        
        attendance = cursor.fetchall()
        
        if not attendance:
            print(f"No attendance records found for {date}.")
            return
        
        # Format data for display
        headers = ["Name", "Time", "Status"]
        print(f"\nAttendance for {date}:")
        print(tabulate(attendance, headers=headers, tablefmt="grid"))
        
        # Count by status
        cursor.execute("""
            SELECT status, COUNT(*) 
            FROM attendance 
            WHERE date = ? 
            GROUP BY status
        """, (date,))
        status_counts = cursor.fetchall()
        
        print("\nAttendance Summary:")
        for status, count in status_counts:
            print(f"- {status.title()}: {count}")
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()

def reset_absent_count(student_name=None):
    """Reset absent count for a student or all students"""
    conn = connect_db()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        
        if student_name:
            # Reset for specific student
            cursor.execute("UPDATE students SET absent_count = 0 WHERE name = ?", (student_name,))
            print(f"Reset absent count for {student_name}")
        else:
            # Reset for all students
            cursor.execute("UPDATE students SET absent_count = 0")
            print("Reset absent count for all students")
            
        conn.commit()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()

def mark_student_dropped(student_name):
    """Mark a student as dropped"""
    conn = connect_db()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        
        # Check if student exists
        cursor.execute("SELECT status FROM students WHERE name = ?", (student_name,))
        result = cursor.fetchone()
        
        if not result:
            print(f"Student {student_name} not found in the database.")
            return
            
        if result[0] == 'dropped':
            print(f"Student {student_name} is already marked as dropped.")
            return
            
        # Mark student as dropped
        cursor.execute("""
            UPDATE students 
            SET status = 'dropped', last_updated = ? 
            WHERE name = ?
        """, (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), student_name))
        
        conn.commit()
        print(f"Student {student_name} has been marked as dropped.")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()

def reactivate_student(student_name):
    """Reactivate a student who was previously dropped"""
    conn = connect_db()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        
        # Check if student exists and is dropped
        cursor.execute("SELECT status FROM students WHERE name = ?", (student_name,))
        result = cursor.fetchone()
        
        if not result:
            print(f"Student {student_name} not found in the database.")
            return
            
        if result[0] != 'dropped':
            print(f"Student {student_name} is already active.")
            return
            
        # Reactivate student
        cursor.execute("""
            UPDATE students 
            SET status = 'active', absent_count = 0, last_updated = ? 
            WHERE name = ?
        """, (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), student_name))
        
        conn.commit()
        print(f"Student {student_name} has been reactivated.")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()

def export_attendance(start_date=None, end_date=None, format='csv'):
    """Export attendance data to CSV or Excel"""
    conn = connect_db()
    if not conn:
        return
    
    try:
        # Set default date range to last 30 days
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        # Query attendance data
        query = """
            SELECT 
                a.student_name as Name, 
                a.date as Date, 
                a.time as Time, 
                a.status as Status
            FROM 
                attendance a
            WHERE 
                a.date BETWEEN ? AND ?
            ORDER BY 
                a.date DESC, a.student_name
        """
        
        # Use pandas to handle the export
        df = pd.read_sql_query(query, conn, params=(start_date, end_date))
        
        if df.empty:
            print(f"No attendance data found between {start_date} and {end_date}")
            return
            
        # Export based on format
        filename = f"attendance_export_{start_date}_to_{end_date}"
        if format.lower() == 'csv':
            export_file = f"{filename}.csv"
            df.to_csv(export_file, index=False)
        elif format.lower() == 'excel':
            export_file = f"{filename}.xlsx"
            df.to_excel(export_file, index=False)
        else:
            print(f"Unsupported export format: {format}. Use 'csv' or 'excel'.")
            return
            
        print(f"Attendance data exported to {export_file}")
        
    except Exception as e:
        print(f"Error exporting data: {e}")
    finally:
        conn.close()

def generate_attendance_report(date=None):
    """Generate attendance report with visualization"""
    try:
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend
    except:
        print("Matplotlib not available. Install with 'pip install matplotlib'")
        return
        
    conn = connect_db()
    if not conn:
        return
    
    try:
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
            
        # Read attendance data
        query = """
            SELECT 
                a.status, 
                COUNT(*) as count
            FROM 
                attendance a
            WHERE 
                a.date = ?
            GROUP BY 
                a.status
        """
        
        df = pd.read_sql_query(query, conn, params=(date,))
        
        if df.empty:
            print(f"No attendance data found for {date}")
            return
            
        # Create pie chart
        plt.figure(figsize=(8, 6))
        plt.pie(df['count'], labels=df['status'], autopct='%1.1f%%', 
                colors=['green', 'yellow', 'red'])
        plt.title(f'Attendance Report for {date}')
        
        # Save chart to file
        report_file = f"attendance_report_{date}.png"
        plt.savefig(report_file)
        
        print(f"Attendance report generated: {report_file}")
        
    except Exception as e:
        print(f"Error generating report: {e}")
    finally:
        conn.close()

def show_help():
    """Display help message"""
    help_text = """
    Attendance Database Utility

    Usage: python db_utils.py [command] [options]

    Commands:
      students            - View all students and their status
      attendance [date]   - View attendance for a specific date (YYYY-MM-DD format)
                           or today if no date specified
      reset [student]     - Reset absent count for a student or all students
      reset_today         - Reset all attendance records for today
      drop [name]        - Mark a student as dropped
      reactivate [name]   - Reactivate a dropped student
      export [start] [end] [format] 
                         - Export attendance data between dates (default: last 30 days)
                           Format can be 'csv' or 'excel'
      report [date]      - Generate attendance report for date (or today)
      help               - Display this help message
    """
    print(help_text)

def reset_today_attendance():
    """Reset all attendance records for today"""
    conn = None
    try:
        current_date = datetime.now().strftime('%Y-%m-%d')
        conn = sqlite3.connect(db_file, timeout=20)
        cursor = conn.cursor()
        
        # Delete all attendance records for today
        cursor.execute("DELETE FROM attendance WHERE date=?", (current_date,))
        deleted_count = cursor.rowcount
        
        # Reset consecutive absences for all students
        cursor.execute("UPDATE students SET consecutive_absences = 0")
        
        conn.commit()
        print(f"Successfully reset {deleted_count} attendance records for {current_date}")
        return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        show_help()
        sys.exit(1)
        
    command = sys.argv[1].lower()
    
    if command == "students":
        view_students()
    elif command == "attendance":
        if len(sys.argv) > 2:
            view_attendance(sys.argv[2])
        else:
            view_attendance()
    elif command == "reset":
        if len(sys.argv) > 2:
            reset_absent_count(sys.argv[2])
        else:
            reset_absent_count()
    elif command == "reset_today":
        reset_today_attendance()
    elif command == "drop":
        if len(sys.argv) > 2:
            mark_student_dropped(sys.argv[2])
        else:
            print("Error: Please provide a student name")
    elif command == "reactivate":
        if len(sys.argv) > 2:
            reactivate_student(sys.argv[2])
        else:
            print("Error: Please provide a student name")
    elif command == "export":
        if len(sys.argv) > 3:
            export_attendance(sys.argv[2], sys.argv[3])
        else:
            export_attendance()
    elif command == "report":
        if len(sys.argv) > 2:
            generate_attendance_report(sys.argv[2])
        else:
            generate_attendance_report()
    else:
        show_help() 