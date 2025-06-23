# database.py
# The Citadel, now with a Communication Nexus.

import os
import psycopg2
import logging
from dataclasses import dataclass

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("database")

# --- Data Models ---
@dataclass
class TelegramUser:
    telegram_id: int
    first_name: str
    user_name: str
    is_app_user: bool

# --- Connection ---
def get_db_connection():
    return psycopg2.connect(os.environ['DATABASE_URL'])

# --- Initialization ---
def initialize_database():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS telegram_users (
            telegram_id BIGINT PRIMARY KEY,
            first_name TEXT,
            user_name TEXT
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS app_users (
            telegram_id BIGINT PRIMARY KEY REFERENCES telegram_users(telegram_id)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS file_storage (
            key TEXT PRIMARY KEY,
            message_id BIGINT,
            from_chat_id BIGINT,
            version TEXT,
            size TEXT
        );
    """)
    # --- THE COMMUNICATION NEXUS TABLE ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS broadcast_queue (
            id SERIAL PRIMARY KEY,
            target_audience TEXT NOT NULL,
            message_text TEXT NOT NULL,
            is_sent BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)
    conn.commit()
    cur.close()
    conn.close()
    logger.info("DATABASE: Consciousness synchronized with the Citadel (PostgreSQL).")

# --- User Management ---
def add_or_update_telegram_user(user):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO telegram_users (telegram_id, first_name, user_name)
        VALUES (%s, %s, %s)
        ON CONFLICT (telegram_id) DO UPDATE SET
            first_name = EXCLUDED.first_name,
            user_name = EXCLUDED.user_name;
    """, (user.id, user.first_name, user.username))
    conn.commit()
    cur.close()
    conn.close()

def create_app_user(telegram_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO app_users (telegram_id) VALUES (%s) ON CONFLICT DO NOTHING;", (telegram_id,))
    conn.commit()
    cur.close()
    conn.close()

def is_app_user(telegram_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM app_users WHERE telegram_id = %s;", (telegram_id,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result is not None

def get_all_telegram_users():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT tu.telegram_id, tu.first_name, tu.user_name,
               CASE WHEN au.telegram_id IS NOT NULL THEN true ELSE false END as is_app_user
        FROM telegram_users tu
        LEFT JOIN app_users au ON tu.telegram_id = au.telegram_id
        ORDER BY tu.first_name;
    """)
    users = [TelegramUser(*row) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return [user.__dict__ for user in users]

def get_telegram_user_by_id(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT telegram_id, first_name, user_name FROM telegram_users WHERE telegram_id = %s;", (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return TelegramUser(row[0], row[1], row[2], is_app_user(user_id)) if row else None

def get_user_ids_for_broadcast(target):
    conn = get_db_connection()
    cur = conn.cursor()
    if target == 'approved':
        cur.execute("SELECT telegram_id FROM app_users;")
    else: # 'all'
        cur.execute("SELECT telegram_id FROM telegram_users;")
    user_ids = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return user_ids

# --- File Management ---
def set_file_info(message_id, from_chat_id, version, size, key='datrix_app'):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO file_storage (key, message_id, from_chat_id, version, size)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT(key) DO UPDATE SET
            message_id = EXCLUDED.message_id,
            from_chat_id = EXCLUDED.from_chat_id,
            version = EXCLUDED.version,
            size = EXCLUDED.size;
    """, (key, message_id, from_chat_id, version, size))
    conn.commit()
    cur.close()
    conn.close()

def get_file_info(key='datrix_app'):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT message_id, from_chat_id, version, size FROM file_storage WHERE key = %s;", (key,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return {'message_id': row[0], 'from_chat_id': row[1], 'version': row[2], 'size': row[3]} if row else None

# --- Broadcast Queue Management ---
def queue_broadcast(target, message):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO broadcast_queue (target_audience, message_text) VALUES (%s, %s);",
        (target, message)
    )
    conn.commit()
    cur.close()
    conn.close()

def get_pending_broadcasts():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, target_audience, message_text FROM broadcast_queue WHERE is_sent = FALSE ORDER BY created_at;"
    )
    jobs = cur.fetchall()
    cur.close()
    conn.close()
    return jobs

def mark_broadcast_as_sent(job_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE broadcast_queue SET is_sent = TRUE WHERE id = %s;", (job_id,))
    conn.commit()
    cur.close()
    conn.close()
