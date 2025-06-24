# V 19
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
import os
import logging
import json
import psycopg2
import requests
from datetime import datetime, timedelta
import asyncio

# Enhanced logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO,
    handlers=[
        logging.FileHandler('datrix_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
DEFAULT_CONFIG = {
    'BOT_TOKEN': '7803291138:AAExEBQq9uZhq6X_ncI_c8E2J80-tpZtq8E',
    'ADMIN_CHAT_ID': '811896458',
    'STORAGE_CHANNEL_ID': '-1002807912676',
    'DATABASE_URL': os.environ.get('DATABASE_URL')
}

def load_config():
    """Load configuration from environment or defaults"""
    try:
        if os.path.exists('config.json'):
            with open('config.json', 'r') as f:
                config = json.load(f)
                logger.info("✅ Configuration loaded from config.json")
                return config
    except Exception as e:
        logger.warning(f"⚠️ Could not load config.json: {e}")
    
    config = {
        'BOT_TOKEN': os.environ.get('BOT_TOKEN', DEFAULT_CONFIG['BOT_TOKEN']),
        'ADMIN_CHAT_ID': os.environ.get('ADMIN_CHAT_ID', DEFAULT_CONFIG['ADMIN_CHAT_ID']),
        'STORAGE_CHANNEL_ID': os.environ.get('STORAGE_CHANNEL_ID', DEFAULT_CONFIG['STORAGE_CHANNEL_ID']),
        'DATABASE_URL': os.environ.get('DATABASE_URL', DEFAULT_CONFIG['DATABASE_URL'])
    }
    logger.info("✅ Using environment/default configuration")
    return config

def save_config(config):
    """Save configuration to file"""
    try:
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=2)
        logger.info("✅ Configuration saved")
        return True
    except Exception as e:
        logger.error(f"❌ Could not save config: {e}")
        return False

# Database functions
def get_db_connection():
    """Get database connection"""
    try:
        return psycopg2.connect(CONFIG['DATABASE_URL'])
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return None

def initialize_database():
    """Initialize database tables"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cur:
            # Original users table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id BIGINT PRIMARY KEY,
                    user_name TEXT,
                    status TEXT DEFAULT 'pending'
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
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            
            # User activity table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_activity (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES datrix_users(telegram_id),
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
                    status TEXT DEFAULT 'pending',
                    admin_response TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    processed_at TIMESTAMP WITH TIME ZONE
                );
            """)
            
            # Bot statistics table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bot_stats (
                    id SERIAL PRIMARY KEY,
                    total_users INTEGER DEFAULT 0,
                    active_users_24h INTEGER DEFAULT 0,
                    total_messages INTEGER DEFAULT 0,
                    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            
            # Insert default file entry
            cur.execute("""
                INSERT INTO stored_files (file_key, description, version, file_size, filename)
                VALUES ('datrix_app', 'DATRIX Accounting Application', 'v2.1.6', '100MB', 'DATRIX_Setup.exe')
                ON CONFLICT (file_key) DO NOTHING;
            """)
            
            conn.commit()
            logger.info("✅ Database initialized successfully")
            return True
            
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        return False
    finally:
        conn.close()

# Load configuration
CONFIG = load_config()
BOT_TOKEN = CONFIG['BOT_TOKEN']
ADMIN_CHAT_ID = CONFIG['ADMIN_CHAT_ID']
STORAGE_CHANNEL_ID = CONFIG['STORAGE_CHANNEL_ID']

# Initialize database
initialize_database()

