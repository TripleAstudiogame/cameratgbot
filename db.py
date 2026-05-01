import sqlite3
import json
from datetime import datetime, timedelta

DB_FILE = 'organizations.db'

def _conn():
    """Get a new DB connection with row factory."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Organizations
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS organizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            bot_token TEXT NOT NULL,
            mail_username TEXT NOT NULL,
            mail_password TEXT NOT NULL,
            subscribers TEXT DEFAULT '[]',
            subscription_end_date TEXT,
            is_active BOOLEAN DEFAULT 1,
            contact_name TEXT DEFAULT '',
            contact_phone TEXT DEFAULT '',
            contact_title TEXT DEFAULT '',
            notes TEXT DEFAULT ''
        )
    ''')
    
    # Events (per-organization activity log)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE
        )
    ''')
    
    # Access Requests (user approval flow)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS access_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            first_name TEXT DEFAULT '',
            last_name TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL,
            FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE
        )
    ''')
    
    # Settings (key-value store)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    
    # Users (admin and regular users)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            role TEXT DEFAULT 'user'
        )
    ''')

    
    # Safe migrations for older DBs
    migration_columns = [
        ("contact_name", "TEXT DEFAULT ''"),
        ("contact_phone", "TEXT DEFAULT ''"),
        ("contact_title", "TEXT DEFAULT ''"),
        ("notes", "TEXT DEFAULT ''"),
        ("mail_check_interval", "INTEGER DEFAULT 0"),
        ("telegram_cooldown", "INTEGER DEFAULT 0"),
        ("user_id", "INTEGER DEFAULT 1"),
        ("cameras", "TEXT DEFAULT '{}'"),
    ]
    for col_name, col_type in migration_columns:
        try:
            cursor.execute(f"ALTER TABLE organizations ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            pass

    # Default settings
    defaults = {
        'mail_check_interval': '3',
        'telegram_cooldown': '10',
        'default_subscription_days': '365',
    }
    for k, v in defaults.items():
        cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (k, v))

    conn.commit()
    conn.close()

# ── Organizations CRUD ──

def get_organizations(user_id=None):
    conn = _conn()
    if user_id:
        rows = conn.execute('SELECT * FROM organizations WHERE user_id = ?', (user_id,)).fetchall()
    else:
        rows = conn.execute('SELECT * FROM organizations').fetchall()
    conn.close()
    orgs = []
    for row in rows:
        org = dict(row)
        org['subscribers'] = json.loads(org.get('subscribers') or '[]')
        org['cameras'] = json.loads(org.get('cameras') or '{}')
        org['is_active'] = bool(org.get('is_active', 1))
        orgs.append(org)
    return orgs

def get_organization(org_id):
    conn = _conn()
    row = conn.execute('SELECT * FROM organizations WHERE id = ?', (org_id,)).fetchone()
    conn.close()
    if row:
        org = dict(row)
        org['subscribers'] = json.loads(org.get('subscribers') or '[]')
        org['cameras'] = json.loads(org.get('cameras') or '{}')
        org['is_active'] = bool(org.get('is_active', 1))
        return org
    return None

def add_organization(data, user_id=1):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Default is 3 days when a user or admin creates an org
    days = 3
    end_date = (datetime.now() + timedelta(days=days)).isoformat()
    cursor.execute('''
        INSERT INTO organizations (name, bot_token, mail_username, mail_password, subscription_end_date,
            contact_name, contact_phone, contact_title, notes, mail_check_interval, telegram_cooldown, user_id, cameras)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (data['name'], data['bot_token'], data['mail_username'], data['mail_password'], end_date,
          data.get('contact_name', ''), data.get('contact_phone', ''), data.get('contact_title', ''),
          data.get('notes', ''), int(data.get('mail_check_interval', 0)), int(data.get('telegram_cooldown', 0)), user_id, json.dumps(data.get('cameras', {}))))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id

def update_organization(org_id, data):
    conn = sqlite3.connect(DB_FILE)
    conn.execute('''
        UPDATE organizations
        SET name=?, bot_token=?, mail_username=?, mail_password=?, is_active=?,
            contact_name=?, contact_phone=?, contact_title=?, notes=?,
            mail_check_interval=?, telegram_cooldown=?, cameras=?
        WHERE id=?
    ''', (data['name'], data['bot_token'], data['mail_username'], data['mail_password'],
          int(data.get('is_active', 1)),
          data.get('contact_name', ''), data.get('contact_phone', ''), data.get('contact_title', ''),
          data.get('notes', ''), int(data.get('mail_check_interval', 0)), int(data.get('telegram_cooldown', 0)),
          json.dumps(data.get('cameras', {})), org_id))
    conn.commit()
    conn.close()

def register_camera(org_id, camera_code):
    org = get_organization(org_id)
    if not org: return False
    cameras = {}
    try:
        cameras = json.loads(org.get('cameras', '{}'))
    except: pass
    if camera_code not in cameras:
        cameras[camera_code] = ""
        conn = sqlite3.connect(DB_FILE)
        conn.execute('UPDATE organizations SET cameras=? WHERE id=?', (json.dumps(cameras), org_id))
        conn.commit()
        conn.close()
        return True
    return False

def extend_subscription(org_id, days=None):
    org = get_organization(org_id)
    if not org:
        return None
    try:
        current_end = datetime.fromisoformat(org.get('subscription_end_date', ''))
        if current_end < datetime.now():
            current_end = datetime.now()
    except (ValueError, TypeError):
        current_end = datetime.now()
        
    if days is None:
        days = int(get_setting('default_subscription_days', '365'))
        
    new_end = current_end + timedelta(days=days)
    conn = sqlite3.connect(DB_FILE)
    conn.execute('UPDATE organizations SET subscription_end_date=?, is_active=1 WHERE id=?',
                 (new_end.isoformat(), org_id))
    conn.commit()
    conn.close()
    return new_end.isoformat()

def delete_organization(org_id):
    conn = sqlite3.connect(DB_FILE)
    conn.execute('DELETE FROM organizations WHERE id=?', (org_id,))
    conn.execute('DELETE FROM events WHERE org_id=?', (org_id,))
    conn.commit()
    conn.close()

def add_subscriber(org_id, chat_id):
    org = get_organization(org_id)
    if org:
        subs = org['subscribers']
        if chat_id not in subs:
            subs.append(chat_id)
            conn = sqlite3.connect(DB_FILE)
            conn.execute('UPDATE organizations SET subscribers=? WHERE id=?', (json.dumps(subs), org_id))
            conn.commit()
            conn.close()
            return True
    return False

def remove_subscriber(org_id, chat_id):
    org = get_organization(org_id)
    if org:
        subs = org['subscribers']
        if chat_id in subs:
            subs.remove(chat_id)
            conn = sqlite3.connect(DB_FILE)
            conn.execute('UPDATE organizations SET subscribers=? WHERE id=?', (json.dumps(subs), org_id))
            conn.commit()
            conn.close()
            return True
    return False

# ── Access Requests ──

def add_access_request(org_id, chat_id, first_name='', last_name='', phone=''):
    """Add a pending access request. Returns True if new, False if exists."""
    conn = sqlite3.connect(DB_FILE)
    existing = conn.execute(
        'SELECT id, status FROM access_requests WHERE org_id=? AND chat_id=?',
        (org_id, chat_id)).fetchone()
    if existing:
        conn.close()
        return False
    conn.execute(
        'INSERT INTO access_requests (org_id, chat_id, first_name, last_name, phone, status, created_at) VALUES (?,?,?,?,?,?,?)',
        (org_id, chat_id, first_name, last_name, phone, 'pending', datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return True

def get_access_requests(org_id, status=None):
    """Get access requests for an org, optionally filtered by status."""
    conn = _conn()
    if status:
        rows = conn.execute(
            'SELECT * FROM access_requests WHERE org_id=? AND status=? ORDER BY created_at DESC',
            (org_id, status)).fetchall()
    else:
        rows = conn.execute(
            'SELECT * FROM access_requests WHERE org_id=? ORDER BY created_at DESC',
            (org_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def approve_access_request(request_id):
    """Approve a pending request and add chat_id to subscribers."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    row = conn.execute('SELECT * FROM access_requests WHERE id=?', (request_id,)).fetchone()
    if not row:
        conn.close()
        return None
    req = dict(row)
    conn.execute('UPDATE access_requests SET status=? WHERE id=?', ('approved', request_id))
    conn.commit()
    conn.close()
    # Add to subscribers
    add_subscriber(req['org_id'], req['chat_id'])
    return req

