# main.py
# Enhanced DATRIX Bot + Web Dashboard

import os
import logging
import asyncio
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
        users = db.get_all_telegram_users()
        for user in users:
            if user['last_seen']:
                user['last_seen_formatted'] = user['last_seen'].strftime('%Y-%m-%d %H:%M')
            else:
                user['last_seen_formatted'] = 'Never'
                
            if user['license_expires']:
                days_remaining = (user['license_expires'] - datetime.now().date()).days
                user['days_remaining'] = max(0, days_remaining)
                user['license_expires_formatted'] = user['license_expires'].strftime('%Y-%m-%d')
            else:
                user['days_remaining'] = 0
                user['license_expires_formatted'] = 'Not set'
        
        return jsonify(users)
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return jsonify({'error': str(e)}), 500

@web_app.route('/api/extend_license', methods=['POST'])
@login_required
def api_extend_license():
    try:
        data = request.json
        user_id = data.get('user_id')
        days = data.get('days', 30)
        
        if not user_id:
            return jsonify({'error': 'User ID required'}), 400
            
        new_expiry = db.update_user_license(user_id, days, 0)
        
        if new_expiry:
            return jsonify({
                'success': True, 
                'new_expiry': new_expiry.strftime('%Y-%m-%d'),
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
    try:
        file_info = db.get_file_info('datrix_app')
        if file_info:
            return jsonify(dict(file_info))
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        logger.error(f"Error getting file info: {e}")
        return jsonify({'error': str(e)}), 500

@web_app.route('/api/update_file', methods=['POST'])
@login_required  
def api_update_file():
    try:
        data = request.json
        message_id = data.get('message_id')
        version = data.get('version')
        file_size = data.get('file_size')
        
        if not message_id:
            return jsonify({'error': 'Message ID required'}), 400
            
        success = db.update_file_info('datrix_app', message_id, version, file_size)
        
        if success:
            return jsonify({'success': True, 'message': 'File info updated'})
        else:
            return jsonify({'error': 'Failed to update file info'}), 500
    except Exception as e:
        logger.error(f"Error updating file info: {e}")
        return jsonify({'error': str(e)}), 500

@web_app.route('/api/broadcast', methods=['POST'])
@login_required
def api_broadcast():
    data = request.json
    message, target = data.get('message'), data.get('target', 'approved')
    
    if not message:
        return jsonify({'status': 'error', 'message': 'Empty message.'}), 400
    
    try:
        db.queue_broadcast(target, message)
        return jsonify({'status': 'success', 'message': f'Broadcast queued for {target} users'})
    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        return jsonify({'status': 'error', 'message': f'Error: {str(e)}'}), 500

# Compatibility routes
@web_app.route('/api/bot_users')
@login_required
def api_bot_users(): 
    return api_datrix_users()

# =================== TELEGRAM BOT ===================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Register user
    db.add_datrix_user(user.id, user.username or user.first_name)
    
    welcome_message = """🤖 **مرحباً بك في DATRIX Bot**

📋 **الأوامر المتاحة:**
• `/datrix_app` - تحميل تطبيق DATRIX
• `/register_company` - تسجيل شركتك
• `/request_license` - طلب ترخيص جديد
• `/my_status` - حالة حسابك
• `/help` - المساعدة

🌐 **يعمل 24/7 على الخادم السحابي**
⚡ **تحميل فوري عبر قناة التخزين**"""
    
    await update.message.reply_text(welcome_message, parse_mode='Markdown')

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
    db.add_datrix_user(user.id, user.username or user.first_name, company_name, sheet_id)
    
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
🏢 {company_name}
📊 `{sheet_id}`"""
    
    await context.bot.send_message(ADMIN_CHAT_ID, admin_msg, parse_mode='Markdown')

async def request_license(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_info = db.get_datrix_user(user.id)
    
    if not user_info or not user_info['company_name']:
        await update.message.reply_text(
            "❌ **يجب تسجيل بيانات الشركة أولاً**\n\n"
            "استخدم: `/register_company [اسم الشركة] [Sheet ID]`",
            parse_mode='Markdown'
        )
        return
    
    # Add license request
    db.add_license_request(user.id, user_info['company_name'], user_info['google_sheet_id'])
    
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
🏢 {user_info['company_name']}
📊 `{user_info['google_sheet_id']}`"""
    
    await context.bot.send_message(ADMIN_CHAT_ID, admin_msg, reply_markup=markup, parse_mode='Markdown')
    await update.message.reply_text("✅ **تم إرسال طلب التمديد للمراجعة**", parse_mode='Markdown')

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
            await context.bot.send_message(user_id, "❌ **تم رفض طلب تمديد الترخيص**")
        else:
            days_map = {"extend_30": 30, "extend_90": 90, "extend_365": 365}
            days = days_map.get(action, 30)
            
            new_expiry = db.update_user_license(user_id, days, query.from_user.id)
            
            await query.edit_message_text(f"✅ **تم منح ترخيص {days} يوم**\n📅 **ينتهي:** {new_expiry.strftime('%Y-%m-%d')}")
            await context.bot.send_message(
                user_id,
                f"🎉 **تم قبول طلب الترخيص!**\n⏰ **المدة:** {days} يوم\n📅 **ينتهي:** {new_expiry.strftime('%Y-%m-%d')}",
                parse_mode='Markdown'
            )

async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_info = db.get_datrix_user(user.id)
    
    if not user_info:
        await update.message.reply_text("❌ **لم يتم العثور على بياناتك**", parse_mode='Markdown')
        return
    
    # Calculate license status
    if user_info['license_expires']:
        days_remaining = (user_info['license_expires'] - datetime.now().date()).days
        if days_remaining > 0:
            license_text = f"✅ نشط ({days_remaining} يوم متبقي)"
        else:
            license_text = f"❌ منتهي الصلاحية"
    else:
        license_text = "⚠️ غير محدد"
    
    status_msg = f"""📊 **حالة حسابك**
👤 {user.first_name}
🏢 {user_info['company_name'] or 'غير مسجل'}
📊 `{user_info['google_sheet_id'] or 'غير محدد'}`
🔑 **الترخيص:** {license_text}"""
    
    await update.message.reply_text(status_msg, parse_mode='Markdown')

async def get_datrix_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Check license
    is_valid, message = db.check_user_license(user.id)
    if not is_valid:
        await update.message.reply_text(
            f"🔒 **الترخيص غير صالح**\n\n{message}\n\nاستخدم `/request_license` لطلب ترخيص",
            parse_mode='Markdown'
        )
        return
    
    # Get file info
    file_info = db.get_file_info('datrix_app')
    if not file_info or not file_info['message_id']:
        await update.message.reply_text("❌ **الملف غير متاح حالياً**", parse_mode='Markdown')
        return
    
    try:
        # Forward file
        await context.bot.forward_message(
            chat_id=update.effective_chat.id,
            from_chat_id=STORAGE_CHANNEL_ID,
            message_id=file_info['message_id']
        )
        
        # Increment download count and track activity
        db.increment_download_count('datrix_app')
        db.track_user_activity(user.id, 'app_download', {'version': file_info['version']})
        
        await update.message.reply_text(
            f"✅ **تم إرسال DATRIX!**\n🔢 **الإصدار:** {file_info['version']}\n💾 **الحجم:** {file_info['file_size']}",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error delivering file: {e}")
        await update.message.reply_text("❌ **خطأ في التحميل**", parse_mode='Markdown')

async def set_file_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        return
    
    if len(context.args) < 1:
        await update.message.reply_text("📝 **الاستخدام:** `/set_file [message_id] [version] [size]`", parse_mode='Markdown')
        return
    
    try:
        message_id = int(context.args[0])
        version = context.args[1] if len(context.args) > 1 else "v2.1.6"
        size = context.args[2] if len(context.args) > 2 else "Unknown"
        
        success = db.update_file_info('datrix_app', message_id, version, size)
        
        if success:
            await update.message.reply_text(
                f"✅ **تم تحديث الملف!**\n🆔 **Message ID:** `{message_id}`\n🔢 **الإصدار:** `{version}`\n💾 **الحجم:** `{size}`",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ **فشل التحديث**", parse_mode='Markdown')
            
    except ValueError:
        await update.message.reply_text("❌ **Message ID يجب أن يكون رقماً**", parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) == ADMIN_CHAT_ID:
        help_text = """🔧 **أوامر المشرف:**
• `/set_file [msg_id] [version] [size]` - تحديث الملف
• `/status` - حالة البوت

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

# =================== BACKGROUND TASKS ===================

async def check_broadcast_queue(app: Application):
    """Check for pending broadcasts"""
    while True:
        try:
            jobs = db.get_pending_broadcasts()
            for job_id, target, message in jobs:
                user_ids = db.get_user_ids_for_broadcast(target)
                
                for user_id in user_ids:
                    try:
                        await app.bot.send_message(chat_id=user_id, text=message)
                        await asyncio.sleep(0.05)
                    except Exception as e:
                        logger.warning(f"Broadcast to {user_id} failed: {e}")
                
                db.mark_broadcast_as_sent(job_id)
                
        except Exception as e:
            logger.error(f"Broadcast monitor error: {e}")
        
        await asyncio.sleep(10)

# =================== MAIN FUNCTION ===================

def main():
    try:
        # Initialize database
        db.initialize_database()
        
        # Create Telegram application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("register_company", register_company))
        application.add_handler(CommandHandler("request_license", request_license))
        application.add_handler(CommandHandler("my_status", my_status))
        application.add_handler(CommandHandler("datrix_app", get_datrix_app))
        application.add_handler(CommandHandler("set_file", set_file_info))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CallbackQueryHandler(callback_query_handler))
        
        # Setup broadcast monitoring
        application.post_init = check_broadcast_queue
        
        print("🚀 DATRIX Bot + Web Dashboard Starting...")
        print(f"🤖 Bot Token: {BOT_TOKEN[:10]}...")
        print(f"👤 Admin ID: {ADMIN_CHAT_ID}")
        print(f"📁 Storage Channel: {STORAGE_CHANNEL_ID}")
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
