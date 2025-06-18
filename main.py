from telegram.ext import Application, CommandHandler, MessageHandler, filters
import logging
import json
import os
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = '7803291138:AAExEBQq9uZhq6X_ncI_c8E2J80-tpZtq8E'
ADMIN_ID = '811896458'
CHANNEL_ID = '-1002807912676'

# User tracking
USERS_FILE = 'users.json'
users_data = {}

def load_users():
    global users_data
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                users_data = json.load(f)
    except:
        users_data = {}

def save_users():
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users_data, f)
    except:
        pass

def add_user(user):
    user_id = str(user.id)
    if user_id not in users_data:
        users_data[user_id] = {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'join_date': datetime.now().isoformat(),
            'last_active': datetime.now().isoformat(),
            'message_count': 0
        }
    else:
        users_data[user_id]['last_active'] = datetime.now().isoformat()
        users_data[user_id]['message_count'] += 1
    
    save_users()

FILES = {
    'datrix_app': {
        'message_id': None, 
        'version': 'v2.1.6', 
        'size': 'Not set',
        'description': 'DATRIX Accounting Application'
    }
}

async def start(update, context):
    add_user(update.effective_user)
    
    message = """🤖 **DATRIX File Server**

📋 **Available Commands:**
• `/datrix_app` - Download DATRIX Application
• `/list_files` - Show available files  
• `/status` - Check bot status
• `/help` - Show this help

🌐 **Running 24/7 on Railway Cloud**
⚡ **Instant Downloads via Channel Forwarding**
📁 **Support for Large Files (100MB+)**

💡 **Welcome to DATRIX! You'll receive automatic updates when new versions are available.**"""
    
    await update.message.reply_text(message, parse_mode='Markdown')
    logger.info(f"New user started bot: {update.effective_user.id}")

async def help_command(update, context):
    add_user(update.effective_user)
    user_id = str(update.effective_user.id)
    
    if user_id == ADMIN_ID:
        help_text = """🔧 **Admin Commands:**

• `/set_file [msg_id] [version] [size]` - Set file for forwarding
• `/broadcast [message]` - Send message to all users
• `/stats` - Show user statistics
• `/status` - Bot status
• `/list_files` - Show files
• `/help` - This help

**Example:** `/set_file 123 v2.1.7 125MB`
**Broadcast:** `/broadcast New version available!`"""
    else:
        help_text = """🤖 **DATRIX Bot Help**

• `/start` - Welcome message
• `/datrix_app` - Download DATRIX Application
• `/list_files` - Show available files
• `/status` - Check bot status
• `/help` - This help

**How to download:** Just send `/datrix_app` and get instant delivery!"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def list_files(update, context):
    add_user(update.effective_user)
    text = "📂 **Available Files:**\n\n"
    
    for key, info in FILES.items():
        if info['message_id']:
            status = "✅ Available for instant download"
            download_cmd = f"/{key}"
        else:
            status = "❌ Not uploaded yet"
            download_cmd = "Not available"
            
        text += f"📄 **{info['description']}**\n"
        text += f"🔢 Version: `{info['version']}`\n"
        text += f"💾 Size: `{info['size']}`\n"
        text += f"📊 Status: {status}\n"
        text += f"⌨️ Command: `{download_cmd}`\n\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def status(update, context):
    add_user(update.effective_user)
    uptime = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    file_info = FILES['datrix_app']
    file_status = "✅ Ready" if file_info['message_id'] else "❌ Not configured"
    
    status_msg = f"""🟢 **DATRIX Bot Status**

✅ **Status:** Online and Running
🌐 **Server:** Railway Cloud Platform  
⏰ **Time:** `{uptime}`
📁 **DATRIX App:** {file_status}
🔢 **Version:** `{file_info['version']}`
💾 **Size:** `{file_info['size']}`
⚡ **Delivery:** Channel Forwarding (Instant)

