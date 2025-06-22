# main.py (Telegram Bot & Web Dashboard)
# FINAL VERSION: Includes Database, Web Server, Secure Dashboard, and Live API.
# This script is the central nervous system of the DATRIX application.

from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import logging
import json
import os
import time
import tempfile
import glob
from datetime import datetime, timedelta
import threading

# --- Web Server Integration ---
from flask import Flask, jsonify, render_template, request, redirect, url_for, session
from functools import wraps

# --- Local Modules ---
import database as db 

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Core Configuration ---
# CRITICAL: These MUST be set in Railway's "Variables" tab for security and proper function.
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID')
CHANNEL_ID = os.environ.get('CHANNEL_ID')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') # The password for the web dashboard
SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(24).hex()) # For session security
PORT = int(os.environ.get('PORT', 8080)) # Provided by Railway

# --- Bot Settings & File Management ---
SETTINGS_FILE = 'settings.json'
BOT_SETTINGS = { 'admin_username': 'Datrix_syr', 'bot_name': 'DATRIX File Server', 'welcome_message': 'Welcome!', 'app_version': 'v2.1.6' }
FILES = { 'datrix_app': { 'message_id': None, 'version': 'v2.1.6', 'size': 'Not set', 'description': 'DATRIX App', 'download_count': 0 } }

# --- Flask Web App Initialization ---
web_app = Flask(__name__, template_folder='templates')
web_app.secret_key = SECRET_KEY # Required for session management

# --- Web Dashboard Security Decorator ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Web Dashboard Routes ---
@web_app.route('/', methods=['GET', 'POST'])
def login():
    """Handles the login page for the Mission Control dashboard."""
    error = None
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            error = 'Invalid Access Code. Please try again.'
    return render_template('login.html', error=error)

@web_app.route('/dashboard')
@login_required
def dashboard():
    """Serves the main dashboard page after a successful login."""
    return render_template('dashboard.html')

@web_app.route('/api/users')
@login_required
def api_get_users():
    """Secure API endpoint to provide live user data to the dashboard."""
    users = db.get_all_app_users()
    return jsonify(users)

# --- Settings and File Data Persistence ---
def load_bot_data():
    if not os.path.exists(SETTINGS_FILE): return
    try:
        with open(SETTINGS_FILE, 'r') as f:
            saved_data = json.load(f)
            BOT_SETTINGS.update(saved_data.get('bot_settings', {}))
            FILES.update(saved_data.get('files', {}))
    except Exception as e: logger.error(f"Error loading bot data: {e}")

def save_bot_data():
    try:
        with open(SETTINGS_FILE, 'w') as f: json.dump({'bot_settings': BOT_SETTINGS, 'files': FILES}, f, indent=2)
    except Exception as e: logger.error(f"Error saving bot data: {e}")

# --- UI: Telegram Keyboards ---
def create_main_keyboard():
    keyboard = [[InlineKeyboardButton("📥 Download DATRIX", callback_data="download_datrix")], [InlineKeyboardButton("📋 Available Files", callback_data="list_files")], [InlineKeyboardButton("📊 Bot Status", callback_data="bot_status"), InlineKeyboardButton("❓ Help", callback_data="help")], [InlineKeyboardButton("📞 Contact Admin", callback_data="contact_admin")]]
    return InlineKeyboardMarkup(keyboard)

def create_admin_keyboard():
    keyboard = [[InlineKeyboardButton("📥 Download DATRIX", callback_data="download_datrix")], [InlineKeyboardButton("📋 Available Files", callback_data="list_files")], [InlineKeyboardButton("📊 Bot Status", callback_data="bot_status"), InlineKeyboardButton("📈 User Stats", callback_data="admin_stats")], [InlineKeyboardButton("🖥️ App Users", callback_data="app_stats"), InlineKeyboardButton("⚙️ Admin Help", callback_data="admin_help")], [InlineKeyboardButton("📞 Contact Info", callback_data="contact_admin")]]
    return InlineKeyboardMarkup(keyboard)

# --- Core Telegram Handlers ---
async def start(update, context):
    db.add_or_update_telegram_user(update.effective_user)
    user_id = str(update.effective_user.id)
    welcome_msg = f"🤖 *{BOT_SETTINGS['bot_name']}*\n\n👋 Hello {update.effective_user.first_name}!\n\n{BOT_SETTINGS['welcome_message']}\n\n🎯 *Choose an option below:*"
    keyboard = create_admin_keyboard() if user_id == ADMIN_ID else create_main_keyboard()
    await update.message.reply_text(welcome_msg, parse_mode='Markdown', reply_markup=keyboard)

