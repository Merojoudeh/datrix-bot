from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import logging
import json
import os
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = '7803291138:AAExEBQq9uZhq6X_ncI_c8E2J80-tpZtq8E'
ADMIN_ID = '811896458'
CHANNEL_ID = '-1002807912676'

# Bot settings
BOT_SETTINGS = {
    'admin_username': 'Datrix_syr',
    'bot_name': 'DATRIX File Server',
    'welcome_message': 'Welcome to DATRIX! Get the latest accounting software instantly.'
}

# User tracking
USERS_FILE = 'users.json'
SETTINGS_FILE = 'settings.json'
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

def load_settings():
    global BOT_SETTINGS
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                saved_settings = json.load(f)
                BOT_SETTINGS.update(saved_settings)
    except:
        pass

def save_settings():
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(BOT_SETTINGS, f)
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
        logger.info(f"New user added: {user.id} ({user.first_name})")
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

def create_main_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("📥 Download DATRIX", callback_data="download_datrix"),
            InlineKeyboardButton("📋 Available Files", callback_data="list_files")
        ],
        [
            InlineKeyboardButton("📊 Bot Status", callback_data="bot_status"),
            InlineKeyboardButton("❓ Help", callback_data="help")
        ],
        [
            InlineKeyboardButton("📞 Contact Admin", callback_data="contact_admin")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_admin_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("📥 Download DATRIX", callback_data="download_datrix"),
            InlineKeyboardButton("📋 Available Files", callback_data="list_files")
        ],
        [
            InlineKeyboardButton("📊 Bot Status", callback_data="bot_status"),
            InlineKeyboardButton("📈 User Stats", callback_data="admin_stats")
        ],
        [
            InlineKeyboardButton("⚙️ Admin Help", callback_data="admin_help"),
            InlineKeyboardButton("📞 Contact Info", callback_data="contact_admin")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update, context):
    add_user(update.effective_user)
    user_id = str(update.effective_user.id)
    
    welcome_msg = f"🤖 **{BOT_SETTINGS['bot_name']}**\n\n"
    welcome_msg += f"👋 Hello {update.effective_user.first_name}!\n\n"
    welcome_msg += f"{BOT_SETTINGS['welcome_message']}\n\n"
    welcome_msg += "🎯 **Choose an option below:**"
    
    keyboard = create_admin_keyboard() if user_id == ADMIN_ID else create_main_keyboard()
    
    await update.message.reply_text(
        welcome_msg, 
        parse_mode='Markdown',
        reply_markup=keyboard
    )

async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    
    add_user(query.from_user)
    user_id = str(query.from_user.id)
    
    if query.data == "download_datrix":
        await handle_download(query, context)
    elif query.data == "list_files":
        await handle_list_files(query, context)
    elif query.data == "bot_status":
        await handle_status(query, context)
    elif query.data == "help":
        await handle_help(query, context)
    elif query.data == "admin_help":
        await handle_admin_help(query, context)
    elif query.data == "admin_stats":
        await handle_admin_stats(query, context)
    elif query.data == "contact_admin":
        await handle_contact_admin(query, context)

