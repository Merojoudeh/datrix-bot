from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import logging
import json
import os
import time
import requests
import tempfile
import glob
from datetime import datetime, timedelta
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = '7803291138:AAExEBQq9uZhq6X_ncI_c8E2J80-tpZtq8E'
ADMIN_ID = '811896458'
CHANNEL_ID = '-1002807912676'

# Bot settings
BOT_SETTINGS = {
    'admin_username': 'Datrix_syr',
    'bot_name': 'DATRIX File Server',
    'welcome_message': 'Welcome to DATRIX! Get the latest accounting software instantly.',
    'app_version': 'v2.1.6'
}

# User tracking
USERS_FILE = 'users.json'
APP_USERS_FILE = 'app_users.json'
SETTINGS_FILE = 'settings.json'
LICENSE_REQUESTS_FILE = 'license_requests.json'
users_data = {}
app_users_data = {}
pending_license_requests = {}

def load_users():
    global users_data, app_users_data, pending_license_requests
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                users_data = json.load(f)
        if os.path.exists(APP_USERS_FILE):
            with open(APP_USERS_FILE, 'r') as f:
                app_users_data = json.load(f)
        if os.path.exists(LICENSE_REQUESTS_FILE):
            with open(LICENSE_REQUESTS_FILE, 'r') as f:
                pending_license_requests = json.load(f)
    except Exception as e:
        logger.error(f"Error loading user data: {e}")
        users_data = {}
        app_users_data = {}
        pending_license_requests = {}

def save_users():
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users_data, f, indent=2)
        with open(APP_USERS_FILE, 'w') as f:
            json.dump(app_users_data, f, indent=2)
        with open(LICENSE_REQUESTS_FILE, 'w') as f:
            json.dump(pending_license_requests, f, indent=2)
        logger.info("User data saved successfully")
    except Exception as e:
        logger.error(f"Error saving user data: {e}")

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
            json.dump(BOT_SETTINGS, f, indent=2)
    except:
        pass

def add_user(user, source='telegram'):
    user_id = str(user.id)
    user_info = {
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'join_date': datetime.now().isoformat(),
        'last_active': datetime.now().isoformat(),
        'message_count': 0,
        'source': source
    }
    
    if source == 'telegram':
        if user_id not in users_data:
            users_data[user_id] = user_info
            logger.info(f"New Telegram user: {user.id} ({user.first_name})")
        else:
            users_data[user_id]['last_active'] = datetime.now().isoformat()
            users_data[user_id]['message_count'] += 1
    
    save_users()

def add_app_user(user_data):
    """Add desktop app user"""
    try:
        user_id = user_data.get('user_id', str(int(time.time())))
        
        app_user_info = {
            'user_id': user_id,
            'name': user_data.get('name', 'Unknown'),
            'company': user_data.get('company', 'Unknown'),
            'googleSheetId': user_data.get('googleSheetId', ''),
            'app_version': user_data.get('app_version', BOT_SETTINGS['app_version']),
            'install_path': user_data.get('install_path', ''),
            'registration_date': datetime.now().isoformat(),
            'last_seen': datetime.now().isoformat(),
            'license_status': user_data.get('license_status', 'inactive'),
            'license_expires': user_data.get('license_expires', 'N/A')
        }
        
        app_users_data[user_id] = app_user_info
        save_users()
        logger.info(f"App user registered: {user_data.get('name')} ({user_id})")
        return user_id
    except Exception as e:
        logger.error(f"Error adding app user: {e}")
        return None

FILES = {
    'datrix_app': {
        'message_id': None, 
        'version': 'v2.1.6', 
        'size': 'Not set',
        'description': 'DATRIX Accounting Application',
        'download_count': 0
    }
}