# Bot handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message with user registration"""
    user = update.effective_user
    
    # Register in both tables
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                # Original users table
                cur.execute("""
                    INSERT INTO users (id, user_name) 
                    VALUES (%s, %s) 
                    ON CONFLICT (id) DO NOTHING
                """, (user.id, user.username or user.first_name))
                
                # DATRIX users table (basic registration)
                cur.execute("""
                    INSERT INTO datrix_users (telegram_id, user_name) 
                    VALUES (%s, %s) 
                    ON CONFLICT (telegram_id) 
                    DO UPDATE SET last_seen = NOW()
                """, (user.id, user.username or user.first_name))
                
                conn.commit()
        except Exception as e:
            logger.error(f"Error registering user: {e}")
        finally:
            conn.close()
    
    welcome_message = """🤖 **مرحباً بك في DATRIX Bot**

📋 **الأوامر المتاحة:**
• `/datrix_app` - تحميل تطبيق DATRIX
• `/list_files` - عرض الملفات المتاحة
• `/register_company` - تسجيل شركتك
• `/request_license` - طلب ترخيص جديد
• `/my_status` - حالة حسابك
• `/status` - حالة البوت
• `/help` - المساعدة

🌐 **يعمل 24/7 على الخادم السحابي**
⚡ **تحميل فوري عبر قناة التخزين**
📁 **دعم الملفات الكبيرة (+100MB)**

💡 **كيف يعمل:** الملفات محفوظة في قناتنا السحابية ويتم إرسالها لك فوراً!"""
    
    await update.message.reply_text(welcome_message, parse_mode='Markdown')
    logger.info(f"✅ User {user.id} ({user.username}) started the bot")

async def register_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Register company information"""
    user = update.effective_user
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "📝 **استخدام الأمر:**\n"
            "`/register_company [اسم الشركة] [Google Sheet ID]`\n\n"
            "**مثال:**\n"
            "`/register_company \"شركة المستقبل\" 1OTNGDMgnVdkhqN9t2ESvuXA`",
            parse_mode='Markdown'
        )
        return
    
    company_name = context.args[0]
    sheet_id = context.args[1]
    
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE datrix_users 
                    SET company_name = %s, google_sheet_id = %s, last_seen = NOW()
                    WHERE telegram_id = %s
                """, (company_name, sheet_id, user.id))
                conn.commit()
                
                await update.message.reply_text(
                    f"✅ **تم تسجيل بيانات الشركة بنجاح!**\n\n"
                    f"🏢 **الشركة:** {company_name}\n"
                    f"📊 **Sheet ID:** `{sheet_id}`\n"
                    f"📅 **تاريخ التسجيل:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                    f"💡 يمكنك الآن طلب ترخيص باستخدام `/request_license`",
                    parse_mode='Markdown'
                )
                
                # Notify admin
                admin_msg = f"""🆕 **تسجيل شركة جديدة**

👤 **المستخدم:** {user.first_name} (@{user.username})
🆔 **Telegram ID:** `{user.id}`
🏢 **الشركة:** {company_name}
📊 **Sheet ID:** `{sheet_id}`
📅 **التاريخ:** {datetime.now().strftime('%Y-%m-%d %H:%M')}"""

                await context.bot.send_message(ADMIN_CHAT_ID, admin_msg, parse_mode='Markdown')
                logger.info(f"✅ Company registered: {company_name} by user {user.id}")
                
        except Exception as e:
            logger.error(f"Error registering company: {e}")
            await update.message.reply_text("❌ خطأ في تسجيل البيانات. يرجى المحاولة مرة أخرى.")
        finally:
            conn.close()

