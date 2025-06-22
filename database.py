# database.py
# VERSION 3.1: Supports User Seeding

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
            telegram_id INTEGER,
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
    conn = get_db_connection(); cursor = conn.cursor()
    new_expiry_date_obj = datetime.now() + timedelta(days=int(days_to_add))
    new_expiry_date_str = new_expiry_date_obj.strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        UPDATE app_users SET license_expires = ?, license_status = 'active' WHERE google_sheet_id = ?
    ''', (new_expiry_date_str, google_sheet_id))
    conn.commit(); conn.close()
    return new_expiry_date_str

def revoke_user_license(google_sheet_id: str):
    conn = get_db_connection(); cursor = conn.cursor()
    past_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        UPDATE app_users SET license_status = 'revoked', license_expires = ? WHERE google_sheet_id = ?
    ''', (past_date, google_sheet_id))
    conn.commit(); conn.close()

# --- NEW: User Seeding Function ---
def create_seed_user(google_sheet_id, user_name, company_name, telegram_id, license_days=30):
    """Creates a new user in the app_users table."""
    conn = get_db_connection(); cursor = conn.cursor()
    expires_date = (datetime.now() + timedelta(days=license_days)).strftime('%Y-%m-%d %H:%M:%S')
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        cursor.execute('''
            INSERT INTO app_users (google_sheet_id, user_name, company_name, license_status, license_expires, days_granted, last_seen, telegram_id)
            VALUES (?, ?, ?, 'active', ?, ?, ?, ?)
        ''', (google_sheet_id, user_name, company_name, expires_date, license_days, now, telegram_id))
        conn.commit()
        logger.info(f"Successfully seeded user: {user_name}")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Seed user with ID {google_sheet_id} or Telegram ID {telegram_id} already exists.")
        return False
    finally:
        conn.close()
