from telegram.ext import Application, CommandHandler
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = '7803291138:AAExEBQq9uZhq6X_ncI_c8E2J80-tpZtq8E'
ADMIN_CHAT_ID = '811896458'
STORAGE_CHANNEL_ID = '-1002807912676'

STORED_FILES = {
    'datrix_app': {
        'message_id': None,
        'description': 'DATRIX Accounting Application',
        'version': 'v2.1.6',
        'size': 'Not set',
        'filename': 'DATRIX_Setup.exe',
        'upload_date': None
    }
}

async def start(update, context):
    message = """🤖 **DATRIX File Server**

📋 **Available Commands:**
• `/datrix_app` - Download DATRIX Application
• `/list_files` - Show available files  
• `/status` - Check bot status
• `/help` - Show this help

🌐 **Running 24/7 on Cloud Server**
⚡ **Instant Downloads via Channel Forwarding**
📁 **Support for Large Files (100MB+)**"""
    
    await update.message.reply_text(message, parse_mode='Markdown')
    logger.info(f"Start command used by {update.effective_user.id}")

async def list_files(update, context):
    text = "📂 **Available Files:**\n\n"
    
    for key, info in STORED_FILES.items():
        if info['message_id']:
            status = "✅ Available for instant download"
            download_cmd = f"/{key}"
        else:
            status = "❌ Not uploaded yet"
            download_cmd = "Not available"
            
        text += f"📄 **{info['description']}**\n"
        text += f"🔢 Version: `{info['version']}`\n"
        text += f"💾 Size: `{info['size']}`\n"
        text += f"📁 File: `{info['filename']}`\n"
        text += f"📊 Status: {status}\n"
        text += f"⌨️ Command: `{download_cmd}`\n"
        if info['upload_date']:
            text += f"📅 Updated: {info['upload_date']}\n"
        text += "\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def get_datrix_app(update, context):
    file_info = STORED_FILES['datrix_app']
    
    if not file_info['message_id']:
        await update.message.reply_text(
            "❌ **DATRIX App Not Available**\n\n"
            "The file hasn't been uploaded yet. Please contact the administrator.",
            parse_mode='Markdown'
        )
        return
    
    await context.bot.forward_message(
        chat_id=update.effective_chat.id,
        from_chat_id=STORAGE_CHANNEL_ID,
        message_id=file_info['message_id']
    )
    
    await update.message.reply_text(
        f"✅ **{file_info['description']} Delivered!**\n\n"
        f"🔢 **Version:** {file_info['version']}\n"
        f"💾 **Size:** {file_info['size']}\n"
        f"⚡ **Delivery:** Instant forwarding from cloud storage\n\n"
        f"🚀 **Enjoy using DATRIX!**",
        parse_mode='Markdown'
    )

async def set_file_info(update, context):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ **Admin access required.**", parse_mode='Markdown')
        return
    
    if len(context.args) < 1:
        await update.message.reply_text(
            "📝 **Usage:** `/set_file [message_id] [version] [size]`\n\n"
            "**Example:** `/set_file 123 v2.1.7 125MB`",
            parse_mode='Markdown'
        )
        return
    
    try:
        message_id = int(context.args[0])
        version = context.args[1] if len(context.args) > 1 else STORED_FILES['datrix_app']['version']
        size = context.args[2] if len(context.args) > 2 else "Unknown"
        
        STORED_FILES['datrix_app']['message_id'] = message_id
        STORED_FILES['datrix_app']['version'] = version
        STORED_FILES['datrix_app']['size'] = size
        STORED_FILES['datrix_app']['upload_date'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        await update.message.reply_text(
            f"✅ **File Information Updated!**\n\n"
            f"🆔 **Message ID:** `{message_id}`\n"
            f"🔢 **Version:** `{version}`\n"
            f"💾 **Size:** `{size}`\n"
            f"📅 **Updated:** {STORED_FILES['datrix_app']['upload_date']}\n\n"
            f"🚀 **File is now available for instant delivery!**",
            parse_mode='Markdown'
        )
        
    except ValueError:
        await update.message.reply_text("❌ **Error:** Message ID must be a number", parse_mode='Markdown')

async def status(update, context):
    uptime = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    file_info = STORED_FILES['datrix_app']
    file_status = "✅ Ready" if file_info['message_id'] else "❌ Not configured"
    
    status_msg = f"""🟢 **DATRIX Bot Status**

✅ **Status:** Online and Running
🌐 **Server:** Cloud Platform  
⏰ **Time:** `{uptime}`
📁 **DATRIX App:** {file_status}
🔢 **Version:** `{file_info['version']}`
💾 **Size:** `{file_info['size']}`
⚡ **Delivery:** Channel Forwarding (Instant)

👤 **User:** {update.effective_user.first_name}"""
    
    await update.message.reply_text(status_msg, parse_mode='Markdown')

async def help_command(update, context):
    user_id = str(update.effective_user.id)
    
    if user_id == ADMIN_CHAT_ID:
        help_text = """🔧 **Admin Commands:**

• `/set_file [msg_id] [version] [size]` - Set file for forwarding
• `/status` - Bot status
• `/list_files` - Show files
• `/help` - This help"""
    else:
        help_text = """🤖 **DATRIX Bot Help**

• `/start` - Welcome message
• `/datrix_app` - Download DATRIX Application
• `/list_files` - Show available files
• `/status` - Check bot status
• `/help` - This help"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("list_files", list_files))
    application.add_handler(CommandHandler("datrix_app", get_datrix_app))
    application.add_handler(CommandHandler("set_file", set_file_info))
    application.add_handler(CommandHandler("status", status))
    
    print("🚀 DATRIX Bot Starting...")
    print(f"🤖 Bot Token: {BOT_TOKEN[:10]}...")
    print(f"👤 Admin ID: {ADMIN_CHAT_ID}")
    print("✅ Bot is ready and listening for messages!")
    
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