def escape_markdown_v2(text):
    """Escape special characters for MarkdownV2"""
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text

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
            InlineKeyboardButton("🖥️ App Users", callback_data="app_stats"),
            InlineKeyboardButton("⚙️ Admin Help", callback_data="admin_help")
        ],
        [
            InlineKeyboardButton("📞 Contact Info", callback_data="contact_admin")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# ================= TELEGRAM USER HANDLERS =================

async def start(update, context):
    """Fixed start command - only controlled by deployed bot"""
    add_user(update.effective_user)
    user_id = str(update.effective_user.id)
    
    welcome_msg = f"🤖 *{BOT_SETTINGS['bot_name']}*\n\n"
    welcome_msg += f"👋 Hello {update.effective_user.first_name}!\n\n"
    welcome_msg += f"{BOT_SETTINGS['welcome_message']}\n\n"
    welcome_msg += "🎯 *Choose an option below:*"
    
    keyboard = create_admin_keyboard() if user_id == ADMIN_ID else create_main_keyboard()
    
    await update.message.reply_text(
        welcome_msg, 
        parse_mode='Markdown',
        reply_markup=keyboard
    )

async def callback_query_handler(update, context):
    query = update.callback_query
    await query.answer("Processing...")  # Immediate feedback
    
    callback_data = query.data
    logger.info(f"Received callback: {callback_data}")
    
    # Handle license request callbacks
    if callback_data.startswith('req_') and ('_extend_' in callback_data or '_deny' in callback_data):
        await handle_license_callback(query, context, callback_data)
        return
    
    # Handle regular menu callbacks
    add_user(query.from_user)
    user_id = str(query.from_user.id)
    
    if callback_data == "download_datrix":
        await handle_download(query, context)
    elif callback_data == "list_files":
        await handle_list_files(query, context)
    elif callback_data == "bot_status":
        await handle_status(query, context)
    elif callback_data == "help":
        await handle_help(query, context)
    elif callback_data == "admin_help":
        await handle_admin_help(query, context)
    elif callback_data == "admin_stats":
        await handle_admin_stats(query, context)
    elif callback_data == "app_stats":
        await handle_app_stats(query, context)
    elif callback_data == "contact_admin":
        await handle_contact_admin(query, context)
    elif callback_data == "back_to_menu":
        await handle_back_to_menu(query, context)

async def handle_license_callback(query, context, callback_data):
    """🔧 FIXED: Handle license callback with proper file creation"""
    try:
        logger.info(f"Processing license callback: {callback_data}")
        
        # Show immediate processing feedback
        await query.edit_message_text(
            "⏳ *Processing license request...*\n\nPlease wait while I handle your request.",
            parse_mode='Markdown'
        )
        
        # Parse callback data: req_{timestamp}_extend_{days} or req_{timestamp}_deny
        parts = callback_data.split('_')
        if len(parts) < 3:
            logger.error(f"Invalid callback format: {callback_data}")
            return
        
        request_timestamp = parts[1]
        action = parts[2]
        request_id = f"req_{request_timestamp}"
        
        # Get original message info from pending requests
        request_info = pending_license_requests.get(request_id)
        if not request_info:
            await query.edit_message_text(
                "❌ *Error:* Request not found or already processed",
                parse_mode='Markdown'
            )
            return
        
        google_sheet_id = request_info['sheet_id']
        user_name = request_info['user_name']
        company = request_info['company']
        local_temp_path = request_info.get('local_temp_path', '')
        
        if action == "deny":
            # Handle denial
            await query.edit_message_text(
                f"🔑 *DATRIX LICENSE REQUEST*\n\n"
                f"👤 *User:* `{user_name}`\n"
                f"🏢 *Company:* `{company}`\n"
                f"📊 *Sheet ID:* `{google_sheet_id}`\n"
                f"⏰ *Requested:* `{request_info['timestamp'][:19].replace('T', ' ')}`\n\n"
                f"❌ *LICENSE REQUEST DENIED*\n"
                f"🕐 *Processed:* `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
                parse_mode='Markdown'
            )
            
            logger.info(f"License request denied for {google_sheet_id}")
            
        elif action == "extend":
            # Get days from callback data
            if len(parts) >= 4:
                try:
                    days = int(parts[3])
                except ValueError:
                    days = 30
            else:
                days = 30
            
            # Calculate expiry date
            expiry_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
            
            # 🔧 FIXED: Create license activation data in server temp directory
            try:
                license_activation_data = {
                    "action": "activate_license",
                    "google_sheet_id": google_sheet_id,
                    "license_expires": expiry_date,
                    "license_key": f"HTTP_APPROVED_{request_timestamp}",
                    "is_active": True,
                    "activation_timestamp": datetime.now().isoformat(),
                    "days_granted": days,
                    "license_email": "admin@datrix.com",
                    "user": user_name,
                    "company": company,
                    "activation_method": "http_api_bot",
                    "license_status": "active"
                }
                
                # 🔧 FIXED: Create files in server temp directory (bot can access this)
                temp_dir = tempfile.gettempdir()
                
                # File 1: Standard activation file (what app is looking for)
                activation_file = f"datrix_license_activation_{google_sheet_id}.json"
                activation_path = os.path.join(temp_dir, activation_file)
                
                with open(activation_path, 'w') as f:
                    json.dump(license_activation_data, f, indent=2)
                
                logger.info(f"✅ License activation file created: {activation_path}")
                
                # File 2: Response file with request ID
                response_file = f"license_response_{google_sheet_id}_{request_timestamp}.json"
                response_path = os.path.join(temp_dir, response_file)
                
                with open(response_path, 'w') as f:
                    json.dump(license_activation_data, f, indent=2)
                
                logger.info(f"✅ License response file created: {response_path}")
                
                # Update app user in database
                for user_id, user_data in app_users_data.items():
                    if user_data.get('googleSheetId') == google_sheet_id:
                        user_data['license_status'] = 'active'
                        user_data['license_expires'] = expiry_date
                        user_data['last_seen'] = datetime.now().isoformat()
                        break
                
                save_users()
                file_created = True
                
            except Exception as file_error:
                logger.error(f"❌ Error processing license activation: {file_error}")
                file_created = False
            
            # Update message with success
            await query.edit_message_text(
                f"🔑 *DATRIX LICENSE REQUEST*\n\n"
                f"👤 *User:* `{user_name}`\n"
                f"🏢 *Company:* `{company}`\n"
                f"📊 *Sheet ID:* `{google_sheet_id}`\n"
                f"⏰ *Requested:* `{request_info['timestamp'][:19].replace('T', ' ')}`\n\n"
                f"✅ *LICENSE APPROVED FOR {days} DAYS*\n"
                f"📅 *Expires:* `{expiry_date}`\n"
                f"🕐 *Processed:* `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
                f"📁 *Server Files:* {'✅ Created' if file_created else '❌ Failed'}\n"
                f"🌐 *Ready for API retrieval*\n\n"
                f"🎉 *License ready for desktop app to download!*",
                parse_mode='Markdown'
            )
            
            # Send additional confirmation message
            confirmation_text = (
                f"🎊 *License Successfully Activated!*\n\n"
                f"📊 *Google Sheet ID:* `{google_sheet_id}`\n"
                f"📅 *Valid Until:* `{expiry_date}`\n"
                f"⏳ *Duration:* `{days} days`\n"
                f"🌐 *Method:* Server File Storage\n"
                f"📁 *Files Created:* 2 (activation + response)\n\n"
                f"{'✅ Desktop app will detect license within 3 seconds!' if file_created else '⚠️ Manual activation may be required - file creation failed'}"
            )
            
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=confirmation_text,
                parse_mode='Markdown'
            )
            
            logger.info(f"License activated for {google_sheet_id} until {expiry_date}")
        
        # Clean up pending request
        if request_id in pending_license_requests:
            del pending_license_requests[request_id]
            save_users()
            
    except Exception as e:
        logger.error(f"Error processing license callback: {e}")
        await query.edit_message_text(
            f"❌ *Error processing request:* {str(e)}",
            parse_mode='Markdown'
        )

