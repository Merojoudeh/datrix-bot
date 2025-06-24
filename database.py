# database.py
# Clean DATRIX Database (Fixed - No first_name column)

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

def fix_database_schema():
    """Fix missing columns in existing database"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cur:
            # Check if first_name column exists
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'datrix_users' AND column_name = 'first_name'
            """)
            
            if not cur.fetchone():
                # Add first_name column if it doesn't exist
                cur.execute("ALTER TABLE datrix_users ADD COLUMN first_name TEXT")
                logger.info("✅ Added first_name column")
            
            # Check other missing columns
            missing_columns = [
                ('license_status', 'TEXT DEFAULT \'active\''),
                ('app_version', 'TEXT'),
            ]
            
            for col_name, col_def in missing_columns:
                cur.execute(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'datrix_users' AND column_name = '{col_name}'
                """)
                
                if not cur.fetchone():
                    cur.execute(f"ALTER TABLE datrix_users ADD COLUMN {col_name} {col_def}")
                    logger.info(f"✅ Added {col_name} column")
            
            conn.commit()
            logger.info("✅ Database schema fixed successfully")
            return True
            
    except Exception as e:
        logger.error(f"Error fixing database schema: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def initialize_simple_database():
    """Initialize database and fix schema issues"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cur:
            # Create table with all columns
            cur.execute("""
                CREATE TABLE IF NOT EXISTS datrix_users (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    user_name TEXT,
                    first_name TEXT,
                    company_name TEXT,
                    google_sheet_id TEXT,
                    license_expires DATE,
                    license_status TEXT DEFAULT 'active',
                    app_version TEXT,
                    download_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    last_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            
            # Create activity table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_activity (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT,
                    activity_type TEXT,
                    activity_data TEXT,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            
            conn.commit()
            logger.info("✅ Database tables created/updated")
            
        # Fix any missing columns in existing database
        fix_database_schema()
        
        return True
        
    except Exception as e:
        logger.error(f"Database init failed: {e}")
        return False
    finally:
        conn.close()

def add_or_update_user(telegram_id, user_name, first_name=None):
    """Add or update user - no first_name column"""
    conn = get_db_connection()
    if not conn:
        return False
        
    try:
        with conn.cursor() as cur:
            # Use first_name as user_name if user_name is empty
            display_name = user_name or first_name or f"User_{telegram_id}"
            
            cur.execute("""
                INSERT INTO datrix_users (telegram_id, user_name, last_seen)
                VALUES (%s, %s, NOW())
                ON CONFLICT (telegram_id) 
                DO UPDATE SET 
                    user_name = EXCLUDED.user_name,
                    last_seen = NOW()
            """, (telegram_id, display_name))
            
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
    """Get user information - no first_name"""
    conn = get_db_connection()
    if not conn:
        return None
        
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT telegram_id, user_name, company_name, 
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
                    'company_name': row[2],
                    'google_sheet_id': row[3],
                    'license_expires': row[4],
                    'download_count': row[5],
                    'created_at': row[6],
                    'last_seen': row[7]
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
                SET license_expires = %s, license_status = 'active', last_seen = NOW()
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
            
            # Log activity
            cur.execute("""
                INSERT INTO user_activity (telegram_id, activity_type, activity_data)
                VALUES (%s, %s, %s)
            """, (telegram_id, 'download', 'DATRIX app downloaded'))
            
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error tracking download: {e}")
        return False
    finally:
        conn.close()

def get_all_datrix_users():
    """Get all users for dashboard - with fallback"""
    conn = get_db_connection()
    if not conn:
        return []
        
    try:
        with conn.cursor() as cur:
            # Try with first_name first
            try:
                cur.execute("""
                    SELECT 
                        telegram_id,
                        user_name,
                        first_name,
                        company_name,
                        google_sheet_id,
                        license_expires,
                        COALESCE(license_status, 'active') as license_status,
                        app_version,
                        download_count,
                        created_at,
                        last_seen,
                        CASE 
                            WHEN license_expires > CURRENT_DATE THEN true 
                            ELSE false 
                        END as is_app_user
                    FROM datrix_users
                    ORDER BY last_seen DESC NULLS LAST
                """)
                
                users = []
                for row in cur.fetchall():
                    users.append({
                        'telegram_id': row[0],
                        'user_name': row[1] or row[2] or f'User_{row[0]}',  # user_name or first_name
                        'company_name': row[3],
                        'google_sheet_id': row[4],
                        'license_expires': row[5],
                        'license_status': row[6],
                        'app_version': row[7],
                        'total_downloads': row[8],
                        'created_at': row[9],
                        'last_seen': row[10],
                        'is_app_user': row[11]
                    })
                return users
                
            except Exception as column_error:
                # Fallback without first_name if column doesn't exist
                logger.warning(f"Using fallback query: {column_error}")
                cur.execute("""
                    SELECT 
                        telegram_id,
                        user_name,
                        company_name,
                        google_sheet_id,
                        license_expires,
                        download_count,
                        created_at,
                        last_seen,
                        CASE 
                            WHEN license_expires > CURRENT_DATE THEN true 
                            ELSE false 
                        END as is_app_user
                    FROM datrix_users
                    ORDER BY last_seen DESC NULLS LAST
                """)
                
                users = []
                for row in cur.fetchall():
                    users.append({
                        'telegram_id': row[0],
                        'user_name': row[1] or f'User_{row[0]}',
                        'company_name': row[2],
                        'google_sheet_id': row[3],
                        'license_expires': row[4],
                        'license_status': 'active',
                        'app_version': None,
                        'total_downloads': row[5],
                        'created_at': row[6],
                        'last_seen': row[7],
                        'is_app_user': row[8]
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
        return {
            'total_users': 0,
            'active_users': 0,
            'downloads_today': 0,
            'licensed_users': 0
        }
        
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
            
            # Total downloads
            cur.execute("""
                SELECT COALESCE(SUM(download_count), 0) FROM datrix_users
            """)
            total_downloads = cur.fetchone()[0]
            
            # Licensed users
            cur.execute("""
                SELECT COUNT(*) FROM datrix_users 
                WHERE license_expires > CURRENT_DATE
            """)
            licensed_users = cur.fetchone()[0]
            
            return {
                'total_users': total_users,
                'active_users': active_users,
                'downloads_today': total_downloads,
                'licensed_users': licensed_users
            }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return {
            'total_users': 0,
            'active_users': 0,
            'downloads_today': 0,
            'licensed_users': 0
        }
    finally:
        conn.close()

def log_user_activity(telegram_id, activity_type, activity_data=""):
    """Log user activity"""
    conn = get_db_connection()
    if not conn:
        return False
        
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_activity (telegram_id, activity_type, activity_data)
                VALUES (%s, %s, %s)
            """, (telegram_id, activity_type, activity_data))
            
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error logging activity: {e}")
        return False
    finally:
        conn.close()

# NO BROADCAST FUNCTIONS - COMPLETELY REMOVED
