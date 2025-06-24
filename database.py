# database.py
# Fixed DATRIX Database Manager

import os
import psycopg2
import logging
from psycopg2.extras import RealDictCursor
import json
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_db_connection():
    """Database connection"""
    try:
        conn = psycopg2.connect(os.environ['DATABASE_URL'])
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return None

def initialize_database():
    """Initialize database with proper schema"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cur:
            # Original users table (compatibility)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id BIGINT PRIMARY KEY,
                    user_name TEXT,
                    status TEXT DEFAULT 'pending'
                );
            """)
            
            # Fixed broadcast_queue table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS broadcast_queue (
                    id SERIAL PRIMARY KEY,
                    target_group VARCHAR(50) NOT NULL,
                    message TEXT NOT NULL,
                    sent_at TIMESTAMP WITH TIME ZONE
                );
            """)
            
            # File submissions table
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
            
            # DATRIX users table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS datrix_users (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    user_name TEXT,
                    company_name TEXT,
                    google_sheet_id TEXT,
                    license_expires DATE,
                    license_status TEXT DEFAULT 'active',
                    app_version TEXT,
                    install_path TEXT,
                    last_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    session_start TIMESTAMP WITH TIME ZONE,
                    total_sessions INTEGER DEFAULT 0,
                    total_downloads INTEGER DEFAULT 0,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            
            # User activity table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_activity (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    activity_type TEXT NOT NULL,
                    activity_data JSONB,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            
            # File storage table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS stored_files (
                    id SERIAL PRIMARY KEY,
                    file_key TEXT UNIQUE NOT NULL,
                    message_id BIGINT,
                    description TEXT,
                    version TEXT,
                    file_size TEXT,
                    filename TEXT,
                    download_count INTEGER DEFAULT 0,
                    upload_date TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            
            # License requests table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS license_requests (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    company_name TEXT,
                    google_sheet_id TEXT,
                    requested_days INTEGER DEFAULT 30,
                    status TEXT DEFAULT 'pending',
                    admin_response TEXT,
                    approved_by BIGINT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    processed_at TIMESTAMP WITH TIME ZONE
                );
            """)
            
            # Bot analytics table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bot_analytics (
                    id SERIAL PRIMARY KEY,
                    date DATE DEFAULT CURRENT_DATE UNIQUE,
                    total_users INTEGER DEFAULT 0,
                    active_users_24h INTEGER DEFAULT 0,
                    active_users_7d INTEGER DEFAULT 0,
                    total_downloads INTEGER DEFAULT 0,
                    total_messages INTEGER DEFAULT 0,
                    license_requests INTEGER DEFAULT 0,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            
            # Insert default file
            cur.execute("""
                INSERT INTO stored_files (file_key, description, version, file_size, filename)
                VALUES ('datrix_app', 'DATRIX Accounting Application', 'v2.1.6', '100MB', 'DATRIX_Setup.exe')
                ON CONFLICT (file_key) DO NOTHING;
            """)
            
            conn.commit()
            logger.info("✅ Database initialized successfully")
            return True
            
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

# DATRIX Functions
def add_datrix_user(telegram_id, user_name, company_name=None, google_sheet_id=None):
    """Add or update DATRIX user"""
    conn = get_db_connection()
    if not conn:
        return None
        
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO datrix_users (telegram_id, user_name, company_name, google_sheet_id)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (telegram_id) 
                DO UPDATE SET 
                    user_name = EXCLUDED.user_name,
                    company_name = COALESCE(EXCLUDED.company_name, datrix_users.company_name),
                    google_sheet_id = COALESCE(EXCLUDED.google_sheet_id, datrix_users.google_sheet_id),
                    last_seen = NOW()
                RETURNING id;
            """, (telegram_id, user_name, company_name, google_sheet_id))
            
            result = cur.fetchone()
            conn.commit()
            return result[0] if result else None
            
    except Exception as e:
        logger.error(f"Error adding user: {e}")
        return None
    finally:
        conn.close()

def get_datrix_user(telegram_id):
    """Get DATRIX user"""
    conn = get_db_connection()
    if not conn:
        return None
        
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM datrix_users WHERE telegram_id = %s", (telegram_id,))
            return cur.fetchone()
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        return None
    finally:
        conn.close()

def update_user_license(telegram_id, days_to_add, admin_id):
    """Update user license"""
    conn = get_db_connection()
    if not conn:
        return None
        
    try:
        with conn.cursor() as cur:
            new_expiry = datetime.now().date() + timedelta(days=days_to_add)
            
            cur.execute("""
                UPDATE datrix_users 
                SET license_expires = %s, license_status = 'active'
                WHERE telegram_id = %s
                RETURNING license_expires;
            """, (new_expiry, telegram_id))
            
            result = cur.fetchone()
            if result:
                cur.execute("""
                    UPDATE license_requests 
                    SET status = 'approved', processed_at = NOW(), approved_by = %s
                    WHERE user_id = %s AND status = 'pending'
                """, (admin_id, telegram_id))
                
                conn.commit()
                return result[0]
            return None
            
    except Exception as e:
        logger.error(f"Error updating license: {e}")
        return None
    finally:
        conn.close()

def check_user_license(telegram_id):
    """Check user license validity"""
    conn = get_db_connection()
    if not conn:
        return False, "Database error"
        
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT license_expires, license_status 
                FROM datrix_users 
                WHERE telegram_id = %s
            """, (telegram_id,))
            
            result = cur.fetchone()
            if not result:
                return False, "User not found"
            
            license_expires, license_status = result
            
            if not license_expires:
                return False, "No license set"
            
            if license_expires <= datetime.now().date():
                return False, "License expired"
            
            if license_status != 'active':
                return False, "License inactive"
            
            days_remaining = (license_expires - datetime.now().date()).days
            return True, f"{days_remaining} days remaining"
            
    except Exception as e:
        logger.error(f"Error checking license: {e}")
        return False, "Database error"
    finally:
        conn.close()

