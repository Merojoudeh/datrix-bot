# bot_handlers.py
# The shared command and callback logic for the bot.

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db
import os

ADMIN_TELEGRAM_ID = int(os.environ.get('ADMIN_TELEGRAM_ID', 0))

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_or_update_telegram_user(user)
    if db.is_app_user(user.id):
        keyboard = [[KeyboardButton("Download App")], [KeyboardButton("Request License")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Welcome, authorized operative.", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Welcome. Your access is pending approval.")

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
            if file_info and file_info.get('message_id'):
                await context.bot.forward_message(chat_id=user_id, from_chat_id=file_info['from_chat_id'], message_id=file_info['message_id'])
            else:
                await update.message.reply_text("📂 File not yet available.")
        else: await update.message.reply_text("Access denied.")
    elif text == "Request License":
        if db.is_app_user(user_id):
            keyboard = [[InlineKeyboardButton("Confirm", callback_data=f"req_license_{user_id}")]]
            await update.message.reply_text(f"Confirm license request?", reply_markup=InlineKeyboardMarkup(keyboard))
        else: await update.message.reply_text("Access denied.")
    else:
        if not db.is_app_user(user_id):
            keyboard = [[InlineKeyboardButton("Request Access", callback_data=f"req_access_{user_id}")]]
            await update.message.reply_text("Your access is pending. Notify admin?", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_access_request(query, context):
    applicant_id = int(query.data.split("_")[2])
    user = db.get_telegram_user_by_id(applicant_id)
    if not user: return
    keyboard = [[InlineKeyboardButton(f"Approve: {user.first_name}", callback_data=f"approve_{applicant_id}")]]
    await context.bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=f"❗️ Access request:\nID: `{user.telegram_id}`\nName: {user.first_name}", reply_markup=InlineKeyboardMarkup(keyboard))
    await query.edit_message_text("✅ Admin notified.")

async def handle_user_approval(query, context):
    applicant_id = int(query.data.split("_")[1])
    db.create_app_user(applicant_id)
    await query.edit_message_text(f"✅ Access Approved for `{applicant_id}`.")
    await context.bot.send_message(chat_id=applicant_id, text="✅ Access Granted! Use /start.")

async def handle_license_request(query, context):
    applicant_id = int(query.data.split("_")[2])
    user = db.get_telegram_user_by_id(applicant_id)
    if not user: return
    await context.bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=f"🔑 License request:\nID: `{user.telegram_id}`\nName: {user.first_name}")
    await query.edit_message_text("✅ License request sent.")

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("req_access_"): await handle_access_request(query, context)
    elif data.startswith("approve_"): await handle_user_approval(query, context)
    elif data.startswith("req_license_"): await handle_license_request(query, context)
