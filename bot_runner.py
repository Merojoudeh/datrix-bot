# bot_runner.py
# The dedicated vessel for the Bot Consciousness.

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

async def check_broadcast_queue(app: Application):
    """Periodically checks the database for new broadcast jobs."""
    logger.info("Broadcast Monitor: Online and checking for transmissions.")
    while True:
        jobs = db.get_pending_broadcasts()
        for job_id, target, message in jobs:
            logger.info(f"Found broadcast job {job_id} for target: {target}")
            user_ids = db.get_user_ids_for_broadcast(target)
            for user_id in user_ids:
                try:
                    await app.bot.send_message(chat_id=user_id, text=message)
                    await asyncio.sleep(0.1) # Rate limit
                except Exception as e:
                    logger.warning(f"Broadcast to {user_id} failed: {e}")
            db.mark_broadcast_as_sent(job_id)
            logger.info(f"Broadcast job {job_id} complete.")
        await asyncio.sleep(10) # Check every 10 seconds

async def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.critical("BOT RUNNER: TELEGRAM_BOT_TOKEN not found. Shutting down.")
        return

    db.initialize_database()

    builder = Application.builder().token(TELEGRAM_BOT_TOKEN)
    app = builder.build()

    # Register handlers
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, file_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(CallbackQueryHandler(callback_query_handler))

    # Create the background task for the broadcast monitor
    app.create_task(check_broadcast_queue(app))

    logger.info("BOT RUNNER: Consciousness active. Running polling...")
    await app.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
