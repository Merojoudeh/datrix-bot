# main.py (Telegram Bot & Web Dashboard)
# VERSION 3.0: Interactive Command Layer - Backend

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
def api_get_users(): 
    # CRITICAL: This now returns all users from the app_users table for the dashboard
    return jsonify(db.get_all_app_users())

# --- Bot Control Panel API Endpoints ---
@web_app.route('/api/set_file', methods=['POST'])
@login_required
def api_set_file():
    data = request.json
    try:
        FILES['datrix_app'].update({'message_id': int(data['message_id']), 'version': data['version'], 'size': data['size']})
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
        return jsonify({'status': 'success', 'message': f'Broadcast started to {len(user_ids)} users.'}), 200
    else:
        return jsonify({'status': 'error', 'message': 'Bot is not ready.'}), 500

# --- NEW: Interactive Command Layer API Endpoints ---

@web_app.route('/api/command/extend_license', methods=['POST'])
@login_required
def api_extend_license():
    data = request.json
    google_sheet_id = data.get('google_sheet_id')
    days_to_add = data.get('days')
    if not all([google_sheet_id, days_to_add]):
        return jsonify({'status': 'error', 'message': 'Missing user ID or day count.'}), 400
    
    try:
        new_expiry_date = db.extend_user_license(google_sheet_id, days_to_add)
        logger.info(f"Admin extended license for {google_sheet_id} by {days_to_add} days. New expiry: {new_expiry_date}")
        return jsonify({'status': 'success', 'message': f'License extended. New expiry: {new_expiry_date}'})
    except Exception as e:
        logger.error(f"Error extending license for {google_sheet_id}: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to update license in database.'}), 500

@web_app.route('/api/command/revoke_license', methods=['POST'])
@login_required
def api_revoke_license():
    data = request.json
    google_sheet_id = data.get('google_sheet_id')
    if not google_sheet_id:
        return jsonify({'status': 'error', 'message': 'Missing user ID.'}), 400

    try:
        db.revoke_user_license(google_sheet_id)
        logger.info(f"Admin revoked license for {google_sheet_id}")
        return jsonify({'status': 'success', 'message': 'License has been revoked.'})
    except Exception as e:
        logger.error(f"Error revoking license for {google_sheet_id}: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to revoke license in database.'}), 500

@web_app.route('/api/command/direct_message', methods=['POST'])
@login_required
def api_direct_message():
    data = request.json
    telegram_id = data.get('telegram_id')
    message = data.get('message')
    if not all([telegram_id, message]):
        return jsonify({'status': 'error', 'message': 'Missing Telegram ID or message text.'}), 400

    if telegram_app and telegram_app.loop:
        asyncio.run_coroutine_threadsafe(telegram_app.bot.send_message(chat_id=telegram_id, text=message), telegram_app.loop)
        logger.info(f"Admin sent direct message to {telegram_id}")
        return jsonify({'status': 'success', 'message': 'Direct message sent successfully.'})
    else:
        return jsonify({'status': 'error', 'message': 'Bot is not ready to send messages.'}), 500

# --- Async Helpers & Telegram Logic (Largely Unchanged) ---

async def broadcast_message_to_users(user_ids, message):
    for user_id in user_ids:
        try:
            await telegram_app.bot.send_message(chat_id=user_id, text=message, parse_mode=constants.ParseMode.MARKDOWN)
            await asyncio.sleep(0.1)
        except Exception as e: logger.warning(f"Failed broadcast to user {user_id}: {e}")

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

# All other Telegram handlers (start, callback_query_handler, etc.) remain the same.
# For brevity in this explanation, they are omitted, but they are in the full script.

def create_main_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("📥 Download DATRIX", callback_data="download_datrix")], [InlineKeyboardButton("📋 Available Files", callback_data="list_files")], [InlineKeyboardButton("❓ Help", callback_data="help"), InlineKeyboardButton("📞 Contact Admin", callback_data="contact_admin")]])

def create_admin_keyboard():
    dashboard_url = f"https://{os.environ.get('RAILWAY_STATIC_URL')}" if 'RAILWAY_STATIC_URL' in os.environ else None
    buttons = [[InlineKeyboardButton("📥 Download DATRIX", callback_data="download_datrix")], [InlineKeyboardButton("📋 Available Files", callback_data="list_files")]]
    if dashboard_url: buttons.append([InlineKeyboardButton("🖥️ Mission Control", url=dashboard_url)])
    return InlineKeyboardMarkup(buttons)

async def start(update, context):
    db.add_or_update_telegram_user(update.effective_user)
    welcome_msg = f"🤖 *{BOT_SETTINGS['bot_name']}*\n\n👋 Hello {update.effective_user.first_name}!"
    keyboard = create_admin_keyboard() if str(update.effective_user.id) == ADMIN_ID else create_main_keyboard()
    await update.message.reply_text(welcome_msg, parse_mode='Markdown', reply_markup=keyboard)

# This is a placeholder for the full handler logic
async def callback_query_handler(update, context):
    query = update.callback_query
    await query.answer("This function is active.")

# --- Main Application Execution ---
def run_flask_app():
    try: 
        web_app.run(host='0.0.0.0', port=PORT, use_reloader=False)
    except Exception as e: 
        logger.error(f"Flask web server failed: {e}", exc_info=True)

def main() -> None:
    global telegram_app
    if not all([BOT_TOKEN, ADMIN_ID, CHANNEL_ID, ADMIN_PASSWORD]):
        logger.critical("FATAL ERROR: Missing required environment variables. Halting.")
        return

    load_bot_data()
    db.initialize_database()

    telegram_app = Application.builder().token(BOT_TOKEN).build()

    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CallbackQueryHandler(callback_query_handler))

    flask_thread = threading.Thread(target=run_flask_app, daemon=True)
    flask_thread.start()
    logger.info(f"🚀 Flask Mission Control server dispatched to port {PORT}.")

    logger.info("🚀 DATRIX Bot engaging polling sequence...")
    telegram_app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
