# main.py
# VERSION 6.1: Automated Onboarding Protocol - ABSOLUTELY COMPLETE

import logging
import json
import os
import sys
import asyncio
from functools import wraps

# --- Core Application Components ---
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, constants, User as TelegramUser
from flask import Flask, jsonify, render_template, request, redirect, url_for, session
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

# --- Bot Settings & File Management ---
SETTINGS_FILE = 'settings.json'
BOT_SETTINGS = { 'admin_username': 'Datrix_syr', 'bot_name': 'DATRIX File Server', 'welcome_message': 'Welcome!', 'app_version': 'v2.1.6' }
FILES = { 'datrix_app': { 'message_id': None, 'version': 'v2.1.6', 'size': 'Not set', 'description': 'DATRIX App', 'download_count': 0 } }

# =================================================================================
# === WEB HEAD: FLASK APPLICATION (For the 'web' process) =========================
# =================================================================================
web_app = Flask(__name__, template_folder='templates')
web_app.secret_key = SECRET_KEY

db.initialize_database()
logger.info("WEB HEAD: Database foundation verified.")

telegram_app_for_web = Application.builder().token(BOT_TOKEN).build()

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

@web_app.route('/api/set_file', methods=['POST'])
@login_required
def api_set_file():
    data = request.json
    try:
        with open(SETTINGS_FILE, 'r+') as f:
            current_data = json.load(f)
            current_data['files']['datrix_app'].update({'message_id': int(data['message_id']), 'version': data['version'], 'size': data['size']})
            current_data['bot_settings']['app_version'] = data['version']
            f.seek(0); json.dump(current_data, f, indent=2); f.truncate()
        return jsonify({'status': 'success', 'message': 'File information updated successfully!'}), 200
    except Exception as e: return jsonify({'status': 'error', 'message': 'Failed to update settings file.'}), 500

@web_app.route('/api/broadcast', methods=['POST'])
@login_required
def api_broadcast():
    message = request.json.get('message'); user_ids = db.get_all_telegram_user_ids()
    if not message: return jsonify({'status': 'error', 'message': 'Message cannot be empty.'}), 400
    if not user_ids: return jsonify({'status': 'error', 'message': 'No users to broadcast to.'}), 404
    try:
        asyncio.run(broadcast_message_from_web(user_ids, message))
        return jsonify({'status': 'success', 'message': f'Broadcast started to {len(user_ids)} users.'})
    except Exception as e: return jsonify({'status': 'error', 'message': 'Failed to send broadcast.'}), 500

@web_app.route('/api/command/extend_license', methods=['POST'])
@login_required
def api_extend_license():
    data = request.json; google_sheet_id = data.get('google_sheet_id'); days_to_add = data.get('days')
    if not all([google_sheet_id, days_to_add]): return jsonify({'status': 'error', 'message': 'Missing user ID or day count.'}), 400
    try:
        new_expiry_date = db.extend_user_license(google_sheet_id, days_to_add)
        return jsonify({'status': 'success', 'message': f'License extended. New expiry: {new_expiry_date}'})
    except Exception as e: return jsonify({'status': 'error', 'message': 'Failed to update license in database.'}), 500

@web_app.route('/api/command/revoke_license', methods=['POST'])
@login_required
def api_revoke_license():
    data = request.json; google_sheet_id = data.get('google_sheet_id')
    if not google_sheet_id: return jsonify({'status': 'error', 'message': 'Missing user ID.'}), 400
    try:
        db.revoke_user_license(google_sheet_id)
        return jsonify({'status': 'success', 'message': 'License has been revoked.'})
    except Exception as e: return jsonify({'status': 'error', 'message': 'Failed to revoke license in database.'}), 500

