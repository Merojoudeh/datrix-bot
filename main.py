# main.py (Telegram Bot & Web Dashboard)
# FINAL, STABLE VERSION: Corrected startup sequence to resolve event loop conflicts.

from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, constants
import logging
import json
import os
import time
import tempfile
from datetime import datetime, timedelta
import threading
import asyncio

# --- Web Server Integration ---
from flask import Flask, jsonify, render_template, request, redirect, url_for, session
from functools import wraps

# --- Local Modules ---
import database as db 

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Core Configuration ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID')
CHANNEL_ID = os.environ.get('CHANNEL_ID')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(24).hex())
PORT = int(os.environ.get('PORT', 8080))

# --- Bot Settings & File Management ---
SETTINGS_FILE = 'settings.json'
BOT_SETTINGS = { 'admin_username': 'Datrix_syr', 'bot_name': 'DATRIX File Server', 'welcome_message': 'Welcome!', 'app_version': 'v2.1.6' }
FILES = { 'datrix_app': { 'message_id': None, 'version': 'v2.1.6', 'size': 'Not set', 'description': 'DATRIX App', 'download_count': 0 } }

# --- Flask Web App Initialization ---
web_app = Flask(__name__, template_folder='templates')
web_app.secret_key = SECRET_KEY

# --- Global Telegram Application Object ---
# This will be initialized in main() and used by Flask routes
telegram_app = None

# --- Web Dashboard Security & API ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@web_app.route('/', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else: error = 'Invalid Access Code.'
    return render_template('login.html', error=error)

@web_app.route('/dashboard')
@login_required
def dashboard(): return render_template('dashboard.html')

@web_app.route('/api/users')
@login_required
def api_get_users(): return jsonify(db.get_all_app_users())

# --- Bot Control API Endpoints ---
@web_app.route('/api/set_file', methods=['POST'])
@login_required
def api_set_file():
    data = request.json
    try:
        FILES['datrix_app'].update({'message_id': int(data['message_id']), 'version': data['version'], 'size': data['size']})
        BOT_SETTINGS['app_version'] = data['version']
        save_bot_data()
        logger.info(f"Admin updated file via dashboard: Version {data['version']}")
        return jsonify({'status': 'success', 'message': 'File information updated successfully!'}), 200
    except Exception as e:
        logger.error(f"API Error in set_file: {e}")
        return jsonify({'status': 'error', 'message': 'Invalid data provided.'}), 400

@web_app.route('/api/broadcast', methods=['POST'])
@login_required
def api_broadcast():
    message = request.json.get('message')
    if not message: return jsonify({'status': 'error', 'message': 'Message cannot be empty.'}), 400
    user_ids = db.get_all_telegram_user_ids()
    if not user_ids: return jsonify({'status': 'error', 'message': 'No users to broadcast to.'}), 404
    
    if telegram_app and telegram_app.loop:
        asyncio.run_coroutine_threadsafe(broadcast_message_to_users(user_ids, message), telegram_app.loop)
        logger.info(f"Admin initiated broadcast to {len(user_ids)} users.")
        return jsonify({'status': 'success', 'message': f'Broadcast started to {len(user_ids)} users.'}), 200
    else:
        logger.error("Broadcast failed: Bot application or event loop not available.")
        return jsonify({'status': 'error', 'message': 'Bot is not ready.'}), 500

async def broadcast_message_to_users(user_ids, message):
    for user_id in user_ids:
        try:
            await telegram_app.bot.send_message(chat_id=user_id, text=message, parse_mode=constants.ParseMode.MARKDOWN)
            await asyncio.sleep(0.1)
        except Exception as e: logger.warning(f"Failed broadcast to user {user_id}: {e}")

# --- Settings Persistence & UI ---
def load_bot_data():
    if not os.path.exists(SETTINGS_FILE): return
    try:
        with open(SETTINGS_FILE, 'r') as f:
            data = json.load(f)
            BOT_SETTINGS.update(data.get('bot_settings', {}))
            FILES.update(data.get('files', {}))
    except Exception as e: logger.error(f"Error loading settings: {e}")

def save_bot_data():
    try:
        with open(SETTINGS_FILE, 'w') as f: json.dump({'bot_settings': BOT_SETTINGS, 'files': FILES}, f, indent=2)
    except Exception as e: logger.error(f"Error saving settings: {e}")

def create_main_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("📥 Download DATRIX", callback_data="download_datrix")], [InlineKeyboardButton("📋 Available Files", callback_data="list_files")], [InlineKeyboardButton("❓ Help", callback_data="help"), InlineKeyboardButton("📞 Contact Admin", callback_data="contact_admin")]])

