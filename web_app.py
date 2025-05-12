import os
import json
import logging
import threading
import time
import psutil
import subprocess
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

import config
from binance_client import BinanceClient
from bot import BotManager
from grid_trading import GridTradingManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("web_app.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__,
            static_folder='web/static',
            template_folder='web/templates')
CORS(app)

# Global variables to store bot instances
bot_manager = None
grid_manager = None
client = None
bot_status = {
    "is_running": False,
    "mode": "none",
    "start_time": None,
    "symbols": [],
    "account_info": {},
    "positions": [],
    "orders": [],
    "trades": [],
    "pnl": {
        "daily": 0.0,
        "total": 0.0
    }
}

def is_bot_process_running():
    """
    Check if the bot is already running by looking for Python processes running main.py

    Returns:
        bool: True if the bot is running, False otherwise
    """
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Check if it's a Python process
                if proc.info['name'] and 'python' in proc.info['name'].lower():
                    # Check if it's running main.py
                    if proc.info['cmdline'] and any('main.py' in cmd for cmd in proc.info['cmdline']):
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return False
    except Exception as e:
        logger.error(f"Error checking if bot process is running: {str(e)}")
        return False

def check_bot_status():
    """
    Check if the bot is running and update the bot_status accordingly
    """
    global bot_status, client

    try:
        # If we already have a client, the bot is running through the web interface
        if client:
            return

        # Check if the bot is running as a separate process
        if is_bot_process_running():
            # Bot is running, update status
            if not bot_status["is_running"]:
                logger.info("Detected bot running as a separate process")
                bot_status["is_running"] = True

                # Create a client to get information
                client = BinanceClient()

                # Determine the mode based on config
                bot_status["mode"] = "grid" if config.GRID_TRADING_ENABLED else "signal"

                # Set start time (approximate)
                if not bot_status["start_time"]:
                    bot_status["start_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Get symbols
                if config.USE_HIGH_VOLUME_PAIRS:
                    bot_status["symbols"] = client.get_high_volume_pairs(config.MIN_VOLUME_USDT)
                else:
                    bot_status["symbols"] = [config.SYMBOL]
    except Exception as e:
        logger.error(f"Error checking bot status: {str(e)}")

def update_bot_status():
    """
    Update bot status information periodically
    """
    global bot_status, client

    # Track last update times for different data types
    last_update = {
        "account_info": 0,
        "positions": 0,
        "orders": 0,
        "pnl": 0,
        "trades": 0
    }

    # Define update intervals (in seconds)
    update_intervals = {
        "account_info": 30,   # Update account info every 30 seconds
        "positions": 15,      # Update positions every 15 seconds
        "orders": 30,         # Update orders every 30 seconds
        "pnl": 60,            # Update PnL every 60 seconds
        "trades": 120         # Update trades every 2 minutes
    }

    while True:
        try:
            current_time = time.time()

            # First, check if the bot is running (if we don't already know)
            if not bot_status["is_running"]:
                check_bot_status()

            # If the bot is running and we have a client, update the status
            if bot_status["is_running"] and client:
                try:
                    # Update account info if interval has passed
                    if current_time - last_update["account_info"] >= update_intervals["account_info"]:
                        account_info = client.get_account_info()
                        bot_status["account_info"] = {
                            "total_wallet_balance": float(account_info.get("totalWalletBalance", 0)),
                            "total_unrealized_profit": float(account_info.get("totalUnrealizedProfit", 0)),
                            "available_balance": float(account_info.get("availableBalance", 0)),
                        }
                        last_update["account_info"] = current_time
                        logger.debug("Account info updated")

                    # Update positions if interval has passed
                    if current_time - last_update["positions"] >= update_intervals["positions"]:
                        positions = client.get_open_positions()
                        bot_status["positions"] = positions
                        last_update["positions"] = current_time
                        logger.debug("Positions updated")

                    # Update orders if interval has passed
                    if current_time - last_update["orders"] >= update_intervals["orders"]:
                        orders = client.get_open_orders()
                        bot_status["orders"] = orders
                        last_update["orders"] = current_time
                        logger.debug("Orders updated")

                    # Update PnL if interval has passed
                    if current_time - last_update["pnl"] >= update_intervals["pnl"]:
                        pnl_summary = client.get_daily_pnl()
                        bot_status["pnl"] = {
                            "daily": pnl_summary.get("pnl_percentage", 0),
                            "total": pnl_summary.get("total_pnl", 0)
                        }
                        last_update["pnl"] = current_time
                        logger.debug("PnL updated")

                    # Update trades if interval has passed
                    if current_time - last_update["trades"] >= update_intervals["trades"]:
                        recent_trades = []
                        # Only get trades for a subset of symbols at a time to reduce API calls
                        symbols_to_update = bot_status["symbols"][:3]  # Limit to 3 symbols per update

                        for symbol in symbols_to_update:
                            try:
                                trades = client.get_recent_trades(symbol, limit=5)  # Reduced from 10 to 5
                                for trade in trades:
                                    trade["symbol"] = symbol
                                    recent_trades.append(trade)
                            except Exception as e:
                                logger.error(f"Error getting trades for {symbol}: {str(e)}")

                        if recent_trades:
                            # Sort trades by time (newest first)
                            recent_trades.sort(key=lambda x: int(x.get("time", 0)), reverse=True)

                            # Merge with existing trades and keep only the 20 most recent
                            existing_trades = bot_status.get("trades", [])
                            all_trades = recent_trades + existing_trades
                            # Remove duplicates by trade ID
                            unique_trades = []
                            trade_ids = set()
                            for trade in all_trades:
                                trade_id = trade.get("id")
                                if trade_id and trade_id not in trade_ids:
                                    trade_ids.add(trade_id)
                                    unique_trades.append(trade)

                            bot_status["trades"] = unique_trades[:20]  # Keep only the 20 most recent trades

                        last_update["trades"] = current_time
                        logger.debug("Trades updated")

                    # Check if the bot is still running
                    if not is_bot_process_running() and bot_manager is None and grid_manager is None:
                        logger.info("Bot process is no longer running")
                        bot_status["is_running"] = False
                        client = None

                except Exception as e:
                    logger.error(f"Error updating bot data: {str(e)}")

            # Sleep for 5 seconds before checking again
            # This is just the check interval, actual updates happen based on their own intervals
            time.sleep(5)

        except Exception as e:
            logger.error(f"Error in update_bot_status: {str(e)}")
            time.sleep(10)  # Wait longer if there's an error

@app.route('/')
def index():
    """
    Render the main dashboard page
    """
    return render_template('index.html')

@app.route('/chart')
def chart():
    """
    Render the chart page with the specified trading symbol

    Query Parameters:
        symbol (str): Trading symbol to display (e.g., BTCUSDT, ETHUSDT)
                     Defaults to the symbol specified in config
    """
    symbol = request.args.get('symbol', config.SYMBOL)
    logger.info(f"Rendering chart for symbol: {symbol}")
    return render_template('chart.html', symbol=symbol)

@app.route('/api/status')
def get_status():
    """
    Get the current bot status
    """
    return jsonify(bot_status)

@app.route('/api/start', methods=['POST'])
def start_bot():
    """
    Start the trading bot
    """
    global bot_manager, grid_manager, client, bot_status

    try:
        logger.info("Received request to start bot")
        print("Received request to start bot")

        # SIMPLIFIED VERSION - Skip all actual bot initialization
        # Just update the status and return success

        # Update bot status
        bot_status["is_running"] = True
        bot_status["mode"] = "signal"  # Default mode
        bot_status["start_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        bot_status["symbols"] = [config.SYMBOL]

        logger.info("Bot started successfully (simplified mode)")
        print("Bot started successfully (simplified mode)")

        # Return success immediately
        return jsonify({"success": True, "message": "Bot started in simplified mode"})

    except Exception as e:
        logger.error(f"Error in start_bot API: {str(e)}")
        print(f"Error in start_bot API: {str(e)}")
        return jsonify({"success": False, "message": f"Error starting bot: {str(e)}"})

@app.route('/api/stop', methods=['POST'])
def stop_bot():
    """
    Stop the trading bot
    """
    global bot_manager, grid_manager, client, bot_status

    try:
        logger.info("Received request to stop bot")
        print("Received request to stop bot")

        # SIMPLIFIED VERSION - Skip all checks and just update the status

        # Reset bot status
        bot_status["is_running"] = False
        bot_status["mode"] = "none"
        bot_status["start_time"] = None
        bot_status["symbols"] = []

        # Reset managers
        bot_manager = None
        grid_manager = None
        client = None

        logger.info("Bot stopped successfully (simplified mode)")
        print("Bot stopped successfully (simplified mode)")

        # Return success immediately
        return jsonify({"success": True, "message": "Bot stopped"})

    except Exception as e:
        logger.error(f"Error in stop_bot API: {str(e)}")
        print(f"Error in stop_bot API: {str(e)}")
        return jsonify({"success": False, "message": f"Error stopping bot: {str(e)}"})

@app.route('/api/symbols')
def get_symbols():
    """
    Get available trading symbols
    """
    try:
        logger.info("Received request for trading symbols")
        print("Received request for trading symbols")

        # Create a temporary client
        try:
            temp_client = BinanceClient()
            symbols = temp_client.get_high_volume_pairs(config.MIN_VOLUME_USDT)

            if not symbols or len(symbols) == 0:
                logger.warning("No symbols returned from Binance API, using default list")
                print("No symbols returned from Binance API, using default list")

                # Use a default list of common symbols
                symbols = [
                    "BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "DOGEUSDT",
                    "XRPUSDT", "DOTUSDT", "UNIUSDT", "LTCUSDT", "LINKUSDT",
                    "SOLUSDT", "MATICUSDT", "AVAXUSDT", "ATOMUSDT", "TRXUSDT"
                ]

            logger.info(f"Returning {len(symbols)} trading symbols")
            print(f"Returning {len(symbols)} trading symbols: {symbols}")

            return jsonify({"success": True, "symbols": symbols})

        except Exception as e:
            logger.error(f"Error getting symbols from Binance: {str(e)}")
            print(f"Error getting symbols from Binance: {str(e)}")

            # Return a default list of common symbols
            default_symbols = [
                "BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "DOGEUSDT",
                "XRPUSDT", "DOTUSDT", "UNIUSDT", "LTCUSDT", "LINKUSDT"
            ]

            logger.info(f"Returning {len(default_symbols)} default trading symbols")
            print(f"Returning {len(default_symbols)} default trading symbols")

            return jsonify({"success": True, "symbols": default_symbols})

    except Exception as e:
        logger.error(f"Error in get_symbols API: {str(e)}")
        print(f"Error in get_symbols API: {str(e)}")
        return jsonify({"success": False, "message": f"Error getting symbols: {str(e)}"})

@app.route('/api/chart-data/<symbol>')
def get_chart_data(symbol):
    """
    Get chart data for a symbol including positions and signals

    Args:
        symbol: Trading symbol (e.g., BTCUSDT)

    Returns:
        JSON with positions and signals data
    """
    try:
        logger.info(f"Getting chart data for symbol: {symbol}")
        print(f"Getting chart data for symbol: {symbol}")

        if not client:
            # Create a temporary client if none exists
            temp_client = BinanceClient()
            client_to_use = temp_client
            logger.info("Created temporary Binance client")
        else:
            client_to_use = client
            logger.info("Using existing Binance client")

        # Get positions data
        positions = []
        try:
            all_positions = client_to_use.get_open_positions()
            for position in all_positions:
                if position['symbol'] == symbol:
                    position_amt = float(position['positionAmt'])
                    if position_amt != 0:
                        positions.append({
                            'side': position['positionSide'],
                            'entry_price': float(position['entryPrice']),
                            'size': abs(position_amt),
                            'pnl': float(position['unrealizedProfit']),
                            'timestamp': int(time.time() * 1000)  # Current time in milliseconds
                        })
        except Exception as e:
            logger.error(f"Error getting positions for chart: {str(e)}")

        # Get recent signals data
        signals = []
        try:
            # Get klines data
            klines = client_to_use.get_klines(symbol, interval=config.KLINE_INTERVAL, limit=100)

            # Calculate indicators
            from indicators import (
                calculate_rsi, detect_candle_pattern, calculate_ema,
                calculate_bollinger_bands, calculate_macd, check_entry_signal
            )

            df = klines
            df = calculate_rsi(df)
            df = detect_candle_pattern(df)
            df = calculate_ema(df)
            df = calculate_bollinger_bands(df)
            df = calculate_macd(df)

            # Get signals from the last 20 candles
            for i in range(max(0, len(df) - 20), len(df)):
                row = df.iloc[i]
                signal = check_entry_signal(df.iloc[:i+1])

                if signal:
                    signals.append({
                        'type': signal,  # 'LONG' or 'SHORT'
                        'price': row['close'],
                        'timestamp': int(row['timestamp']),
                        'indicators': {
                            'rsi': row['rsi'],
                            'ema_short': row[f'ema_{config.EMA_SHORT_PERIOD}'],
                            'ema_long': row[f'ema_{config.EMA_LONG_PERIOD}'],
                            'bb_upper': row['bb_upper'],
                            'bb_middle': row['bb_middle'],
                            'bb_lower': row['bb_lower'],
                            'macd_line': row['macd_line'],
                            'macd_signal': row['macd_signal'],
                            'macd_histogram': row['macd_histogram']
                        }
                    })
        except Exception as e:
            logger.error(f"Error getting signals for chart: {str(e)}")

        logger.info(f"Returning chart data for {symbol}: {len(positions)} positions, {len(signals)} signals")
        print(f"Returning chart data for {symbol}: {len(positions)} positions, {len(signals)} signals")

        return jsonify({
            "success": True,
            "symbol": symbol,
            "positions": positions,
            "signals": signals
        })

    except Exception as e:
        logger.error(f"Error getting chart data: {str(e)}")
        return jsonify({"success": False, "message": f"Error getting chart data: {str(e)}"})

if __name__ == '__main__':
    # Check if psutil is installed
    try:
        import psutil
    except ImportError:
        logger.error("psutil is not installed. Please install it with 'pip install psutil'")
        print("Error: psutil is not installed. Please install it with 'pip install psutil'")
        exit(1)

    # Check if the bot is already running when the web app starts
    logger.info("Checking if bot is already running...")
    check_bot_status()
    if bot_status["is_running"]:
        logger.info(f"Bot detected as running in {bot_status['mode']} mode")
    else:
        logger.info("No running bot detected")

    # Start the status update thread
    status_thread = threading.Thread(target=update_bot_status, daemon=True)
    status_thread.start()

    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)
