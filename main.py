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
    await query.answer("Processing...")
    
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
        
        await query.edit_message_text(
            "⏳ *Processing license request...*\n\nPlease wait while I handle your request.",
            parse_mode='Markdown'
        )
        
        parts = callback_data.split('_')
        if len(parts) < 3:
            logger.error(f"Invalid callback format: {callback_data}")
            return
        
        request_timestamp = parts[1]
        action = parts[2]
        request_id = f"req_{request_timestamp}"
        
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
        
        if action == "deny":
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
            if len(parts) >= 4:
                try:
                    days = int(parts[3])
                except ValueError:
                    days = 30
            else:
                days = 30
            
            expiry_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
            
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
                
                temp_dir = tempfile.gettempdir()
                
                activation_file = f"datrix_license_activation_{google_sheet_id}.json"
                activation_path = os.path.join(temp_dir, activation_file)
                
                with open(activation_path, 'w') as f:
                    json.dump(license_activation_data, f, indent=2)
                
                logger.info(f"✅ License activation file created: {activation_path}")
                
                response_file = f"license_response_{google_sheet_id}_{request_timestamp}.json"
                response_path = os.path.join(temp_dir, response_file)
                
                with open(response_path, 'w') as f:
                    json.dump(license_activation_data, f, indent=2)
                
                logger.info(f"✅ License response file created: {response_path}")
                
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
                f"🎉 *License ready for desktop app!*",
                parse_mode='Markdown'
            )
            
            logger.info(f"License activated for {google_sheet_id} until {expiry_date}")
        
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
    status_msg += f"🌐 *License API:* ✅ Active\n\n"
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
    help_text += "`/stats` - Show detailed user statistics\n"
    help_text += "`/app_stats` - Show app user statistics\n"
    help_text += "`/activate [sheet_id] [yyyy-mm-dd]` - Activate app license\n"
    help_text += "`/clear_temp_files` - Clear temporary license files\n\n"
    help_text += "*🔧 PROFESSIONAL LICENSE SYSTEM:*\n"
    help_text += "• Silent API processing (no spam to admin)\n"
    help_text += "• Desktop app waits for admin approval\n"
    help_text += "• Automatic file cleanup after retrieval\n"
    help_text += "• Real-time license activation\n\n"
    help_text += "*API Commands (processed silently):*\n"
    help_text += "• API version checks\n"
    help_text += "• User registration\n"
    help_text += "• License data retrieval\n\n"
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
    stats_msg += f"🌐 *License API:* ✅ Active\n\n"
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
    stats_msg += f"🌐 *License API:* ✅ Enabled\n\n"
    
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

# ================= API COMMANDS FOR DATRIX APP (SILENT PROCESSING) =================

async def api_check_version(update, context):
    """🔧 FIXED: Silent API processing - no messages to admin"""
    try:
        await update.message.delete()
        
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
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"API_RESPONSE: {json.dumps(response)}"
        )
        
        logger.info(f"Silent version check: {current_version} -> {latest_version}")
        
    except Exception as e:
        error_response = {"status": "error", "message": str(e)}
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"API_RESPONSE: {json.dumps(error_response)}"
        )

async def api_register_user(update, context):
    """🔧 FIXED: Silent API processing for user registration"""
    try:
        await update.message.delete()
        
        if len(context.args) < 1:
            response = {"status": "error", "message": "Usage: /api_register [user_data_json]"}
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"API_RESPONSE: {json.dumps(response)}"
            )
            return
        
        full_text = update.message.text
        user_data_start = full_text.find(' ') + 1
        user_data_str = full_text[user_data_start:].strip()
        
        try:
            user_data = json.loads(user_data_str)
        except:
            try:
                clean_str = user_data_str.replace("'", '"').replace('\\', '')
                user_data = json.loads(clean_str)
            except:
                response = {"status": "error", "message": "Invalid user data format"}
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"API_RESPONSE: {json.dumps(response)}"
                )
                return
        
        if 'user_id' not in user_data:
            user_data['user_id'] = str(int(time.time()))
        
        user_id = add_app_user(user_data)
        
        if user_id:
            response = {
                "status": "success",
                "user_id": user_id,
                "message": "User registered successfully",
                "latest_version": FILES['datrix_app']['version']
            }
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"API_RESPONSE: {json.dumps(response)}"
            )
            
            logger.info(f"Silent user registration: {user_data.get('name')} ({user_id})")
        else:
            response = {"status": "error", "message": "Failed to register user"}
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"API_RESPONSE: {json.dumps(response)}"
            )
        
    except Exception as e:
        logger.error(f"Error in api_register_user: {e}")
        error_response = {"status": "error", "message": str(e)}
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"API_RESPONSE: {json.dumps(error_response)}"
        )