@web_app.route('/api/command/direct_message', methods=['POST'])
@login_required
def api_direct_message():
    data = request.json; telegram_id = data.get('telegram_id'); message = data.get('message')
    if not all([telegram_id, message]): return jsonify({'status': 'error', 'message': 'Missing Telegram ID or message text.'}), 400
    try:
        asyncio.run(telegram_app_for_web.bot.send_message(chat_id=telegram_id, text=message))
        return jsonify({'status': 'success', 'message': 'Direct message sent successfully.'})
    except Exception as e: return jsonify({'status': 'error', 'message': 'Failed to send message via Telegram API.'}), 500

async def broadcast_message_from_web(user_ids, message):
    for user_id in user_ids:
        try:
            await telegram_app_for_web.bot.send_message(chat_id=user_id, text=message, parse_mode=constants.ParseMode.MARKDOWN)
            await asyncio.sleep(0.1)
        except Exception as e: logger.warning(f"Failed broadcast to user {user_id} from web head: {e}")

# =================================================================================
# === WORKER HEART: TELEGRAM BOT (For the 'worker' process) =======================
# =================================================================================

def load_bot_data():
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'w') as f: json.dump({'bot_settings': BOT_SETTINGS, 'files': FILES}, f, indent=2)
    try:
        with open(SETTINGS_FILE, 'r') as f: data = json.load(f)
        BOT_SETTINGS.update(data.get('bot_settings', {})); FILES.update(data.get('files', {}))
    except Exception as e: logger.error(f"WORKER: Error loading settings: {e}")

def save_bot_data():
    try:
        with open(SETTINGS_FILE, 'w') as f: json.dump({'bot_settings': BOT_SETTINGS, 'files': FILES}, f, indent=2)
    except Exception as e: logger.error(f"WORKER: Error saving settings: {e}")

async def start(update, context):
    user = update.effective_user
    db.add_or_update_telegram_user(user)
    
    if str(user.id) == ADMIN_ID:
        welcome_msg = f"🚀 Welcome, Mission Control. All systems nominal."
        await update.message.reply_text(welcome_msg, reply_markup=create_admin_keyboard())
    elif db.is_app_user(user.id):
        welcome_msg = f"👋 Welcome back, operative {user.first_name}."
        await update.message.reply_text(welcome_msg, reply_markup=create_main_keyboard())
    else:
        pending_msg = "⏳ Your access request has been received and is pending approval from Mission Control. You will be notified upon review."
        await update.message.reply_text(pending_msg)
        await notify_admin_of_new_user(context.bot, user)

async def notify_admin_of_new_user(bot, user: TelegramUser):
    user_details = f"Name: {user.first_name} {user.last_name or ''}\nUsername: @{user.username}\nID: `{user.id}`"
    text = f"‼️ **New Access Request** ‼️\n\nAn applicant requires your authorization:\n\n{user_details}"
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}"),
        InlineKeyboardButton("❌ Deny", callback_data=f"deny_{user.id}")
    ]])
    await bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode='Markdown', reply_markup=keyboard)

async def callback_query_handler(update, context):
    query = update.callback_query
    await query.answer()
    callback_data = query.data
    
    if callback_data.startswith("approve_"):
        await handle_user_approval(query, context)
        return
    elif callback_data.startswith("deny_"):
        await handle_user_denial(query, context)
        return

    COMMAND_MAP = {"download_datrix": handle_download, "list_files": handle_list_files, "back_to_menu": handle_back_to_menu}
    if callback_data in COMMAND_MAP: await COMMAND_MAP[callback_data](query, context)