async def callback_query_handler(update, context):
    query = update.callback_query
    await query.answer("Processing...")
    callback_data = query.data
    logger.info(f"Received callback: {callback_data}")
    db.add_or_update_telegram_user(query.from_user)
    COMMAND_MAP = {"download_datrix": handle_download, "list_files": handle_list_files, "bot_status": handle_status, "help": handle_help, "admin_help": handle_admin_help, "admin_stats": handle_admin_stats, "app_stats": handle_app_stats, "contact_admin": handle_contact_admin, "back_to_menu": handle_back_to_menu}
    if callback_data.startswith('req_'): await handle_license_callback(query, context, callback_data)
    elif callback_data in COMMAND_MAP: await COMMAND_MAP[callback_data](query, context)
    else: logger.warning(f"Unknown callback query data: {callback_data}")

async def handle_license_callback(query, context, callback_data):
    try:
        await query.edit_message_text("⏳ *Processing license request...*", parse_mode='Markdown')
        parts = callback_data.split('_')
        request_id, action = f"req_{parts[1]}", parts[2]
        request_info = db.get_license_request(request_id)
        if not request_info:
            await query.edit_message_text("❌ *Error:* Request not found or already processed.", parse_mode='Markdown')
            return
        
        google_sheet_id, user_name, company = request_info['google_sheet_id'], request_info['user_name'], request_info['company_name']
        
        if action == "deny":
            db.delete_license_request(request_id)
            await query.edit_message_text(f"🔑 *License Request Denied*\n\nFor User: `{user_name}`", parse_mode='Markdown')
        elif action == "extend":
            days = {"30": 31, "90": 92, "365": 365}.get(parts[3], 31)
            expiry_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
            license_key = f"ADMIN_APPROVED_{request_id}"
            db.activate_app_user_license(google_sheet_id, expiry_date, days, license_key)
            
            license_data = {"googleSheetId": google_sheet_id, "license_expires": expiry_date, "license_key": license_key, "is_active": True, "days_granted": days, "admin_approved_days": days, "user": user_name, "company": company}
            license_file_path = os.path.join(tempfile.gettempdir(), f"datrix_license_activation_{google_sheet_id}.json")
            with open(license_file_path, 'w') as f: json.dump(license_data, f, indent=2)
            
            await query.edit_message_text(f"✅ *License Approved for {days} Days*\n\nUser: `{user_name}`\nExpires: `{expiry_date}`", parse_mode='Markdown')
            db.delete_license_request(request_id)
    except Exception as e:
        logger.error(f"❌ Error in license callback: {e}", exc_info=True)
        await query.edit_message_text(f"❌ *Error processing request:* {str(e)}", parse_mode='Markdown')

