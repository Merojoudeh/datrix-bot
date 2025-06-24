# main.py
# DATRIX Bot + Web Dashboard (مع تعطيل البرودكاست مؤقتاً)

import os
import logging
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from functools import wraps
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
import database as db

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO,
    handlers=[
        logging.FileHandler('datrix.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '7803291138:AAExEBQq9uZhq6X_ncI_c8E2J80-tpZtq8E')
ADMIN_CHAT_ID = os.environ.get('ADMIN_TELEGRAM_ID', '811896458')
STORAGE_CHANNEL_ID = os.environ.get('STORAGE_CHANNEL_ID', '-1002807912676')
WEB_USER = os.environ.get('WEB_USER', 'admin')
WEB_PASS = os.environ.get('WEB_PASS', 'datrix2024')

# Global variable to store current file info
CURRENT_FILE = {
    'file_id': None,
    'version': 'v2.1.6',
    'size': 'Unknown',
    'filename': 'DATRIX_Setup.exe',
    'upload_date': None
}

# =================== FLASK WEB APP ===================
web_app = Flask(__name__)

def check_auth(username, password): 
    return username == WEB_USER and password == WEB_PASS

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return ('Unauthorized', 401, {'WWW-Authenticate': 'Basic realm="DATRIX Control Panel"'})
        return f(*args, **kwargs)
    return decorated_function

@web_app.route('/')
@login_required
def dashboard(): 
    return render_template('dashboard.html')

@web_app.route('/api/datrix_users')
@login_required
def api_datrix_users():
    try:
        users = db.get_all_datrix_users()  # Function نحتاج نعملها
        
        for user in users:
            if user.get('last_seen'):
                user['last_seen_formatted'] = user['last_seen'].strftime('%Y-%m-%d %H:%M')
            else:
                user['last_seen_formatted'] = 'Never'
                
            if user.get('license_expires'):
                days_remaining = (user['license_expires'] - datetime.now().date()).days
                user['days_remaining'] = max(0, days_remaining)
                user['license_expires_formatted'] = user['license_expires'].strftime('%Y-%m-%d')
            else:
                user['days_remaining'] = 0
                user['license_expires_formatted'] = 'Not set'
        
        return jsonify(users)
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return jsonify([])  # Return empty list instead of error

@web_app.route('/api/extend_license', methods=['POST'])
@login_required
def api_extend_license():
    try:
        data = request.json
        user_id = data.get('user_id')
        days = data.get('days', 30)
        
        if not user_id:
            return jsonify({'error': 'User ID required'}), 400
            
        success = db.extend_user_license(user_id, days)  # Function بسيطة
        
        if success:
            return jsonify({
                'success': True, 
                'message': f'License extended by {days} days'
            })
        else:
            return jsonify({'error': 'Failed to extend license'}), 500
    except Exception as e:
        logger.error(f"Error extending license: {e}")
        return jsonify({'error': str(e)}), 500

@web_app.route('/api/file_info')
@login_required
def api_file_info():
    """Get current file info"""
    return jsonify(CURRENT_FILE)

@web_app.route('/api/bot_stats')
@login_required
def api_bot_stats():
    """Get basic bot statistics"""
    try:
        stats = db.get_basic_stats()  # Function بسيطة
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({
            'total_users': 0,
            'active_users': 0,
            'downloads_today': 0
        })

# =================== TELEGRAM BOT ===================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Register user
    db.add_or_update_user(user.id, user.username or user.first_name)
    
    welcome_message = """🤖 **مرحباً بك في DATRIX Bot**

📋 **الأوامر المتاحة:**
• `/datrix_app` - تحميل تطبيق DATRIX
• `/register_company` - تسجيل شركتك
• `/request_license` - طلب ترخيص جديد
• `/my_status` - حالة حسابك
• `/help` - المساعدة

🌐 **يعمل 24/7 على الخادم السحابي**
⚡ **تحميل فوري مباشرة من البوت**"""
    
    await update.message.reply_text(welcome_message, parse_mode='Markdown')
    logger.info(f"✅ User {user.id} started the bot")

async def register_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    
    # Update user info
    success = db.update_user_company(user.id, company_name, sheet_id)
    
    if success:
        await update.message.reply_text(
            f"✅ **تم تسجيل بيانات الشركة!**\n\n"
            f"🏢 **الشركة:** {company_name}\n"
            f"📊 **Sheet ID:** `{sheet_id}`\n\n"
            f"💡 يمكنك الآن طلب ترخيص باستخدام `/request_license`",
            parse_mode='Markdown'
        )
        
        # Notify admin
        admin_msg = f"""🆕 **تسجيل شركة جديدة**
👤 {user.first_name} (@{user.username})
🆔 `{user.id}`
🏢 {company_name}
📊 `{sheet_id}`"""
        
        try:
            await context.bot.send_message(ADMIN_CHAT_ID, admin_msg, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")
    else:
        await update.message.reply_text("❌ حدث خطأ في التسجيل. يرجى المحاولة مرة أخرى.")

async def request_license(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_info = db.get_user_info(user.id)
    
    if not user_info or not user_info.get('company_name'):
        await update.message.reply_text(
            "❌ **يجب تسجيل بيانات الشركة أولاً**\n\n"
            "استخدم: `/register_company [اسم الشركة] [Sheet ID]`",
            parse_mode='Markdown'
        )
        return
    
    # Create admin keyboard
    keyboard = [
        [
            InlineKeyboardButton("منح 30 يوم", callback_data=f"extend_30:{user.id}"),
            InlineKeyboardButton("منح 90 يوم", callback_data=f"extend_90:{user.id}"),
        ],
        [
            InlineKeyboardButton("منح سنة", callback_data=f"extend_365:{user.id}"),
            InlineKeyboardButton("رفض", callback_data=f"extend_deny:{user.id}"),
        ]
    ]
    markup = InlineKeyboardMarkup(keyboard)
    
    admin_msg = f"""🔑 **طلب تمديد ترخيص**
👤 {user.first_name} (@{user.username})
🆔 `{user.id}`
🏢 {user_info['company_name']}
📊 `{user_info.get('google_sheet_id', 'غير محدد')}`
📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}"""
    
    try:
        await context.bot.send_message(ADMIN_CHAT_ID, admin_msg, reply_markup=markup, parse_mode='Markdown')
        await update.message.reply_text("✅ **تم إرسال طلب التمديد للمراجعة**", parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Failed to send license request: {e}")
        await update.message.reply_text("❌ حدث خطأ في إرسال الطلب")

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if str(query.from_user.id) != ADMIN_CHAT_ID:
        return
    
    data = query.data
    if data.startswith("extend_"):
        action, user_id_str = data.split(":", 1)
        user_id = int(user_id_str)
        
        if action == "extend_deny":
            await query.edit_message_text(f"❌ **تم رفض طلب الترخيص للمستخدم {user_id}**")
            try:
                await context.bot.send_message(user_id, "❌ **تم رفض طلب تمديد الترخيص**")
            except:
                pass
        else:
            days_map = {"extend_30": 30, "extend_90": 90, "extend_365": 365}
            days = days_map.get(action, 30)
            
            success = db.extend_user_license(user_id, days)
            
            if success:
                await query.edit_message_text(f"✅ **تم منح ترخيص {days} يوم للمستخدم {user_id}**")
                try:
                    await context.bot.send_message(
                        user_id,
                        f"🎉 **تم قبول طلب الترخيص!**\n⏰ **المدة:** {days} يوم\n\n✅ يمكنك الآن تحميل DATRIX!",
                        parse_mode='Markdown'
                    )
                except:
                    pass
            else:
                await query.edit_message_text(f"❌ **فشل في منح الترخيص للمستخدم {user_id}**")

async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_info = db.get_user_info(user.id)
    
    if not user_info:
        await update.message.reply_text("❌ **لم يتم العثور على بياناتك**\n\nاستخدم `/start` للتسجيل", parse_mode='Markdown')
        return
    
    # Calculate license status
    license_text = "⚠️ غير محدد"
    if user_info.get('license_expires'):
        days_remaining = (user_info['license_expires'] - datetime.now().date()).days
        if days_remaining > 0:
            license_text = f"✅ نشط ({days_remaining} يوم متبقي)"
        else:
            license_text = f"❌ منتهي الصلاحية"
    
    status_msg = f"""📊 **حالة حسابك**
👤 {user.first_name}
🆔 `{user.id}`
🏢 {user_info.get('company_name') or 'غير مسجل'}
📊 `{user_info.get('google_sheet_id') or 'غير محدد'}`
🔑 **الترخيص:** {license_text}
📅 **التسجيل:** {user_info.get('created_at', 'غير محدد')}"""
    
    await update.message.reply_text(status_msg, parse_mode='Markdown')

async def get_datrix_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Check if user has valid license
    user_info = db.get_user_info(user.id)
    if not user_info:
        await update.message.reply_text("❌ **يجب التسجيل أولاً**\nاستخدم `/start`", parse_mode='Markdown')
        return
    
    # Check license
    if user_info.get('license_expires'):
        if user_info['license_expires'] <= datetime.now().date():
            await update.message.reply_text(
                "🔒 **الترخيص منتهي الصلاحية**\n\nاستخدم `/request_license` لطلب تمديد",
                parse_mode='Markdown'
            )
            return
    else:
        await update.message.reply_text(
            "🔒 **لا يوجد ترخيص**\n\nاستخدم `/request_license` لطلب ترخيص",
            parse_mode='Markdown'
        )
        return
    
    # Check if file is available
    if not CURRENT_FILE.get('file_id'):
        await update.message.reply_text("❌ **التطبيق غير متاح حالياً**\nيرجى المحاولة لاحقاً", parse_mode='Markdown')
        return
    
    try:
        # Send the file directly
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=CURRENT_FILE['file_id'],
            caption=f"✅ **{CURRENT_FILE['filename']}**\n🔢 **الإصدار:** {CURRENT_FILE['version']}\n💾 **الحجم:** {CURRENT_FILE['size']}"
        )
        
        # Track download
        db.track_download(user.id)
        
        logger.info(f"✅ DATRIX delivered to user {user.id}")
        
    except Exception as e:
        logger.error(f"Error delivering file: {e}")
        await update.message.reply_text("❌ **خطأ في التحميل**\nيرجى المحاولة مرة أخرى", parse_mode='Markdown')

# Admin commands
async def set_file_waiting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to prepare for file upload"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        return
    
    version = context.args[0] if context.args else "v2.1.6"
    
    # Set waiting state
    context.user_data['waiting_for_file'] = True
    context.user_data['file_version'] = version
    
    await update.message.reply_text(
        f"✅ **جاهز لاستقبال ملف DATRIX {version}**\n\n"
        f"📤 ارسل الملف الآن وسيتم حفظه تلقائياً",
        parse_mode='Markdown'
    )

async def handle_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle file uploads from admin"""
    user_id = str(update.effective_user.id)
    
    # Only admin can upload files
    if user_id != ADMIN_CHAT_ID:
        return
    
    # Check if admin is waiting to upload a file
    if not context.user_data.get('waiting_for_file'):
        return
    
    document = update.message.document
    if not document:
        return
    
    try:
        # Save file info globally
        CURRENT_FILE.update({
            'file_id': document.file_id,
            'version': context.user_data.get('file_version', 'v2.1.6'),
            'size': f"{document.file_size // (1024*1024)}MB" if document.file_size else "Unknown",
            'filename': document.file_name or 'DATRIX_Setup.exe',
            'upload_date': datetime.now().strftime('%Y-%m-%d %H:%M')
        })
        
        # Clear waiting state
        context.user_data['waiting_for_file'] = False
        
        await update.message.reply_text(
            f"✅ **تم حفظ الملف بنجاح!**\n\n"
            f"📄 **الملف:** {CURRENT_FILE['filename']}\n"
            f"🔢 **الإصدار:** {CURRENT_FILE['version']}\n"
            f"💾 **الحجم:** {CURRENT_FILE['size']}\n"
            f"📅 **التاريخ:** {CURRENT_FILE['upload_date']}\n\n"
            f"🚀 **الملف متاح الآن للمستخدمين!**",
            parse_mode='Markdown'
        )
        
        logger.info(f"✅ Admin uploaded new file: {CURRENT_FILE['filename']}")
        
    except Exception as e:
        logger.error(f"Error handling file upload: {e}")
        await update.message.reply_text("❌ **خطأ في حفظ الملف**", parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) == ADMIN_CHAT_ID:
        help_text = """🔧 **أوامر المشرف:**
• `/set_file [version]` - تحضير لرفع ملف جديد
• `/current_file` - معلومات الملف الحالي
• `/stats` - إحصائيات سريعة

**أوامر المستخدمين:**
• `/start` - البداية
• `/register_company` - تسجيل الشركة  
• `/request_license` - طلب ترخيص
• `/my_status` - حالة الحساب
• `/datrix_app` - تحميل التطبيق"""
    else:
        help_text = """🤖 **مساعدة DATRIX Bot**
• `/start` - رسالة الترحيب
• `/register_company` - تسجيل الشركة
• `/request_license` - طلب ترخيص
• `/my_status` - حالة حسابك
• `/datrix_app` - تحميل التطبيق
• `/help` - هذه المساعدة"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def current_file_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current file info (admin only)"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        return
    
    if CURRENT_FILE.get('file_id'):
        info = f"""📁 **معلومات الملف الحالي:**
📄 **الملف:** {CURRENT_FILE['filename']}
🔢 **الإصدار:** {CURRENT_FILE['version']}
💾 **الحجم:** {CURRENT_FILE['size']}
📅 **التاريخ:** {CURRENT_FILE['upload_date']}
✅ **الحالة:** متاح للتحميل"""
    else:
        info = "❌ **لا يوجد ملف محفوظ حالياً**\n\nاستخدم `/set_file` لرفع ملف جديد"
    
    await update.message.reply_text(info, parse_mode='Markdown')

# =================== MAIN FUNCTION ===================

def main():
    try:
        # Initialize database
        db.initialize_simple_database()
        
        # Create Telegram application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("register_company", register_company))
        application.add_handler(CommandHandler("request_license", request_license))
        application.add_handler(CommandHandler("my_status", my_status))
        application.add_handler(CommandHandler("datrix_app", get_datrix_app))
        application.add_handler(CommandHandler("help", help_command))
        
        # Admin commands
        application.add_handler(CommandHandler("set_file", set_file_waiting))
        application.add_handler(CommandHandler("current_file", current_file_info))
        
        # File upload handler
        application.add_handler(MessageHandler(filters.Document.ALL, handle_file_upload))
        
        # Callback handler
        application.add_handler(CallbackQueryHandler(callback_query_handler))
        
        print("🚀 DATRIX Bot + Web Dashboard Starting...")
        print(f"🤖 Bot Token: {BOT_TOKEN[:10]}...")
        print(f"👤 Admin ID: {ADMIN_CHAT_ID}")
        print(f"🌐 Web User: {WEB_USER}")
        print("✅ System ready!")
        
        # Start bot in a thread
        def run_bot():
            application.run_polling(drop_pending_updates=True)
        
        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()
        
        # Start web app
        web_app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
        
    except Exception as e:
        logger.error(f"Failed to start: {e}")

if __name__ == '__main__':
    main()