async def request_license(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request license extension"""
    user = update.effective_user
    
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                # Get user info
                cur.execute("""
                    SELECT company_name, google_sheet_id 
                    FROM datrix_users 
                    WHERE telegram_id = %s
                """, (user.id,))
                
                user_info = cur.fetchone()
                if not user_info or not user_info[0]:
                    await update.message.reply_text(
                        "❌ **يجب تسجيل بيانات الشركة أولاً**\n\n"
                        "استخدم الأمر: `/register_company [اسم الشركة] [Sheet ID]`",
                        parse_mode='Markdown'
                    )
                    return
                
                company_name, sheet_id = user_info
                
                # Add license request
                cur.execute("""
                    INSERT INTO license_requests (user_id, company_name, google_sheet_id)
                    VALUES (%s, %s, %s)
                """, (user.id, company_name, sheet_id))
                conn.commit()
                
                # Create admin keyboard
                keyboard = [
                    [
                        InlineKeyboardButton("منح 30 يوم", callback_data=f"extend_30:{user.id}"),
                        InlineKeyboardButton("منح 90 يوم", callback_data=f"extend_90:{user.id}"),
                    ],
                    [
                        InlineKeyboardButton("منح سنة كاملة", callback_data=f"extend_365:{user.id}"),
                        InlineKeyboardButton("رفض الطلب", callback_data=f"extend_deny:{user.id}"),
                    ]
                ]
                markup = InlineKeyboardMarkup(keyboard)
                
                admin_msg = f"""🔑 **طلب تمديد ترخيص DATRIX**

👤 **المستخدم:** {user.first_name} (@{user.username})
🆔 **Telegram ID:** `{user.id}`
🏢 **الشركة:** {company_name}
📊 **Sheet ID:** `{sheet_id}`
📅 **تاريخ الطلب:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

⏰ **يرجى اختيار فترة التمديد:**"""
                
                await context.bot.send_message(
                    ADMIN_CHAT_ID, 
                    admin_msg, 
                    reply_markup=markup,
                    parse_mode='Markdown'
                )
                
                await update.message.reply_text(
                    "✅ **تم إرسال طلب التمديد للمراجعة**\n\n"
                    "📧 سيتم إشعارك فور الموافقة على الطلب\n"
                    "⏰ عادة ما يتم الرد خلال 24 ساعة",
                    parse_mode='Markdown'
                )
                
                logger.info(f"✅ License request from user {user.id} ({company_name})")
                
        except Exception as e:
            logger.error(f"Error processing license request: {e}")
            await update.message.reply_text("❌ خطأ في إرسال الطلب. يرجى المحاولة مرة أخرى.")
        finally:
            conn.close()

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks"""
    query = update.callback_query
    await query.answer()
    
    if not str(query.from_user.id) == ADMIN_CHAT_ID:
        await query.answer("غير مسموح", show_alert=True)
        return
    
    data = query.data
    
    if data.startswith("extend_"):
        action, user_id_str = data.split(":", 1)
        user_id = int(user_id_str)
        
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    if action == "extend_deny":
                        # Deny request
                        await query.edit_message_text(
                            f"❌ **تم رفض طلب تمديد الترخيص للمستخدم {user_id}**"
                        )
                        
                        await context.bot.send_message(
                            user_id,
                            "❌ **تم رفض طلب تمديد الترخيص**\n\n"
                            "يرجى التواصل مع الإدارة لمزيد من المعلومات."
                        )
                        
                    else:
                        # Grant license
                        days_map = {
                            "extend_30": 30,
                            "extend_90": 90,
                            "extend_365": 365
                        }
                        
                        days = days_map.get(action, 30)
                        new_expiry = datetime.now() + timedelta(days=days)
                        
                        # Update license
                        cur.execute("""
                            UPDATE datrix_users 
                            SET license_expires = %s, license_status = 'active'
                            WHERE telegram_id = %s
                        """, (new_expiry.date(), user_id))
                        
                        # Update license requests
                        cur.execute("""
                            UPDATE license_requests 
                            SET status = 'approved', processed_at = NOW()
                            WHERE user_id = %s AND status = 'pending'
                        """, (user_id,))
                        
                        conn.commit()
                        
                        await query.edit_message_text(
                            f"✅ **تم منح ترخيص {days} يوم للمستخدم {user_id}**\n"
                            f"📅 **ينتهي في:** {new_expiry.strftime('%Y-%m-%d')}"
                        )
                        
                        await context.bot.send_message(
                            user_id,
                            f"🎉 **تم قبول طلب تمديد الترخيص!**\n\n"
                            f"⏰ **المدة الممنوحة:** {days} يوم\n"
                            f"📅 **ينتهي في:** {new_expiry.strftime('%Y-%m-%d')}\n\n"
                            f"✅ يمكنك الآن استخدام DATRIX بكامل المميزات!",
                            parse_mode='Markdown'
                        )
                        
                        logger.info(f"✅ License granted: {days} days to user {user_id}")
                        
            except Exception as e:
                logger.error(f"Error processing license: {e}")
            finally:
                conn.close()

async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user status"""
    user = update.effective_user
    
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT company_name, google_sheet_id, license_expires, 
                           license_status, app_version, last_seen
                    FROM datrix_users 
                    WHERE telegram_id = %s
                """, (user.id,))
                
                user_info = cur.fetchone()
                if not user_info:
                    await update.message.reply_text(
                        "❌ **لم يتم العثور على بياناتك**\n\n"
                        "يرجى استخدام `/register_company` للتسجيل أولاً.",
                        parse_mode='Markdown'
                    )
                    return
                
                company, sheet_id, license_exp, license_stat, version, last_seen = user_info
                
                # Calculate days remaining
                if license_exp:
                    days_remaining = (license_exp - datetime.now().date()).days
                    if days_remaining > 0:
                        license_text = f"✅ نشط ({days_remaining} يوم متبقي)"
                    else:
                        license_text = f"❌ منتهي الصلاحية ({abs(days_remaining)} يوم)"
                else:
                    license_text = "⚠️ غير محدد"
                
                status_msg = f"""📊 **حالة حسابك في DATRIX**

👤 **المستخدم:** {user.first_name}
🆔 **Telegram ID:** `{user.id}`
🏢 **الشركة:** {company or 'غير مسجل'}
📊 **Sheet ID:** `{sheet_id or 'غير محدد'}`

🔑 **حالة الترخيص:** {license_text}
📅 **تاريخ انتهاء الترخيص:** {license_exp or 'غير محدد'}
📱 **إصدار التطبيق:** {version or 'غير محدد'}
⏰ **آخر نشاط:** {last_seen.strftime('%Y-%m-%d %H:%M') if last_seen else 'غير محدد'}

💡 **إجراءات متاحة:**
• `/request_license` - طلب تمديد الترخيص
• `/datrix_app` - تحميل التطبيق"""
                
                await update.message.reply_text(status_msg, parse_mode='Markdown')
                
        except Exception as e:
            logger.error(f"Error getting user status: {e}")
            await update.message.reply_text("❌ خطأ في جلب البيانات.")
        finally:
            conn.close()

