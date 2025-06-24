# fix_database.py
# Fix database schema for DATRIX

import os
import psycopg2
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_database():
    """Fix database schema issues"""
    try:
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            logger.error("DATABASE_URL not found")
            return False
        
        conn = psycopg2.connect(database_url)
        with conn.cursor() as cur:
            logger.info("🔧 Starting database schema fix...")
            
            # 1. Check if broadcast_queue table exists and fix it
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'broadcast_queue' 
                AND column_name = 'message';
            """)
            
            if not cur.fetchone():
                logger.info("Adding missing 'message' column to broadcast_queue...")
                cur.execute("""
                    ALTER TABLE broadcast_queue 
                    ADD COLUMN IF NOT EXISTS message TEXT NOT NULL DEFAULT '';
                """)
            
            # 2. Create DATRIX tables if they don't exist
            logger.info("Creating DATRIX tables...")
            
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
            
            # Insert default DATRIX file if not exists
            cur.execute("""
                INSERT INTO stored_files (file_key, description, version, file_size, filename)
                VALUES ('datrix_app', 'DATRIX Accounting Application', 'v2.1.6', '100MB', 'DATRIX_Setup.exe')
                ON CONFLICT (file_key) DO NOTHING;
            """)
            
            # Create indexes
            cur.execute("CREATE INDEX IF NOT EXISTS idx_datrix_users_telegram_id ON datrix_users(telegram_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_user_activity_user_id ON user_activity(user_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_user_activity_timestamp ON user_activity(timestamp);")
            
            conn.commit()
            logger.info("✅ Database schema fixed successfully!")
            return True
            
    except Exception as e:
        logger.error(f"❌ Database fix failed: {e}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    fix_database()
