# database.py
# VERSION 2.0: Phoenix Protocol - Hardened Core

import sqlite3
import logging

logger = logging.getLogger(__name__)
DATABASE_FILE = 'mission_control.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    # User tables (unchanged)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS telegram_users (
            telegram_id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            user_name TEXT,
            is_app_user BOOLEAN DEFAULT FALSE,
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # --- [NEW] File State Table ---
    # This replaces the volatile settings.json file
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_files (
            file_key TEXT PRIMARY KEY,
            message_id INTEGER,
            version TEXT,
            size TEXT
        )
    ''')
    # Ensure the default app file entry exists
    cursor.execute("INSERT OR IGNORE INTO bot_files (file_key) VALUES (?)", ('datrix_app',))
    conn.commit()
    conn.close()
    logger.info("DATABASE: Phoenix Core initialized successfully.")

# --- User Functions (unchanged) ---
def add_or_update_telegram_user(user):
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO telegram_users (telegram_id, first_name, last_name, user_name)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET
            first_name=excluded.first_name,
            last_name=excluded.last_name,
            user_name=excluded.user_name
    ''', (user.id, user.first_name, user.last_name, user.username))
    conn.commit()
    conn.close()

def create_app_user(user):
    conn = get_db_connection()
    conn.execute("UPDATE telegram_users SET is_app_user = TRUE WHERE telegram_id = ?", (user.id,))
    conn.commit()
    conn.close()
    logger.info(f"Successfully created app user: {user.full_name} ({user.id})")
    return True

def is_app_user(telegram_id):
    conn = get_db_connection()
    user = conn.execute("SELECT is_app_user FROM telegram_users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    conn.close()
    return user and user['is_app_user']

def get_all_telegram_users():
    conn = get_db_connection()
    users = conn.execute("SELECT telegram_id, first_name, user_name, is_app_user FROM telegram_users ORDER BY join_date DESC").fetchall()
    conn.close()
    return [dict(row) for row in users]

# --- [NEW] File State Functions ---
def get_file_info(file_key='datrix_app'):
    """Retrieves file info from the database."""
    conn = get_db_connection()
    info = conn.execute("SELECT * FROM bot_files WHERE file_key = ?", (file_key,)).fetchone()
    conn.close()
    return dict(info) if info else None

def set_file_info(message_id: int, version: str, size: str, file_key='datrix_app'):
    """Saves file info to the database."""
    conn = get_db_connection()
    conn.execute('''
        UPDATE bot_files 
        SET message_id = ?, version = ?, size = ?
        WHERE file_key = ?
    ''', (message_id, version, size, file_key))
    conn.commit()
    conn.close()
    logger.info(f"DATABASE: File info updated for {file_key}. Version: {version}")
    return True