def reject_access_request(request_id):
    """Reject and delete a pending request."""
    conn = sqlite3.connect(DB_FILE)
    conn.execute('DELETE FROM access_requests WHERE id=?', (request_id,))
    conn.commit()
    conn.close()

def revoke_access(request_id):
    """Revoke an approved user — remove from subscribers and delete request."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    row = conn.execute('SELECT * FROM access_requests WHERE id=?', (request_id,)).fetchone()
    if not row:
        conn.close()
        return None
    req = dict(row)
    conn.execute('DELETE FROM access_requests WHERE id=?', (request_id,))
    conn.commit()
    conn.close()
    remove_subscriber(req['org_id'], req['chat_id'])
    return req

def is_user_approved(org_id, chat_id):
    """Check if user has approved access."""
    conn = _conn()
    row = conn.execute(
        'SELECT id FROM access_requests WHERE org_id=? AND chat_id=? AND status=?',
        (org_id, chat_id, 'approved')).fetchone()
    conn.close()
    return row is not None

def has_pending_request(org_id, chat_id):
    """Check if user already has a pending request."""
    conn = _conn()
    row = conn.execute(
        'SELECT id FROM access_requests WHERE org_id=? AND chat_id=? AND status=?',
        (org_id, chat_id, 'pending')).fetchone()
    conn.close()
    return row is not None

# ── Events (Activity Log) ──

def add_event(org_id, event_type, message):
    """event_type: 'notification', 'error', 'subscriber', 'system'"""
    conn = sqlite3.connect(DB_FILE)
    conn.execute('INSERT INTO events (org_id, event_type, message, created_at) VALUES (?,?,?,?)',
                 (org_id, event_type, message, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_events(org_id, limit=50):
    conn = _conn()
    rows = conn.execute(
        'SELECT * FROM events WHERE org_id=? ORDER BY created_at DESC LIMIT ?',
        (org_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_events(limit=100):
    conn = _conn()
    rows = conn.execute('''
        SELECT e.*, o.name as org_name FROM events e
        LEFT JOIN organizations o ON e.org_id = o.id
        ORDER BY e.created_at DESC LIMIT ?
    ''', (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_event_stats(org_id=None, days=30):
    """Get notification count per day for charts."""
    conn = _conn()
    since = (datetime.now() - timedelta(days=days)).isoformat()
    if org_id:
        rows = conn.execute('''
            SELECT DATE(created_at) as day, COUNT(*) as count FROM events
            WHERE org_id=? AND event_type='notification' AND created_at>=?
            GROUP BY DATE(created_at) ORDER BY day
        ''', (org_id, since)).fetchall()
    else:
        rows = conn.execute('''
            SELECT DATE(created_at) as day, COUNT(*) as count FROM events
            WHERE event_type='notification' AND created_at>=?
            GROUP BY DATE(created_at) ORDER BY day
        ''', (since,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_camera_stats(days=30):
    """Top cameras by notification count."""
    conn = _conn()
    since = (datetime.now() - timedelta(days=days)).isoformat()
    rows = conn.execute('''
        SELECT message, COUNT(*) as count FROM events
        WHERE event_type='notification' AND created_at>=?
        GROUP BY message ORDER BY count DESC LIMIT 10
    ''', (since,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── Settings ──

def get_setting(key, default=''):
    conn = _conn()
    row = conn.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
    conn.close()
    return row['value'] if row else default

def set_setting(key, value):
    conn = sqlite3.connect(DB_FILE)
    conn.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)', (key, str(value)))
    conn.commit()
    conn.close()

def get_all_settings():
    conn = _conn()
    rows = conn.execute('SELECT * FROM settings').fetchall()
    conn.close()
    return {r['key']: r['value'] for r in rows}

# ── Users CRUD ──

def get_user_by_username(username):
    conn = _conn()
    row = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_id(user_id):
    conn = _conn()
    row = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_users():
    conn = _conn()
    rows = conn.execute("SELECT id, username, name, phone, role FROM users WHERE role != 'admin'").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_user(username, password_hash, name, phone):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO users (username, password_hash, name, phone, role) VALUES (?, ?, ?, ?, ?)',
            (username, password_hash, name, phone, 'user')
        )
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return new_id
    except sqlite3.IntegrityError:
        return None # Username exists

def update_user_password(user_id, password_hash):
    conn = sqlite3.connect(DB_FILE)
    conn.execute('UPDATE users SET password_hash = ? WHERE id = ?', (password_hash, user_id))
    conn.commit()
    conn.close()

def delete_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Find admin user id
    admin_row = cursor.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1").fetchone()
    admin_id = admin_row[0] if admin_row else 1
    
    # Reassign organizations to admin
    cursor.execute("UPDATE organizations SET user_id = ? WHERE user_id = ?", (admin_id, user_id))
    
    # Delete user
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

# Initialize
init_db()
