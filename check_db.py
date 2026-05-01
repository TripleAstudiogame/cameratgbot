import sqlite3
conn = sqlite3.connect('organizations.db')
row = conn.execute('SELECT sql FROM sqlite_master WHERE type="table" AND name="users"').fetchone()
if row:
    print(row[0])
else:
    print("Table users not found")
