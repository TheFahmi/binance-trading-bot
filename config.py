import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Binance API credentials
API_KEY = os.getenv('BINANCE_API_KEY', '')
API_SECRET = os.getenv('BINANCE_API_SECRET', '')

# Telegram settings
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# Trading parameters
SYMBOL = os.getenv('TRADING_SYMBOL', 'BTCUSDT')  # Default trading pair if no high volume pairs found
LEVERAGE = int(os.getenv('LEVERAGE', '10'))      # Default leverage
POSITION_SIZE_PERCENT = float(os.getenv('POSITION_SIZE_PERCENT', '5.0'))  # Percentage of account balance to use for position
MIN_VOLUME_USDT = float(os.getenv('MIN_VOLUME_USDT', '1000000'))  # Minimum 24h volume in USDT (default: 1 million)
USE_HIGH_VOLUME_PAIRS = os.getenv('USE_HIGH_VOLUME_PAIRS', 'TRUE').upper() == 'TRUE'  # Whether to use high volume pairs
MAX_ACCOUNT_USAGE = float(os.getenv('MAX_ACCOUNT_USAGE', '60.0'))  # Maximum percentage of account balance to use for all positions (default: 60%)

# Hedge mode settings
HEDGE_MODE = os.getenv('HEDGE_MODE', 'TRUE').upper() == 'TRUE'  # Whether to use hedge mode (allow both LONG and SHORT positions simultaneously)
ALLOW_BOTH_POSITIONS = os.getenv('ALLOW_BOTH_POSITIONS', 'TRUE').upper() == 'TRUE'  # Whether to allow both LONG and SHORT positions on the same pair
AUTO_HEDGE = os.getenv('AUTO_HEDGE', 'FALSE').upper() == 'TRUE'  # Whether to automatically hedge positions when they reach a certain profit/loss
AUTO_HEDGE_PROFIT_THRESHOLD = float(os.getenv('AUTO_HEDGE_PROFIT_THRESHOLD', '1.0'))  # Profit threshold to trigger auto-hedging (percentage)
AUTO_HEDGE_LOSS_THRESHOLD = float(os.getenv('AUTO_HEDGE_LOSS_THRESHOLD', '1.0'))  # Loss threshold to trigger auto-hedging (percentage)
HEDGE_POSITION_SIZE_RATIO = float(os.getenv('HEDGE_POSITION_SIZE_RATIO', '0.5'))  # Ratio of hedge position size to original position size (0.5 = 50%)

# Signal parameters
RSI_PERIOD = int(os.getenv('RSI_PERIOD', '14'))  # RSI calculation period
RSI_OVERSOLD = int(os.getenv('RSI_OVERSOLD', '30'))  # RSI oversold threshold
RSI_OVERBOUGHT = int(os.getenv('RSI_OVERBOUGHT', '70'))  # RSI overbought threshold

# EMA parameters
EMA_SHORT_PERIOD = int(os.getenv('EMA_SHORT_PERIOD', '20'))  # Short EMA period (default: 20)
EMA_LONG_PERIOD = int(os.getenv('EMA_LONG_PERIOD', '50'))  # Long EMA period (default: 50)

# Bollinger Bands parameters
BB_PERIOD = int(os.getenv('BB_PERIOD', '20'))  # Bollinger Bands period (default: 20)
BB_STD_DEV = float(os.getenv('BB_STD_DEV', '2.0'))  # Number of standard deviations (default: 2.0)

# MACD parameters
MACD_FAST_PERIOD = int(os.getenv('MACD_FAST_PERIOD', '5'))  # Fast EMA period (default: 5)
MACD_SLOW_PERIOD = int(os.getenv('MACD_SLOW_PERIOD', '13'))  # Slow EMA period (default: 13)
MACD_SIGNAL_PERIOD = int(os.getenv('MACD_SIGNAL_PERIOD', '1'))  # Signal EMA period (default: 1)

# Smart Money Concept (SMC) parameters
SMC_LOOKBACK = int(os.getenv('SMC_LOOKBACK', '10'))  # Lookback period for market structure analysis
SMC_ENABLED = os.getenv('SMC_ENABLED', 'TRUE').upper() == 'TRUE'  # Whether to use SMC indicators
FVG_ENTRY_THRESHOLD = float(os.getenv('FVG_ENTRY_THRESHOLD', '0.01'))  # Threshold for FVG-based entries (1% of price)

# Take profit and stop loss settings
TAKE_PROFIT_PERCENT = float(os.getenv('TAKE_PROFIT_PERCENT', '0.6'))  # 0.6% take profit
STOP_LOSS_PERCENT = float(os.getenv('STOP_LOSS_PERCENT', '0.3'))  # 0.3% stop loss
RISK_PERCENTAGE = float(os.getenv('RISK_PERCENTAGE', '1.0'))  # 1% risk per trade

# Daily PnL settings
DAILY_PROFIT_TARGET = float(os.getenv('DAILY_PROFIT_TARGET', '10.0'))  # 10% daily profit target
DAILY_LOSS_LIMIT = float(os.getenv('DAILY_LOSS_LIMIT', '5.0'))  # 5% daily loss limit
PNL_REPORT_INTERVAL = int(os.getenv('PNL_REPORT_INTERVAL', '3600'))  # Send PnL report every hour (3600 seconds)
SEND_INITIAL_PNL_REPORT = os.getenv('SEND_INITIAL_PNL_REPORT', 'FALSE').upper() == 'TRUE'  # Whether to send PnL report when bot starts