👤 **User:** {update.effective_user.first_name}
🆔 **User ID:** `{update.effective_user.id}`"""
    
    await update.message.reply_text(status_msg, parse_mode='Markdown')

async def get_datrix_app(update, context):
    add_user(update.effective_user)
    file_info = FILES['datrix_app']
    
    if not file_info['message_id']:
        await update.message.reply_text(
            "❌ **DATRIX App Not Available**\n\n"
            "The file hasn't been uploaded yet. Please contact the administrator.",
            parse_mode='Markdown'
        )
        return
    
    try:
        await context.bot.forward_message(
            chat_id=update.effective_chat.id,
            from_chat_id=CHANNEL_ID,
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
        logger.info(f"File delivered to user {update.effective_user.id}")
        
    except Exception as e:
        await update.message.reply_text(
            "❌ **Download Error**\n\nSorry, there was an error delivering the file. Please try again.",
            parse_mode='Markdown'
        )
        logger.error(f"Error delivering file: {e}")

async def set_file(update, context):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ **Admin access required.**", parse_mode='Markdown')
        return
    
    if not context.args:
        await update.message.reply_text(
            "📝 **Usage:** `/set_file [message_id] [version] [size]`\n\n"
            "**Example:** `/set_file 123 v2.1.7 125MB`",
            parse_mode='Markdown'
        )
        return
    
    try:
        message_id = int(context.args[0])
        version = context.args[1] if len(context.args) > 1 else FILES['datrix_app']['version']
        size = context.args[2] if len(context.args) > 2 else "Unknown"
        
        FILES['datrix_app']['message_id'] = message_id
        FILES['datrix_app']['version'] = version
        FILES['datrix_app']['size'] = size
        
        await update.message.reply_text(
            f"✅ **File Information Updated!**\n\n"
            f"🆔 **Message ID:** `{message_id}`\n"
            f"🔢 **Version:** `{version}`\n"
            f"💾 **Size:** `{size}`\n\n"
            f"🚀 **File is now available for instant delivery!**\n"
            f"⚡ **Users can get it with:** `/datrix_app`",
            parse_mode='Markdown'
        )
        logger.info(f"Admin updated file: ID={message_id}, Version={version}")
        
    except ValueError:
        await update.message.reply_text("❌ **Error:** Message ID must be a number", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ **Error:** {str(e)}", parse_mode='Markdown')

async def broadcast(update, context):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ **Admin access required.**", parse_mode='Markdown')
        return
    
    if not context.args:
        await update.message.reply_text(
            "📝 **Usage:** `/broadcast [message]`\n\n"
            "**Example:** `/broadcast New DATRIX version v2.1.8 is available!`",
            parse_mode='Markdown'
        )
        return
    
    message = ' '.join(context.args)
    sent_count = 0
    failed_count = 0
    
    load_users()
    
    await update.message.reply_text("📡 **Starting broadcast...**", parse_mode='Markdown')
    
    for user_id_str, user_info in users_data.items():
        try:
            await context.bot.send_message(
                chat_id=int(user_id_str),
                text=f"📢 **DATRIX Broadcast Message**\n\n{message}",
                parse_mode='Markdown'
            )
            sent_count += 1
        except:
            failed_count += 1
    
    await update.message.reply_text(
        f"✅ **Broadcast Complete!**\n\n"
        f"📤 **Sent:** {sent_count} messages\n"
        f"❌ **Failed:** {failed_count} messages\n"
        f"👥 **Total Users:** {len(users_data)}",
        parse_mode='Markdown'
    )

async def stats(update, context):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ **Admin access required.**", parse_mode='Markdown')
        return
    
    load_users()
    
    total_users = len(users_data)
    total_messages = sum(user['message_count'] for user in users_data.values())
    
    # Recent users (last 24 hours)
    recent_users = 0
    now = datetime.now()
    for user in users_data.values():
        try:
            last_active = datetime.fromisoformat(user['last_active'])
            if (now - last_active).days < 1:
                recent_users += 1
        except:
            pass
    
    stats_msg = f"""📊 **Bot Statistics**

👥 **Total Users:** {total_users}
💬 **Total Messages:** {total_messages}
🕐 **Active (24h):** {recent_users}
📁 **File Status:** {"✅ Ready" if FILES['datrix_app']['message_id'] else "❌ Not set"}
🔢 **Current Version:** {FILES['datrix_app']['version']}

📈 **Usage:** {total_messages/max(total_users, 1):.1f} messages per user"""
    
    await update.message.reply_text(stats_msg, parse_mode='Markdown')

def main():
    load_users()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("list_files", list_files))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("datrix_app", get_datrix_app))
    app.add_handler(CommandHandler("set_file", set_file))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("stats", stats))
    
    print("🚀 DATRIX Bot Starting...")
    print(f"🤖 Bot Token: {BOT_TOKEN[:10]}...")
    print(f"👤 Admin ID: {ADMIN_ID}")
    print(f"📁 Channel ID: {CHANNEL_ID}")
    print("📊 User tracking enabled")
    print("📡 Broadcast system ready")
    print("✅ Bot is ready and listening for messages!")
    
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
