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

# ================= API COMMANDS FOR DATRIX APP (SILENT PROCESSING) =================

async def api_check_version(update, context):
    """🔧 FIXED: Silent API processing - no messages to admin"""
    try:
        # Delete the command message immediately
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
        
        # Send response back to the app (not to admin)
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

async def get_license_data(update, context):
    """🔧 FIXED: Silent API processing - only respond with data, no admin notification"""
    try:
        # Delete the command message immediately to keep admin chat clean
        await update.message.delete()
        
        if not context.args:
            error_response = {"status": "error", "message": "Usage: /get_license_data [sheet_id]"}
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"LICENSE_API_RESPONSE: {json.dumps(error_response)}"
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
        
        # Send response back silently
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
        # Handle both manual admin usage and automatic app requests
        if len(context.args) < 1:
            await update.message.reply_text(
                "*Usage:* `/request_license [user_name] [company] [sheet_id] [local_temp_path]`\n\n"
                "*Example:* `/request_license John_Doe ACME_Corp abc123xyz C:\\Users\\John\\AppData\\Local\\Temp\\datrix_license_activation_abc123xyz.json`\n"
                "*Note:* Use N/A for unknown values. Local temp path is optional.",
                parse_mode='Markdown'
            )
            return
        
        # Delete the original command message immediately
        await update.message.delete()
        
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
            error_msg = "❌ *Error:* Invalid arguments. Please provide user_name, company, and sheet_id at minimum"
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=error_msg,
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
        
        # Send ONLY to admin (clean professional approach)
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=request_message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        logger.info(f"License request created: {request_id} for {sheet_id}")
        
    except Exception as e:
        logger.error(f"Error creating license request: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ Error creating license request: {str(e)}"
        )

# ... [Include all other handlers - keeping them the same] ...

# For brevity, I'm showing the key changes. The rest of the handlers remain the same.

def main():
    load_users()
    load_settings()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Telegram user handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_query_handler))
    
    # 🔧 FIXED: Silent API handlers for DATRIX app
    app.add_handler(CommandHandler("api_version", api_check_version))
    app.add_handler(CommandHandler("api_register", api_register_user))  # Will add silent version
    app.add_handler(CommandHandler("api_error", api_report_error))      # Will add silent version
    app.add_handler(CommandHandler("api_license", api_check_license))   # Will add silent version
    app.add_handler(CommandHandler("get_license_data", get_license_data))  # FIXED: Silent processing
    
    # Admin commands (visible to admin)
    app.add_handler(CommandHandler("set_file", set_file))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("app_stats", app_stats))
    app.add_handler(CommandHandler("update_admin", update_admin))
    app.add_handler(CommandHandler("activate", activate_license))
    app.add_handler(CommandHandler("request_license", request_license_activation))  # FIXED: Silent processing
    app.add_handler(CommandHandler("clear_temp_files", clear_temp_files))
    
    print("🚀 DATRIX Professional Bot Starting...")
    print("🔧 FIXED: Silent API processing - no spam to admin")
    print("📡 API commands are processed silently")
    print("🎯 Only license requests and approvals shown to admin")
    print("✅ Professional bot behavior implemented!")
    
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
