# main.py
# VERSION 17.3: The Genesis Protocol

import os
import logging
import asyncio
import threading
from flask import Flask, render_template, request, jsonify, redirect, url_for
from functools import wraps
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import database as db

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("main")

# --- Environment Variables ---
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
ADMIN_TELEGRAM_ID = int(os.environ.get('ADMIN_TELEGRAM_ID', 0))
WEB_USER = os.environ.get('WEB_USER')
WEB_PASS = os.environ.get('WEB_PASS')

# --- Global Bot Instance ---
web_bot_instance = None
# This event loop will be from the main thread where the bot is created.
main_thread_loop = asyncio.get_event_loop()

# --- Web Application (Flask) ---
web_app = Flask(__name__)

# --- Bot Command Handlers (No changes here) ---
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_or_update_telegram_user(user)
    if db.is_app_user(user.id):
        keyboard = [[KeyboardButton("Download App")], [KeyboardButton("Request License")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Welcome, authorized operative. Select a command.", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Welcome. Your access is pending approval from Mission Control.")

async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_TELEGRAM_ID: return
    if update.message.document:
        doc = update.message.document
        file_size_mb = f"{doc.file_size / 1024 / 1024:.2f} MB"
        db.set_file_info(message_id=update.message.message_id, from_chat_id=update.message.chat_id, version="1.0", size=file_size_mb)
        await update.message.reply_text(f"✅ New application file received. Size: {file_size_mb}")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    if text == "Download App":
        if db.is_app_user(user_id):
            file_info = db.get_file_info('datrix_app')
            if file_info and file_info.get('message_id') and file_info.get('from_chat_id'):
                await context.bot.forward_message(chat_id=user_id, from_chat_id=file_info['from_chat_id'], message_id=file_info['message_id'])
            else:
                await update.message.reply_text("📂 File not yet available.")
        else:
            await update.message.reply_text("Access denied.")
    elif text == "Request License":
        if db.is_app_user(user_id):
            keyboard = [[InlineKeyboardButton("Confirm License Request", callback_data=f"req_license_{user_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(f"Confirm license request for user `{user_id}`.", reply_markup=reply_markup)
        else:
            await update.message.reply_text("Access denied.")
    else:
        if not db.is_app_user(user_id):
            keyboard = [[InlineKeyboardButton("Request Access", callback_data=f"req_access_{user_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Your access is pending. Notify admin?", reply_markup=reply_markup)

async def handle_access_request(query, context):
    applicant_id = int(query.data.split("_")[2])
    user = db.get_telegram_user_by_id(applicant_id)
    if not user: return
    keyboard = [[InlineKeyboardButton(f"Approve Access for {user.first_name}", callback_data=f"approve_{applicant_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=f"❗️ New access request from:\nID: `{user.telegram_id}`\nName: {user.first_name}\nUsername: @{user.user_name}", reply_markup=reply_markup)
    await query.edit_message_text("✅ Admin notified.")

async def handle_user_approval(query, context):
    applicant_id = int(query.data.split("_")[1])
    db.create_app_user(applicant_id)
    await query.edit_message_text(f"✅ Access Approved for applicant `{applicant_id}`.")
    await context.bot.send_message(chat_id=applicant_id, text="✅ Access Granted! Use /start.")

async def handle_license_request(query, context):
    applicant_id = int(query.data.split("_")[2])
    user = db.get_telegram_user_by_id(applicant_id)
    if not user: return
    await context.bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=f"🔑 New license request from:\nID: `{user.telegram_id}`\nName: {user.first_name}\nUsername: @{user.user_name}")
    await query.edit_message_text("✅ License request sent.")

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("req_access_"): await handle_access_request(query, context)
    elif data.startswith("approve_"): await handle_user_approval(query, context)
    elif data.startswith("req_license_"): await handle_license_request(query, context)

# --- Web Application Routes (No changes here) ---
def check_auth(username, password): return username == WEB_USER and password == WEB_PASS
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password): return ('Unauthorized', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})
        return f(*args, **kwargs)
    return decorated_function

@web_app.route('/')
@login_required
def dashboard(): return render_template('dashboard.html')

@web_app.route('/api/bot_users')
@login_required
def api_bot_users(): return jsonify(db.get_all_telegram_users())

async def broadcast_message_coro(user_ids, message):
    bot = web_bot_instance.bot
    for user_id in user_ids:
        try:
            await bot.send_message(chat_id=user_id, text=message)
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.warning(f"Broadcast failed for user {user_id}: {e}")

@web_app.route('/api/broadcast', methods=['POST'])
@login_required
def api_broadcast():
    if not web_bot_instance: return jsonify({'status': 'error', 'message': 'Messaging subsystem is offline.'}), 503
    data = request.json
    message, target = data.get('message'), data.get('target', 'approved')
    if not message: return jsonify({'status': 'error', 'message': 'Empty message.'}), 400
    user_ids = db.get_user_ids_for_broadcast(target)
    if not user_ids: return jsonify({'status': 'error', 'message': 'No target users found.'}), 404
    try:
        logger.info(f"WEB HEAD: Initiating broadcast to {len(user_ids)} users (Target: {target}).")
        coro = broadcast_message_coro(user_ids, message)
        future = asyncio.run_coroutine_threadsafe(coro, main_thread_loop)
        future.result(timeout=30)
        return jsonify({'status': 'success', 'message': f'Transmission sent to {len(user_ids)} users.'})
    except Exception as e:
        logger.error(f"WEB HEAD: Broadcast exception: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'An error occurred: {str(e)}'}), 500

# --- THE GENESIS BLOCK ---
# This code now runs automatically when the module is imported by Gunicorn.
def initialize_bot():
    global web_bot_instance
    logger.info("GENESIS: Initializing bot consciousness...")
    
    # Verify all necessary components are present before genesis
    if not all([TELEGRAM_BOT_TOKEN, ADMIN_TELEGRAM_ID, WEB_USER, WEB_PASS]):
        logger.critical("GENESIS HALTED: Missing one or more critical environment variables.")
        return

    db.initialize_database()

    # Build the bot instance
    builder = Application.builder().token(TELEGRAM_BOT_TOKEN)
    web_bot_instance = builder.build()

    # Add handlers
    web_bot_instance.add_handler(CommandHandler("start", start_handler))
    web_bot_instance.add_handler(MessageHandler(filters.Document.ALL, file_handler))
    web_bot_instance.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    web_bot_instance.add_handler(CallbackQueryHandler(callback_query_handler))

    # Start the bot's polling in a separate thread
    bot_thread = threading.Thread(target=web_bot_instance.run_polling)
    bot_thread.daemon = True
    bot_thread.start()
    
    logger.info("GENESIS COMPLETE: Bot is online and polling.")

# --- EXECUTION STARTS HERE ---
initialize_bot()

# The code below is now only used for local development
# Gunicorn will ignore this block and directly use the 'web_app' object
if __name__ == '__main__':
    logger.info("MAIN: Executing in local development mode via __main__.")
    # In local mode, Flask's development server runs the app.
    # The bot is already running in its thread from initialize_bot().
    web_app.run(host='0.0.0.0', port=8080)