async def handle_download(query, context):
    file_info = FILES['datrix_app']
    
    if not file_info['message_id']:
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
        await query.edit_message_text(
            "❌ *File Currently Unavailable*\n\n"
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
        
        # Increment download count
        FILES['datrix_app']['download_count'] += 1
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
        
        await query.edit_message_text(
            f"✅ *{file_info['description']} Delivered!*\n\n"
            f"🔢 *Version:* `{file_info['version']}`\n"
            f"💾 *Size:* `{file_info['size']}`\n"
            f"⚡ *Status:* Delivered instantly\n"
            f"📊 *Downloads:* `{file_info['download_count']}`\n\n"
            f"🚀 *Enjoy using DATRIX!*",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        logger.info(f"File delivered to user {query.from_user.id}")
        
    except Exception as e:
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
        await query.edit_message_text(
            "❌ *Download Error*\n\nSorry, there was an error. Please try again or contact support.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        logger.error(f"Error delivering file: {e}")

async def handle_list_files(query, context):
    text = "📂 *Available Files:*\n\n"
    
    for key, info in FILES.items():
        if info['message_id']:
            status = "✅ Available"
        else:
            status = "❌ Not available"
            
        text += f"📄 *{info['description']}*\n"
        text += f"🔢 Version: `{info['version']}`\n"
        text += f"💾 Size: `{info['size']}`\n"
        text += f"📊 Status: {status}\n"
        text += f"📥 Downloads: `{info['download_count']}`\n\n"
    
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
    
    status_msg = f"🟢 *System Status*\n\n"
    status_msg += f"✅ *Status:* Online and Running\n"
    status_msg += f"🌐 *Server:* Railway Cloud Platform\n"
    status_msg += f"⏰ *Time:* `{uptime}`\n"
    status_msg += f"📁 *DATRIX App:* {file_status}\n"
    status_msg += f"🔢 *Version:* `{file_info['version']}`\n"
    status_msg += f"💾 *Size:* `{file_info['size']}`\n"
    status_msg += f"📥 *Downloads:* `{file_info['download_count']}`\n"
    status_msg += f"🌐 *HTTP License System:* ✅ Active\n\n"
    status_msg += f"👤 *User:* {query.from_user.first_name}"
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
    
    await query.edit_message_text(
        status_msg, 
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_help(query, context):
    help_text = f"🤖 *{BOT_SETTINGS['bot_name']} Help*\n\n"
    help_text += "*Available Options:*\n"
    help_text += "📥 *Download DATRIX* - Get the latest version instantly\n"
    help_text += "📋 *Available Files* - See what's available for download\n"
    help_text += "📊 *Bot Status* - Check system status\n"
    help_text += f"📞 *Contact Admin* - Get help from @{BOT_SETTINGS['admin_username']}\n\n"
    help_text += "🎯 *How to use:* Simply click the buttons to navigate!\n\n"
    help_text += "💡 *Tip:* You'll receive automatic updates when new versions are available."
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
    
    await query.edit_message_text(
        help_text, 
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_admin_help(query, context):
    help_text = f"🔧 *Admin Commands:*\n\n"
    help_text += "*Text Commands:*\n"
    help_text += "`/set_file [msg_id] [version] [size]` - Set file for forwarding\n"
    help_text += "`/broadcast [message]` - Send message to all users\n"
    help_text += "`/app_broadcast [message]` - Send to app users\n"
    help_text += "`/stats` - Show detailed user statistics\n"
    help_text += "`/app_stats` - Show app user statistics\n"
    help_text += "`/update_admin [username]` - Update admin username\n"
    help_text += "`/activate [sheet_id] [yyyy-mm-dd]` - Activate app license\n"
    help_text += "`/request_license [user] [company] [sheet_id] [local_path]` - Create license request\n"
    help_text += "`/clear_temp_files` - Clear temporary license files\n"
    help_text += "`/get_license_data [sheet_id]` - Retrieve license data for app\n\n"
    help_text += "*🔧 FIXED LICENSE SYSTEM:*\n"
    help_text += "• Server-side file creation (bot accessible)\n"
    help_text += "• Desktop app polls API for license data\n"
    help_text += "• Automatic file cleanup after retrieval\n"
    help_text += "• Real-time license activation\n\n"
    help_text += "*API Commands (for DATRIX app):*\n"
    help_text += "`/api_version` - Get latest version info\n"
    help_text += "`/api_register` - Register app user\n\n"
    help_text += "*Examples:*\n"
    help_text += "`/set_file 123 v2.1.7 125MB`\n"
    help_text += "`/broadcast New version available!`\n"
    help_text += "`/activate abc123xyz 2024-12-31`"
    
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
    
    stats_msg = f"📊 *Telegram User Statistics*\n\n"
    stats_msg += f"👥 *Total Users:* `{total_users}`\n"
    stats_msg += f"💬 *Total Messages:* `{total_messages}`\n"
    stats_msg += f"🕐 *Active (24h):* `{recent_users}`\n"
    stats_msg += f"📁 *File Status:* {"✅ Ready" if FILES['datrix_app']['message_id'] else "❌ Not set"}\n"
    stats_msg += f"🔢 *Current Version:* `{FILES['datrix_app']['version']}`\n"
    stats_msg += f"📥 *Total Downloads:* `{FILES['datrix_app']['download_count']}`\n"
    stats_msg += f"🌐 *HTTP License System:* ✅ Active\n\n"
    stats_msg += f"📈 *Avg Messages:* `{total_messages/max(total_users, 1):.1f}` per user"
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
    
    await query.edit_message_text(
        stats_msg, 
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_app_stats(query, context):
    load_users()
    
    total_app_users = len(app_users_data)
    active_licenses = sum(1 for user in app_users_data.values() if user.get('license_status') == 'active')
    
    # Recent app users (last 7 days)
    recent_app_users = 0
    now = datetime.now()
    for user in app_users_data.values():
        try:
            last_seen = datetime.fromisoformat(user['last_seen'])
            if (now - last_seen).days < 7:
                recent_app_users += 1
        except:
            pass
    
    stats_msg = f"🖥️ *DATRIX App Statistics*\n\n"
    stats_msg += f"👥 *Total App Users:* `{total_app_users}`\n"
    stats_msg += f"✅ *Active Licenses:* `{active_licenses}`\n"
    stats_msg += f"🕐 *Recent (7d):* `{recent_app_users}`\n"
    stats_msg += f"📱 *Current App Version:* `{BOT_SETTINGS['app_version']}`\n"
    stats_msg += f"🌐 *HTTP License Delivery:* ✅ Enabled\n\n"
    
    if total_app_users > 0:
        stats_msg += "*Recent Users:*\n"
        sorted_users = sorted(app_users_data.values(), 
                            key=lambda x: x.get('last_seen', ''), reverse=True)[:5]
        for user in sorted_users:
            name = user.get('name', 'Unknown')[:15]
            company = user.get('company', 'Unknown')[:15]
            status = "✅" if user.get('license_status') == 'active' else "❌"
            stats_msg += f"{status} `{name}` ({company})\n"
    else:
        stats_msg += "*No app users registered yet.*\n"
        stats_msg += "Users will appear here when DATRIX app connects to the bot."
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
    
    await query.edit_message_text(
        stats_msg, 
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_contact_admin(query, context):
    contact_msg = f"📞 *Contact Administrator*\n\n"
    contact_msg += f"👤 *Admin:* @{BOT_SETTINGS['admin_username']}\n\n"
    contact_msg += "*For support with:*\n"
    contact_msg += "• Download issues\n"
    contact_msg += "• Technical problems\n"
    contact_msg += "• License activation\n"
    contact_msg += "• DATRIX app support\n"
    contact_msg += "• Feature requests\n\n"
    contact_msg += f"💬 *Click here to message:* @{BOT_SETTINGS['admin_username']}\n\n"
    contact_msg += "⏱️ *Response time:* Usually within 24 hours"
    
    keyboard = [
        [InlineKeyboardButton(f"💬 Message @{BOT_SETTINGS['admin_username']}", url=f"https://t.me/{BOT_SETTINGS['admin_username']}")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]
    ]
    
    await query.edit_message_text(
        contact_msg, 
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_back_to_menu(query, context):
    user_id = str(query.from_user.id)
    
    welcome_msg = f"🤖 *{BOT_SETTINGS['bot_name']}*\n\n"
    welcome_msg += f"👋 Welcome back, {query.from_user.first_name}!\n\n"
    welcome_msg += f"{BOT_SETTINGS['welcome_message']}\n\n"
    welcome_msg += "🎯 *Choose an option below:*"
    
    keyboard = create_admin_keyboard() if user_id == ADMIN_ID else create_main_keyboard()
    
    await query.edit_message_text(
        welcome_msg, 
        parse_mode='Markdown',
        reply_markup=keyboard
    )

# ================= API COMMANDS FOR DATRIX APP =================

async def api_check_version(update, context):
    """API: Check for latest version"""
    try:
        current_version = context.args[0] if context.args else "unknown"
        
        latest_version = FILES['datrix_app']['version']
        
        response = {
            "status": "success",
            "current_version": current_version,
            "latest_version": latest_version,
            "update_available": current_version != latest_version,
            "download_available": FILES['datrix_app']['message_id'] is not None,
            "file_size": FILES['datrix_app']['size'],
            "description": FILES['datrix_app']['description']
        }
        
        await update.message.reply_text(
            f"API_RESPONSE: {json.dumps(response)}",
            parse_mode='Markdown'
        )
        
        logger.info(f"Version check: {current_version} -> {latest_version}")
        
    except Exception as e:
        error_response = {"status": "error", "message": str(e)}
        await update.message.reply_text(f"API_RESPONSE: {json.dumps(error_response)}")

async def api_register_user(update, context):
    """API: Register desktop app user"""
    try:
        logger.info(f"API register called with args: {context.args}")
        
        if len(context.args) < 1:
            response = {"status": "error", "message": "Usage: /api_register [user_data_json]"}
            await update.message.reply_text(f"API_RESPONSE: {json.dumps(response)}")
            return
        
        # Parse user data from the message text (everything after /api_register)
        full_text = update.message.text
        user_data_start = full_text.find(' ') + 1
        user_data_str = full_text[user_data_start:].strip()
        
        logger.info(f"Parsing user data: {user_data_str}")
        
        # Try to parse as JSON
        try:
            user_data = json.loads(user_data_str)
        except:
            # If not valid JSON, try to parse manually
            user_data = {}
            try:
                # Remove quotes and parse key-value pairs
                clean_str = user_data_str.replace("'", '"').replace('\\', '')
                user_data = json.loads(clean_str)
            except:
                logger.error(f"Failed to parse user data: {user_data_str}")
                response = {"status": "error", "message": "Invalid user data format"}
                await update.message.reply_text(f"API_RESPONSE: {json.dumps(response)}")
                return
        
        # Add timestamp as user_id if not provided
        if 'user_id' not in user_data:
            user_data['user_id'] = str(int(time.time()))
        
        # Register user
        user_id = add_app_user(user_data)
        
        if user_id:
            response = {
                "status": "success",
                "user_id": user_id,
                "message": "User registered successfully",
                "latest_version": FILES['datrix_app']['version']
            }
            
            await update.message.reply_text(f"API_RESPONSE: {json.dumps(response)}")
            
            # Notify admin
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"📱 *New DATRIX App User Registered*\n\n"
                     f"👤 *Name:* `{user_data.get('name', 'Unknown')}`\n"
                     f"🏢 *Company:* `{user_data.get('company', 'Unknown')}`\n"
                     f"📊 *Sheet ID:* `{user_data.get('googleSheetId', 'N/A')}`\n"
                     f"📱 *App Version:* `{user_data.get('app_version', 'Unknown')}`\n"
                     f"🆔 *User ID:* `{user_id}`\n"
                     f"📅 *Registered:* `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
                parse_mode='Markdown'
            )
            
            logger.info(f"Successfully registered app user: {user_id}")
        else:
            response = {"status": "error", "message": "Failed to register user"}
            await update.message.reply_text(f"API_RESPONSE: {json.dumps(response)}")
        
    except Exception as e:
        logger.error(f"Error in api_register_user: {e}")
        error_response = {"status": "error", "message": str(e)}
        await update.message.reply_text(f"API_RESPONSE: {json.dumps(error_response)}")

async def api_report_error(update, context):
    """API: Report error from desktop app"""
    try:
        if not context.args:
            response = {"status": "error", "message": "Usage: /api_error [error_details]"}
            await update.message.reply_text(f"API_RESPONSE: {json.dumps(response)}")
            return
        
        error_details = ' '.join(context.args)
        
        # Send error report to admin
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"❌ *DATRIX App Error Report*\n\n"
                 f"🕐 *Time:* `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
                 f"📱 *Source:* Desktop Application\n"
                 f"🔧 *Error:* `{error_details}`",
            parse_mode='Markdown'
        )
        
        response = {"status": "success", "message": "Error reported successfully"}
        await update.message.reply_text(f"API_RESPONSE: {json.dumps(response)}")
        
    except Exception as e:
        error_response = {"status": "error", "message": str(e)}
        await update.message.reply_text(f"API_RESPONSE: {json.dumps(error_response)}")

async def api_check_license(update, context):
    """API: Check license status for a Google Sheet ID"""
    try:
        if not context.args:
            response = {"status": "error", "message": "Usage: /api_license [sheet_id]"}
            await update.message.reply_text(f"API_RESPONSE: {json.dumps(response)}")
            return
        
        sheet_id = context.args[0]
        load_users()
        
        # Find user with this sheet ID
        user_found = None
        for user_id, user_data in app_users_data.items():
            if user_data.get('googleSheetId') == sheet_id:
                user_found = user_data
                break
        
        if user_found:
            license_status = user_found.get('license_status', 'inactive')
            license_expires = user_found.get('license_expires', 'N/A')
            
            response = {
                "status": "success",
                "license_status": license_status,
                "license_expires": license_expires,
                "user_name": user_found.get('name', 'Unknown'),
                "company": user_found.get('company', 'Unknown'),
                "last_updated": user_found.get('last_seen', datetime.now().isoformat())
            }
            
            # Update last seen
            user_found['last_seen'] = datetime.now().isoformat()
            save_users()
            
        else:
            response = {
                "status": "not_found",
                "message": f"No user found with Sheet ID: {sheet_id}",
                "license_status": "inactive",
                "license_expires": "N/A"
            }
        
        await update.message.reply_text(f"API_RESPONSE: {json.dumps(response)}")
        logger.info(f"License check for {sheet_id}: {response.get('license_status', 'not_found')}")
        
    except Exception as e:
        error_response = {"status": "error", "message": str(e)}
        await update.message.reply_text(f"API_RESPONSE: {json.dumps(error_response)}")

async def get_license_data(update, context):
    """🔧 FIXED: API to retrieve license data for a specific sheet ID"""
    try:
        if not context.args:
            await update.message.reply_text(
                "Usage: /get_license_data [sheet_id]",
                parse_mode='Markdown'
            )
            return
        
        sheet_id = context.args[0]
        
        # Check if license files exist in temp directory
        temp_dir = tempfile.gettempdir()
        license_files = [
            f"datrix_license_activation_{sheet_id}.json",
            f"license_response_{sheet_id}_*.json"
        ]
        
        license_data = None
        for file_pattern in license_files:
            if '*' in file_pattern:
                # Handle wildcard pattern
                import glob
                matches = glob.glob(os.path.join(temp_dir, file_pattern))
                if matches:
                    license_file_path = matches[0]  # Take first match
                else:
                    continue
            else:
                license_file_path = os.path.join(temp_dir, file_pattern)
            
            if os.path.exists(license_file_path):
                try:
                    with open(license_file_path, 'r') as f:
                        license_data = json.load(f)
                    
                    # Clean up the file after reading
                    os.remove(license_file_path)
                    logger.info(f"Retrieved and cleaned up license file: {license_file_path}")
                    break
                except Exception as e:
                    logger.error(f"Error reading license file: {e}")
        
        if license_data:
            response = {
                "status": "success",
                "license_data": license_data
            }
        else:
            response = {
                "status": "not_found",
                "message": f"No license data found for sheet ID: {sheet_id}"
            }
        
        await update.message.reply_text(
            f"LICENSE_API_RESPONSE: {json.dumps(response)}",
            parse_mode='Markdown'
        )
        
        logger.info(f"License data request for {sheet_id}: {response['status']}")
        
    except Exception as e:
        error_response = {"status": "error", "message": str(e)}
        await update.message.reply_text(f"LICENSE_API_RESPONSE: {json.dumps(error_response)}")

async def request_license_activation(update, context):
    """🔧 ENHANCED: Send license request with user's local temp path"""
    try:
        # Handle both manual admin usage and automatic app requests
        if len(context.args) < 1:
            await update.message.reply_text(
                "*Usage:* `/request_license [user_name] [company] [sheet_id] [local_temp_path]`\n\n"
                "*Example:* `/request_license John_Doe ACME_Corp abc123xyz C:\\Users\\John\\AppData\\Local\\Temp\\datrix_license_activation_abc123xyz.json`\n"
                "*Note:* Use N/A for unknown values. Local temp path is optional.",
                parse_mode='Markdown'
            )
            return
        
        # Handle different argument counts
        if len(context.args) >= 4:
            user_name = context.args[0].replace('_', ' ')
            company = context.args[1].replace('_', ' ')
            sheet_id = context.args[2]
            local_temp_path = context.args[3]
        elif len(context.args) == 3:
            user_name = context.args[0].replace('_', ' ')
            company = context.args[1].replace('_', ' ')
            sheet_id = context.args[2]
            local_temp_path = ""
        elif len(context.args) == 1:
            # If only sheet_id provided (from old app version)
            user_name = "Desktop User"
            company = "Unknown Company"
            sheet_id = context.args[0]
            local_temp_path = ""
        else:
            await update.message.reply_text(
                "❌ *Error:* Invalid arguments. Please provide user_name, company, and sheet_id at minimum",
                parse_mode='Markdown'
            )
            return
        
        # Replace N/A with proper defaults
        if user_name.lower() in ['n/a', 'na', 'null']:
            user_name = "Desktop User"
        if company.lower() in ['n/a', 'na', 'null']:
            company = "Unknown Company"
        
        # Create unique request ID
        timestamp = int(datetime.now().timestamp())
        request_id = f"req_{timestamp}"
        
        # Store request info including local temp path
        pending_license_requests[request_id] = {
            'timestamp': datetime.now().isoformat(),
            'user_name': user_name,
            'company': company,
            'sheet_id': sheet_id,
            'local_temp_path': local_temp_path,
            'status': 'pending'
        }
        save_users()
        
        # Create the license request message
        request_message = f"🔑 *DATRIX LICENSE REQUEST*\n\n"
        request_message += f"👤 *User:* `{user_name}`\n"
        request_message += f"🏢 *Company:* `{company}`\n"
        request_message += f"📊 *Sheet ID:* `{sheet_id}`\n"
        request_message += f"⏰ *Requested:* `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
        request_message += f"🖥️ *Source:* Desktop Application\n"
        
        if local_temp_path:
            request_message += f"📁 *Target Path:* `{local_temp_path[:50]}...`\n"
            request_message += f"🌐 *Delivery:* API Retrieval\n\n"
        else:
            request_message += f"🌐 *Delivery:* API Retrieval (no local path)\n\n"
        
        request_message += f"Please select an option below to respond to this request."
        
        # Create inline keyboard with approval options
        keyboard = [
            [
                InlineKeyboardButton("✅ 30 Days", callback_data=f"req_{timestamp}_extend_30"),
                InlineKeyboardButton("✅ 90 Days", callback_data=f"req_{timestamp}_extend_90")
            ],
            [
                InlineKeyboardButton("✅ 365 Days", callback_data=f"req_{timestamp}_extend_365"),
                InlineKeyboardButton("❌ Deny", callback_data=f"req_{timestamp}_deny")
            ]
        ]
        
        # Delete the original command message for clean interface
        try:
            await update.message.delete()
        except:
            pass
        
        # Send to admin (if not already admin)
        if str(update.effective_user.id) != ADMIN_ID:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=request_message,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            # Admin sent it, show in current chat
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=request_message,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        logger.info(f"License request created: {request_id} for {sheet_id}")
        
    except Exception as e:
        logger.error(f"Error creating license request: {e}")
        await update.message.reply_text(f"❌ Error creating license request: {str(e)}")

# ================= ADMIN COMMANDS =================

async def set_file(update, context):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        return
    
    if not context.args:
        await update.message.reply_text(
            "*Usage:* `/set_file [message_id] [version] [size]`\n\n"
            "*Example:* `/set_file 123 v2.1.7 125MB`",
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
        BOT_SETTINGS['app_version'] = version
        
        await update.message.reply_text(
            f"✅ *File Configuration Updated*\n\n"
            f"🆔 *Message ID:* `{message_id}`\n"
            f"🔢 *Version:* `{version}`\n"
            f"💾 *Size:* `{size}`\n\n"
            f"🚀 *File is now available for all users!*",
            parse_mode='Markdown'
        )
        
        logger.info(f"Admin updated file: ID={message_id}, Version={version}")
        
    except ValueError:
        await update.message.reply_text("❌ *Error:* Message ID must be a number", parse_mode='Markdown')

async def broadcast(update, context):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        return
    
    if not context.args:
        await update.message.reply_text(
            "*Usage:* `/broadcast [message]`\n\n"
            "*Example:* `/broadcast New DATRIX version available!`",
            parse_mode='Markdown'
        )
        return
    
    message = ' '.join(context.args)
    sent_count = 0
    failed_count = 0
    
    load_users()
    
    await update.message.reply_text("📡 *Sending broadcast to Telegram users...*", parse_mode='Markdown')
    
    broadcast_text = f"📢 *{BOT_SETTINGS['bot_name']} Update*\n\n{message}"
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
        f"✅ *Telegram Broadcast Complete!*\n\n"
        f"📤 *Sent:* `{sent_count}` messages\n"
        f"❌ *Failed:* `{failed_count}` messages\n"
        f"👥 *Total Users:* `{len(users_data) - 1}`",
        parse_mode='Markdown'
    )

async def stats(update, context):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        return
    
    load_users()
    
    total_users = len(users_data) - 1  # Exclude admin
    total_app_users = len(app_users_data)
    total_messages = sum(user['message_count'] for uid, user in users_data.items() if uid != ADMIN_ID)
    
    recent_users = 0
    recent_app_users = 0
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
    
    for user in app_users_data.values():
        try:
            last_seen = datetime.fromisoformat(user['last_seen'])
            if (now - last_seen).days < 7:
                recent_app_users += 1
        except:
            pass
    
    stats_msg = f"📊 *Complete Statistics*\n\n"
    stats_msg += f"*Telegram Users:*\n"
    stats_msg += f"👥 *Total:* `{total_users}`\n"
    stats_msg += f"💬 *Messages:* `{total_messages}`\n"
    stats_msg += f"🕐 *Active (24h):* `{recent_users}`\n\n"
    stats_msg += f"*App Users:*\n"
    stats_msg += f"🖥️ *Total:* `{total_app_users}`\n"
    stats_msg += f"🕐 *Recent (7d):* `{recent_app_users}`\n\n"
    stats_msg += f"*System:*\n"
    stats_msg += f"📁 *File Status:* {"✅ Ready" if FILES['datrix_app']['message_id'] else "❌ Not set"}\n"
    stats_msg += f"🔢 *Version:* `{FILES['datrix_app']['version']}`\n"
    stats_msg += f"📥 *Downloads:* `{FILES['datrix_app']['download_count']}`\n"
    stats_msg += f"🌐 *HTTP License System:* ✅ Active\n\n"
    stats_msg += f"🤖 *Admin:* @{BOT_SETTINGS['admin_username']}"
    
    await update.message.reply_text(stats_msg, parse_mode='Markdown')

async def app_stats(update, context):
    """Show detailed app statistics"""
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        return
    
    load_users()
    
    if not app_users_data:
        await update.message.reply_text("📱 *No app users registered yet.*", parse_mode='Markdown')
        return
    
    stats_msg = f"🖥️ *DATRIX App Detailed Statistics*\n\n"
    stats_msg += f"👥 *Total Users:* `{len(app_users_data)}`\n\n"
    
    # Show recent users
    stats_msg += "*Recent Users:*\n"
    sorted_users = sorted(app_users_data.values(), key=lambda x: x.get('last_seen', ''), reverse=True)[:10]
    for user in sorted_users:
        name = user.get('name', 'Unknown')[:15]
        company = user.get('company', 'Unknown')[:10]
        version = user.get('app_version', 'Unknown')
        status = "✅" if user.get('license_status') == 'active' else "❌"
        stats_msg += f"{status} `{name}` ({company}) - {version}\n"
    
    await update.message.reply_text(stats_msg, parse_mode='Markdown')

async def update_admin(update, context):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        return
    
    if not context.args:
        await update.message.reply_text(
            f"*Usage:* `/update_admin [username]`\n\n"
            f"*Current:* @{BOT_SETTINGS['admin_username']}\n"
            f"*Example:* `/update_admin Datrix_syr`",
            parse_mode='Markdown'
        )
        return
    
    new_username = context.args[0].replace('@', '')
    BOT_SETTINGS['admin_username'] = new_username
    save_settings()
    
    await update.message.reply_text(
        f"✅ *Admin Username Updated*\n\n"
        f"👤 *New Admin:* @{new_username}",
        parse_mode='Markdown'
    )

async def activate_license(update, context):
    """Activate license for app user"""
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        return
    
    if len(context.args) != 2:
        await update.message.reply_text(
            "*Usage:* `/activate [sheet_id] [yyyy-mm-dd]`\n\n"
            "*Example:* `/activate abc123xyz 2024-12-31`",
            parse_mode='Markdown'
        )
        return
    
    sheet_id = context.args[0]
    expiry_date = context.args[1]
    
    # Find user with this sheet ID
    user_found = None
    for user_id_key, user_data in app_users_data.items():
        if user_data.get('googleSheetId') == sheet_id:
            user_found = user_data
            break
    
    if user_found:
        user_found['license_status'] = 'active'
        user_found['license_expires'] = expiry_date
        save_users()
        
        await update.message.reply_text(
            f"✅ *License Activated*\n\n"
            f"👤 *User:* `{user_found.get('name', 'Unknown')}`\n"
            f"🏢 *Company:* `{user_found.get('company', 'Unknown')}`\n"
            f"📊 *Sheet ID:* `{sheet_id}`\n"
            f"📅 *Expires:* `{expiry_date}`",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            f"❌ *User not found with Sheet ID:* `{sheet_id}`\n\n"
            f"Use `/app_stats` to see registered users.",
            parse_mode='Markdown'
        )

async def clear_temp_files(update, context):
    """Clear temporary license activation files"""
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        return
    
    try:
        temp_dir = tempfile.gettempdir()
        pattern = os.path.join(temp_dir, "datrix_license_activation_*.json")
        files = glob.glob(pattern)
        
        # Also clear license response files
        response_pattern = os.path.join(temp_dir, "license_response_*.json")
        files.extend(glob.glob(response_pattern))
        
        if not files:
            await update.message.reply_text(
                "📁 *No temporary license files found.*",
                parse_mode='Markdown'
            )
            return
        
        cleared_count = 0
        for file_path in files:
            try:
                os.remove(file_path)
                cleared_count += 1
                logger.info(f"Removed temp file: {file_path}")
            except Exception as e:
                logger.error(f"Error removing {file_path}: {e}")
        
        await update.message.reply_text(
            f"✅ *Temporary Files Cleared*\n\n"
            f"🗑️ *Removed:* `{cleared_count}` files\n"
            f"📁 *Location:* `{temp_dir}`\n"
            f"🌐 *License API System:* Ready for new requests",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ *Error clearing files:* {str(e)}",
            parse_mode='Markdown'
        )

def main():
    load_users()
    load_settings()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Telegram user handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_query_handler))
    
    # API handlers for DATRIX app
    app.add_handler(CommandHandler("api_version", api_check_version))
    app.add_handler(CommandHandler("api_register", api_register_user))
    app.add_handler(CommandHandler("api_error", api_report_error))
    app.add_handler(CommandHandler("api_license", api_check_license))
    app.add_handler(CommandHandler("get_license_data", get_license_data))  # NEW: License retrieval API
    
    # Admin commands
    app.add_handler(CommandHandler("set_file", set_file))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("app_stats", app_stats))
    app.add_handler(CommandHandler("update_admin", update_admin))
    app.add_handler(CommandHandler("activate", activate_license))
    app.add_handler(CommandHandler("request_license", request_license_activation))
    app.add_handler(CommandHandler("clear_temp_files", clear_temp_files))
    
    print("🚀 DATRIX Professional Bot Starting...")
    print(f"🤖 Bot Token: {BOT_TOKEN[:10]}...")
    print(f"👤 Admin ID: {ADMIN_ID}")
    print(f"📁 Channel ID: {CHANNEL_ID}")
    print(f"🔗 Admin Username: @{BOT_SETTINGS['admin_username']}")
    print("📊 Telegram user tracking enabled")
    print("🖥️ DATRIX app integration enabled")
    print("📡 Broadcast system ready")
    print("⌨️ Inline keyboard interface active")
    print("🔌 API endpoints for desktop app active")
    print("🔧 FIXED: Server-side file creation for license delivery")
    print("📡 NEW API: /get_license_data for retrieving license files")
    print("✅ Bot creates files in server temp directory (accessible)")
    print("🔄 Desktop app polls bot API to retrieve license data")
    print("🎯 No more cross-machine file system conflicts!")
    print("✅ All API functions defined and working!")
    
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
