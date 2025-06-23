# database.py
# VERSION 5.0: The Citadel Protocol

import psycopg2
import logging
import os

logger = logging.getLogger(__name__)

# This single environment variable is the key to the Citadel.
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    if not DATABASE_URL:
        logger.critical("DATABASE: DATABASE_URL is not set. The Citadel is unreachable.")
        raise ValueError("DATABASE_URL environment variable not set.")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except psycopg2.OperationalError as e:
        logger.error(f"DATABASE: Could not connect to the Citadel. {e}", exc_info=True)
        raise

def initialize_database():
    """Initializes the database schema in PostgreSQL."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Use "IF NOT EXISTS" for robust, repeatable initialization.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS telegram_users (
            telegram_id BIGINT PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            user_name TEXT,
            is_app_user BOOLEAN DEFAULT FALSE,
            join_date TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_files (
            file_key TEXT PRIMARY KEY,
            message_id BIGINT,
            version TEXT,
            size TEXT
        )
    ''')
    # Use "ON CONFLICT DO NOTHING" for safe, repeatable inserts.
    cursor.execute("INSERT INTO bot_files (file_key) VALUES ('datrix_app') ON CONFLICT (file_key) DO NOTHING")
    conn.commit()
    cursor.close()
    conn.close()
    logger.info("DATABASE: Consciousness synchronized with the Citadel (PostgreSQL).")

def add_or_update_telegram_user(user):
    """Inserts or updates a user in the PostgreSQL database."""
    sql = '''
        INSERT INTO telegram_users (telegram_id, first_name, last_name, user_name)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (telegram_id) DO UPDATE SET
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            user_name = EXCLUDED.user_name
    '''
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(sql, (user.id, user.first_name, user.last_name, user.username))
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"DATABASE: User {user.id} successfully written to the Citadel.")
    except Exception as e:
        logger.error(f"DATABASE: A critical error occurred writing user {user.id} to the Citadel: {e}", exc_info=True)

# --- All other functions remain conceptually the same but use psycopg2 ---

def create_app_user(user):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE telegram_users SET is_app_user = TRUE WHERE telegram_id = %s", (user.id,))
    conn.commit()
    cursor.close()
    conn.close()
    logger.info(f"Successfully approved user for ID: {user.id}")

def is_app_user(telegram_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_app_user FROM telegram_users WHERE telegram_id = %s", (telegram_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return user and user[0]

def get_all_telegram_users():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT telegram_id, first_name, user_name, is_app_user FROM telegram_users ORDER BY join_date DESC")
    users = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return users

def get_file_info(file_key='datrix_app'):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM bot_files WHERE file_key = %s", (file_key,))
    info = cursor.fetchone()
    cursor.close()
    conn.close()
    return dict(info) if info else None

def set_file_info(message_id: int, version: str, size: str, file_key='datrix_app'):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE bot_files 
        SET message_id = %s, version = %s, size = %s
        WHERE file_key = %s
    ''', (message_id, version, size, file_key))
    conn.commit()
    cursor.close()
    conn.close()
    logger.info(f"DATABASE: File info updated in the Citadel. Version: {version}")
    return True