async def track_user_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Track user activity (for app integration)"""
    user = update.effective_user
    
    if len(context.args) < 1:
        await update.message.reply_text("❌ تنسيق خاطئ للأمر")
        return
    
    try:
        activity_data = json.loads(' '.join(context.args))
        
        conn = get_db_connection()
        if conn:
            with conn.cursor() as cur:
                # Update last seen
                cur.execute("""
                    UPDATE datrix_users 
                    SET last_seen = NOW() 
                    WHERE telegram_id = %s
                """, (user.id,))
                
                # Add activity
                cur.execute("""
                    INSERT INTO user_activity (user_id, activity_type, activity_data)
                    VALUES (%s, %s, %s)
                """, (
                    user.id,
                    activity_data.get('activity_type'),
                    json.dumps(activity_data.get('metadata', {}))
                ))
                conn.commit()
                
            conn.close()
            
        await update.message.reply_text("✅ تم تسجيل النشاط")
        
    except Exception as e:
        logger.error(f"Error tracking activity: {e}")
        await update.message.reply_text("❌ خطأ في تسجيل النشاط")

async def get_datrix_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Download DATRIX app with license check"""
    user = update.effective_user
    
    # Check license first
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT license_expires, license_status, company_name
                    FROM datrix_users 
                    WHERE telegram_id = %s
                """, (user.id,))
                
                user_info = cur.fetchone()
                if user_info:
                    license_exp, license_stat, company = user_info
                    
                    # Check if license is valid
                    if license_exp and license_exp > datetime.now().date():
                        # License is valid, proceed with download
                        pass
                    else:
                        await update.message.reply_text(
                            "🔒 **الترخيص منتهي الصلاحية**\n\n"
                            "يرجى طلب تمديد الترخيص باستخدام `/request_license`\n"
                            "أو التواصل مع الإدارة.",
                            parse_mode='Markdown'
                        )
                        conn.close()
                        return
                        
        except Exception as e:
            logger.error(f"Error checking license: {e}")
        finally:
            conn.close()
    
    # Get file info from database
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT message_id, version, file_size, description, upload_date
                    FROM stored_files 
                    WHERE file_key = 'datrix_app'
                """, )
                
                file_info = cur.fetchone()
                if not file_info or not file_info[0]:
                    await update.message.reply_text(
                        "❌ **ملف DATRIX غير متاح حالياً**\n\n"
                        "يرجى التواصل مع الإدارة.",
                        parse_mode='Markdown'
                    )
                    conn.close()
                    return
                
                message_id, version, file_size, description, upload_date = file_info
                
        except Exception as e:
            logger.error(f"Error getting file info: {e}")
            await update.message.reply_text("❌ خطأ في جلب معلومات الملف")
            conn.close()
            return
        finally:
            conn.close()
    
    try:
        # Forward file from storage channel
        await context.bot.forward_message(
            chat_id=update.effective_chat.id,
            from_chat_id=STORAGE_CHANNEL_ID,
            message_id=message_id
        )
        
        # Send confirmation
        await update.message.reply_text(
            f"✅ **تم إرسال {description}!**\n\n"
            f"🔢 **الإصدار:** {version}\n"
            f"💾 **الحجم:** {file_size}\n"
            f"⚡ **طريقة التسليم:** فوري من التخزين السحابي\n"
            f"📅 **آخر تحديث:** {upload_date.strftime('%Y-%m-%d') if upload_date else 'مؤخراً'}\n\n"
            f"🚀 **استمتع باستخدام DATRIX!**",
            parse_mode='Markdown'
        )
        
        # Track download activity
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO user_activity (user_id, activity_type, activity_data)
                        VALUES (%s, %s, %s)
                    """, (user.id, 'app_download', json.dumps({'version': version})))
                    conn.commit()
            except Exception as e:
                logger.error(f"Error tracking download: {e}")
            finally:
                conn.close()
        
        logger.info(f"✅ DATRIX app delivered to user {user.id} ({user.username})")
        
    except Exception as e:
        logger.error(f"❌ Error delivering file to {user.id}: {e}")
        await update.message.reply_text(
            "❌ **خطأ في التحميل**\n\nعذراً، حدث خطأ في تسليم الملف. يرجى المحاولة مرة أخرى.",
            parse_mode='Markdown'
        )

async def list_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List available files"""
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT file_key, description, version, file_size, 
                           filename, message_id, upload_date
                    FROM stored_files
                """)
                
                files = cur.fetchall()
                
                if not files:
                    await update.message.reply_text("📂 لا توجد ملفات متاحة حالياً")
                    return
                
                text = "📂 **الملفات المتاحة:**\n\n"
                
                for file_data in files:
                    key, desc, version, size, filename, msg_id, upload_date = file_data
                    
                    if msg_id:
                        status = "✅ متاح للتحميل الفوري"
                        download_cmd = f"/{key}"
                    else:
                        status = "❌ لم يتم رفعه بعد"
                        download_cmd = "غير متاح"
                    
                    text += f"📄 **{desc}**\n"
                    text += f"🔢 الإصدار: `{version}`\n"
                    text += f"💾 الحجم: `{size}`\n"
                    text += f"📁 الملف: `{filename}`\n"
                    text += f"📊 الحالة: {status}\n"
                    text += f"⌨️ الأمر: `{download_cmd}`\n"
                    if upload_date:
                        text += f"📅 التحديث: {upload_date.strftime('%Y-%m-%d')}\n"
                    text += "\n"
                
                await update.message.reply_text(text, parse_mode='Markdown')
                
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            await update.message.reply_text("❌ خطأ في جلب قائمة الملفات")
        finally:
            conn.close()

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot status with enhanced statistics"""
    try:
        uptime = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # Get statistics from database
        conn = get_db_connection()
        total_users = 0
        active_users = 0
        total_messages = 0
        
        if conn:
            try:
                with conn.cursor() as cur:
                    # Total DATRIX users
                    cur.execute("SELECT COUNT(*) FROM datrix_users")
                    total_users = cur.fetchone()[0]
                    
                    # Active users (last 24h)
                    cur.execute("""
                        SELECT COUNT(*) FROM datrix_users 
                        WHERE last_seen > NOW() - INTERVAL '24 hours'
                    """)
                    active_users = cur.fetchone()[0]
                    
                    # Total activities
                    cur.execute("SELECT COUNT(*) FROM user_activity")
                    total_messages = cur.fetchone()[0]
                    
            except Exception as e:
                logger.error(f"Error getting stats: {e}")
            finally:
                conn.close()
        
        # Get file status
        file_status = "❌ غير مكون"
        file_version = "غير محدد"
        
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT message_id, version FROM stored_files 
                        WHERE file_key = 'datrix_app'
                    """)
                    file_info = cur.fetchone()
                    if file_info and file_info[0]:
                        file_status = "✅ جاهز للتسليم الفوري"
                        file_version = file_info[1]
            except Exception as e:
                logger.error(f"Error getting file status: {e}")
            finally:
                conn.close()
        
        status_msg = f"""🟢 **حالة DATRIX Bot**

