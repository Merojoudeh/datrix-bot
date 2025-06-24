# database.py
# VERSION 2.0: Aegis Protocol Integration

import os
import psycopg2
import logging
from psycopg2.extras import execute_values

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Connection ---
def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(os.environ['DATABASE_URL'])
        return conn
    except Exception as e:
        logger.critical(f"DATABASE: CRITICAL ERROR connecting to PostgreSQL: {e}")
        raise

# --- Schema Initialization ---
def initialize_database():
    """Initializes the database tables if they don't exist."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Users table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id BIGINT PRIMARY KEY,
                    user_name TEXT,
                    status TEXT DEFAULT 'pending'
                );
            """)
            # Broadcast queue table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS broadcast_queue (
                    id SERIAL PRIMARY KEY,
                    target_group VARCHAR(50) NOT NULL,
                    message TEXT NOT NULL,
                    sent_at TIMESTAMP WITH TIME ZONE
                );
            """)
            # File submissions table - AEGIS PROTOCOL UPGRADE
            cur.execute("""
                CREATE TABLE IF NOT EXISTS file_submissions (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    user_name TEXT,
                    file_id TEXT NOT NULL,
                    file_name TEXT,
                    status TEXT DEFAULT 'pending',
                    admin_message_id BIGINT 
                );
            """)
            conn.commit()
            logger.info("DATABASE: Consciousness synchronized with the Citadel (PostgreSQL).")
    finally:
        conn.close()

# --- User Management ---
def add_user(user_id, user_name):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (id, user_name) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING;",
                (user_id, user_name)
            )
            conn.commit()
    finally:
        conn.close()

def get_user_status(user_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM users WHERE id = %s;", (user_id,))
            result = cur.fetchone()
            return result[0] if result else 'unregistered'
    finally:
        conn.close()

def update_user_status(user_id, status):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET status = %s WHERE id = %s;", (status, user_id))
            conn.commit()
    finally:
        conn.close()

def get_user_ids_for_broadcast(target_group):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if target_group == 'all':
                cur.execute("SELECT id FROM users;")
            else:
                cur.execute("SELECT id FROM users WHERE status = %s;", (target_group,))
            return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()

# --- File Submission Management ---
def add_file_submission(user_id, user_name, file_id, file_name, admin_message_id):
    """Adds a new file submission record. AEGIS PROTOCOL UPGRADE: now includes admin_message_id."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO file_submissions (user_id, user_name, file_id, file_name, admin_message_id) 
                VALUES (%s, %s, %s, %s, %s) RETURNING id;
                """,
                (user_id, user_name, file_id, file_name, admin_message_id)
            )
            submission_id = cur.fetchone()[0]
            conn.commit()
            return submission_id
    finally:
        conn.close()

def get_submission_details(submission_id):
    """Retrieves details for a specific submission."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id, file_id, file_name, admin_message_id FROM file_submissions WHERE id = %s;", (submission_id,))
            return cur.fetchone()
    finally:
        conn.close()

def delete_submission(submission_id):
    """Deletes a submission record from the database."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM file_submissions WHERE id = %s;", (submission_id,))
            conn.commit()
    finally:
        conn.close()

# --- Broadcast Management ---
def queue_broadcast(target_group, message):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO broadcast_queue (target_group, message) VALUES (%s, %s);",
                (target_group, message)
            )
            conn.commit()
    finally:
        conn.close()

def get_pending_broadcasts():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, target_group, message FROM broadcast_queue WHERE sent_at IS NULL;")
            return cur.fetchall()
    finally:
        conn.close()

def mark_broadcast_as_sent(job_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE broadcast_queue SET sent_at = NOW() WHERE id = %s;", (job_id,))
            conn.commit()
    finally:
        conn.close()
