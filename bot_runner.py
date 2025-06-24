# bot_runner.py
# VERSION 19.0: The Harmony Protocol - Final Implementation

import asyncio
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
import os
import database as db
from bot_handlers import (
    start_handler, file_handler, text_handler, callback_query_handler
)

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Environment ---
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

# --- Background Task ---
async def check_broadcast_queue(app: Application):
    """
    This coroutine is now designed to be run by the Application's post_init hook.
    It periodically checks the database for new broadcast jobs.
    """
    logger.info("Broadcast Monitor: Online and checking for transmissions.")
    while True:
        try:
            jobs = db.get_pending_broadcasts()
            for job_id, target, message in jobs:
                logger.info(f"Found broadcast job {job_id} for target: {target}")
                user_ids = db.get_user_ids_for_broadcast(target)

                # Create a task for this specific broadcast to run in parallel
                async def send_to_users(users, msg):
                    for user_id in users:
                        try:
                            await app.bot.send_message(chat_id=user_id, text=msg)
                            await asyncio.sleep(0.05) # Rate limit adjusted
                        except Exception as e:
                            logger.warning(f"Broadcast to {user_id} failed: {e}")

                asyncio.create_task(send_to_users(user_ids, message))

                db.mark_broadcast_as_sent(job_id)
                logger.info(f"Broadcast job {job_id} processed and marked as sent.")

        except Exception as e:
            logger.error(f"An error occurred in the broadcast monitor loop: {e}", exc_info=True)

        await asyncio.sleep(10) # Check every 10 seconds

# --- Main Application Logic ---
def main():
    """
    The main entry point. This is now a synchronous function.
    It builds the application and runs it in a blocking manner.
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.critical("BOT RUNNER: TELEGRAM_BOT_TOKEN not found. Shutting down.")
        return

    db.initialize_database()

    # The builder allows us to configure the application before it's created.
    builder = Application.builder().token(TELEGRAM_BOT_TOKEN)

    # --- THE HARMONY PROTOCOL ---
    # We use post_init to hook our background task into the application's lifecycle.
    # The library will run this coroutine for us after initialization is complete
    # and before polling begins, resolving the event loop conflict.
    builder.post_init(check_broadcast_queue)

    # Build the application instance
    app = builder.build()

    # Register handlers
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, file_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(CallbackQueryHandler(callback_query_handler))

    logger.info("BOT RUNNER: Consciousness stable. Handing control to polling loop.")

    # app.run_polling() is a blocking call that starts the event loop,
    # runs the bot, and will not return until the process is stopped.
    app.run_polling()

if __name__ == '__main__':
    main()