✅ **الحالة:** يعمل بشكل طبيعي
🌐 **الخادم:** Railway Cloud Platform  
⏰ **الوقت الحالي:** `{uptime}`
🔄 **إعادة التشغيل التلقائي:** مفعل

📊 **إحصائيات المستخدمين:**
👥 **إجمالي المستخدمين:** {total_users}
🟢 **نشط (24 ساعة):** {active_users}
📈 **إجمالي الأنشطة:** {total_messages}

📁 **حالة ملف DATRIX:** {file_status}
🔢 **الإصدار:** `{file_version}`

⚡ **طريقة التسليم:** إعادة توجيه من القناة (فوري)
🚀 **أقصى حجم ملف:** 2GB (حد تليغرام)
🎯 **الأداء:** محسن للسرعة

👤 **طلب من:** {update.effective_user.first_name}
🆔 **معرف المستخدم:** `{update.effective_user.id}`"""
        
        await update.message.reply_text(status_msg, parse_mode='Markdown')
        logger.info(f"✅ Status check by user {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"❌ Error in status command: {e}")
        await update.message.reply_text("❌ عذراً، حدث خطأ. يرجى المحاولة مرة أخرى.")

# Admin commands
async def set_file_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set file message ID and info (Admin only)"""
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ **مطلوب صلاحية المشرف.**", parse_mode='Markdown')
        return
    
    if len(context.args) < 1:
        await update.message.reply_text(
            "📝 **الاستخدام:** `/set_file [message_id] [version] [size]`\n\n"
            "**مثال:** `/set_file 123 v2.1.7 125MB`",
            parse_mode='Markdown'
        )
        return
    
    try:
        message_id = int(context.args[0])
        version = context.args[1] if len(context.args) > 1 else "v2.1.6"
        size = context.args[2] if len(context.args) > 2 else "Unknown"
        
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE stored_files 
                        SET message_id = %s, version = %s, file_size = %s, upload_date = NOW()
                        WHERE file_key = 'datrix_app'
                    """, (message_id, version, size))
                    conn.commit()
                    
                await update.message.reply_text(
                    f"✅ **تم تحديث معلومات الملف!**\n\n"
                    f"🆔 **معرف الرسالة:** `{message_id}`\n"
                    f"🔢 **الإصدار:** `{version}`\n"
                    f"💾 **الحجم:** `{size}`\n"
                    f"📅 **التحديث:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                    f"🚀 **الملف متاح الآن للتسليم الفوري!**",
                    parse_mode='Markdown'
                )
                
                logger.info(f"✅ Admin updated file info: ID={message_id}, Version={version}")
                
            except Exception as e:
                logger.error(f"Error updating file info: {e}")
                await update.message.reply_text("❌ خطأ في تحديث معلومات الملف")
            finally:
                conn.close()
                
    except ValueError:
        await update.message.reply_text("❌ **خطأ:** معرف الرسالة يجب أن يكون رقماً", parse_mode='Markdown')
    except Exception as e:
        logger.error(f"❌ Error in set_file_info: {e}")
        await update.message.reply_text(f"❌ **خطأ:** {str(e)}", parse_mode='Markdown')

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin statistics"""
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ **مطلوب صلاحية المشرف.**", parse_mode='Markdown')
        return
    
    conn = get_db_connection()
    if conn:
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
                active_24h = cur.fetchone()[0]
                
                # Active users (7 days)
                cur.execute("""
                    SELECT COUNT(*) FROM datrix_users 
                    WHERE last_seen > NOW() - INTERVAL '7 days'
                """)
                active_7d = cur.fetchone()[0]
                
                # License requests
                cur.execute("""
                    SELECT COUNT(*) FROM license_requests 
                    WHERE status = 'pending'
                """)
                pending_requests = cur.fetchone()[0]
                
                # Top activities
                cur.execute("""
                    SELECT activity_type, COUNT(*) 
                    FROM user_activity 
                    WHERE timestamp > NOW() - INTERVAL '7 days'
                    GROUP BY activity_type 
                    ORDER BY COUNT(*) DESC 
                    LIMIT 5
                """)
                top_activities = cur.fetchall()
                
                # Recent registrations
                cur.execute("""
                    SELECT user_name, company_name, created_at
                    FROM datrix_users 
                    WHERE created_at > NOW() - INTERVAL '7 days'
                    ORDER BY created_at DESC 
                    LIMIT 5
                """)
                recent_users = cur.fetchall()
                
                stats_msg = f"""📊 **إحصائيات DATRIX المتقدمة**

👥 **المستخدمين:**
• إجمالي المستخدمين: {total_users}
• نشط (24 ساعة): {active_24h}
• نشط (7 أيام): {active_7d}

🔑 **طلبات التراخيص:**
• في الانتظار: {pending_requests}

📈 **الأنشطة الأكثر (7 أيام):**"""

                for activity, count in top_activities:
                    activity_emoji = {
                        'app_download': '📦',
                        'excel_open': '📊',
                        'deportation': '📤',
                        'login': '🔐'
                    }.get(activity, '📌')
                    
                    stats_msg += f"\n• {activity_emoji} {activity}: {count}"
                
                if recent_users:
                    stats_msg += f"\n\n👤 **تسجيلات حديثة:**"
                    for user_name, company, created_at in recent_users:
                        stats_msg += f"\n• {user_name} ({company}) - {created_at.strftime('%m-%d')}"
                
                await update.message.reply_text(stats_msg, parse_mode='Markdown')
                
        except Exception as e:
            logger.error(f"Error getting admin stats: {e}")
            await update.message.reply_text("❌ خطأ في جلب الإحصائيات")
        finally:
            conn.close()

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced help based on user type"""
    user_id = str(update.effective_user.id)
    
    if user_id == ADMIN_CHAT_ID:
        help_text = """🔧 **أوامر المشرف:**

