# database.py
# Simplified DATRIX Database

import os
import psycopg2
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    try:
        return psycopg2.connect(os.environ['DATABASE_URL'])
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return None

def initialize_simple_database():
    """Initialize only essential tables"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cur:
            # Simple users table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS datrix_users (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    user_name TEXT,
                    first_name TEXT,
                    company_name TEXT,
                    google_sheet_id TEXT,
                    license_expires DATE,
                    download_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    last_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            
            conn.commit()
            logger.info("✅ Simple database initialized")
            return True
            
    except Exception as e:
        logger.error(f"Database init failed: {e}")
        return False
    finally:
        conn.close()

def add_or_update_user(telegram_id, user_name, first_name=None):
    """Add or update user"""
    conn = get_db_connection()
    if not conn:
        return False
        
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO datrix_users (telegram_id, user_name, first_name, last_seen)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (telegram_id) 
                DO UPDATE SET 
                    user_name = EXCLUDED.user_name,
                    first_name = EXCLUDED.first_name,
                    last_seen = NOW()
            """, (telegram_id, user_name, first_name))
            
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error adding user: {e}")
        return False
    finally:
        conn.close()

def update_user_company(telegram_id, company_name, google_sheet_id):
    """Update user company info"""
    conn = get_db_connection()
    if not conn:
        return False
        
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE datrix_users 
                SET company_name = %s, google_sheet_id = %s, last_seen = NOW()
                WHERE telegram_id = %s
            """, (company_name, google_sheet_id, telegram_id))
            
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error updating company: {e}")
        return False
    finally:
        conn.close()

def get_user_info(telegram_id):
    """Get user information"""
    conn = get_db_connection()
    if not conn:
        return None
        
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT telegram_id, user_name, first_name, company_name, 
                       google_sheet_id, license_expires, download_count, 
                       created_at, last_seen
                FROM datrix_users 
                WHERE telegram_id = %s
            """, (telegram_id,))
            
            row = cur.fetchone()
            if row:
                return {
                    'telegram_id': row[0],
                    'user_name': row[1],
                    'first_name': row[2],
                    'company_name': row[3],
                    'google_sheet_id': row[4],
                    'license_expires': row[5],
                    'download_count': row[6],
                    'created_at': row[7],
                    'last_seen': row[8]
                }
            return None
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        return None
    finally:
        conn.close()

def extend_user_license(telegram_id, days):
    """Extend user license"""
    conn = get_db_connection()
    if not conn:
        return False
        
    try:
        with conn.cursor() as cur:
            new_expiry = datetime.now().date() + timedelta(days=days)
            
            cur.execute("""
                UPDATE datrix_users 
                SET license_expires = %s, last_seen = NOW()
                WHERE telegram_id = %s
            """, (new_expiry, telegram_id))
            
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error extending license: {e}")
        return False
    finally:
        conn.close()

def track_download(telegram_id):
    """Track download"""
    conn = get_db_connection()
    if not conn:
        return False
        
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE datrix_users 
                SET download_count = download_count + 1, last_seen = NOW()
                WHERE telegram_id = %s
            """, (telegram_id,))
            
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error tracking download: {e}")
        return False
    finally:
        conn.close()

def get_all_datrix_users():
    """Get all users for dashboard"""
    conn = get_db_connection()
    if not conn:
        return []
        
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT telegram_id, user_name, first_name, company_name,
                       google_sheet_id, license_expires, download_count,
                       created_at, last_seen
                FROM datrix_users 
                ORDER BY last_seen DESC NULLS LAST
            """)
            
            users = []
            for row in cur.fetchall():
                users.append({
                    'telegram_id': row[0],
                    'user_name': row[1] or row[2],  # user_name or first_name
                    'company_name': row[3],
                    'google_sheet_id': row[4],
                    'license_expires': row[5],
                    'total_downloads': row[6],
                    'created_at': row[7],
                    'last_seen': row[8]
                })
            
            return users
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return []
    finally:
        conn.close()

def get_basic_stats():
    """Get basic statistics"""
    conn = get_db_connection()
    if not conn:
        return {}
        
    try:
        with conn.cursor() as cur:
            # Total users
            cur.execute("SELECT COUNT(*) FROM datrix_users")
            total_users = cur.fetchone()[0]
            
            # Active users (24h)
            cur.execute("""
                SELECT COUNT(*) FROM datrix_users 
                WHERE last_seen > NOW() - INTERVAL '24 hours'
            """)
            active_users = cur.fetchone()[0]
            
            # Downloads today
            cur.execute("""
                SELECT COALESCE(SUM(download_count), 0) FROM datrix_users
            """)
            total_downloads = cur.fetchone()[0]
            
            return {
                'total_users': total_users,
                'active_users': active_users,
                'downloads_today': total_downloads
            }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return {}
    finally:
        conn.close()