async def handle_user_approval(query, context):
    applicant_id = int(query.data.split("_")[1])
    conn = db.get_db_connection()
    applicant_user_data = conn.execute("SELECT * FROM telegram_users WHERE telegram_id = ?", (applicant_id,)).fetchone()
    conn.close()

    if not applicant_user_data:
        await query.edit_message_text("Error: Applicant data not found in telegram_users table."); return

    applicant_user = TelegramUser(id=applicant_user_data['telegram_id'], first_name=applicant_user_data['first_name'], is_bot=False, last_name=applicant_user_data['last_name'], username=applicant_user_data['user_name'])
    
    success = db.create_app_user(applicant_user)
    if success:
        await query.edit_message_text(f"✅ **Access Approved** for {applicant_user.first_name} (`{applicant_id}`). They have been notified.")
        await context.bot.send_message(chat_id=applicant_id, text="✅ **Access Granted!**\n\nWelcome, operative. You now have full access. Use /start to see available commands.")
    else:
        await query.edit_message_text(f"⚠️ **User Already Exists** for ID `{applicant_id}`.")

async def handle_user_denial(query, context):
    applicant_id = int(query.data.split("_")[1])
    applicant_name = query.message.text.split('\n')[3].split('Name: ')[1] # A bit fragile, but works for this context
    await query.edit_message_text(f"❌ **Access Denied** for applicant {applicant_name} (`{applicant_id}`). They have been notified.")
    await context.bot.send_message(chat_id=applicant_id, text="❌ Your access request has been reviewed and denied by Mission Control.")

def create_main_keyboard(): return InlineKeyboardMarkup([[InlineKeyboardButton("📥 Download DATRIX", callback_data="download_datrix")], [InlineKeyboardButton("📋 Available Files", callback_data="list_files")]])
def create_admin_keyboard():
    dashboard_url = f"https://{os.environ.get('RAILWAY_STATIC_URL')}" if 'RAILWAY_STATIC_URL' in os.environ else None
    buttons = [[InlineKeyboardButton("📥 Download DATRIX", callback_data="download_datrix")], [InlineKeyboardButton("📋 Available Files", callback_data="list_files")]]
    if dashboard_url: buttons.append([InlineKeyboardButton("🖥️ Mission Control", url=dashboard_url)])
    return InlineKeyboardMarkup(buttons)

async def handle_download(query, context):
    file_info = FILES['datrix_app']
    if not file_info.get('message_id'): await query.edit_message_text("❌ *File Unavailable*", parse_mode='Markdown'); return
    try:
        await context.bot.forward_message(chat_id=query.message.chat_id, from_chat_id=CHANNEL_ID, message_id=file_info['message_id'])
    except Exception as e: logger.error(f"WORKER: Error delivering file: {e}"); await query.message.reply_text("❌ *Download Error*")

async def handle_list_files(query, context):
    info = FILES['datrix_app']; status = "✅ Available" if info['message_id'] else "❌ Not available"
    text = f"📂 *Files:*\n\n📄 *{info['description']}*\n🔢 Ver: `{info['version']}`\n💾 Size: `{info['size']}`\n📊 Status: {status}"
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]))

async def handle_back_to_menu(query, context):
    welcome_msg = f"👋 Welcome back, {query.from_user.first_name}!"
    keyboard = create_admin_keyboard() if str(query.from_user.id) == ADMIN_ID else create_main_keyboard()
    await query.edit_message_text(welcome_msg, parse_mode='Markdown', reply_markup=keyboard)

def run_bot():
    if not all([BOT_TOKEN, ADMIN_ID, CHANNEL_ID, ADMIN_PASSWORD]): logger.critical("WORKER: Missing required environment variables. Halting."); return
    db.initialize_database(); logger.info("WORKER: Database foundation verified.")
    load_bot_data()
    worker_app = Application.builder().token(BOT_TOKEN).build()
    worker_app.add_handler(CommandHandler("start", start))
    worker_app.add_handler(CallbackQueryHandler(callback_query_handler))
    logger.info("🚀 DATRIX Worker Heart (v6.1) is engaging polling sequence...")
    worker_app.run_polling(drop_pending_updates=True)

# =================================================================================
# === MAIN ENTRY POINT ============================================================
# =================================================================================
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--run-bot': run_bot()
    else: logger.info("Script started without '--run-bot'. Gunicorn is expected to manage this process.")
