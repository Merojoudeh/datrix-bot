# main.py
# Clean DATRIX Bot + Web Dashboard (No Broadcast)

import os
import logging
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from functools import wraps
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
import database as db

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO,
    handlers=[
        logging.FileHandler('datrix.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '7803291138:AAExEBQq9uZhq6X_ncI_c8E2J80-tpZtq8E')
ADMIN_CHAT_ID = os.environ.get('ADMIN_TELEGRAM_ID', '811896458')
WEB_USER = os.environ.get('WEB_USER', 'admin')
WEB_PASS = os.environ.get('WEB_PASS', 'datrix2024')

# Global variable to store current file info
CURRENT_FILE = {
    'file_id': None,
    'version': 'v2.1.6',
    'size': 'Unknown',
    'filename': 'DATRIX_Setup.exe',
    'upload_date': None
}

# =================== FLASK WEB APP ===================
web_app = Flask(__name__)

def check_auth(username, password): 
    return username == WEB_USER and password == WEB_PASS

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return ('Unauthorized', 401, {'WWW-Authenticate': 'Basic realm="DATRIX Control Panel"'})
        return f(*args, **kwargs)
    return decorated_function

@web_app.route('/')
@login_required
def dashboard(): 
    # Try to load template, fallback to embedded HTML
    try:
        return render_template('dashboard.html')
    except:
        # Embedded dashboard if template not found
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>DATRIX Control Panel</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; background: #f8f9fa; }
                .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
                .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 12px; margin-bottom: 30px; text-align: center; }
                .header h1 { font-size: 2.5rem; margin-bottom: 10px; }
                .header p { opacity: 0.9; font-size: 1.1rem; }
                .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
                .stat { background: white; padding: 25px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center; }
                .stat h3 { font-size: 2rem; margin-bottom: 5px; color: #333; }
                .stat p { color: #666; font-weight: 500; }
                .stat.users h3 { color: #3498db; }
                .stat.active h3 { color: #2ecc71; }
                .stat.licensed h3 { color: #e74c3c; }
                .stat.downloads h3 { color: #f39c12; }
                .section { background: white; border-radius: 12px; padding: 25px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                .section h2 { margin-bottom: 20px; color: #333; }
                .table { width: 100%; border-collapse: collapse; }
                .table th, .table td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; }
                .table th { background: #f8f9fa; font-weight: 600; }
                .table tr:hover { background: #f8f9fa; }
                .btn { background: #3498db; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 14px; }
                .btn:hover { background: #2980b9; }
                .btn.success { background: #2ecc71; }
                .btn.success:hover { background: #27ae60; }
                .status.active { color: #2ecc71; font-weight: 600; }
                .status.expired { color: #e74c3c; font-weight: 600; }
                .loading { text-align: center; padding: 50px; color: #666; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🤖 DATRIX Control Panel</h1>
                    <p>Bot Management & User Analytics Dashboard</p>
                </div>
                
                <div class="stats">
                    <div class="stat users">
                        <h3 id="totalUsers">-</h3>
                        <p>Total Users</p>
                    </div>
                    <div class="stat active">
                        <h3 id="activeUsers">-</h3>
                        <p>Active Users (24h)</p>
                    </div>
                    <div class="stat licensed">
                        <h3 id="licensedUsers">-</h3>
                        <p>Licensed Users</p>
                    </div>
                    <div class="stat downloads">
                        <h3 id="downloads">-</h3>
                        <p>Total Downloads</p>
                    </div>
                </div>
                
                <div class="section">
                    <h2>📋 Users Management</h2>
                    <div id="usersContainer">
                        <div class="loading">Loading users data...</div>
                    </div>
                </div>
            </div>
            
            <script>
                // Load stats
                fetch('/api/bot_stats')
                    .then(r => r.json())
                    .then(data => {
                        document.getElementById('totalUsers').textContent = data.total_users || 0;
                        document.getElementById('activeUsers').textContent = data.active_users || 0;
                        document.getElementById('licensedUsers').textContent = data.licensed_users || 0;
                        document.getElementById('downloads').textContent = data.downloads_today || 0;
                    })
                    .catch(e => console.error('Error loading stats:', e));
                
                // Load users
                fetch('/api/datrix_users')
                    .then(r => r.json())
                    .then(users => {
                        const container = document.getElementById('usersContainer');
                        
                        if (users.length === 0) {
                            container.innerHTML = '<div class="loading">No users found</div>';
                            return;
                        }
                        
                        const table = `
                            <table class="table">
                                <thead>
                                    <tr>
                                        <th>User ID</th>
                                        <th>Name</th>
                                        <th>Company</th>
                                        <th>License Status</th>
                                        <th>Downloads</th>
                                        <th>Last Seen</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${users.map(user => `
                                        <tr>
                                            <td>${user.telegram_id}</td>
                                            <td>${user.user_name || 'Unknown'}</td>
                                            <td>${user.company_name || 'Not set'}</td>
                                            <td class="status ${user.is_app_user ? 'active' : 'expired'}">
                                                ${user.is_app_user ? '✅ Active' : '❌ Expired'}
                                            </td>
                                            <td>${user.total_downloads || 0}</td>
                                            <td>${user.last_seen_formatted || 'Never'}</td>
                                            <td>
                                                <button class="btn" onclick="extendLicense(${user.telegram_id}, 30)">+30d</button>
                                                <button class="btn success" onclick="extendLicense(${user.telegram_id}, 90)">+90d</button>
                                            </td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        `;
                        
                        container.innerHTML = table;
                    })
                    .catch(e => {
                        console.error('Error loading users:', e);
                        document.getElementById('usersContainer').innerHTML = '<div class="loading">Error loading users</div>';
                    });
                
                function extendLicense(userId, days) {
                    if (!confirm(`Extend license for user ${userId} by ${days} days?`)) return;
                    
                    fetch('/api/extend_license', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({user_id: userId, days: days})
                    })
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            alert('License extended successfully!');
                            location.reload();
                        } else {
                            alert('Error: ' + (data.error || 'Unknown error'));
                        }
                    })
                    .catch(e => {
                        alert('Network error: ' + e.message);
                    });
                }
                
                // Refresh data every 30 seconds
                setInterval(() => {
                    location.reload();
                }, 30000);
            </script>
        </body>
        </html>
        """
@web_app.route('/api/extend_license', methods=['POST'])
@login_required
def api_extend_license():
    try:
        data = request.json
        user_id = data.get('user_id')
        days = data.get('days', 30)
        
        if not user_id:
            return jsonify({'error': 'User ID required'}), 400
            
        success = db.extend_user_license(user_id, days)
        
        if success:
            return jsonify({
                'success': True, 
                'message': f'License extended by {days} days'
            })
        else:
            return jsonify({'error': 'Failed to extend license'}), 500
    except Exception as e:
        logger.error(f"Error extending license: {e}")
        return jsonify({'error': str(e)}), 500

@web_app.route('/api/file_info')
@login_required
def api_file_info():
    """Get current file info"""
    return jsonify(CURRENT_FILE)

@web_app.route('/api/bot_stats')
@login_required
def api_bot_stats():
    """Get basic bot statistics"""
    try:
        stats = db.get_basic_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({
            'total_users': 0,
            'active_users': 0,
            'downloads_today': 0,
            'licensed_users': 0
        })

# Original compatibility routes (empty implementations)
@web_app.route('/api/bot_users')
@login_required
def api_bot_users(): 
    return api_datrix_users()

# =================== TELEGRAM BOT ===================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Register user
    db.add_or_update_user(user.id, user.username, user.first_name)
    db.log_user_activity(user.id, 'start', 'User started bot')
    
    welcome_message = """🤖 **مرحباً بك في DATRIX Bot**

📋 **الأوامر المتاحة:**
• `/datrix_app` - تحميل تطبيق DATRIX
• `/register_company` - تسجيل شركتك
• `/request_license` - طلب ترخيص جديد
• `/my_status` - حالة حسابك
• `/help` - المساعدة

🌐 **يعمل 24/7 على الخادم السحابي**
⚡ **تحميل فوري مباشرة من البوت**

💡 **للبدء:** استخدم `/register_company` لتسجيل شركتك"""
    
    await update.message.reply_text(welcome_message, parse_mode='Markdown')
    logger.info(f"✅ User {user.id} started the bot")

async def register_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "📝 **استخدام الأمر:**\n"
            "`/register_company \"اسم الشركة\" google_sheet_id`\n\n"
            "**مثال:**\n"
            "`/register_company \"شركة المستقبل\" 1OTNGDMgnVdkhqN9t2ESvuXA`",
            parse_mode='Markdown'
        )
        return
    
    # Parse company name (may have quotes)
    args_text = ' '.join(context.args)
    if args_text.startswith('"'):
        # Extract quoted company name
        end_quote = args_text.find('"', 1)
        if end_quote != -1:
            company_name = args_text[1:end_quote]
            remaining = args_text[end_quote+1:].strip()
            sheet_id = remaining.split()[0] if remaining.split() else None
        else:
            company_name = context.args[0]
            sheet_id = context.args[1] if len(context.args) > 1 else None
    else:
        company_name = context.args[0]
        sheet_id = context.args[1] if len(context.args) > 1 else None
    
    if not sheet_id:
        await update.message.reply_text("❌ **يرجى إدخال Google Sheet ID**", parse_mode='Markdown')
        return
    
    # Update user info
    success = db.update_user_company(user.id, company_name, sheet_id)
    
    if success:
        db.log_user_activity(user.id, 'register_company', f'{company_name} - {sheet_id}')
        
        await update.message.reply_text(
            f"✅ **تم تسجيل بيانات الشركة!**\n\n"
            f"🏢 **الشركة:** {company_name}\n"
            f"📊 **Sheet ID:** `{sheet_id}`\n\n"
            f"💡 يمكنك الآن طلب ترخيص باستخدام `/request_license`",
            parse_mode='Markdown'
        )
        
        # Notify admin
        admin_msg = f"""🆕 **تسجيل شركة جديدة**
👤 {user.first_name} (@{user.username})
🆔 `{user.id}`
🏢 {company_name}
📊 `{sheet_id}`
📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}"""
        
        try:
            await context.bot.send_message(ADMIN_CHAT_ID, admin_msg, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")
    else:
        await update.message.reply_text("❌ حدث خطأ في التسجيل. يرجى المحاولة مرة أخرى.")

async def request_license(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_info = db.get_user_info(user.id)
    
    if not user_info or not user_info.get('company_name'):
        await update.message.reply_text(
            "❌ **يجب تسجيل بيانات الشركة أولاً**\n\n"
            "استخدم: `/register_company \"اسم الشركة\" sheet_id`",
            parse_mode='Markdown'
        )
        return
    
    db.log_user_activity(user.id, 'request_license', f"Company: {user_info['company_name']}")
    
    # Create admin keyboard
    keyboard = [
        [
            InlineKeyboardButton("منح 30 يوم", callback_data=f"extend_30:{user.id}"),
            InlineKeyboardButton("منح 90 يوم", callback_data=f"extend_90:{user.id}"),
        ],
        [
            InlineKeyboardButton("منح سنة", callback_data=f"extend_365:{user.id}"),
            InlineKeyboardButton("رفض", callback_data=f"extend_deny:{user.id}"),
        ]
    ]
    markup = InlineKeyboardMarkup(keyboard)
    
    admin_msg = f"""🔑 **طلب تمديد ترخيص DATRIX**

👤 **المستخدم:** {user.first_name} (@{user.username})
🆔 **Telegram ID:** `{user.id}`
🏢 **الشركة:** {user_info['company_name']}
📊 **Sheet ID:** `{user_info.get('google_sheet_id', 'غير محدد')}`
📅 **تاريخ الطلب:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

⏰ **يرجى اختيار فترة التمديد:**"""
    
    try:
        await context.bot.send_message(ADMIN_CHAT_ID, admin_msg, reply_markup=markup, parse_mode='Markdown')
        await update.message.reply_text("✅ **تم إرسال طلب التمديد للمراجعة**\n\n📧 سيتم إشعارك فور الموافقة", parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Failed to send license request: {e}")
        await update.message.reply_text("❌ حدث خطأ في إرسال الطلب")

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if str(query.from_user.id) != ADMIN_CHAT_ID:
        return
    
    data = query.data
    if data.startswith("extend_"):
        action, user_id_str = data.split(":", 1)
        user_id = int(user_id_str)
        
        if action == "extend_deny":
            await query.edit_message_text(f"❌ **تم رفض طلب الترخيص للمستخدم {user_id}**")
            try:
                await context.bot.send_message(user_id, "❌ **تم رفض طلب تمديد الترخيص**\n\nيرجى التواصل مع الإدارة للمزيد من المعلومات.")
            except:
                pass
        else:
            days_map = {"extend_30": 30, "extend_90": 90, "extend_365": 365}
            days = days_map.get(action, 30)
            
            success = db.extend_user_license(user_id, days)
            
            if success:
                expiry_date = (datetime.now().date() + timedelta(days=days)).strftime('%Y-%m-%d')
                await query.edit_message_text(f"✅ **تم منح ترخيص {days} يوم للمستخدم {user_id}**\n📅 **ينتهي في:** {expiry_date}")
                try:
                    await context.bot.send_message(
                        user_id,
                        f"🎉 **تم قبول طلب الترخيص!**\n\n"
                        f"⏰ **المدة الممنوحة:** {days} يوم\n"
                        f"📅 **ينتهي في:** {expiry_date}\n\n"
                        f"✅ يمكنك الآن تحميل DATRIX باستخدام `/datrix_app`",
                        parse_mode='Markdown'
                    )
                except:
                    pass
            else:
                await query.edit_message_text(f"❌ **فشل في منح الترخيص للمستخدم {user_id}**")

async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_info = db.get_user_info(user.id)
    
    if not user_info:
        await update.message.reply_text("❌ **لم يتم العثور على بياناتك**\n\nاستخدم `/start` للتسجيل", parse_mode='Markdown')
        return
    
    # Calculate license status
    license_text = "⚠️ غير محدد"
    if user_info.get('license_expires'):
        days_remaining = (user_info['license_expires'] - datetime.now().date()).days
        if days_remaining > 0:
            license_text = f"✅ نشط ({days_remaining} يوم متبقي)"
        else:
            license_text = f"❌ منتهي الصلاحية ({abs(days_remaining)} يوم)"
    
    status_msg = f"""📊 **حالة حسابك في DATRIX**

👤 **المستخدم:** {user.first_name}
🆔 **Telegram ID:** `{user.id}`
🏢 **الشركة:** {user_info.get('company_name') or 'غير مسجل'}
📊 **Sheet ID:** `{user_info.get('google_sheet_id') or 'غير محدد'}`

🔑 **حالة الترخيص:** {license_text}
📅 **تاريخ انتهاء الترخيص:** {user_info['license_expires'].strftime('%Y-%m-%d') if user_info.get('license_expires') else 'غير محدد'}
📦 **عدد التحميلات:** {user_info.get('download_count', 0)}
📅 **تاريخ التسجيل:** {user_info['created_at'].strftime('%Y-%m-%d') if user_info.get('created_at') else 'غير محدد'}

💡 **إجراءات متاحة:**
• `/request_license` - طلب تمديد الترخيص
• `/datrix_app` - تحميل التطبيق (إذا كان الترخيص نشط)"""
    
    await update.message.reply_text(status_msg, parse_mode='Markdown')

async def get_datrix_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Check if user exists
    user_info = db.get_user_info(user.id)
    if not user_info:
        await update.message.reply_text("❌ **يجب التسجيل أولاً**\nاستخدم `/start`", parse_mode='Markdown')
        return
    
    # Check license
    if user_info.get('license_expires'):
        if user_info['license_expires'] <= datetime.now().date():
            await update.message.reply_text(
                "🔒 **الترخيص منتهي الصلاحية**\n\nاستخدم `/request_license` لطلب تمديد الترخيص",
                parse_mode='Markdown'
            )
            return
    else:
        await update.message.reply_text(
            "🔒 **لا يوجد ترخيص نشط**\n\nاستخدم `/request_license` لطلب ترخيص جديد",
            parse_mode='Markdown'
        )
        return
    
    # Check if file is available
    if not CURRENT_FILE.get('file_id'):
        await update.message.reply_text("❌ **التطبيق غير متاح حالياً**\n\nيرجى المحاولة لاحقاً أو التواصل مع الإدارة", parse_mode='Markdown')
        return
    
    try:
        # Send the file directly
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=CURRENT_FILE['file_id'],
            caption=f"✅ **{CURRENT_FILE['filename']}**\n\n🔢 **الإصدار:** {CURRENT_FILE['version']}\n💾 **الحجم:** {CURRENT_FILE['size']}\n📅 **تاريخ الرفع:** {CURRENT_FILE['upload_date']}\n\n🚀 **استمتع باستخدام DATRIX!**"
        )
        
        # Track download
        db.track_download(user.id)
        
        logger.info(f"✅ DATRIX delivered to user {user.id} ({user.username})")
        
    except Exception as e:
        logger.error(f"Error delivering file to {user.id}: {e}")
        await update.message.reply_text("❌ **خطأ في التحميل**\n\nيرجى المحاولة مرة أخرى أو التواصل مع الإدارة", parse_mode='Markdown')

# Admin commands
async def set_file_waiting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to prepare for file upload"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        return
    
    version = context.args[0] if context.args else "v2.1.6"
    
    # Set waiting state
    context.user_data['waiting_for_file'] = True
    context.user_data['file_version'] = version
    
    await update.message.reply_text(
        f"✅ **جاهز لاستقبال ملف DATRIX {version}**\n\n"
        f"📤 أرسل الملف الآن وسيتم حفظه تلقائياً",
        parse_mode='Markdown'
    )

async def handle_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle file uploads from admin"""
    user_id = str(update.effective_user.id)
    
    # Only admin can upload files
    if user_id != ADMIN_CHAT_ID:
        return
    
    # Check if admin is waiting to upload a file
    if not context.user_data.get('waiting_for_file'):
        return
    
    document = update.message.document
    if not document:
        return
    
    try:
        # Save file info globally
        CURRENT_FILE.update({
            'file_id': document.file_id,
            'version': context.user_data.get('file_version', 'v2.1.6'),
            'size': f"{document.file_size // (1024*1024)}MB" if document.file_size else "Unknown",
            'filename': document.file_name or 'DATRIX_Setup.exe',
            'upload_date': datetime.now().strftime('%Y-%m-%d %H:%M')
        })
        
        # Clear waiting state
        context.user_data['waiting_for_file'] = False
        
        await update.message.reply_text(
            f"✅ **تم حفظ الملف بنجاح!**\n\n"
            f"📄 **الملف:** {CURRENT_FILE['filename']}\n"
            f"🔢 **الإصدار:** {CURRENT_FILE['version']}\n"
            f"💾 **الحجم:** {CURRENT_FILE['size']}\n"
            f"📅 **تاريخ الرفع:** {CURRENT_FILE['upload_date']}\n\n"
            f"🚀 **الملف متاح الآن للمستخدمين المرخصين!**",
            parse_mode='Markdown'
        )
        
        logger.info(f"✅ Admin uploaded new file: {CURRENT_FILE['filename']} ({CURRENT_FILE['version']})")
        
    except Exception as e:
        logger.error(f"Error handling file upload: {e}")
        await update.message.reply_text("❌ **خطأ في حفظ الملف**", parse_mode='Markdown')

async def current_file_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current file info (admin only)"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        return
    
    if CURRENT_FILE.get('file_id'):
        info = f"""📁 **معلومات الملف الحالي:**

📄 **اسم الملف:** {CURRENT_FILE['filename']}
🔢 **الإصدار:** {CURRENT_FILE['version']}
💾 **الحجم:** {CURRENT_FILE['size']}
📅 **تاريخ الرفع:** {CURRENT_FILE['upload_date']}
🆔 **File ID:** `{CURRENT_FILE['file_id'][:20]}...`

✅ **الحالة:** متاح للتحميل من قبل المستخدمين المرخصين"""
    else:
        info = "❌ **لا يوجد ملف محفوظ حالياً**\n\nاستخدم `/set_file [version]` ثم أرسل الملف لرفع نسخة جديدة"
    
    await update.message.reply_text(info, parse_mode='Markdown')

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show admin statistics"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        return
    
    try:
        stats = db.get_basic_stats()
        
        stats_msg = f"""📊 **إحصائيات DATRIX Bot**

👥 **المستخدمين:**
• إجمالي المستخدمين: {stats['total_users']}
• نشط (24 ساعة): {stats['active_users']}
• لديهم تراخيص نشطة: {stats['licensed_users']}

📦 **التحميلات:**
• إجمالي التحميلات: {stats['downloads_today']}

📁 **الملف الحالي:**
• الإصدار: {CURRENT_FILE.get('version', 'غير محدد')}
• الحالة: {'✅ متاح' if CURRENT_FILE.get('file_id') else '❌ غير متاح'}

📅 **التاريخ:** {datetime.now().strftime('%Y-%m-%d %H:%M')}"""
        
        await update.message.reply_text(stats_msg, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error getting admin stats: {e}")
        await update.message.reply_text("❌ خطأ في جلب الإحصائيات")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) == ADMIN_CHAT_ID:
        help_text = """🔧 **أوامر المشرف:**

**إدارة الملفات:**
• `/set_file [version]` - تحضير لرفع ملف جديد
• `/current_file` - معلومات الملف الحالي

**إحصائيات:**
• `/admin_stats` - إحصائيات مفصلة

**أوامر المستخدمين:**
• `/start` - رسالة الترحيب والتسجيل
• `/register_company` - تسجيل الشركة  
• `/request_license` - طلب ترخيص جديد
• `/my_status` - حالة الحساب والترخيص
• `/datrix_app` - تحميل التطبيق
• `/help` - عرض هذه المساعدة"""
    else:
        help_text = """🤖 **مساعدة DATRIX Bot**

**الأوامر المتاحة:**
• `/start` - رسالة الترحيب والتسجيل
• `/register_company` - تسجيل بيانات الشركة
• `/request_license` - طلب ترخيص جديد
• `/my_status` - عرض حالة حسابك
• `/datrix_app` - تحميل تطبيق DATRIX
• `/help` - عرض هذه المساعدة

**خطوات البدء:**
1. استخدم `/register_company` لتسجيل شركتك
2. استخدم `/request_license` لطلب ترخيص
3. بعد الموافقة، حمل التطبيق بـ `/datrix_app`

**المميزات:**
• ⚡ تحميل فوري مباشرة من البوت
• 🔐 نظام تراخيص آمن
• 📊 تتبع الاستخدام
• 🌐 متاح 24/7

**تحتاج مساعدة؟**
تواصل مع فريق الدعم إذا واجهت أي مشاكل."""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

# =================== MAIN FUNCTION ===================

def main():
    try:
        # Initialize database
        db.initialize_simple_database()
        
        # Create Telegram application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Add user handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("register_company", register_company))
        application.add_handler(CommandHandler("request_license", request_license))
        application.add_handler(CommandHandler("my_status", my_status))
        application.add_handler(CommandHandler("datrix_app", get_datrix_app))
        application.add_handler(CommandHandler("help", help_command))
        
        # Add admin handlers
        application.add_handler(CommandHandler("set_file", set_file_waiting))
        application.add_handler(CommandHandler("current_file", current_file_info))
        application.add_handler(CommandHandler("admin_stats", admin_stats))
        
        # File upload handler (admin only)
        application.add_handler(MessageHandler(filters.Document.ALL, handle_file_upload))
        
        # Callback handler for license approval
        application.add_handler(CallbackQueryHandler(callback_query_handler))
        
        print("🚀 DATRIX Bot + Web Dashboard Starting...")
        print(f"🤖 Bot Token: {BOT_TOKEN[:10]}...")
        print(f"👤 Admin ID: {ADMIN_CHAT_ID}")
        print(f"🌐 Web User: {WEB_USER}")
        print("✅ System ready!")
        
        # Start bot in a separate process using multiprocessing
        import multiprocessing
        import asyncio
        
        def run_bot_process():
            """Run bot in separate process"""
            try:
                # Create new event loop for this process
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Run the bot
                application.run_polling(drop_pending_updates=True)
            except Exception as e:
                print(f"❌ Bot process error: {e}")
        
        # Start bot process
        bot_process = multiprocessing.Process(target=run_bot_process, daemon=True)
        bot_process.start()
        
        # Start web app in main process
        web_app.run(
            host='0.0.0.0', 
            port=int(os.environ.get('PORT', 8080)),
            debug=False,
            use_reloader=False
        )
        
    except Exception as e:
        logger.error(f"Failed to start: {e}")
        
if __name__ == '__main__':
    main()
