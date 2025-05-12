import logging
import time
import os
import threading
from dotenv import load_dotenv

import config
from bot import BotManager
from grid_trading import GridTradingManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def check_environment():
    """
    Check if environment variables are set
    """
    # Load environment variables
    load_dotenv()

    # Check required environment variables
    required_vars = ['BINANCE_API_KEY', 'BINANCE_API_SECRET']
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please create a .env file with the required variables.")
        return False

    # Check optional environment variables
    optional_vars = ['TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']
    missing_optional = [var for var in optional_vars if not os.getenv(var)]

    if missing_optional:
        logger.warning(f"Missing optional environment variables: {', '.join(missing_optional)}")
        logger.warning("Telegram notifications will be disabled.")

    return True

def main():
    """
    Main entry point
    """
    print("Starting Binance Trading Bot")
    logger.info("Starting Binance Trading Bot")

    # Check environment variables
    if not check_environment():
        return

    print("Environment check passed")

    # Create and start the appropriate trading manager
    if config.GRID_TRADING_ENABLED:
        print("Creating grid trading manager...")
        logger.info("Starting in Grid Trading mode")
        manager = GridTradingManager()
        print("Starting all grid trading bots...")
        manager.start_all()
        print("All grid trading bots started successfully")

        # No monitor thread for grid trading
        monitor_thread = None
    else:
        print("Creating signal trading manager...")
        logger.info("Starting in Signal Trading mode")
        manager = BotManager()
        print("Starting all signal trading bots...")
        manager.start_all()
        print("All signal trading bots started successfully")

        # Start monitor thread for signal trading
        monitor_thread = threading.Thread(target=manager.monitor, daemon=True)
        monitor_thread.start()

    # Keep the main thread alive and update trading pairs periodically
    try:
        last_update_time = time.time()
        update_interval = 4 * 3600  # Update trading pairs every 4 hours

        while True:
            current_time = time.time()

            # Update trading pairs periodically if enabled (only for signal trading)
            if not config.GRID_TRADING_ENABLED and config.USE_HIGH_VOLUME_PAIRS and (current_time - last_update_time) >= update_interval:
                manager.update_trading_pairs()
                last_update_time = current_time

            time.sleep(60)  # Check every minute

    except KeyboardInterrupt:
        logger.info("Bot stopped by user")

if __name__ == "__main__":
    main()