**إدارة الملفات:**
• `/set_file [msg_id] [version] [size]` - تعيين معلومات الملف
• `/admin_stats` - إحصائيات تفصيلية

**مراقبة النظام:**
• `/status` - حالة البوت التفصيلية
• `/list_files` - عرض جميع الملفات

**أوامر المستخدمين العادية:**
• `/start` - رسالة الترحيب
• `/datrix_app` - تحميل DATRIX
• `/help` - عرض هذه المساعدة

**عملية الإعداد:**
1. رفع الملف الكبير إلى قناة التخزين
2. نسخ معرف الرسالة من الملف المرفوع
3. استخدام `/set_file [message_id] [version] [size]`
4. الملف أصبح متاحاً للتسليم الفوري!"""
    else:
        help_text = """🤖 **مساعدة DATRIX Bot**

**الأوامر المتاحة:**
• `/start` - رسالة الترحيب ومعلومات البوت
• `/register_company` - تسجيل بيانات الشركة
• `/datrix_app` - تحميل تطبيق DATRIX
• `/request_license` - طلب ترخيص جديد
• `/my_status` - عرض حالة حسابك
• `/list_files` - عرض الملفات المتاحة
• `/status` - حالة البوت
• `/help` - عرض هذه المساعدة

**خطوات البدء:**
1. استخدم `/register_company` لتسجيل شركتك
2. استخدم `/request_license` لطلب ترخيص
3. بعد الموافقة، حمل التطبيق بـ `/datrix_app`