async def handle_download(query, context):
    file_info = FILES['datrix_app']
    if not file_info.get('message_id'):
        await query.edit_message_text("❌ *File Currently Unavailable*", parse_mode='Markdown')
        return
    try:
        await context.bot.forward_message(chat_id=query.message.chat_id, from_chat_id=CHANNEL_ID, message_id=file_info['message_id'])
        file_info['download_count'] += 1
        save_bot_data()
        await query.edit_message_text(f"✅ *Delivered:* {file_info['description']}", parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error delivering file: {e}")
        await query.edit_message_text("❌ *Download Error*", parse_mode='Markdown')

async def handle_list_files(query, context):
    info = FILES['datrix_app']
    status = "✅ Available" if info['message_id'] else "❌ Not available"
    text = f"📂 *Available Files:*\n\n📄 *{info['description']}*\n🔢 Version: `{info['version']}`\n💾 Size: `{info['size']}`\n📊 Status: {status}"
    keyboard = [[InlineKeyboardButton("📥 Download DATRIX", callback_data="download_datrix")], [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_status(query, context):
    file_info = FILES['datrix_app']
    file_status = "✅ Available" if file_info['message_id'] else "❌ Not configured"
    status_msg = f"🟢 *System Status*\n\n✅ *Status:* Online\n⏰ *Time:* `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n📁 *DATRIX App:* {file_status}"
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
    await query.edit_message_text(status_msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_help(query, context):
    help_text = f"🤖 *Help*\n\nUse the buttons to navigate. For support, contact @{BOT_SETTINGS['admin_username']}."
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
    await query.edit_message_text(help_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_admin_help(query, context):
    if str(query.from_user.id) != ADMIN_ID: return
    help_text = "🔧 *Admin Commands:*\n\n`/set_file [id] [ver] [size]`\n`/broadcast [msg]`"
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
    await query.edit_message_text(help_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_admin_stats(query, context):
    if str(query.from_user.id) != ADMIN_ID: return
    await query.edit_message_text("📊 *Admin Stats*\n\nThis feature has been upgraded. Please use the web dashboard for live analytics.", parse_mode='Markdown')

async def handle_app_stats(query, context):
    if str(query.from_user.id) != ADMIN_ID: return
    await query.edit_message_text("🖥️ *App User Stats*\n\nThis feature has been upgraded. Please use the web dashboard for a complete user table.", parse_mode='Markdown')

async def handle_contact_admin(query, context):
    contact_msg = f"📞 *Contact Administrator*\n\nClick below to message @{BOT_SETTINGS['admin_username']}."
    keyboard = [[InlineKeyboardButton(f"💬 Message @{BOT_SETTINGS['admin_username']}", url=f"https://t.me/{BOT_SETTINGS['admin_username']}")], [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
    await query.edit_message_text(contact_msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_back_to_menu(query, context):
    user_id = str(query.from_user.id)
    welcome_msg = f"🤖 *{BOT_SETTINGS['bot_name']}*\n\n👋 Welcome back, {query.from_user.first_name}!"
    keyboard = create_admin_keyboard() if user_id == ADMIN_ID else create_main_keyboard()
    await query.edit_message_text(welcome_msg, parse_mode='Markdown', reply_markup=keyboard)

# --- Silent API Handlers ---
async def silent_api_handler(update, context):
    try:
        command = update.message.text.split()[0].lower()
        API_COMMAND_MAP = {"/request_license": handle_request_license_silent, "/get_license_data": handle_get_license_data_silent}
        if command in API_COMMAND_MAP: await API_COMMAND_MAP[command](update, context)
        await update.message.delete()
    except Exception as e: logger.error(f"Error in silent_api_handler: {e}", exc_info=True)

async def handle_request_license_silent(update, context):
    try:
        args = update.message.text.split()[1:]
        if len(args) < 3: return
        user_name, company, sheet_id = args[0].replace('_', ' '), args[1].replace('_', ' '), args[2]
        request_id = f"req_{int(time.time())}"
        if db.add_license_request(request_id, user_name, company, sheet_id):
            request_message = f"🔑 *DATRIX LICENSE REQUEST*\n\n👤 User: `{user_name}`\n🏢 Company: `{company}`\n📊 Sheet ID: `{sheet_id}`\n\n🎯 *Select duration:*"
            keyboard = [[InlineKeyboardButton("✅ 31 Days", callback_data=f"{request_id}_extend_30"), InlineKeyboardButton("✅ 92 Days", callback_data=f"{request_id}_extend_90")], [InlineKeyboardButton("✅ 365 Days", callback_data=f"{request_id}_extend_365"), InlineKeyboardButton("❌ Deny", callback_data=f"{request_id}_deny")]]
            await context.bot.send_message(chat_id=ADMIN_ID, text=request_message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e: logger.error(f"Error in handle_request_license_silent: {e}", exc_info=True)

async def handle_get_license_data_silent(update, context):
    try:
        sheet_id = update.message.text.split()[1]
        license_file_path = os.path.join(tempfile.gettempdir(), f"datrix_license_activation_{sheet_id}.json")
        if os.path.exists(license_file_path):
            with open(license_file_path, 'r') as f: license_data = json.load(f)
            os.remove(license_file_path)
            response = {"status": "success", "license_data": license_data, "stop_polling": True}
        else:
            response = {"status": "not_found", "continue_polling": True}
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"LICENSE_API_RESPONSE: {json.dumps(response)}")
    except Exception as e: logger.error(f"Error in handle_get_license_data_silent: {e}", exc_info=True)

# --- Admin Text Commands ---
async def set_file(update, context):
    if str(update.effective_user.id) != ADMIN_ID: return
    try:
        _, message_id, version, size = context.args
        FILES['datrix_app'].update({'message_id': int(message_id), 'version': version, 'size': size})
        BOT_SETTINGS['app_version'] = version
        save_bot_data()
        await update.message.reply_text(f"✅ *File Configured*", parse_mode='Markdown')
    except (ValueError, IndexError):
        await update.message.reply_text("Usage: /set_file [id] [ver] [size]")

# --- Function to run the Flask web server ---
def run_flask_app():
    """Runs the Flask web server in a dedicated thread."""
    try:
        web_app.run(host='0.0.0.0', port=PORT)
    except Exception as e:
        logger.error(f"❌ Flask web server failed to start: {e}", exc_info=True)

# --- Main Application Execution ---
def main():
    """Initializes and runs both the Telegram bot and the Flask web server."""
    if not all([BOT_TOKEN, ADMIN_ID, CHANNEL_ID, ADMIN_PASSWORD]):
        logger.critical("FATAL ERROR: Missing required environment variables. Please set BOT_TOKEN, ADMIN_ID, CHANNEL_ID, and ADMIN_PASSWORD in Railway.")
        return

    load_bot_data()
    db.initialize_database()

    flask_thread = threading.Thread(target=run_flask_app, daemon=True)
    flask_thread.start()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add All Telegram Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_query_handler))
    api_commands = ["request_license", "get_license_data"]
    app.add_handler(CommandHandler(api_commands, silent_api_handler))
    app.add_handler(CommandHandler("set_file", set_file))
    
    logger.info("🚀 DATRIX Bot and Mission Control are starting...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
