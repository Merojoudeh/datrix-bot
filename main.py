# main.py
# VERSION 14.0: The Penance Protocol - Defect-Free

import logging, os, sys, asyncio, re
from functools import wraps
import database as db
from flask import Flask, jsonify, render_template, request, redirect, url_for, session
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, constants, User as TelegramUser
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ApplicationBuilder
from telegram.error import InvalidToken

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration (Verified) ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(24).hex())

# =================================================================================
# === WEB HEAD: FLASK APPLICATION (Stable) ========================================
# =================================================================================
web_app = Flask(__name__, template_folder='templates'); web_app.secret_key = SECRET_KEY
db.initialize_database()

try:
    web_bot_instance = Bot(token=BOT_TOKEN) if BOT_TOKEN else None
except InvalidToken: web_bot_instance = None
if not web_bot_instance: logger.error("WEB HEAD: Bot instance failed to initialize. Messaging disabled.")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@web_app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if not ADMIN_PASSWORD: return "CRITICAL ERROR: ADMIN_PASSWORD NOT SET", 503
        if request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Invalid Access Code.')
    return render_template('login.html')

@web_app.route('/dashboard')
@login_required
def dashboard(): return render_template('dashboard.html')

@web_app.route('/api/bot_users')
@login_required
def api_get_bot_users(): return jsonify(db.get_all_telegram_users())

@web_app.route('/api/set_file', methods=['POST'])
@login_required
def api_set_file():
    data = request.json
    try:
        db.set_file_info(int(data['message_id']), data['version'], data['size'])
        return jsonify({'status': 'success', 'message': f"File version set to {data['version']}"})
    except Exception as e: return jsonify({'status': 'error', 'message': str(e)}), 500

@web_app.route('/api/broadcast', methods=['POST'])
@login_required
def api_broadcast():
    if not web_bot_instance: return jsonify({'status': 'error', 'message': 'Messaging disabled.'}), 503
    message = request.json.get('message'); user_ids = [u['telegram_id'] for u in db.get_all_telegram_users() if u['is_app_user']]
    if not message or not user_ids: return jsonify({'status': 'error', 'message': 'Message empty or no approved users.'}), 400
    try:
        logger.info(f"WEB HEAD: Initiating broadcast to {len(user_ids)} users.")
        asyncio.run(broadcast_message_from_web(user_ids, message))
        return jsonify({'status': 'success', 'message': f'Broadcast sent to {len(user_ids)} users.'})
    except Exception as e: logger.error(f"WEB HEAD: Broadcast exception: {e}"); return jsonify({'status': 'error', 'message': str(e)}), 500

async def broadcast_message_from_web(user_ids, message):
    for user_id in user_ids:
        try: await web_bot_instance.send_message(chat_id=user_id, text=message); await asyncio.sleep(0.1)
        except Exception as e: logger.warning(f"Broadcast failed for user {user_id}: {e}")

# =================================================================================
# === WORKER HEART: TELEGRAM BOT (Stable) =========================================
# =================================================================================
def escape_markdown_v2(text: str) -> str:
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

async def start(update, context):
    user = update.effective_user; db.add_or_update_telegram_user(user)
    if str(user.id) == ADMIN_ID: await update.message.reply_text("🚀 Welcome, Mission Control.", reply_markup=create_admin_keyboard())
    elif db.is_app_user(user.id): await update.message.reply_text(f"👋 Welcome back, operative {user.first_name}.", reply_markup=create_main_keyboard())
    else:
        await update.message.reply_text("⏳ Your access request is pending approval from Mission Control.")
        await notify_admin_of_new_user(context.bot, user)

async def notify_admin_of_new_user(bot, user: TelegramUser):
    safe_full_name = escape_markdown_v2(user.full_name)
    safe_username = escape_markdown_v2(f"@{user.username}" if user.username else "N/A")
    details = (f"*Name*: {safe_full_name}\n*Username*: {safe_username}\n*ID*: `{user.id}`")
    text = f"‼️ *New Access Request* ‼️\n\n{details}"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}"), InlineKeyboardButton("❌ Deny", callback_data=f"deny_{user.id}")]])
    await bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode=constants.ParseMode.MARKDOWN_V2, reply_markup=keyboard)

async def callback_query_handler(update, context):
    query = update.callback_query; await query.answer()
    data = query.data
    if data.startswith("approve_"): await handle_user_approval(query, context); return
    if data.startswith("deny_"): await handle_user_denial(query, context); return
    if data == "download_app": await download_app_handler(query, context); return

async def handle_user_approval(query, context):
    applicant_id = int(query.data.split("_")[1]); user_data = db.get_all_telegram_users()
    applicant = next((u for u in user_data if u['telegram_id'] == applicant_id), None)
    if not applicant: await query.edit_message_text("Error: Applicant not found."); return
    db.create_app_user(TelegramUser(id=applicant['telegram_id'], first_name=applicant['first_name'], is_bot=False))
    await query.edit_message_text(f"✅ Access Approved for {applicant['first_name']}.")
    await context.bot.send_message(chat_id=applicant_id, text="✅ Access Granted! Use /start to see available commands.")

async def handle_user_denial(query, context):
    applicant_id = int(query.data.split("_")[1])
    await query.edit_message_text(f"❌ Access Denied for applicant `{applicant_id}`.")
    await context.bot.send_message(chat_id=applicant_id, text="❌ Your access request has been denied.")

async def download_app_handler(query, context):
    file_info = db.get_file_info('datrix_app')
    if file_info and file_info['message_id']:
        await context.bot.forward_message(chat_id=query.from_user.id, from_chat_id=ADMIN_ID, message_id=file_info['message_id'])
    else:
        await context.bot.send_message(chat_id=query.from_user.id, text="📂 The file is not yet available from Mission Control. Please check back later.")

def create_main_keyboard(): return InlineKeyboardMarkup([[InlineKeyboardButton("📥 Download App", callback_data="download_app")]])
def create_admin_keyboard():
    url = f"https://{os.environ.get('RAILWAY_STATIC_URL')}" if 'RAILWAY_STATIC_URL' in os.environ else None
    buttons = [[InlineKeyboardButton("📥 Download App", callback_data="download_app")]]
    if url: buttons.append([InlineKeyboardButton("🖥️ Mission Control", url=url)])
    return InlineKeyboardMarkup(buttons)

def run_bot():
    worker_app = None
    try:
        if not all([BOT_TOKEN, ADMIN_ID]):
            logger.critical("WORKER: Critical configuration missing. Halting.")
            return
        db.initialize_database()
        worker_app = ApplicationBuilder().token(BOT_TOKEN).build()
        worker_app.add_handler(CommandHandler("start", start))
        worker_app.add_handler(CallbackQueryHandler(callback_query_handler))
        logger.info("SYSTEM ONLINE: Worker engaging polling sequence.")
    except Exception as e:
        logger.critical(f"WORKER: CATASTROPHIC BOOT FAILURE: {e}", exc_info=True)
        return
        
    if worker_app:
        worker_app.run_polling()
