import sqlite3
import hashlib
import binascii
import os

DB_FILE = 'organizations.db'

def _hash(pw):
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac('sha256', pw.encode('utf-8'), salt, 100000)
    return binascii.hexlify(salt).decode('utf-8') + ':' + binascii.hexlify(dk).decode('utf-8')

if not os.path.exists(DB_FILE):
    print("Ошибка: База данных (organizations.db) не найдена. Сначала запустите сервер.")
    exit(1)

conn = sqlite3.connect(DB_FILE)
try:
    new_hash = _hash('Amir')
    cursor = conn.execute("UPDATE users SET password_hash = ? WHERE role = 'admin'", (new_hash,))
    conn.commit()
    print(f"УСПЕХ! Пароль для всех администраторов сброшен на 'Amir'.")
    
    rows = conn.execute("SELECT username FROM users WHERE role = 'admin'").fetchall()
    print("\nВаши доступные логины:")
    for row in rows:
        print(f" Логин: {row[0]}")
    print(" Пароль: Amir")
    print("\nТеперь вы можете войти в систему.")
except Exception as e:
    print(f"Ошибка: {e}")
finally:
    conn.close()
