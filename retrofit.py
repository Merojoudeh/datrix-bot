# retrofit.py
# A single-use engineering drone to upgrade the Citadel's schema.

import os
import psycopg2
import logging

# Basic logging to observe the drone's operation
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("RETROFIT_DRONE")

# The command to add the missing column.
# "IF NOT EXISTS" makes the drone safe to run multiple times.
RETROFIT_COMMAND = "ALTER TABLE bot_files ADD COLUMN IF NOT EXISTS from_chat_id BIGINT;"

def run_retrofit():
    """Connects to the Citadel and executes the upgrade command."""
    
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        logger.critical("FATAL: DATABASE_URL not found. Drone cannot navigate to Citadel.")
        return

    logger.info("Drone activated. Attempting to connect to the Citadel...")
    
    conn = None
    try:
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        logger.info(f"Connection successful. Executing retrofit command: {RETROFIT_COMMAND}")
        cursor.execute(RETROFIT_COMMAND)
        conn.commit()
        
        logger.info("Command executed. The Citadel has been successfully retrofitted.")
        
        cursor.close()
    except Exception as e:
        logger.error(f"An error occurred during the retrofit operation: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()
            logger.info("Connection to Citadel closed. Drone returning to base.")

if __name__ == '__main__':
    run_retrofit()