**المميزات:**
• ⚡ تسليم فوري عبر إعادة التوجيه السحابي
• 📁 دعم الملفات الكبيرة (+100MB)
• 🌐 متاح 24/7
• 🚀 دائماً أحدث إصدار

**تحتاج مساعدة؟**
تواصل مع المشرف إذا واجهت أي مشاكل."""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')
    logger.info(f"✅ Help requested by user {update.effective_user.id}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced error handling with admin notification"""
    logger.error(f'Update {update} caused error {context.error}')
    
    try:
        if update and update.effective_chat:
            error_msg = f"""⚠️ **تقرير خطأ في البوت**

**الخطأ:** `{context.error}`
**المستخدم:** {update.effective_user.id if update.effective_user else 'غير محدد'}
**المحادثة:** {update.effective_chat.id}
**الوقت:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**الأمر:** {update.message.text if update.message else 'غير محدد'}"""

            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=error_msg,
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Could not send error notification: {e}")

def main():
    """Start the enhanced DATRIX bot"""
    try:
        # Create application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Add command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("register_company", register_company))
        application.add_handler(CommandHandler("request_license", request_license))
        application.add_handler(CommandHandler("my_status", my_status))
        application.add_handler(CommandHandler("track_activity", track_user_activity))
        application.add_handler(CommandHandler("list_files", list_files))
        application.add_handler(CommandHandler("datrix_app", get_datrix_app))
        application.add_handler(CommandHandler("status", status))
        
        # Admin commands
        application.add_handler(CommandHandler("set_file", set_file_info))
        application.add_handler(CommandHandler("admin_stats", admin_stats))
        
        # Callback query handler
        application.add_handler(CallbackQueryHandler(callback_query_handler))
        
        # Error handler
        application.add_error_handler(error_handler)
        
        print("🚀 DATRIX Enhanced Bot Starting...")
        print(f"🤖 Bot Token: {BOT_TOKEN[:10]}...")
        print(f"👤 Admin ID: {ADMIN_CHAT_ID}")
        print(f"📁 Storage Channel: {STORAGE_CHANNEL_ID}")
        print(f"🗄️ Database: {'Connected' if CONFIG['DATABASE_URL'] else 'Not configured'}")
        print("⚡ Large file support: Up to 2GB")
        print("🚀 Instant forwarding: Enabled")
        print("🔑 License management: Active")
        print("📊 User tracking: Enabled")
        print("📋 All handlers registered successfully")
        print("✅ Enhanced DATRIX Bot is ready!")
        
        # Start the bot
        application.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
        print(f"❌ Failed to start bot: {e}")

if __name__ == '__main__':
    main()