async def handle_download(query, context):
    file_info = FILES['datrix_app']
    
    if not file_info['message_id']:
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
        await query.edit_message_text(
            "❌ **File Currently Unavailable**\n\n"
            f"📧 Please contact @{BOT_SETTINGS['admin_username']} for assistance.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    try:
        await context.bot.forward_message(
            chat_id=query.message.chat_id,
            from_chat_id=CHANNEL_ID,
            message_id=file_info['message_id']
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
        
        await query.edit_message_text(
            f"✅ **{file_info['description']} Delivered!**\n\n"
            f"🔢 **Version:** {file_info['version']}\n"
            f"💾 **Size:** {file_info['size']}\n"
            f"⚡ **Status:** Delivered instantly\n\n"
            f"🚀 **Enjoy using DATRIX!**",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        logger.info(f"File delivered to user {query.from_user.id}")
        
    except Exception as e:
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
        await query.edit_message_text(
            "❌ **Download Error**\n\n"
            "Sorry, there was an error. Please try again or contact support.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        logger.error(f"Error delivering file: {e}")

async def handle_list_files(query, context):
    text = "📂 **Available Files:**\n\n"
    
    for key, info in FILES.items():
        if info['message_id']:
            status = "✅ Available"
        else:
            status = "❌ Not available"
            
        text += f"📄 **{info['description']}**\n"
        text += f"🔢 Version: `{info['version']}`\n"
        text += f"💾 Size: `{info['size']}`\n"
        text += f"📊 Status: {status}\n\n"
    
    keyboard = [
        [InlineKeyboardButton("📥 Download DATRIX", callback_data="download_datrix")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]
    ]
    
    await query.edit_message_text(
        text, 
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_status(query, context):
    uptime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_info = FILES['datrix_app']
    file_status = "✅ Available" if file_info['message_id'] else "❌ Not configured"
    
    status_msg = f"🟢 **System Status**\n\n"
    status_msg += f"✅ **Status:** Online and Running\n"
    status_msg += f"🌐 **Server:** Cloud Platform\n"
    status_msg += f"⏰ **Time:** `{uptime}`\n"
    status_msg += f"📁 **DATRIX App:** {file_status}\n"
    status_msg += f"🔢 **Version:** `{file_info['version']}`\n"
    status_msg += f"💾 **Size:** `{file_info['size']}`\n\n"
    status_msg += f"👤 **User:** {query.from_user.first_name}"
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
    
    await query.edit_message_text(
        status_msg, 
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_help(query, context):
    help_text = f"🤖 **{BOT_SETTINGS['bot_name']} Help**\n\n"
    help_text += "**Available Options:**\n"
    help_text += "📥 **Download DATRIX** - Get the latest version instantly\n"
    help_text += "📋 **Available Files** - See what's available for download\n"
    help_text += "📊 **Bot Status** - Check system status\n"
    help_text += f"📞 **Contact Admin** - Get help from @{BOT_SETTINGS['admin_username']}\n\n"
    help_text += "🎯 **How to use:** Simply click the buttons to navigate!\n\n"
    help_text += "💡 **Tip:** You'll receive automatic updates when new versions are available."
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
    
    await query.edit_message_text(
        help_text, 
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_admin_help(query, context):
    help_text = f"🔧 **Admin Commands:**\n\n"
    help_text += "**Text Commands:**\n"
    help_text += "`/set_file [msg_id] [version] [size]` - Set file for forwarding\n"
    help_text += "`/broadcast [message]` - Send message to all users\n"
    help_text += "`/stats` - Show detailed user statistics\n"
    help_text += "`/update_admin [username]` - Update admin username\n\n"
    help_text += "**Examples:**\n"
    help_text += "`/set_file 123 v2.1.7 125MB`\n"
    help_text += "`/broadcast New version available!`\n"
    help_text += "`/update_admin Datrix_syr`"
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
    
    await query.edit_message_text(
        help_text, 
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_admin_stats(query, context):
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
    
    stats_msg = f"📊 **Admin Statistics**\n\n"
    stats_msg += f"👥 **Total Users:** {total_users}\n"
    stats_msg += f"💬 **Total Messages:** {total_messages}\n"
    stats_msg += f"🕐 **Active (24h):** {recent_users}\n"
    stats_msg += f"📁 **File Status:** {"✅ Ready" if FILES['datrix_app']['message_id'] else "❌ Not set"}\n"
    stats_msg += f"🔢 **Current Version:** {FILES['datrix_app']['version']}\n\n"
    stats_msg += f"📈 **Avg Messages:** {total_messages/max(total_users, 1):.1f} per user"
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
    
    await query.edit_message_text(
        stats_msg, 
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_contact_admin(query, context):
    contact_msg = f"📞 **Contact Administrator**\n\n"
    contact_msg += f"👤 **Admin:** @{BOT_SETTINGS['admin_username']}\n\n"
    contact_msg += "📝 **For support with:**\n"
    contact_msg += "• Download issues\n"
    contact_msg += "• Technical problems\n"
    contact_msg += "• Feature requests\n"
    contact_msg += "• General questions\n\n"
    contact_msg += f"💬 **Click here to message:** @{BOT_SETTINGS['admin_username']}\n\n"
    contact_msg += "⏱️ **Response time:** Usually within 24 hours"
    
    keyboard = [
        [InlineKeyboardButton(f"💬 Message @{BOT_SETTINGS['admin_username']}", url=f"https://t.me/{BOT_SETTINGS['admin_username']}")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]
    ]
    
    await query.edit_message_text(
        contact_msg, 
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Handle back to menu
async def handle_back_to_menu(update, context):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        user_id = str(query.from_user.id)
        
        welcome_msg = f"🤖 **{BOT_SETTINGS['bot_name']}**\n\n"
        welcome_msg += f"👋 Welcome back, {query.from_user.first_name}!\n\n"
        welcome_msg += f"{BOT_SETTINGS['welcome_message']}\n\n"
        welcome_msg += "🎯 **Choose an option below:**"
        
        keyboard = create_admin_keyboard() if user_id == ADMIN_ID else create_main_keyboard()
        
        await query.edit_message_text(
            welcome_msg, 
            parse_mode='Markdown',
            reply_markup=keyboard
        )

# Register back to menu handler
async def callback_query_handler(update, context):
    query = update.callback_query
    
    if query.data == "back_to_menu":
        await handle_back_to_menu(update, context)
    else:
        await button_handler(update, context)

# Admin commands
async def set_file(update, context):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
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
            f"✅ **File Configuration Updated**\n\n"
            f"🆔 **Message ID:** `{message_id}`\n"
            f"🔢 **Version:** `{version}`\n"
            f"💾 **Size:** `{size}`\n\n"
            f"🚀 **File is now available for users!**",
            parse_mode='Markdown'
        )
        
        logger.info(f"Admin updated file: ID={message_id}, Version={version}")
        
    except ValueError:
        await update.message.reply_text("❌ **Error:** Message ID must be a number", parse_mode='Markdown')

async def broadcast(update, context):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        return
    
    if not context.args:
        await update.message.reply_text(
            "📝 **Usage:** `/broadcast [message]`\n\n"
            "**Example:** `/broadcast New DATRIX version available!`",
            parse_mode='Markdown'
        )
        return
    
    message = ' '.join(context.args)
    sent_count = 0
    failed_count = 0
    
    load_users()
    
    await update.message.reply_text("📡 **Sending broadcast...**", parse_mode='Markdown')
    
    broadcast_text = f"📢 **{BOT_SETTINGS['bot_name']} Update**\n\n{message}"
    keyboard = create_main_keyboard()
    
    for user_id_str, user_info in users_data.items():
        if user_id_str == ADMIN_ID:  # Skip admin
            continue
            
        try:
            await context.bot.send_message(
                chat_id=int(user_id_str),
                text=broadcast_text,
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            sent_count += 1
        except:
            failed_count += 1
    
    await update.message.reply_text(
        f"✅ **Broadcast Complete!**\n\n"
        f"📤 **Sent:** {sent_count} messages\n"
        f"❌ **Failed:** {failed_count} messages\n"
        f"👥 **Total Users:** {len(users_data) - 1}",  # -1 to exclude admin
        parse_mode='Markdown'
    )

async def stats(update, context):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        return
    
    load_users()
    
    total_users = len(users_data) - 1  # Exclude admin
    total_messages = sum(user['message_count'] for uid, user in users_data.items() if uid != ADMIN_ID)
    
    recent_users = 0
    now = datetime.now()
    for uid, user in users_data.items():
        if uid == ADMIN_ID:
            continue
        try:
            last_active = datetime.fromisoformat(user['last_active'])
            if (now - last_active).days < 1:
                recent_users += 1
        except:
            pass
    
    stats_msg = f"📊 **Detailed Statistics**\n\n"
    stats_msg += f"👥 **Total Users:** {total_users}\n"
    stats_msg += f"💬 **Total Messages:** {total_messages}\n"
    stats_msg += f"🕐 **Active (24h):** {recent_users}\n"
    stats_msg += f"📁 **File Status:** {"✅ Ready" if FILES['datrix_app']['message_id'] else "❌ Not set"}\n"
    stats_msg += f"🔢 **Current Version:** {FILES['datrix_app']['version']}\n"
    stats_msg += f"📈 **Usage:** {total_messages/max(total_users, 1):.1f} messages per user\n\n"
    stats_msg += f"🤖 **Admin:** @{BOT_SETTINGS['admin_username']}"
    
    await update.message.reply_text(stats_msg, parse_mode='Markdown')

async def update_admin(update, context):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        return
    
    if not context.args:
        await update.message.reply_text(
            f"📝 **Usage:** `/update_admin [username]`\n\n"
            f"**Current:** @{BOT_SETTINGS['admin_username']}\n"
            f"**Example:** `/update_admin Datrix_syr`",
            parse_mode='Markdown'
        )
        return
    
    new_username = context.args[0].replace('@', '')
    BOT_SETTINGS['admin_username'] = new_username
    save_settings()
    
    await update.message.reply_text(
        f"✅ **Admin Username Updated**\n\n"
        f"👤 **New Admin:** @{new_username}",
        parse_mode='Markdown'
    )

def main():
    load_users()
    load_settings()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("set_file", set_file))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("update_admin", update_admin))
    app.add_handler(CallbackQueryHandler(callback_query_handler))
    
    print("🚀 DATRIX Professional Bot Starting...")
    print(f"🤖 Bot Token: {BOT_TOKEN[:10]}...")
    print(f"👤 Admin ID: {ADMIN_ID}")
    print(f"📁 Channel ID: {CHANNEL_ID}")
    print(f"🔗 Admin Username: @{BOT_SETTINGS['admin_username']}")
    print("📊 User tracking enabled")
    print("📡 Broadcast system ready")
    print("⌨️ Inline keyboard interface active")
    print("✅ Bot is ready and listening for messages!")
    
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