def add_license_request(telegram_id, company_name, google_sheet_id, requested_days=30):
    """Add license request"""
    conn = get_db_connection()
    if not conn:
        return None
        
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO license_requests 
                (user_id, company_name, google_sheet_id, requested_days)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
            """, (telegram_id, company_name, google_sheet_id, requested_days))
            
            result = cur.fetchone()
            conn.commit()
            return result[0] if result else None
            
    except Exception as e:
        logger.error(f"Error adding license request: {e}")
        return None
    finally:
        conn.close()

def track_user_activity(telegram_id, activity_type, activity_data=None):
    """Track user activity"""
    conn = get_db_connection()
    if not conn:
        return False
        
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE datrix_users 
                SET last_seen = NOW() 
                WHERE telegram_id = %s
            """, (telegram_id,))
            
            cur.execute("""
                INSERT INTO user_activity (user_id, activity_type, activity_data)
                VALUES (%s, %s, %s)
            """, (telegram_id, activity_type, json.dumps(activity_data) if activity_data else None))
            
            conn.commit()
            return True
            
    except Exception as e:
        logger.error(f"Error tracking activity: {e}")
        return False
    finally:
        conn.close()

def get_file_info(file_key):
    """Get file information"""
    conn = get_db_connection()
    if not conn:
        return None
        
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM stored_files WHERE file_key = %s", (file_key,))
            return cur.fetchone()
    except Exception as e:
        logger.error(f"Error getting file info: {e}")
        return None
    finally:
        conn.close()

def update_file_info(file_key, message_id, version=None, file_size=None):
    """Update file information"""
    conn = get_db_connection()
    if not conn:
        return False
        
    try:
        with conn.cursor() as cur:
            update_fields = ["message_id = %s", "upload_date = NOW()"]
            params = [message_id]
            
            if version:
                update_fields.append("version = %s")
                params.append(version)
                
            if file_size:
                update_fields.append("file_size = %s")
                params.append(file_size)
            
            params.append(file_key)
            
            query = f"""
                UPDATE stored_files 
                SET {', '.join(update_fields)}
                WHERE file_key = %s
                RETURNING id;
            """
            
            cur.execute(query, params)
            result = cur.fetchone()
            conn.commit()
            return result is not None
            
    except Exception as e:
        logger.error(f"Error updating file: {e}")
        return False
    finally:
        conn.close()

def increment_download_count(file_key):
    """Increment download count"""
    conn = get_db_connection()
    if not conn:
        return False
        
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE stored_files 
                SET download_count = download_count + 1
                WHERE file_key = %s
            """, (file_key,))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error incrementing download: {e}")
        return False
    finally:
        conn.close()

def get_all_telegram_users():
    """Get all users for dashboard"""
    conn = get_db_connection()
    if not conn:
        return []
        
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    du.telegram_id,
                    du.user_name,
                    du.company_name,
                    du.google_sheet_id,
                    du.license_expires,
                    du.license_status,
                    du.app_version,
                    du.last_seen,
                    du.total_downloads,
                    du.created_at,
                    CASE 
                        WHEN du.license_expires > CURRENT_DATE THEN true 
                        ELSE false 
                    END as is_app_user,
                    COALESCE(activity_count.count, 0) as activity_count_24h
                FROM datrix_users du
                LEFT JOIN (
                    SELECT user_id, COUNT(*) as count
                    FROM user_activity 
                    WHERE timestamp > NOW() - INTERVAL '24 hours'
                    GROUP BY user_id
                ) activity_count ON du.telegram_id = activity_count.user_id
                ORDER BY du.last_seen DESC NULLS LAST
            """)
            
            users = cur.fetchall()
            return [dict(user) for user in users]
            
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return []
    finally:
        conn.close()

