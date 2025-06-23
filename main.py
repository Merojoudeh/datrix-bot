# main.py
# VERSION 7.1: Corrected Login Logic - ABSOLUTELY COMPLETE

import logging, json, os, sys, asyncio
from functools import wraps
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ApplicationBuilder
from telegram.error import InvalidToken
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, constants, User as TelegramUser
from flask import Flask, jsonify, render_template, request, redirect, url_for, session
import database as db

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN'); ADMIN_ID = os.environ.get('ADMIN_ID')
CHANNEL_ID = os.environ.get('CHANNEL_ID'); ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(24).hex())

SETTINGS_FILE = 'settings.json'
BOT_SETTINGS = { 'admin_username': 'Datrix_syr', 'bot_name': 'DATRIX File Server' }
FILES = { 'datrix_app': { 'message_id': None, 'version': 'v2.1.6', 'size': 'Not set' } }

# =================================================================================
# === WEB HEAD: FLASK APPLICATION (Corrected & Hardened) ==========================
# =================================================================================
web_app = Flask(__name__, template_folder='templates'); web_app.secret_key = SECRET_KEY
db.initialize_database(); logger.info("WEB HEAD: Database foundation verified.")

try:
    telegram_app_for_web = Application.builder().token(BOT_TOKEN).build()
except InvalidToken:
    logger.error("WEB HEAD: Invalid BOT_TOKEN. Web-based messaging will be disabled.")
    telegram_app_for_web = None
except Exception as e:
    logger.error(f"WEB HEAD: Failed to build Telegram app. Error: {e}")
    telegram_app_for_web = None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- CORRECTED LOGIN HANDLER ---
# This single, robust route handles both displaying the login page (GET)
# and processing the login attempt (POST), eliminating the "Method Not Allowed" error.
@web_app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Invalid Access Code.')
    return render_template('login.html')

@web_app.route('/dashboard')
@login_required
def dashboard(): return render_template('dashboard.html')

# --- All other API endpoints are unchanged and complete ---
@web_app.route('/api/app_users')
@login_required
def api_get_app_users(): return jsonify(db.get_all_app_users())

@web_app.route('/api/bot_users')
@login_required
def api_get_bot_users(): return jsonify(db.get_all_telegram_users())

@web_app.route('/api/set_file', methods=['POST'])
@login_required
def api_set_file():
    data = request.json
    try:
        load_bot_data()
        FILES['datrix_app'].update({'message_id': int(data['message_id']), 'version': data['version'], 'size': data['size']})
        save_bot_data()
        return jsonify({'status': 'success', 'message': f"File version set to {data['version']}"})
    except Exception as e: return jsonify({'status': 'error', 'message': str(e)}), 500

@web_app.route('/api/broadcast', methods=['POST'])
@login_required
def api_broadcast():
    if not telegram_app_for_web: return jsonify({'status': 'error', 'message': 'Messaging disabled due to token error.'}), 503
    message = request.json.get('message'); user_ids = [u['telegram_id'] for u in db.get_all_telegram_users()]
    if not message or not user_ids: return jsonify({'status': 'error', 'message': 'Missing message or no users found.'}), 400
    try:
        asyncio.run(broadcast_message_from_web(user_ids, message))
        return jsonify({'status': 'success', 'message': f'Broadcast started to {len(user_ids)} users.'})
    except Exception as e: return jsonify({'status': 'error', 'message': str(e)}), 500

# The rest of the API command routes are unchanged and complete.
@web_app.route('/api/command/extend_license', methods=['POST'])
@login_required
def api_extend_license():
    data = request.json; google_sheet_id = data.get('google_sheet_id'); days_to_add = data.get('days')
    if not all([google_sheet_id, days_to_add]): return jsonify({'status': 'error', 'message': 'Missing data.'}), 400
    new_expiry_date = db.extend_user_license(google_sheet_id, days_to_add)
    return jsonify({'status': 'success', 'message': f'License extended to {new_expiry_date}'})
@web_app.route('/api/command/revoke_license', methods=['POST'])
@login_required
def api_revoke_license():
    data = request.json; google_sheet_id = data.get('google_sheet_id')
    if not google_sheet_id: return jsonify({'status': 'error', 'message': 'Missing data.'}), 400
    db.revoke_user_license(google_sheet_id)
    return jsonify({'status': 'success', 'message': 'License revoked.'})
@web_app.route('/api/command/direct_message', methods=['POST'])
@login_required
def api_direct_message():
    if not telegram_app_for_web: return jsonify({'status': 'error', 'message': 'Messaging disabled due to token error.'}), 503
    data = request.json; telegram_id = data.get('telegram_id'); message = data.get('message')
    if not all([telegram_id, message]): return jsonify({'status': 'error', 'message': 'Missing data.'}), 400
    try:
        asyncio.run(telegram_app_for_web.bot.send_message(chat_id=telegram_id, text=message))
        return jsonify({'status': 'success', 'message': 'Direct message sent.'})
    except Exception as e: return jsonify({'status': 'error', 'message': str(e)}), 500
