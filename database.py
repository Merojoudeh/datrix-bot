# database.py
# VERSION 3.2: Supports Operative Status Checks

import sqlite3
from datetime import datetime, timedelta
import logging

DB_FILE = 'datrix_bot.db'
logger = logging.getLogger(__name__)

def get_db_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS telegram_users (
            telegram_id INTEGER PRIMARY KEY,
            user_name TEXT,
            first_name TEXT,
            last_name TEXT,
            last_seen TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS app_users (
            google_sheet_id TEXT PRIMARY KEY,
            user_name TEXT,
            company_name TEXT,
            license_status TEXT DEFAULT 'inactive',
            license_key TEXT,
            license_expires TEXT,
            days_granted INTEGER,
            last_seen TEXT,
            telegram_id INTEGER UNIQUE,
            FOREIGN KEY (telegram_id) REFERENCES telegram_users(telegram_id)
        )
    ''')
    conn.commit()
    conn.close()

def add_or_update_telegram_user(user):
    conn = get_db_connection(); cursor = conn.cursor(); now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        INSERT INTO telegram_users (telegram_id, user_name, first_name, last_name, last_seen)
        VALUES (?, ?, ?, ?, ?) ON CONFLICT(telegram_id) DO UPDATE SET
        user_name=excluded.user_name, first_name=excluded.first_name,
        last_name=excluded.last_name, last_seen=excluded.last_seen
    ''', (user.id, user.username, user.first_name, user.last_name, now))
    conn.commit(); conn.close()

# --- NEW: Operative Status Check ---
def is_app_user(telegram_id: int) -> bool:
    """Checks if a Telegram user is an authorized app user."""
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM app_users WHERE telegram_id = ?", (telegram_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def get_all_telegram_user_ids():
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute('SELECT telegram_id FROM telegram_users')
    user_ids = [row[0] for row in cursor.fetchall()]; conn.close()
    return user_ids

def get_all_app_users():
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM app_users').fetchall(); conn.close()
    return [dict(user) for user in users]

def extend_user_license(google_sheet_id: str, days_to_add: int) -> str:
    # ... (function is unchanged) ...
    conn = get_db_connection(); cursor = conn.cursor()
    new_expiry_date_obj = datetime.now() + timedelta(days=int(days_to_add))
    new_expiry_date_str = new_expiry_date_obj.strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("UPDATE app_users SET license_expires = ?, license_status = 'active' WHERE google_sheet_id = ?", (new_expiry_date_str, google_sheet_id))
    conn.commit(); conn.close()
    return new_expiry_date_str

def revoke_user_license(google_sheet_id: str):
    # ... (function is unchanged) ...
    conn = get_db_connection(); cursor = conn.cursor()
    past_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("UPDATE app_users SET license_status = 'revoked', license_expires = ? WHERE google_sheet_id = ?", (past_date, google_sheet_id))
    conn.commit(); conn.close()

def create_app_user(telegram_user, license_days=30):
    """Creates a new app user from a telegram user object."""
    conn = get_db_connection(); cursor = conn.cursor()
    expires_date = (datetime.now() + timedelta(days=license_days)).strftime('%Y-%m-%d %H:%M:%S')
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # Generate a unique Google Sheet ID for simplicity
    google_sheet_id = f"GS-{telegram_user.id}"
    user_name = telegram_user.first_name
    if telegram_user.last_name:
        user_name += f" {telegram_user.last_name}"
    
    try:
        cursor.execute('''
            INSERT INTO app_users (google_sheet_id, user_name, company_name, license_status, license_expires, days_granted, last_seen, telegram_id)
            VALUES (?, ?, ?, 'active', ?, ?, ?, ?)
        ''', (google_sheet_id, user_name, "New Recruit", expires_date, license_days, now, telegram_user.id))
        conn.commit()
        logger.info(f"Successfully created app user: {user_name} ({telegram_user.id})")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"App user with Telegram ID {telegram_user.id} already exists.")
        return False
    finally:
        conn.close()
