# main.py
# VERSION 6.0: Automated Onboarding Protocol

import logging, json, os, sys, asyncio
from functools import wraps
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, constants, User as TelegramUser
import database as db

# --- Configuration & Initialization ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN'); ADMIN_ID = os.environ.get('ADMIN_ID')
CHANNEL_ID = os.environ.get('CHANNEL_ID'); ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(24).hex())

SETTINGS_FILE = 'settings.json'
BOT_SETTINGS = { 'admin_username': 'Datrix_syr', 'bot_name': 'DATRIX File Server' }
FILES = { 'datrix_app': { 'message_id': None, 'version': 'v2.1.6', 'size': 'Not set' } }

# --- WEB HEAD (Unchanged) ---
from flask import Flask, jsonify, render_template, request, redirect, url_for, session
web_app = Flask(__name__, template_folder='templates'); web_app.secret_key = SECRET_KEY
db.initialize_database(); logger.info("WEB HEAD: Database foundation verified.")
telegram_app_for_web = Application.builder().token(BOT_TOKEN).build()
# All Flask routes (@web_app.route(...)) are unchanged and omitted for brevity. They remain as they were in v5.3.

# --- WORKER HEART: The Bot Logic ---

# --- SENTRY: The Evolved /start Command ---
async def start(update, context):
    user = update.effective_user
    db.add_or_update_telegram_user(user)
    
    if str(user.id) == ADMIN_ID:
        # Admin gets the command deck
        welcome_msg = f"🚀 Welcome, Mission Control. All systems nominal."
        await update.message.reply_text(welcome_msg, reply_markup=create_admin_keyboard())
    elif db.is_app_user(user.id):
        # Existing operative gets the standard menu
        welcome_msg = f"👋 Welcome back, operative {user.first_name}."
        await update.message.reply_text(welcome_msg, reply_markup=create_main_keyboard())
    else:
        # New applicant is placed in pending state
        pending_msg = "⏳ Your access request has been received and is pending approval from Mission Control. You will be notified upon review."
        await update.message.reply_text(pending_msg)
        # --- ALERT: Notify Admin of New Applicant ---
        await notify_admin_of_new_user(context.bot, user)

# --- ALERT & GATEKEEPER ---
async def notify_admin_of_new_user(bot, user: TelegramUser):
    user_details = f"Name: {user.first_name} {user.last_name or ''}\nUsername: @{user.username}\nID: `{user.id}`"
    text = f"‼️ **New Access Request** ‼️\n\nAn applicant requires your authorization:\n\n{user_details}"
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}"),
            InlineKeyboardButton("❌ Deny", callback_data=f"deny_{user.id}")
        ]
    ])
    await bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode='Markdown', reply_markup=keyboard)

async def callback_query_handler(update, context):
    query = update.callback_query
    await query.answer()
    callback_data = query.data
    
    # --- GATEKEEPER Logic ---
    if callback_data.startswith("approve_"):
        await handle_user_approval(query, context)
        return
    elif callback_data.startswith("deny_"):
        await handle_user_denial(query, context)
        return

    # Existing handler logic
    COMMAND_MAP = {"download_datrix": handle_download, "list_files": handle_list_files}
    if callback_data in COMMAND_MAP: await COMMAND_MAP[callback_data](query, context)

async def handle_user_approval(query, context):
    applicant_id = int(query.data.split("_")[1])
    # This is a simplified way to get the user object; a more robust solution might store it temporarily.
    # For now, we rely on the fact that the user is in the telegram_users table.
    conn = db.get_db_connection()
    applicant_user_data = conn.execute("SELECT * FROM telegram_users WHERE telegram_id = ?", (applicant_id,)).fetchone()
    conn.close()

    if not applicant_user_data:
        await query.edit_message_text("Error: Applicant data not found.")
        return

    # Create a mock user object for the creation function
    applicant_user = TelegramUser(id=applicant_user_data['telegram_id'], first_name=applicant_user_data['first_name'], is_bot=False, last_name=applicant_user_data['last_name'], username=applicant_user_data['user_name'])

    success = db.create_app_user(applicant_user)
    if success:
        await query.edit_message_text(f"✅ **Access Approved** for {applicant_user.first_name} (`{applicant_id}`). They have been notified.")
        # Notify the new operative
        await context.bot.send_message(chat_id=applicant_id, text="✅ **Access Granted!**\n\nWelcome, operative. You now have full access to the system. Use /start to see available commands.")
    else:
        await query.edit_message_text(f"⚠️ **User Already Exists** for ID `{applicant_id}`.")

async def handle_user_denial(query, context):
    applicant_id = int(query.data.split("_")[1])
    await query.edit_message_text(f"❌ **Access Denied** for applicant `{applicant_id}`. They have been notified.")
    # Notify the denied applicant
    await context.bot.send_message(chat_id=applicant_id, text="❌ Your access request has been reviewed and denied by Mission Control.")

# --- Other Bot Functions (Unchanged) ---
def create_main_keyboard(): return InlineKeyboardMarkup([[InlineKeyboardButton("📥 Download DATRIX", callback_data="download_datrix")]])
def create_admin_keyboard():
    dashboard_url = f"https://{os.environ.get('RAILWAY_STATIC_URL')}" if 'RAILWAY_STATIC_URL' in os.environ else None
    buttons = [[InlineKeyboardButton("📥 Download DATRIX", callback_data="download_datrix")]]
    if dashboard_url: buttons.append([InlineKeyboardButton("🖥️ Mission Control", url=dashboard_url)])
    return InlineKeyboardMarkup(buttons)
async def handle_download(query, context):
    # ... (function is unchanged) ...
    pass 

# --- Main Execution Logic (Unchanged) ---
def run_bot():
    # ... (function is unchanged) ...
    worker_app = Application.builder().token(BOT_TOKEN).build()
    worker_app.add_handler(CommandHandler("start", start))
    worker_app.add_handler(CallbackQueryHandler(callback_query_handler))
    logger.info("🚀 DATRIX Worker Heart (v6.0) is engaging polling sequence...")
    worker_app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--run-bot': run_bot()
    else: pass # Gunicorn manages the web process
