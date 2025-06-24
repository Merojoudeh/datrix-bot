# bot_handlers.py
# VERSION 2.0: Aegis Protocol Integration

import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Environment ---
ADMIN_TELEGRAM_ID = int(os.environ.get('ADMIN_TELEGRAM_ID'))

# --- Handlers ---

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greets the user and registers them."""
    user = update.effective_user
    db.add_user(user.id, user.username or user.first_name)
    await update.message.reply_text("Welcome. You are now registered. You can send me files for approval.")

async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles file submissions from users."""
    user = update.effective_user
    user_status = db.get_user_status(user.id)

    if user_status == 'unregistered':
        db.add_user(user.id, user.username or user.first_name)
        await update.message.reply_text("I've registered you. Please send the file again.")
        return

    if user_status == 'rejected':
        await update.message.reply_text("Your access has been rejected by the administrator.")
        return

    doc = update.message.document
    file_id = doc.file_id
    file_name = doc.file_name

    # Admin notification keyboard
    admin_keyboard = [
        [
            InlineKeyboardButton("Approve", callback_data=f"approve:{user.id}"),
            InlineKeyboardButton("Reject", callback_data=f"reject:{user.id}"),
        ]
    ]
    admin_markup = InlineKeyboardMarkup(admin_keyboard)

    # Send notification to admin FIRST to get the message_id
    admin_message = await context.bot.send_message(
        chat_id=ADMIN_TELEGRAM_ID,
        text=f"New file submission from {user.first_name} (@{user.username}, ID: {user.id})\nFile: {file_name}",
        reply_markup=admin_markup
    )

    # Add to DB, now including the admin_message_id
    submission_id = db.add_file_submission(user.id, user.username, file_id, file_name, admin_message.message_id)

    # --- AEGIS PROTOCOL IMPLEMENTATION ---
    # User confirmation keyboard with a "Cancel" button
    user_keyboard = [
        [InlineKeyboardButton("Cancel Submission", callback_data=f"cancel:{submission_id}")]
    ]
    user_markup = InlineKeyboardMarkup(user_keyboard)

    await update.message.reply_text(
        "Your file has been submitted for approval. You can cancel it before the admin takes action.",
        reply_markup=user_markup
    )

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles regular text messages."""
    user_status = db.get_user_status(update.effective_user.id)
    if user_status == 'approved':
        await update.message.reply_text("Your account is approved. Send a file to have it processed.")
    else:
        await update.message.reply_text("Your account is pending approval or has been rejected. Please submit a file for review.")

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles button presses from inline keyboards."""
    query = update.callback_query
    await query.answer()
    data = query.data
    
    # --- ADMIN ACTION LOGIC ---
    if data.startswith("approve:") or data.startswith("reject:"):
        if query.from_user.id != ADMIN_TELEGRAM_ID:
            await query.answer("Unauthorized action.", show_alert=True)
            return

        action, user_id_str = data.split(":")
        user_id = int(user_id_str)
        
        db.update_user_status(user_id, f"{action}d") # approved or rejected
        
        status_text = "approved" if action == "approve" else "rejected"
        await query.edit_message_text(text=f"User {user_id} has been {status_text}.")
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"Your account status has been updated to: {status_text}."
            )
        except Exception as e:
            logger.warning(f"Could not notify user {user_id} of status change: {e}")

    # --- AEGIS PROTOCOL CANCELLATION LOGIC ---
    elif data.startswith("cancel:"):
        submission_id_str = data.split(":")[1]
        submission_id = int(submission_id_str)
        
        details = db.get_submission_details(submission_id)
        if not details:
            await query.edit_message_text("This submission has already been processed or cancelled.")
            return

        original_user_id, file_id, file_name, admin_message_id = details
        
        # Security check: ensure the user clicking is the one who submitted
        if query.from_user.id != original_user_id:
            await query.answer("This is not your submission to cancel.", show_alert=True)
            return
            
        # Proceed with cancellation
        db.delete_submission(submission_id)
        
        # Notify user
        await query.edit_message_text(text=f"Your submission for '{file_name}' has been successfully cancelled.")
        
        # Notify admin by editing their original message
        try:
            await context.bot.edit_message_text(
                chat_id=ADMIN_TELEGRAM_ID,
                message_id=admin_message_id,
                text=f"Submission from @{query.from_user.username} (File: {file_name}) was CANCELLED by the user.",
                reply_markup=None # Remove buttons
            )
        except Exception as e:
            logger.warning(f"Could not edit admin message for cancelled submission {submission_id}: {e}")
