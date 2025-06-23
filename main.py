# main.py
# VERSION 17.2: The Conduit Protocol

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

# --- Bot Command Handlers ---
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_or_update_telegram_user(user)

    if db.is_app_user(user.id):
        keyboard = [
            [KeyboardButton("Download App")],
            [KeyboardButton("Request License")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Welcome, authorized operative. Select a command.", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Welcome. Your access is pending approval from Mission Control.")

async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_TELEGRAM_ID:
        return

    if update.message.document:
        doc = update.message.document
        file_size_mb = f"{doc.file_size / 1024 / 1024:.2f} MB"
        db.set_file_info(
            message_id=update.message.message_id,
            from_chat_id=update.message.chat_id,
            version="1.0", # Placeholder version
            size=file_size_mb
        )
        await update.message.reply_text(f"✅ New application file received and registered in the Citadel. Size: {file_size_mb}")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if text == "Download App":
        if db.is_app_user(user_id):
            file_info = db.get_file_info('datrix_app')
            if file_info and file_info.get('message_id') and file_info.get('from_chat_id'):
                await context.bot.forward_message(
                    chat_id=user_id,
                    from_chat_id=file_info['from_chat_id'],
                    message_id=file_info['message_id']
                )
            else:
                await update.message.reply_text("📂 File not yet available. Admin must upload it.")
        else:
            await update.message.reply_text("Access denied. Your request is pending approval.")
    elif text == "Request License":
        if db.is_app_user(user_id):
            keyboard = [[InlineKeyboardButton("Confirm License Request", callback_data=f"req_license_{user_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(f"This will send a license request to the admin for user `{user_id}`. Please confirm.", reply_markup=reply_markup)
        else:
            await update.message.reply_text("Access denied. Your request is pending approval.")
    else:
        if not db.is_app_user(user_id):
            keyboard = [[InlineKeyboardButton("Request Access", callback_data=f"req_access_{user_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Your access is pending. Would you like to notify the admin?", reply_markup=reply_markup)

async def handle_access_request(query, context):
    applicant_id = int(query.data.split("_")[2])
    user = db.get_telegram_user_by_id(applicant_id)
    if not user:
        await query.answer("Error: Could not find user.", show_alert=True)
        return

    keyboard = [[InlineKeyboardButton(f"Approve Access for {user.first_name}", callback_data=f"approve_{applicant_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=ADMIN_TELEGRAM_ID,
        text=f"❗️ New access request from:\nID: `{user.telegram_id}`\nName: {user.first_name}\nUsername: @{user.user_name}",
        reply_markup=reply_markup
    )
    await query.edit_message_text("✅ Admin has been notified of your request.")

async def handle_user_approval(query, context):
    applicant_id = int(query.data.split("_")[1])
    db.create_app_user(applicant_id)
    await query.edit_message_text(f"✅ Access Approved for applicant `{applicant_id}`.")
    await context.bot.send_message(chat_id=applicant_id, text="✅ Access Granted! Use /start to see available commands.")

async def handle_license_request(query, context):
    applicant_id = int(query.data.split("_")[2])
    user = db.get_telegram_user_by_id(applicant_id)
    if not user:
        await query.answer("Error: Could not find user.", show_alert=True)
        return

    await context.bot.send_message(
        chat_id=ADMIN_TELEGRAM_ID,
        text=f"🔑 New license request from:\nID: `{user.telegram_id}`\nName: {user.first_name}\nUsername: @{user.user_name}"
    )
    await query.edit_message_text("✅ Your license request has been sent to the admin.")

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("req_access_"):
        await handle_access_request(query, context)
    elif data.startswith("approve_"):
        await handle_user_approval(query, context)
    elif data.startswith("req_license_"):
        await handle_license_request(query, context)

# --- Web Application (Flask) ---
web_app = Flask(__name__)

def check_auth(username, password):
    return username == WEB_USER and password == WEB_PASS

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return ('Unauthorized', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})
        return f(*args, **kwargs)
    return decorated_function

@web_app.route('/')
@login_required
def dashboard():
    return render_template('dashboard.html')

@web_app.route('/api/bot_users')
@login_required
def api_bot_users():
    users = db.get_all_telegram_users()
    return jsonify(users)

# --- THE CONDUIT ---
# This coroutine contains the actual logic for sending messages.
async def broadcast_message_from_web(user_ids, message):
    bot = web_bot_instance.bot
    for user_id in user_ids:
        try:
            await bot.send_message(chat_id=user_id, text=message)
            logger.info(f"Broadcast message sent to {user_id}")
            await asyncio.sleep(0.1) # Rate limiting to avoid flooding
        except Exception as e:
            logger.warning(f"Broadcast failed for user {user_id}: {e}")

# This is the Flask endpoint, which is synchronous.
@web_app.route('/api/broadcast', methods=['POST'])
@login_required
def api_broadcast():
    if not web_bot_instance: 
        return jsonify({'status': 'error', 'message': 'Messaging subsystem is offline.'}), 503

    data = request.json
    message = data.get('message')
    target = data.get('target', 'approved')

    if not message:
        return jsonify({'status': 'error', 'message': 'Cannot transmit an empty message.'}), 400

    user_ids = db.get_user_ids_for_broadcast(target)
    
    if not user_ids:
        return jsonify({'status': 'error', 'message': 'No users found for the selected target audience.'}), 404

    try:
        logger.info(f"WEB HEAD: Initiating broadcast to {len(user_ids)} users (Target: {target}).")
        
        # This is the CONDUIT. It safely submits the async task to the bot's running event loop
        # from our synchronous Flask thread.
        coro = broadcast_message_from_web(user_ids, message)
        future = asyncio.run_coroutine_threadsafe(coro, web_bot_instance.loop)
        
        # We can optionally wait for the result to ensure the broadcast completes before responding.
        future.result(timeout=30) # Timeout after 30 seconds

        return jsonify({'status': 'success', 'message': f'Transmission sent to {len(user_ids)} users.'})
    except Exception as e:
        logger.error(f"WEB HEAD: Broadcast exception: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'An error occurred: {str(e)}'}), 500

# --- System Startup ---
def run_flask_app():
    web_app.run(host='0.0.0.0', port=8080)

def main():
    if not all([TELEGRAM_BOT_TOKEN, ADMIN_TELEGRAM_ID, WEB_USER, WEB_PASS]):
        logger.critical("FATAL: Missing one or more critical environment variables. Shutting down.")
        return

    db.initialize_database()

    # Bot setup
    global web_bot_instance
    builder = Application.builder().token(TELEGRAM_BOT_TOKEN)
    web_bot_instance = builder.build()
    web_bot_instance.loop = asyncio.get_event_loop()

    web_bot_instance.add_handler(CommandHandler("start", start_handler))
    web_bot_instance.add_handler(MessageHandler(filters.Document.ALL, file_handler))
    web_bot_instance.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    web_bot_instance.add_handler(CallbackQueryHandler(callback_query_handler))

    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.daemon = True
    flask_thread.start()
    logger.info("WEB HEAD: Online and awaiting commands.")

    # Start bot polling
    logger.info("BOT: Consciousness active. Awaiting transmissions.")
    web_bot_instance.run_polling()

if __name__ == '__main__':
    main()