# Notification settings
NOTIFY_SIGNALS = os.getenv('NOTIFY_SIGNALS', 'FALSE').upper() == 'TRUE'  # Whether to send signal notifications
NOTIFY_ENTRIES = os.getenv('NOTIFY_ENTRIES', 'TRUE').upper() == 'TRUE'  # Whether to send position entry notifications
NOTIFY_EXITS = os.getenv('NOTIFY_EXITS', 'TRUE').upper() == 'TRUE'  # Whether to send position exit notifications
NOTIFY_PNL = os.getenv('NOTIFY_PNL', 'TRUE').upper() == 'TRUE'  # Whether to send PnL notifications

# Grid Trading settings
GRID_TRADING_ENABLED = os.getenv('GRID_TRADING_ENABLED', 'FALSE').upper() == 'TRUE'  # Whether to use grid trading
GRID_BUY_COUNT = int(os.getenv('GRID_BUY_COUNT', '2'))  # Number of buy grids
GRID_SELL_COUNT = int(os.getenv('GRID_SELL_COUNT', '2'))  # Number of sell grids
GRID_BUY_TRIGGER_PERCENTAGES = [float(x) for x in os.getenv('GRID_BUY_TRIGGER_PERCENTAGES', '1.0,0.8').split(',')]  # Trigger percentages for buy grids
GRID_BUY_STOP_PERCENTAGES = [float(x) for x in os.getenv('GRID_BUY_STOP_PERCENTAGES', '1.05,1.03').split(',')]  # Stop price percentages for buy grids
GRID_BUY_LIMIT_PERCENTAGES = [float(x) for x in os.getenv('GRID_BUY_LIMIT_PERCENTAGES', '1.051,1.031').split(',')]  # Limit price percentages for buy grids
GRID_BUY_QUANTITIES_USDT = [float(x) for x in os.getenv('GRID_BUY_QUANTITIES_USDT', '50,100').split(',')]  # USDT amounts for buy grids
GRID_SELL_TRIGGER_PERCENTAGES = [float(x) for x in os.getenv('GRID_SELL_TRIGGER_PERCENTAGES', '1.05,1.08').split(',')]  # Trigger percentages for sell grids
GRID_SELL_STOP_PERCENTAGES = [float(x) for x in os.getenv('GRID_SELL_STOP_PERCENTAGES', '0.97,0.95').split(',')]  # Stop price percentages for sell grids
GRID_SELL_LIMIT_PERCENTAGES = [float(x) for x in os.getenv('GRID_SELL_LIMIT_PERCENTAGES', '0.969,0.949').split(',')]  # Limit price percentages for sell grids
GRID_SELL_QUANTITIES_PERCENTAGES = [float(x) for x in os.getenv('GRID_SELL_QUANTITIES_PERCENTAGES', '0.5,1.0').split(',')]  # Percentage of available quantity to sell for each grid
GRID_LAST_BUY_PRICE_REMOVAL_THRESHOLD = float(os.getenv('GRID_LAST_BUY_PRICE_REMOVAL_THRESHOLD', '10.0'))  # Minimum value in USDT to keep last buy price

# Bot settings
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '30'))  # Check for signals every 30 seconds
KLINE_INTERVAL = os.getenv('KLINE_INTERVAL', '1m')  # Default candle interval
KLINE_LIMIT = int(os.getenv('KLINE_LIMIT', '100'))  # Number of candles to fetch

# API settings
RECV_WINDOW = int(os.getenv('RECV_WINDOW', '60000'))  # recvWindow parameter for API requests (milliseconds)

# Network settings
USE_PROXY = os.getenv('USE_PROXY', 'FALSE').upper() == 'TRUE'  # Whether to use a proxy for API requests
PROXY_URL = os.getenv('PROXY_URL', '')  # Proxy URL (e.g., 'http://user:pass@host:port')

# Margin percentage rules based on leverage
# lev ≤ 25x margin 5%
# lev 50x margin 4%
# lev 75x margin 3%
# lev 100x margin 2%
# lev > 100x margin 1%
def get_margin_percentage(leverage):
    if leverage <= 25:
        return 5.0
    elif leverage <= 50:
        return 4.0
    elif leverage <= 75:
        return 3.0
    elif leverage <= 100:
        return 2.0
    else:
        return 1.0

# Calculate margin percentage based on configured leverage
MARGIN_PERCENTAGE = get_margin_percentage(LEVERAGE)

# Binance API URLs
# Primary API endpoint only
PRIMARY_BASE_URL = 'https://fapi.binance.com'  # Primary Futures API base URL
FALLBACK_BASE_URLS = []  # No fallback URLs - use only the primary URL
BASE_URL = PRIMARY_BASE_URL  # Default to primary URL

# Trading fee settings
MAKER_FEE_RATE = float(os.getenv('MAKER_FEE_RATE', '0.0002'))  # 0.02% maker fee
TAKER_FEE_RATE = float(os.getenv('TAKER_FEE_RATE', '0.0004'))  # 0.04% taker fee
MIN_PROFIT_AFTER_FEES = float(os.getenv('MIN_PROFIT_AFTER_FEES', '0.05'))  # Minimum profit percentage after fees (0.05%)

# API request settings
API_RETRY_COUNT = int(os.getenv('API_RETRY_COUNT', '3'))  # Number of retries for API requests
API_TIMEOUT = int(os.getenv('API_TIMEOUT', '30'))  # Timeout for API requests in seconds
API_CONNECT_TIMEOUT = int(os.getenv('API_CONNECT_TIMEOUT', '10'))  # Connection timeout in seconds