async def api_report_error(update, context):
    """🔧 FIXED: Silent API processing for error reporting"""
    try:
        await update.message.delete()
        
        if not context.args:
            response = {"status": "error", "message": "Usage: /api_error [error_details]"}
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"API_RESPONSE: {json.dumps(response)}"
            )
            return
        
        error_details = ' '.join(context.args)
        
        # Send error report to admin silently
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"❌ *DATRIX App Error Report*\n\n"
                 f"🕐 *Time:* `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
                 f"📱 *Source:* Desktop Application\n"
                 f"🔧 *Error:* `{error_details}`",
            parse_mode='Markdown'
        )
        
        response = {"status": "success", "message": "Error reported successfully"}
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"API_RESPONSE: {json.dumps(response)}"
        )
        
    except Exception as e:
        error_response = {"status": "error", "message": str(e)}
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"API_RESPONSE: {json.dumps(error_response)}"
        )

async def api_check_license(update, context):
    """🔧 FIXED: Silent API processing for license checking"""
    try:
        await update.message.delete()
        
        if not context.args:
            response = {"status": "error", "message": "Usage: /api_license [sheet_id]"}
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"API_RESPONSE: {json.dumps(response)}"
            )
            return
        
        sheet_id = context.args[0]
        load_users()
        
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
            
            user_found['last_seen'] = datetime.now().isoformat()
            save_users()
            
        else:
            response = {
                "status": "not_found",
                "message": f"No user found with Sheet ID: {sheet_id}",
                "license_status": "inactive",
                "license_expires": "N/A"
            }
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"API_RESPONSE: {json.dumps(response)}"
        )
        
        logger.info(f"Silent license check for {sheet_id}: {response.get('license_status', 'not_found')}")
        
    except Exception as e:
        error_response = {"status": "error", "message": str(e)}
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"API_RESPONSE: {json.dumps(error_response)}"
        )

async def get_license_data(update, context):
    """🔧 FIXED: Silent API processing - only respond with data, no admin notification"""
    try:
        await update.message.delete()
        
        if not context.args:
            error_response = {"status": "error", "message": "Usage: /get_license_data [sheet_id]"}
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"LICENSE_API_RESPONSE: {json.dumps(error_response)}"
            )
            return
        
        sheet_id = context.args[0]
        
        temp_dir = tempfile.gettempdir()
        license_files = [
            f"datrix_license_activation_{sheet_id}.json",
            f"license_response_{sheet_id}_*.json"
        ]
        
        license_data = None
        for file_pattern in license_files:
            if '*' in file_pattern:
                import glob
                matches = glob.glob(os.path.join(temp_dir, file_pattern))
                if matches:
                    license_file_path = matches[0]
                else:
                    continue
            else:
                license_file_path = os.path.join(temp_dir, file_pattern)
            
            if os.path.exists(license_file_path):
                try:
                    with open(license_file_path, 'r') as f:
                        license_data = json.load(f)
                    
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
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"LICENSE_API_RESPONSE: {json.dumps(response)}"
        )
        
        logger.info(f"Silent license data request for {sheet_id}: {response['status']}")
        
    except Exception as e:
        error_response = {"status": "error", "message": str(e)}
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"LICENSE_API_RESPONSE: {json.dumps(error_response)}"
        )

async def request_license_activation(update, context):
    """🔧 FIXED: Only show license request to admin, hide from chat"""
    try:
        if len(context.args) < 1:
            await update.message.reply_text(
                "*Usage:* `/request_license [user_name] [company] [sheet_id] [local_temp_path]`",
                parse_mode='Markdown'
            )
            return
        
        await update.message.delete()
        
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
            user_name = "Desktop User"
            company = "Unknown Company"
            sheet_id = context.args[0]
            local_temp_path = ""
        
        if user_name.lower() in ['n/a', 'na', 'null']:
            user_name = "Desktop User"
        if company.lower() in ['n/a', 'na', 'null']:
            company = "Unknown Company"
        
        timestamp = int(datetime.now().timestamp())
        request_id = f"req_{timestamp}"
        
        pending_license_requests[request_id] = {
            'timestamp': datetime.now().isoformat(),
            'user_name': user_name,
            'company': company,
            'sheet_id': sheet_id,
            'local_temp_path': local_temp_path,
            'status': 'pending'
        }
        save_users()
        
        request_message = f"🔑 *DATRIX LICENSE REQUEST*\n\n"
        request_message += f"👤 *User:* `{user_name}`\n"
        request_message += f"🏢 *Company:* `{company}`\n"
        request_message += f"📊 *Sheet ID:* `{sheet_id}`\n"
        request_message += f"⏰ *Requested:* `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
        request_message += f"🖥️ *Source:* Desktop Application\n\n"
        request_message += f"Please select an option below to respond to this request."
        
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
        
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=request_message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        logger.info(f"License request created: {request_id} for {sheet_id}")
        
    except Exception as e:
        logger.error(f"Error creating license request: {e}")

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
    
    await update.message.reply_text("📡 *Sending broadcast...*", parse_mode='Markdown')
    
    broadcast_text = f"📢 *{BOT_SETTINGS['bot_name']} Update*\n\n{message}"
    keyboard = create_main_keyboard()
    
    for user_id_str, user_info in users_data.items():
        if user_id_str == ADMIN_ID:
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
        f"✅ *Broadcast Complete!*\n\n"
        f"📤 *Sent:* `{sent_count}` messages\n"
        f"❌ *Failed:* `{failed_count}` messages",
        parse_mode='Markdown'
    )

