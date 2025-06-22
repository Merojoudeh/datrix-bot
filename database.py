# database.py
# VERSION 3.0: Supports the Interactive Command Layer

import sqlite3
from datetime import datetime, timedelta
import logging

# --- Database Configuration ---
DB_FILE = 'datrix_bot.db'
logger = logging.getLogger(__name__)

# --- Core Functions ---
def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    """Creates the necessary tables if they don't already exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Main table for Telegram users interacting with the bot
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS telegram_users (
            telegram_id INTEGER PRIMARY KEY,
            user_name TEXT,
            first_name TEXT,
            last_name TEXT,
            last_seen TEXT
        )
    ''')
    # Table for app users, linked by a unique ID (e.g., from a Google Sheet)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS app_users (
            google_sheet_id TEXT PRIMARY KEY,
            user_name TEXT,
            company_name TEXT,
            license_status TEXT DEFAULT 'inactive',
            license_key TEXT,
            license_expires TEXT,
            days_granted INTEGER,
            last_seen TEXT
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully.")

# --- User Management ---
def add_or_update_telegram_user(user):
    """Adds a new Telegram user or updates their last_seen timestamp."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        INSERT INTO telegram_users (telegram_id, user_name, first_name, last_name, last_seen)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET
        user_name=excluded.user_name,
        first_name=excluded.first_name,
        last_name=excluded.last_name,
        last_seen=excluded.last_seen
    ''', (user.id, user.username, user.first_name, user.last_name, now))
    conn.commit()
    conn.close()

def get_all_telegram_user_ids():
    """Retrieves a list of all known Telegram user IDs."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT telegram_id FROM telegram_users')
    user_ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    return user_ids

def get_all_app_users():
    """Retrieves all users from the app_users table for the dashboard."""
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM app_users').fetchall()
    conn.close()
    # Convert sqlite3.Row objects to standard dictionaries for JSON serialization
    return [dict(user) for user in users]

# --- NEW: Interactive Command Functions ---

def extend_user_license(google_sheet_id: str, days_to_add: int) -> str:
    """Extends a user's license by a number of days from today."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Calculate the new expiry date from today
    new_expiry_date_obj = datetime.now() + timedelta(days=int(days_to_add))
    new_expiry_date_str = new_expiry_date_obj.strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
        UPDATE app_users
        SET license_expires = ?, license_status = 'active'
        WHERE google_sheet_id = ?
    ''', (new_expiry_date_str, google_sheet_id))
    
    conn.commit()
    conn.close()
    logger.info(f"Extended license for {google_sheet_id} to {new_expiry_date_str}")
    return new_expiry_date_str

def revoke_user_license(google_sheet_id: str):
    """Revokes a user's license by setting its status to 'expired'."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Set expiry to a past date to ensure it's invalid
    past_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
        UPDATE app_users
        SET license_status = 'revoked', license_expires = ?
        WHERE google_sheet_id = ?
    ''', (past_date, google_sheet_id))
    
    conn.commit()
    conn.close()
    logger.info(f"Revoked license for {google_sheet_id}")

# --- Dummy/Example Functions (for testing if needed) ---
def add_dummy_app_user(google_sheet_id, user_name, company_name):
    """Adds a sample app user for testing the dashboard."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO app_users (google_sheet_id, user_name, company_name, license_status, last_seen)
            VALUES (?, ?, ?, 'active', ?)
        ''', (google_sheet_id, user_name, company_name, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
    except sqlite3.IntegrityError:
        logger.warning(f"Dummy user {google_sheet_id} already exists.")
    finally:
        conn.close()
