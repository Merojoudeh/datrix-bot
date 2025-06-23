# main.py
# VERSION 18
# The Web Head, streamlined for web operations only.

import os
import logging
from flask import Flask, render_template, request, jsonify
from functools import wraps
import database as db

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("main")

# --- Environment ---
WEB_USER = os.environ.get('WEB_USER')
WEB_PASS = os.environ.get('WEB_PASS')

# --- Web Application ---
web_app = Flask(__name__)
db.initialize_database() # Ensure tables exist when web app starts

# --- Authentication ---
def check_auth(username, password): return username == WEB_USER and password == WEB_PASS
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return ('Unauthorized', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})
        return f(*args, **kwargs)
    return decorated_function

# --- Web Routes ---
@web_app.route('/')
@login_required
def dashboard(): return render_template('dashboard.html')

@web_app.route('/api/bot_users')
@login_required
def api_bot_users(): return jsonify(db.get_all_telegram_users())

@web_app.route('/api/broadcast', methods=['POST'])
@login_required
def api_broadcast():
    data = request.json
    message, target = data.get('message'), data.get('target', 'approved')
    
    if not message:
        return jsonify({'status': 'error', 'message': 'Empty message.'}), 400
    
    try:
        logger.info(f"WEB HEAD: Queuing broadcast for target: {target}.")
        db.queue_broadcast(target, message) # The new mechanism
        return jsonify({'status': 'success', 'message': f'Broadcast job has been queued for transmission.'})
    except Exception as e:
        logger.error(f"WEB HEAD: Broadcast queueing exception: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'An error occurred: {str(e)}'}), 500

if __name__ == '__main__':
    logger.info("MAIN: Executing in local development mode. Note: The bot worker must be run separately.")
    web_app.run(host='0.0.0.0', port=8080)
