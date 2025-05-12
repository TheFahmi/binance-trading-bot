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

# Take profit and stop loss settings
TAKE_PROFIT_PERCENT = float(os.getenv('TAKE_PROFIT_PERCENT', '0.6'))  # 0.6% take profit
STOP_LOSS_PERCENT = float(os.getenv('STOP_LOSS_PERCENT', '0.3'))  # 0.3% stop loss

# Daily PnL settings
DAILY_PROFIT_TARGET = float(os.getenv('DAILY_PROFIT_TARGET', '10.0'))  # 10% daily profit target
DAILY_LOSS_LIMIT = float(os.getenv('DAILY_LOSS_LIMIT', '5.0'))  # 5% daily loss limit
PNL_REPORT_INTERVAL = int(os.getenv('PNL_REPORT_INTERVAL', '3600'))  # Send PnL report every hour (3600 seconds)

# Bot settings
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '30'))  # Check for signals every 30 seconds
KLINE_INTERVAL = os.getenv('KLINE_INTERVAL', '1m')  # Default candle interval
KLINE_LIMIT = int(os.getenv('KLINE_LIMIT', '100'))  # Number of candles to fetch

# API settings
RECV_WINDOW = int(os.getenv('RECV_WINDOW', '60000'))  # recvWindow parameter for API requests (milliseconds)

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
BASE_URL = 'https://fapi.binance.com'  # Futures API base URL
