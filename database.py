# database.py
import sqlite3
import logging
from datetime import datetime

DATABASE_FILE = 'datrix_bot.db'
logger = logging.getLogger(__name__)

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    """Creates the necessary tables if they don't exist."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Create App Users Table (for DATRIX desktop app users)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS app_users (
                google_sheet_id TEXT PRIMARY KEY,
                user_name TEXT,
                company_name TEXT,
                license_key TEXT,
                license_status TEXT DEFAULT 'inactive',
                license_expires TEXT,
                days_granted INTEGER,
                registration_date TEXT,
                last_seen TEXT,
                is_online BOOLEAN DEFAULT 0
            )
        ''')

        # Create Telegram Users Table (for bot interactors)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS telegram_users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                join_date TEXT,
                last_active TEXT,
                message_count INTEGER DEFAULT 0
            )
        ''')
        
        # Create Pending License Requests Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS license_requests (
                request_id TEXT PRIMARY KEY,
                user_name TEXT,
                company_name TEXT,
                google_sheet_id TEXT,
                request_timestamp TEXT
            )
        ''')

        conn.commit()
        conn.close()
        logger.info("✅ Database initialized successfully.")
    except Exception as e:
        logger.error(f"❌ DATABASE INIT ERROR: {e}")

def add_or_update_telegram_user(user):
    """Adds a new Telegram user or updates their last active time."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        
        cursor.execute(
            "INSERT OR IGNORE INTO telegram_users (user_id, username, first_name, join_date, last_active, message_count) VALUES (?, ?, ?, ?, ?, 0)",
            (user.id, user.username, user.first_name, now, now)
        )
        
        cursor.execute(
            "UPDATE telegram_users SET last_active = ?, message_count = message_count + 1 WHERE user_id = ?",
            (now, user.id)
        )
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"❌ DB ERROR (add_or_update_telegram_user): {e}")

def add_license_request(request_id, user_name, company, sheet_id):
    """Adds a new pending license request to the database."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        
        cursor.execute(
            "INSERT INTO license_requests (request_id, user_name, company_name, google_sheet_id, request_timestamp) VALUES (?, ?, ?, ?, ?)",
            (request_id, user_name, company, sheet_id, now)
        )
        
        conn.commit()
        conn.close()
        logger.info(f"✅ DB: License request for {sheet_id} saved.")
        return True
    except Exception as e:
        logger.error(f"❌ DB ERROR (add_license_request): {e}")
        return False

def get_license_request(request_id):
    """Retrieves a license request by its ID."""
    try:
        conn = get_db_connection()
        request = conn.execute("SELECT * FROM license_requests WHERE request_id = ?", (request_id,)).fetchone()
        conn.close()
        return dict(request) if request else None
    except Exception as e:
        logger.error(f"❌ DB ERROR (get_license_request): {e}")
        return None

def delete_license_request(request_id):
    """Deletes a license request after it has been processed."""
    try:
        conn = get_db_connection()
        conn.execute("DELETE FROM license_requests WHERE request_id = ?", (request_id,))
        conn.commit()
        conn.close()
        logger.info(f"✅ DB: License request {request_id} deleted.")
    except Exception as e:
        logger.error(f"❌ DB ERROR (delete_license_request): {e}")

def activate_app_user_license(sheet_id, expiry_date, days_granted, license_key):
    """Activates or updates the license for a desktop app user."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        # This will update the user if they exist, or do nothing if they don't.
        # Registration should happen separately.
        cursor.execute("""
            UPDATE app_users 
            SET license_status = 'active', license_expires = ?, days_granted = ?, license_key = ?, last_seen = ?
            WHERE google_sheet_id = ?
        """, (expiry_date, days_granted, license_key, now, sheet_id))

        # Check if any row was updated
        if cursor.rowcount == 0:
            logger.warning(f"⚠️ DB: Tried to activate license for non-existent user with Sheet ID: {sheet_id}. No changes made.")
        else:
            logger.info(f"✅ DB: License for {sheet_id} activated. Expires: {expiry_date}")
            
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"❌ DB ERROR (activate_app_user_license): {e}")

def get_all_app_users():
    """Retrieves all registered desktop application users."""
    try:
        conn = get_db_connection()
        users = conn.execute("SELECT * FROM app_users ORDER BY last_seen DESC").fetchall()
        conn.close()
        return [dict(user) for user in users]
    except Exception as e:
        logger.error(f"❌ DB ERROR (get_all_app_users): {e}")
        return []

# Initialize the database when the module is loaded
initialize_database()
