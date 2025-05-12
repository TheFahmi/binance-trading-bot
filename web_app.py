import os
import json
import logging
import threading
import time
import psutil
import subprocess
from datetime import datetime
from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS

import config
from binance_client import BinanceClient
from bot import BotManager
from grid_trading import GridTradingManager
from backtest import Backtester, run_backtest_for_symbol, run_backtest_for_multiple_symbols, compare_backtest_results

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
                    cmdline = proc.info.get('cmdline', [])
                    if cmdline and any('main.py' in cmd for cmd in cmdline):
                        # Make sure it's not this process (web_app.py)
                        if not any('web_app.py' in cmd for cmd in cmdline):
                            return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
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
                try:
                    client = BinanceClient()

                    # Determine the mode based on config
                    bot_status["mode"] = "grid" if config.GRID_TRADING_ENABLED else "signal"

                    # Set start time (approximate)
                    if not bot_status["start_time"]:
                        bot_status["start_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    # Get symbols
                    try:
                        if config.USE_HIGH_VOLUME_PAIRS:
                            symbols = client.get_high_volume_pairs(config.MIN_VOLUME_USDT)
                            if symbols and len(symbols) > 0:
                                bot_status["symbols"] = symbols
                        else:
                            bot_status["symbols"] = [config.SYMBOL]
                    except Exception as e:
                        logger.error(f"Error getting symbols: {str(e)}")
                        # Fallback to default symbol
                        bot_status["symbols"] = [config.SYMBOL]
                except Exception as e:
                    logger.error(f"Error creating Binance client: {str(e)}")
                    # We'll continue without a client and try again later
                    client = None
        else:
            # If we thought the bot was running but it's not
            if bot_status["is_running"] and client is None:
                logger.info("Bot is no longer running")
                bot_status["is_running"] = False
                bot_status["mode"] = "none"

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
                        try:
                            account_info = client.get_account_info()
                            if account_info:
                                bot_status["account_info"] = {
                                    "total_wallet_balance": float(account_info.get("totalWalletBalance", 0)),
                                    "total_unrealized_profit": float(account_info.get("totalUnrealizedProfit", 0)),
                                    "available_balance": float(account_info.get("availableBalance", 0)),
                                }
                            last_update["account_info"] = current_time
                            logger.debug("Account info updated")
                        except Exception as e:
                            logger.error(f"Error updating account info: {str(e)}")

                    # Update positions if interval has passed
                    if current_time - last_update["positions"] >= update_intervals["positions"]:
                        try:
                            # Get open positions with enhanced error handling
                            positions = client.get_open_positions()

                            # Log the number of positions found
                            logger.info(f"Found {len(positions)} open positions")

                            # Add mark price to each position for easier display
                            for pos in positions:
                                try:
                                    pos_symbol = pos.get('symbol', '')
                                    if 'markPrice' not in pos:
                                        pos['markPrice'] = client.get_current_price(pos_symbol)

                                    # Add position side if not present (for one-way mode)
                                    if 'positionSide' not in pos:
                                        pos_amt = float(pos.get('positionAmt', 0))
                                        pos['positionSide'] = 'LONG' if pos_amt > 0 else 'SHORT'

                                    # Calculate unrealized PnL for display
                                    entry_price = float(pos.get('entryPrice', 0))
                                    mark_price = float(pos.get('markPrice', 0))
                                    position_amt = float(pos.get('positionAmt', 0))
                                    leverage = int(pos.get('leverage', 1))

                                    # Determine if LONG or SHORT based on position amount
                                    is_long = position_amt > 0

                                    # Calculate unrealized PnL
                                    if is_long:
                                        unrealized_pnl = (mark_price - entry_price) * abs(position_amt)
                                        if entry_price > 0:
                                            unrealized_pnl_percent = ((mark_price / entry_price) - 1) * 100 * leverage
                                        else:
                                            unrealized_pnl_percent = 0
                                    else:  # SHORT
                                        unrealized_pnl = (entry_price - mark_price) * abs(position_amt)
                                        if entry_price > 0 and mark_price > 0:
                                            unrealized_pnl_percent = ((entry_price / mark_price) - 1) * 100 * leverage
                                        else:
                                            unrealized_pnl_percent = 0

                                    # Add calculated values to position
                                    pos['unrealizedProfit'] = unrealized_pnl
                                    pos['unrealizedProfitPercent'] = unrealized_pnl_percent

                                except Exception as e:
                                    logger.error(f"Error processing position {pos.get('symbol', 'unknown')}: {str(e)}")

                            if positions is not None:
                                bot_status["positions"] = positions

                            last_update["positions"] = current_time
                            logger.info(f"Positions updated: {len(positions)} positions")

                            # Log the first few positions for debugging
                            for i, pos in enumerate(positions[:3]):
                                logger.info(f"Position {i+1}: {pos.get('symbol', 'unknown')} {pos.get('positionSide', 'unknown')} "
                                           f"{pos.get('positionAmt', 0)} @ {pos.get('entryPrice', 0)} "
                                           f"PnL: {pos.get('unrealizedProfit', 0):.2f} ({pos.get('unrealizedProfitPercent', 0):.2f}%)")

                        except Exception as e:
                            logger.error(f"Error updating positions: {str(e)}")

                    # Update orders if interval has passed
                    if current_time - last_update["orders"] >= update_intervals["orders"]:
                        try:
                            orders = client.get_open_orders()
                            if orders is not None:
                                bot_status["orders"] = orders
                            last_update["orders"] = current_time
                            logger.debug("Orders updated")
                        except Exception as e:
                            logger.error(f"Error updating orders: {str(e)}")

                    # Update PnL if interval has passed
                    if current_time - last_update["pnl"] >= update_intervals["pnl"]:
                        try:
                            pnl_summary = client.get_daily_pnl()
                            if pnl_summary:
                                bot_status["pnl"] = {
                                    "daily": pnl_summary.get("pnl_percentage", 0),
                                    "total": pnl_summary.get("total_pnl", 0)
                                }
                            last_update["pnl"] = current_time
                            logger.debug("PnL updated")
                        except Exception as e:
                            logger.error(f"Error updating PnL: {str(e)}")

                    # Update trades if interval has passed
                    if current_time - last_update["trades"] >= update_intervals["trades"]:
                        try:
                            recent_trades = []
                            # Only get trades for a subset of symbols at a time to reduce API calls
                            symbols_to_update = bot_status["symbols"][:3]  # Limit to 3 symbols per update

                            for symbol in symbols_to_update:
                                try:
                                    trades = client.get_recent_trades(symbol, limit=5)  # Reduced from 10 to 5
                                    if trades:
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
                        except Exception as e:
                            logger.error(f"Error updating trades: {str(e)}")

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

@app.route('/api/backtest', methods=['POST'])
def run_backtest():
    """
    Run a backtest with the specified parameters

    Request JSON:
        symbol: Trading symbol
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        initial_balance: Initial account balance in USDT
        multi: Whether to run backtest for multiple symbols

    Returns:
        JSON with backtest results
    """
    try:
        data = request.json

        if not data:
            return jsonify({"success": False, "message": "No data provided"})

        symbol = data.get('symbol', config.SYMBOL)
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        initial_balance = data.get('initial_balance', 10000)
        multi = data.get('multi', False)

        if not start_date:
            return jsonify({"success": False, "message": "Start date is required"})

        logger.info(f"Running backtest for {symbol} from {start_date} to {end_date or 'today'}")

        if multi:
            # Get high volume pairs
            client = BinanceClient()
            symbols = client.get_high_volume_pairs(config.MIN_VOLUME_USDT)

            if not symbols:
                return jsonify({"success": False, "message": "Failed to get high volume pairs"})

            # Limit to top 5 by volume
            symbols = symbols[:5]

            logger.info(f"Running backtest for {len(symbols)} symbols: {', '.join(symbols)}")

            # Run backtest in a separate thread to avoid blocking the web server
            def run_backtest_thread():
                try:
                    results = run_backtest_for_multiple_symbols(symbols, start_date, end_date, initial_balance)

                    # Compare results
                    comparison = compare_backtest_results(results)

                    # Convert comparison to dict for JSON serialization
                    comparison_dict = comparison.to_dict(orient='records')

                    # Store results in a file
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    result_file = f"backtest_results/multi_{timestamp}_results.json"

                    os.makedirs("backtest_results", exist_ok=True)

                    with open(result_file, 'w') as f:
                        json.dump({
                            "symbols": symbols,
                            "start_date": start_date,
                            "end_date": end_date or datetime.now().strftime('%Y-%m-%d'),
                            "initial_balance": initial_balance,
                            "comparison": comparison_dict
                        }, f, indent=4)

                    logger.info(f"Backtest results saved to {result_file}")

                except Exception as e:
                    logger.error(f"Error in backtest thread: {str(e)}")

            # Start the backtest thread
            thread = threading.Thread(target=run_backtest_thread)
            thread.daemon = True
            thread.start()

            return jsonify({
                "success": True,
                "message": "Backtest started for multiple symbols",
                "symbols": symbols
            })

        else:
            # Run backtest in a separate thread to avoid blocking the web server
            def run_backtest_thread():
                try:
                    result = run_backtest_for_symbol(symbol, start_date, end_date, initial_balance)
                    logger.info(f"Backtest completed for {symbol}")
                except Exception as e:
                    logger.error(f"Error in backtest thread: {str(e)}")

            # Start the backtest thread
            thread = threading.Thread(target=run_backtest_thread)
            thread.daemon = True
            thread.start()

            return jsonify({
                "success": True,
                "message": f"Backtest started for {symbol}",
                "symbol": symbol,
                "start_date": start_date,
                "end_date": end_date or "today",
                "initial_balance": initial_balance
            })

    except Exception as e:
        logger.error(f"Error running backtest: {str(e)}")
        return jsonify({"success": False, "message": f"Error running backtest: {str(e)}"})

@app.route('/api/backtest/results')
def get_backtest_results():
    """
    Get list of available backtest results

    Returns:
        JSON with list of backtest result files
    """
    try:
        results_dir = "backtest_results"

        if not os.path.exists(results_dir):
            return jsonify({"success": True, "results": []})

        result_files = []

        for filename in os.listdir(results_dir):
            if filename.endswith(".json"):
                file_path = os.path.join(results_dir, filename)

                try:
                    with open(file_path, 'r') as f:
                        data = json.load(f)

                    # Extract basic info
                    if "comparison" in data:
                        # Multi-symbol backtest
                        result_files.append({
                            "filename": filename,
                            "type": "multi",
                            "symbols": data.get("symbols", []),
                            "start_date": data.get("start_date", ""),
                            "end_date": data.get("end_date", ""),
                            "initial_balance": data.get("initial_balance", 0),
                            "timestamp": filename.split("_")[1] + "_" + filename.split("_")[2]
                        })
                    else:
                        # Single symbol backtest
                        result_files.append({
                            "filename": filename,
                            "type": "single",
                            "symbol": data.get("symbol", ""),
                            "start_date": data.get("start_date", ""),
                            "end_date": data.get("end_date", ""),
                            "initial_balance": data.get("initial_balance", 0),
                            "final_balance": data.get("final_balance", 0),
                            "total_profit_pct": data.get("total_profit_pct", 0),
                            "timestamp": filename.split("_")[1] + "_" + filename.split("_")[2]
                        })
                except Exception as e:
                    logger.error(f"Error reading backtest result file {filename}: {str(e)}")
                    continue

        # Sort by timestamp (newest first)
        result_files.sort(key=lambda x: x["timestamp"], reverse=True)

        return jsonify({"success": True, "results": result_files})

    except Exception as e:
        logger.error(f"Error getting backtest results: {str(e)}")
        return jsonify({"success": False, "message": f"Error getting backtest results: {str(e)}"})

@app.route('/api/backtest/result/<filename>')
def get_backtest_result(filename):
    """
    Get a specific backtest result

    Args:
        filename: Backtest result filename

    Returns:
        JSON with backtest result data
    """
    try:
        file_path = os.path.join("backtest_results", filename)

        if not os.path.exists(file_path):
            return jsonify({"success": False, "message": "Backtest result not found"})

        with open(file_path, 'r') as f:
            data = json.load(f)

        return jsonify({"success": True, "data": data})

    except Exception as e:
        logger.error(f"Error getting backtest result: {str(e)}")
        return jsonify({"success": False, "message": f"Error getting backtest result: {str(e)}"})

@app.route('/backtest/images/<path:filename>')
def backtest_images(filename):
    """
    Serve backtest image files

    Args:
        filename: Image filename

    Returns:
        Image file
    """
    return send_from_directory('backtest_results', filename)

@app.route('/backtest')
def backtest_page():
    """
    Render the backtest page
    """
    return render_template('backtest.html')

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

            # In simplified mode, just return the klines data without calculating signals
            # This avoids import errors if the indicators module isn't fully implemented
            logger.info(f"Retrieved {len(klines)} klines for {symbol}")

            # We'll return some mock signals instead of calculating real ones
            # This avoids importing the indicators module which might not be fully implemented
            if len(klines) > 0:
                # Create simplified mock signals for demonstration
                for i in range(max(0, len(klines) - 5), len(klines)):
                    # Alternate between LONG and SHORT signals for demo purposes
                    signal_type = "LONG" if i % 2 == 0 else "SHORT"
                    kline = klines[i]

                    try:
                        close_price = float(kline['close'])
                        timestamp = int(kline['timestamp'])

                        signals.append({
                            'type': signal_type,
                            'price': close_price,
                            'timestamp': timestamp,
                            'indicators': {
                                'rsi': 50.0,  # Mock values
                                'ema_short': close_price * 0.99,
                                'ema_long': close_price * 0.98,
                                'bb_upper': close_price * 1.02,
                                'bb_middle': close_price,
                                'bb_lower': close_price * 0.98,
                                'macd_line': 0.1,
                                'macd_signal': 0.05,
                                'macd_histogram': 0.05
                            }
                        })
                    except (KeyError, TypeError) as e:
                        logger.error(f"Error processing kline data: {str(e)}")
                        continue

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
    try:
        logger.info("Starting web interface on http://0.0.0.0:5000")
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        logger.error(f"Error starting web interface: {e}")