def create_admin_keyboard():
    dashboard_url = f"https://{os.environ.get('RAILWAY_STATIC_URL')}" if 'RAILWAY_STATIC_URL' in os.environ else None
    buttons = [[InlineKeyboardButton("📥 Download DATRIX", callback_data="download_datrix")], [InlineKeyboardButton("📋 Available Files", callback_data="list_files")]]
    if dashboard_url: buttons.append([InlineKeyboardButton("🖥️ Mission Control", url=dashboard_url)])
    else: buttons.append([InlineKeyboardButton("📞 Contact Info", callback_data="contact_admin")])
    return InlineKeyboardMarkup(buttons)

# --- Core Telegram Handlers ---
async def start(update, context):
    db.add_or_update_telegram_user(update.effective_user)
    welcome_msg = f"🤖 *{BOT_SETTINGS['bot_name']}*\n\n👋 Hello {update.effective_user.first_name}!"
    keyboard = create_admin_keyboard() if str(update.effective_user.id) == ADMIN_ID else create_main_keyboard()
    await update.message.reply_text(welcome_msg, parse_mode='Markdown', reply_markup=keyboard)

async def callback_query_handler(update, context):
    query = update.callback_query
    await query.answer()
    callback_data = query.data
    db.add_or_update_telegram_user(query.from_user)
    COMMAND_MAP = {"download_datrix": handle_download, "list_files": handle_list_files, "help": handle_help, "contact_admin": handle_contact_admin, "back_to_menu": handle_back_to_menu}
    if callback_data in COMMAND_MAP: await COMMAND_MAP[callback_data](query, context)
    else: logger.warning(f"Unknown callback query data: {callback_data}")

async def handle_download(query, context):
    file_info = FILES['datrix_app']
    if not file_info.get('message_id'):
        await query.edit_message_text("❌ *File Unavailable*", parse_mode='Markdown'); return
    try:
        await context.bot.forward_message(chat_id=query.message.chat_id, from_chat_id=CHANNEL_ID, message_id=file_info['message_id'])
        file_info['download_count'] += 1; save_bot_data()
        await query.edit_message_text(f"✅ *Delivered:* {file_info['description']}", parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error delivering file: {e}")
        await query.edit_message_text("❌ *Download Error*", parse_mode='Markdown')

async def handle_list_files(query, context):
    info = FILES['datrix_app']
    status = "✅ Available" if info['message_id'] else "❌ Not available"
    text = f"📂 *Files:*\n\n📄 *{info['description']}*\n🔢 Ver: `{info['version']}`\n💾 Size: `{info['size']}`\n📊 Status: {status}"
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_help(query, context):
    help_text = f"🤖 *Help*\n\nUse the buttons to navigate. For support, contact @{BOT_SETTINGS['admin_username']}."
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]
    await query.edit_message_text(help_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_contact_admin(query, context):
    contact_msg = f"📞 *Contact Admin*\n\nClick below to message @{BOT_SETTINGS['admin_username']}."
    keyboard = [[InlineKeyboardButton(f"💬 Message Admin", url=f"https://t.me/{BOT_SETTINGS['admin_username']}")], [InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]
    await query.edit_message_text(contact_msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_back_to_menu(query, context):
    user_id = str(query.from_user.id)
    welcome_msg = f"🤖 *{BOT_SETTINGS['bot_name']}*\n\n👋 Welcome back, {query.from_user.first_name}!"
    keyboard = create_admin_keyboard() if user_id == ADMIN_ID else create_main_keyboard()
    await query.edit_message_text(welcome_msg, parse_mode='Markdown', reply_markup=keyboard)

# --- Main Application Execution ---
def run_flask_app():
    """Runs the Flask web server in a dedicated, non-blocking thread."""
    try: 
        # use_reloader=False is critical for preventing the server from starting twice in debug mode
        web_app.run(host='0.0.0.0', port=PORT, use_reloader=False)
    except Exception as e: 
        logger.error(f"Flask web server failed: {e}", exc_info=True)

def main() -> None:
    """The main entry point for the entire application."""
    if not all([BOT_TOKEN, ADMIN_ID, CHANNEL_ID, ADMIN_PASSWORD]):
        logger.critical("FATAL ERROR: Missing one or more required environment variables. Halting.")
        return

    # --- Synchronous Setup ---
    global telegram_app
    load_bot_data()
    db.initialize_database()

    # Initialize the Telegram Application object
    telegram_app = Application.builder().token(BOT_TOKEN).build()

    # Add all handlers to the application
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CallbackQueryHandler(callback_query_handler))
    # Add other handlers (e.g., for silent API, admin commands) as needed here

    # Start the Flask web server in a separate, non-blocking thread
    flask_thread = threading.Thread(target=run_flask_app, daemon=True)
    flask_thread.start()
    logger.info(f"🚀 Flask Mission Control server has been dispatched to port {PORT}.")

    # --- Handover to the Master Conductor ---
    # This call is blocking. It will run the bot until the process is stopped.
    # It manages its own asyncio event loop gracefully.
    logger.info("🚀 DATRIX Bot is engaging polling sequence...")
    telegram_app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
