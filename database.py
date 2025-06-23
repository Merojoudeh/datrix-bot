# database.py
# VERSION 5.2: The Phantom Protocol

import psycopg2
import psycopg2.extras
import logging
import os

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
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
    conn = get_db_connection()
    cursor = conn.cursor()
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
            from_chat_id BIGINT, -- <-- NEW COLUMN: The origin map coordinate
            version TEXT,
            size TEXT
        )
    ''')
    cursor.execute("INSERT INTO bot_files (file_key) VALUES ('datrix_app') ON CONFLICT (file_key) DO NOTHING")
    conn.commit()
    cursor.close()
    conn.close()
    logger.info("DATABASE: Consciousness synchronized with the Citadel (PostgreSQL).")

# This function is now modified to accept the new from_chat_id
def set_file_info(message_id: int, from_chat_id: int, version: str, size: str, file_key='datrix_app'):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE bot_files 
        SET message_id = %s, from_chat_id = %s, version = %s, size = %s
        WHERE file_key = %s
    ''', (message_id, from_chat_id, version, size, file_key)) # <-- NEW DATA POINT
    conn.commit()
    cursor.close()
    conn.close()
    logger.info(f"DATABASE: File info updated in Citadel. Origin: {from_chat_id}, ID: {message_id}, Version: {version}")
    return True

# This function now correctly uses the from_chat_id
async def download_app_handler(query, context):
    file_info = get_file_info('datrix_app')
    # Check for both message_id AND the new from_chat_id
    if file_info and file_info['message_id'] and file_info['from_chat_id']:
        await context.bot.forward_message(
            chat_id=query.from_user.id,
            from_chat_id=file_info['from_chat_id'], # <-- USE THE CORRECT MAP
            message_id=file_info['message_id']
        )
    else:
        await query.message.reply_text("📂 The file is not yet available from Mission Control. The Admin must upload it first.")

# --- All other functions remain unchanged ---

def add_or_update_telegram_user(user):
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

def create_app_user(user):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE telegram_users SET is_app_user = TRUE WHERE telegram_id = %s", (user.id,))
    conn.commit()
    cursor.close()
    conn.close()

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
