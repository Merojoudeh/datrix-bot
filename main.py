from telegram.ext import Application, CommandHandler
import os
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration - Fixed values
BOT_TOKEN = '7803291138:AAExEBQq9uZhq6X_ncI_c8E2J80-tpZtq8E'
ADMIN_CHAT_ID = '811896458'
STORAGE_CHANNEL_ID = '-1002807912676'

# File storage
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
    """Welcome message"""
    try:
        message = """🤖 **DATRIX File Server**

📋 **Available Commands:**
• `/datrix_app` - Download DATRIX Application
• `/list_files` - Show available files  
• `/status` - Check bot status
• `/help` - Show this help

🌐 **Running 24/7 on Cloud Server**
⚡ **Instant Downloads via Channel Forwarding**
📁 **Support for Large Files (100MB+)**

💡 **How it works:** Files are stored in our cloud channel and forwarded instantly to you!"""
        
        await update.message.reply_text(message, parse_mode='Markdown')
        logger.info(f"✅ /start command used by {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"❌ Error in start command: {e}")
        await update.message.reply_text("❌ Sorry, there was an error. Please try again.")

async def list_files(update, context):
    """List available files"""
    try:
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
        logger.info(f"✅ /list_files command used by {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"❌ Error in list_files command: {e}")
        await update.message.reply_text("❌ Sorry, there was an error. Please try again.")

async def get_datrix_app(update, context):
    """Download DATRIX app"""
    try:
        file_info = STORED_FILES['datrix_app']
        
        if not file_info['message_id']:
            await update.message.reply_text(
                "❌ **DATRIX App Not Available**\n\n"
                "The file hasn't been uploaded yet. Please contact the administrator.\n\n"
                "📧 Admin: Contact for file access",
                parse_mode='Markdown'
            )
            logger.warning(f"❌ File request but not available - User: {update.effective_user.id}")
            return
        
        # Forward directly from storage channel for INSTANT delivery
        await context.bot.forward_message(
            chat_id=update.effective_chat.id,
            from_chat_id=STORAGE_CHANNEL_ID,
            message_id=file_info['message_id']
        )
        
        # Send confirmation message
        await update.message.reply_text(
            f"✅ **{file_info['description']} Delivered!**\n\n"
            f"🔢 **Version:** {file_info['version']}\n"
            f"💾 **Size:** {file_info['size']}\n"
            f"⚡ **Delivery:** Instant forwarding from cloud storage\n"
            f"📅 **Last Updated:** {file_info['upload_date'] or 'Recently'}\n\n"
            f"🚀 **Enjoy using DATRIX!**",
            parse_mode='Markdown'
        )
        
        logger.info(f"✅ DATRIX app delivered to user {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"❌ Error delivering file to {update.effective_user.id}: {e}")
        await update.message.reply_text(
            "❌ **Download Error**\n\nSorry, there was an error delivering the file. Please try again or contact support.",
            parse_mode='Markdown'
        )

async def set_file_info(update, context):
    """Set file message ID and info (Admin only)"""
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ **Admin access required.**", parse_mode='Markdown')
        return
    
    if len(context.args) < 1:
        await update.message.reply_text(
            "📝 **Usage:** `/set_file [message_id] [version] [size]`\n\n"
            "**Example:** `/set_file 123 v2.1.7 125MB`\n\n"
            "This sets the message ID of the file in the storage channel for instant forwarding.",
            parse_mode='Markdown'
        )
        return
    
    try:
        message_id = int(context.args[0])
        version = context.args[1] if len(context.args) > 1 else STORED_FILES['datrix_app']['version']
        size = context.args[2] if len(context.args) > 2 else "Unknown"
        
        # Update file info
        STORED_FILES['datrix_app']['message_id'] = message_id
        STORED_FILES['datrix_app']['version'] = version
        STORED_FILES['datrix_app']['size'] = size
        STORED_FILES['datrix_app']['upload_date'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        await update.message.reply_text(
            f"✅ **File Information Updated!**\n\n"
            f"🆔 **Message ID:** `{message_id}`\n"
            f"🔢 **Version:** `{version}`\n"
            f"💾 **Size:** `{size}`\n"
            f"📁 **File:** {STORED_FILES['datrix_app']['filename']}\n"
            f"📅 **Updated:** {STORED_FILES['datrix_app']['upload_date']}\n\n"
            f"🚀 **File is now available for instant delivery!**\n"
            f"⚡ **Users can get it with:** `/datrix_app`",
            parse_mode='Markdown'
        )
        
        logger.info(f"✅ Admin updated file info: ID={message_id}, Version={version}")
        
    except ValueError:
        await update.message.reply_text("❌ **Error:** Message ID must be a number", parse_mode='Markdown')
    except Exception as e:
        logger.error(f"❌ Error in set_file_info: {e}")
        await update.message.reply_text(f"❌ **Error:** {str(e)}", parse_mode='Markdown')

async def status(update, context):
    """Bot status check"""
    try:
        uptime = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        file_info = STORED_FILES['datrix_app']
        file_status = "✅ Ready for instant delivery" if file_info['message_id'] else "❌ Not configured"
        
        status_msg = f"""🟢 **DATRIX Bot Status**

✅ **Status:** Online and Running
🌐 **Server:** Cloud Platform  
⏰ **Current Time:** `{uptime}`
🔄 **Auto-Restart:** Enabled
📊 **Files Available:** {len([f for f in STORED_FILES.values() if f['message_id']])}

📁 **DATRIX App Status:** {file_status}
🔢 **Version:** `{file_info['version']}`
💾 **Size:** `{file_info['size']}`
📅 **Last Updated:** {file_info['upload_date'] or 'Not set'}

⚡ **Delivery Method:** Channel Forwarding (Instant)
🚀 **Max File Size:** 2GB (Telegram limit)
🎯 **Performance:** Optimized for speed

👤 **Requested by:** {update.effective_user.first_name}
🆔 **User ID:** `{update.effective_user.id}`"""
        
        await update.message.reply_text(status_msg, parse_mode='Markdown')
        logger.info(f"✅ Status check by user {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"❌ Error in status command: {e}")
        await update.message.reply_text("❌ Sorry, there was an error. Please try again.")

async def help_command(update, context):
    """Show help based on user type"""
    try:
        user_id = str(update.effective_user.id)
        
        if user_id == ADMIN_CHAT_ID:
            help_text = """🔧 **Admin Commands:**

**File Management:**
• `/set_file [msg_id] [version] [size]` - Set file info for forwarding

**Monitoring:**
• `/status` - Detailed bot status
• `/list_files` - Show all files and status

**User Commands:**
• `/start` - Welcome message
• `/datrix_app` - Download DATRIX (forwarded instantly)
• `/help` - Show this help

**Setup Process:**
1. Upload large file to storage channel
2. Copy message ID from the uploaded file
3. Use `/set_file [message_id] [version] [size]`
4. File is now available for instant delivery!"""
        else:
            help_text = """🤖 **DATRIX Bot Help**

**Available Commands:**
• `/start` - Welcome message and bot info
• `/datrix_app` - Download DATRIX Application
• `/list_files` - Show available files
• `/status` - Check bot status
• `/help` - Show this help

**How to Download:**
1. Send `/datrix_app` command
2. File will be forwarded instantly
3. No waiting or upload delays!

**Features:**
• ⚡ Instant delivery via cloud forwarding
• 📁 Large file support (100MB+)
• 🌐 24/7 availability
• 🚀 Always latest version

**Need Support?**
Contact the administrator if you experience any issues."""
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
        logger.info(f"✅ Help requested by user {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"❌ Error in help command: {e}")
        await update.message.reply_text("❌ Sorry, there was an error. Please try again.")

def main():
    """Start the bot."""
    try:
        # Create application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Add command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("list_files", list_files))
        application.add_handler(CommandHandler("datrix_app", get_datrix_app))
        application.add_handler(CommandHandler("set_file", set_file_info))
        application.add_handler(CommandHandler("status", status))
        
        print("🚀 DATRIX Bot Starting...")
        print(f"🤖 Bot Token: {BOT_TOKEN[:10]}...")
        print(f"👤 Admin ID: {ADMIN_CHAT_ID}")
        print(f"📁 Storage Channel: {STORAGE_CHANNEL_ID}")
        print("⚡ Large file support: Up to 2GB")
        print("🚀 Instant forwarding: Enabled")
        print("📋 All handlers registered successfully")
        print("✅ Bot is ready and listening for messages!")
        
        # Start the bot
        application.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
        print(f"❌ Failed to start bot: {e}")

if __name__ == '__main__':
    main()