# Original compatibility functions
def add_user(user_id, user_name):
    conn = get_db_connection()
    if not conn:
        return
        
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (id, user_name) 
                VALUES (%s, %s) 
                ON CONFLICT (id) DO NOTHING;
            """, (user_id, user_name))
            conn.commit()
    except Exception as e:
        logger.error(f"Error adding user: {e}")
    finally:
        conn.close()

def get_user_status(user_id):
    conn = get_db_connection()
    if not conn:
        return 'unregistered'
        
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM users WHERE id = %s;", (user_id,))
            result = cur.fetchone()
            return result[0] if result else 'unregistered'
    except Exception as e:
        logger.error(f"Error getting user status: {e}")
        return 'unregistered'
    finally:
        conn.close()

def update_user_status(user_id, status):
    conn = get_db_connection()
    if not conn:
        return
        
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET status = %s WHERE id = %s;", (status, user_id))
            conn.commit()
    except Exception as e:
        logger.error(f"Error updating user status: {e}")
    finally:
        conn.close()

def get_user_ids_for_broadcast(target_group):
    conn = get_db_connection()
    if not conn:
        return []
        
    try:
        with conn.cursor() as cur:
            if target_group == 'all': 
                cur.execute("SELECT telegram_id FROM datrix_users;")
            elif target_group == 'approved':
                cur.execute("""
                    SELECT telegram_id FROM datrix_users 
                    WHERE license_status = 'active' 
                    AND (license_expires IS NULL OR license_expires > CURRENT_DATE)
                """)
            else: 
                cur.execute("SELECT id FROM users WHERE status = %s;", (target_group,))
            return [row[0] for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Error getting broadcast users: {e}")
        return []
    finally:
        conn.close()

def queue_broadcast(target_group, message):
    conn = get_db_connection()
    if not conn:
        return
        
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO broadcast_queue (target_group, message) 
                VALUES (%s, %s);
            """, (target_group, message))
            conn.commit()
    except Exception as e:
        logger.error(f"Error queuing broadcast: {e}")
    finally:
        conn.close()

def get_pending_broadcasts():
    conn = get_db_connection()
    if not conn:
        return []
        
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, target_group, message 
                FROM broadcast_queue 
                WHERE sent_at IS NULL;
            """)
            return cur.fetchall()
    except Exception as e:
        logger.error(f"Error getting broadcasts: {e}")
        return []
    finally:
        conn.close()

def mark_broadcast_as_sent(job_id):
    conn = get_db_connection()
    if not conn:
        return
        
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE broadcast_queue 
                SET sent_at = NOW() 
                WHERE id = %s;
            """, (job_id,))
            conn.commit()
    except Exception as e:
        logger.error(f"Error marking broadcast sent: {e}")
    finally:
        conn.close()

# File submissions
def add_file_submission(user_id, user_name, file_id, file_name, admin_message_id):
    conn = get_db_connection()
    if not conn:
        return None
        
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO file_submissions 
                (user_id, user_name, file_id, file_name, admin_message_id) 
                VALUES (%s, %s, %s, %s, %s) 
                RETURNING id;
            """, (user_id, user_name, file_id, file_name, admin_message_id))
            result = cur.fetchone()
            conn.commit()
            return result[0] if result else None
    except Exception as e:
        logger.error(f"Error adding file submission: {e}")
        return None
    finally:
        conn.close()

def get_submission_details(submission_id):
    conn = get_db_connection()
    if not conn:
        return None
        
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT user_id, file_id, file_name, admin_message_id 
                FROM file_submissions 
                WHERE id = %s;
            """, (submission_id,))
            return cur.fetchone()
    except Exception as e:
        logger.error(f"Error getting submission: {e}")
        return None
    finally:
        conn.close()

def delete_submission(submission_id):
    conn = get_db_connection()
    if not conn:
        return
        
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM file_submissions WHERE id = %s;", (submission_id,))
            conn.commit()
    except Exception as e:
        logger.error(f"Error deleting submission: {e}")
    finally:
        conn.close()