async def stats(update, context):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        return
    
    load_users()
    
    total_users = len(users_data) - 1
    total_app_users = len(app_users_data)
    
    stats_msg = f"📊 *Complete Statistics*\n\n"
    stats_msg += f"*Telegram Users:* `{total_users}`\n"
    stats_msg += f"*App Users:* `{total_app_users}`\n"
    stats_msg += f"*File Status:* {"✅ Ready" if FILES['datrix_app']['message_id'] else "❌ Not set"}\n"
    stats_msg += f"*Downloads:* `{FILES['datrix_app']['download_count']}`\n"
    stats_msg += f"*License API:* ✅ Active"
    
    await update.message.reply_text(stats_msg, parse_mode='Markdown')

async def app_stats(update, context):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        return
    
    load_users()
    
    if not app_users_data:
        await update.message.reply_text("📱 *No app users registered yet.*", parse_mode='Markdown')
        return
    
    stats_msg = f"🖥️ *DATRIX App Statistics*\n\n"
    stats_msg += f"👥 *Total Users:* `{len(app_users_data)}`\n\n"
    
    stats_msg += "*Recent Users:*\n"
    sorted_users = sorted(app_users_data.values(), key=lambda x: x.get('last_seen', ''), reverse=True)[:10]
    for user in sorted_users:
        name = user.get('name', 'Unknown')[:15]
        company = user.get('company', 'Unknown')[:10]
        status = "✅" if user.get('license_status') == 'active' else "❌"
        stats_msg += f"{status} `{name}` ({company})\n"
    
    await update.message.reply_text(stats_msg, parse_mode='Markdown')

async def activate_license(update, context):
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
            f"📊 *Sheet ID:* `{sheet_id}`\n"
            f"📅 *Expires:* `{expiry_date}`",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            f"❌ *User not found with Sheet ID:* `{sheet_id}`",
            parse_mode='Markdown'
        )

async def clear_temp_files(update, context):
    user_id = str(update.effective_user.id)
    if user_id != ADMIN_ID:
        return
    
    try:
        temp_dir = tempfile.gettempdir()
        pattern = os.path.join(temp_dir, "datrix_license_activation_*.json")
        files = glob.glob(pattern)
        
        response_pattern = os.path.join(temp_dir, "license_response_*.json")
        files.extend(glob.glob(response_pattern))
        
        cleared_count = 0
        for file_path in files:
            try:
                os.remove(file_path)
                cleared_count += 1
            except:
                pass
        
        await update.message.reply_text(
            f"✅ *Temporary Files Cleared*\n\n"
            f"🗑️ *Removed:* `{cleared_count}` files",
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
    
    # 🔧 FIXED: Silent API handlers for DATRIX app
    app.add_handler(CommandHandler("api_version", api_check_version))
    app.add_handler(CommandHandler("api_register", api_register_user))
    app.add_handler(CommandHandler("api_error", api_report_error))
    app.add_handler(CommandHandler("api_license", api_check_license))
    app.add_handler(CommandHandler("get_license_data", get_license_data))
    
    # Admin commands
    app.add_handler(CommandHandler("set_file", set_file))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("app_stats", app_stats))
    app.add_handler(CommandHandler("activate", activate_license))
    app.add_handler(CommandHandler("request_license", request_license_activation))
    app.add_handler(CommandHandler("clear_temp_files", clear_temp_files))
    
    print("🚀 DATRIX Professional Bot Starting...")
    print("🔧 FIXED: All API functions included and working")
    print("📡 Silent API processing - no spam to admin")
    print("🎯 Only license requests shown to admin")
    print("✅ Professional bot behavior implemented!")
    
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