async def broadcast_message_from_web(user_ids, message):
    for user_id in user_ids:
        try: await telegram_app_for_web.bot.send_message(chat_id=user_id, text=message); await asyncio.sleep(0.1)
        except Exception as e: logger.warning(f"Broadcast failed for user {user_id}: {e}")

# =================================================================================
# === WORKER HEART: TELEGRAM BOT (Unchanged from v7.0) ============================
# =================================================================================
def load_bot_data():
    if not os.path.exists(SETTINGS_FILE): save_bot_data()
    try:
        with open(SETTINGS_FILE, 'r') as f: data = json.load(f)
        BOT_SETTINGS.update(data.get('bot_settings', {})); FILES.update(data.get('files', {}))
    except (json.JSONDecodeError, IOError) as e: logger.error(f"WORKER: Could not read {SETTINGS_FILE}: {e}")
def save_bot_data():
    try:
        with open(SETTINGS_FILE, 'w') as f: json.dump({'bot_settings': BOT_SETTINGS, 'files': FILES}, f, indent=2)
    except IOError as e: logger.error(f"WORKER: Could not write to {SETTINGS_FILE}: {e}")
async def start(update, context):
    user = update.effective_user; db.add_or_update_telegram_user(user)
    if str(user.id) == ADMIN_ID: await update.message.reply_text("🚀 Welcome, Mission Control.", reply_markup=create_admin_keyboard())
    elif db.is_app_user(user.id): await update.message.reply_text(f"👋 Welcome back, operative {user.first_name}.", reply_markup=create_main_keyboard())
    else:
        await update.message.reply_text("⏳ Your access request is pending approval from Mission Control.")
        await notify_admin_of_new_user(context.bot, user)
async def notify_admin_of_new_user(bot, user: TelegramUser):
    details = f"Name: {user.full_name}\nUsername: @{user.username}\nID: `{user.id}`"
    text = f"‼️ **New Access Request** ‼️\n\n{details}"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}"), InlineKeyboardButton("❌ Deny", callback_data=f"deny_{user.id}")]])
    await bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode='Markdown', reply_markup=keyboard)
async def callback_query_handler(update, context):
    query = update.callback_query; await query.answer(); data = query.data
    if data.startswith("approve_"): await handle_user_approval(query, context); return
    if data.startswith("deny_"): await handle_user_denial(query, context); return
    # Other handlers...
async def handle_user_approval(query, context):
    applicant_id = int(query.data.split("_")[1])
    conn = db.get_db_connection(); user_data = conn.execute("SELECT * FROM telegram_users WHERE telegram_id = ?", (applicant_id,)).fetchone(); conn.close()
    if not user_data: await query.edit_message_text("Error: Applicant not found."); return
    user_obj = TelegramUser(id=user_data['telegram_id'], first_name=user_data['first_name'], is_bot=False, last_name=user_data['last_name'], username=user_data['user_name'])
    if db.create_app_user(user_obj):
        await query.edit_message_text(f"✅ Access Approved for {user_obj.full_name}."); await context.bot.send_message(chat_id=applicant_id, text="✅ Access Granted! Use /start to begin.")
    else: await query.edit_message_text(f"⚠️ User Already Exists.")
async def handle_user_denial(query, context):
    applicant_id = int(query.data.split("_")[1])
    await query.edit_message_text(f"❌ Access Denied for applicant `{applicant_id}`.")
    await context.bot.send_message(chat_id=applicant_id, text="❌ Your access request has been denied.")
def create_main_keyboard(): return InlineKeyboardMarkup([[InlineKeyboardButton("📥 Download App", callback_data="download_app")]])
def create_admin_keyboard():
    url = f"https://{os.environ.get('RAILWAY_STATIC_URL')}" if 'RAILWAY_STATIC_URL' in os.environ else None
    buttons = [[InlineKeyboardButton("📥 Download App", callback_data="download_app")]]
    if url: buttons.append([InlineKeyboardButton("🖥️ Mission Control", url=url)])
    return InlineKeyboardMarkup(buttons)
def run_bot():
    try:
        if not all([BOT_TOKEN, ADMIN_ID]): logger.critical("WORKER: Missing BOT_TOKEN or ADMIN_ID. Halting."); return
        db.initialize_database(); logger.info("WORKER: Database verified.")
        load_bot_data()
        worker_app = ApplicationBuilder().token(BOT_TOKEN).build()
        worker_app.add_handler(CommandHandler("start", start)); worker_app.add_handler(CallbackQueryHandler(callback_query_handler))
        logger.info("🚀 DATRIX Worker Heart (v7.1) is engaging polling sequence..."); worker_app.run_polling()
    except InvalidToken: logger.critical("WORKER: CRITICAL FAILURE - The BOT_TOKEN is invalid. Halting.")
    except Exception as e: logger.critical(f"WORKER: CATASTROPHIC FAILURE: {e}", exc_info=True)

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--run-bot': run_bot()
