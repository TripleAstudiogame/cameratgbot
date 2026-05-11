import sqlite3
import db

def check_and_fix():
    conn = sqlite3.connect(db.DB_FILE)
    cursor = conn.cursor()
    
    # Check users table columns
    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]
    print(f"Users columns: {columns}")
    
    if 'name' not in columns:
        print("Adding 'name' column to users...")
        cursor.execute("ALTER TABLE users ADD COLUMN name TEXT DEFAULT ''")
    if 'phone' not in columns:
        print("Adding 'phone' column to users...")
        cursor.execute("ALTER TABLE users ADD COLUMN phone TEXT DEFAULT ''")
    if 'role' not in columns:
        print("Adding 'role' column to users...")
        cursor.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
        
    conn.commit()
    conn.close()
    print("Done.")

if __name__ == "__main__":
    check_and_fix()
