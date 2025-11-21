import sqlite3
import os
from pathlib import Path

def main():
    home = os.path.expanduser('~')
    db_path = os.path.join(home, '.monitor-tool', 'monitor_data.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT count(*) FROM process_data")
        count = cursor.fetchone()[0]
        print(f"Total process records: {count}")
        
        if count > 0:
            print("\nLatest 5 records:")
            cursor.execute("""
                SELECT timestamp, name, cpu_percent, memory_rss 
                FROM process_data 
                ORDER BY timestamp DESC 
                LIMIT 5
            """)
            for row in cursor.fetchall():
                print(row)
    except sqlite3.OperationalError as e:
        print(f"Error querying database: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    main()
