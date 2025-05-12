# Binance Trading Bot

A Python-based trading bot for Binance Futures with multiple technical indicators including RSI, EMA, Bollinger Bands, and MACD (5/13/1).

## Features

1. **Signal Checking Every 30 Seconds**
   - Automatically checks for trading signals every 30 seconds
   - Takes positions when conditions are met

2. **Multiple Technical Indicators**
   - RSI + Candle Pattern:
     - LONG signal: RSI < 30 + green candle
     - SHORT signal: RSI > 70 + red candle
   - EMA Crossover (20/50):
     - LONG signal: EMA 20 crosses above EMA 50
     - SHORT signal: EMA 20 crosses below EMA 50
   - Bollinger Bands Breakout:
     - LONG signal: Price breaks above upper band
     - SHORT signal: Price breaks below lower band
   - MACD (5/13/1):
     - LONG signal: MACD line crosses above signal line or MACD line crosses above zero
     - SHORT signal: MACD line crosses below signal line or MACD line crosses below zero
   - Signal strength: At least 2 out of 5 indicators must agree for entry

3. **Automatic Position Sizing Based on Account Balance**
   - Uses a percentage of your account balance for position sizing
   - Calculates margin amount based on leverage:
     - Leverage ≤ 25x: 5% margin
     - Leverage 50x: 4% margin
     - Leverage 75x: 3% margin
     - Leverage 100x: 2% margin
     - Leverage > 100x: 1% margin
   - Position sizing formula: `(account_balance * position_size_percent * margin_percentage * leverage) / market_price`
   - Respects symbol precision requirements
   - Provides detailed position size information in notifications

4. **Automatic SL/TP Management**
   - Take Profit (TP): +0.6% from entry, using TAKE_PROFIT_MARKET
   - Stop Loss (SL): -0.3% from entry, using STOP_MARKET
   - Prices automatically rounded according to each coin's precision
   - All positions use positionSide='LONG' or 'SHORT' to support hedge mode

5. **Telegram Notifications**
   - All important actions (executed orders, errors, TP/SL) sent to Telegram
   - Uses TELEGRAM_TOKEN and TELEGRAM_CHAT_ID for configuration

6. **Advanced Hedge Mode Support**
   - Supports both hedge mode and one-way mode
   - In hedge mode, can hold both LONG and SHORT positions simultaneously
   - Configurable to allow or disallow both positions on the same pair
   - Automatically sets position mode based on configuration
   - Auto-hedging feature to automatically hedge positions when they reach profit/loss thresholds
   - Customizable hedge position size ratio (e.g., 50% of original position)
   - Combined PnL tracking for hedged positions

7. **Daily PnL Tracking and Management**
   - Tracks daily profit and loss
   - Automatically stops trading when daily profit target is reached
   - Automatically stops trading when daily loss limit is exceeded
   - Sends periodic PnL reports via Telegram
   - Resets PnL tracking at the start of each new day

8. **Advanced Technical Analysis**
   - Combines multiple indicators for more reliable signals
   - MACD (5/13/1) provides early trend detection
   - RSI identifies overbought/oversold conditions
   - EMA crossovers confirm trend direction
   - Bollinger Bands identify volatility breakouts
   - Signal strength scoring system (requires at least 2 out of 5 indicators to agree)

9. **24/7 Automatic Operation**
   - All bots run as threads
   - Main loop keeps the program running indefinitely

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/binance-bot.git
   cd binance-bot
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Create a `.env` file based on the `.env.example` template:
   ```
   cp .env.example .env
   ```

4. Edit the `.env` file with your Binance API keys and other settings.

## Usage

Run the bot:
```
python main.py
```

## Configuration

All configuration is done through environment variables or the `.env` file:

- `BINANCE_API_KEY` and `BINANCE_API_SECRET`: Your Binance API credentials
- `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID`: For Telegram notifications
- `TRADING_SYMBOL`: The trading pair (default: BTCUSDT)
- `LEVERAGE`: Trading leverage (default: 10)
- `POSITION_SIZE_PERCENT`: Percentage of account balance to use (default: 5%)
- `HEDGE_MODE`: Whether to use hedge mode (default: TRUE)
- `ALLOW_BOTH_POSITIONS`: Whether to allow both LONG and SHORT positions on the same pair (default: TRUE)
- `AUTO_HEDGE`: Whether to automatically hedge positions (default: FALSE)
- `AUTO_HEDGE_PROFIT_THRESHOLD`: Profit threshold to trigger auto-hedging (default: 1.0%)
- `AUTO_HEDGE_LOSS_THRESHOLD`: Loss threshold to trigger auto-hedging (default: 1.0%)
- `HEDGE_POSITION_SIZE_RATIO`: Ratio of hedge position size to original position (default: 0.5)
- `RSI_PERIOD`, `RSI_OVERSOLD`, `RSI_OVERBOUGHT`: RSI settings
- `EMA_SHORT_PERIOD`, `EMA_LONG_PERIOD`: EMA periods (default: 20/50)
- `BB_PERIOD`, `BB_STD_DEV`: Bollinger Bands settings (period and standard deviation)
- `MACD_FAST_PERIOD`, `MACD_SLOW_PERIOD`, `MACD_SIGNAL_PERIOD`: MACD settings (default: 5/13/1)
- `TAKE_PROFIT_PERCENT` and `STOP_LOSS_PERCENT`: TP/SL settings
- `DAILY_PROFIT_TARGET`: Daily profit target in percentage (default: 5%)
- `DAILY_LOSS_LIMIT`: Daily loss limit in percentage (default: 3%)
- `PNL_REPORT_INTERVAL`: How often to send PnL reports in seconds (default: 3600)
- `CHECK_INTERVAL`: How often to check for signals (in seconds)
- `KLINE_INTERVAL`: Candle interval (e.g., 1m, 5m, 15m)

## Important Notes

1. **API Key Permissions**: Your Binance API key needs futures trading permissions.
2. **Risk Warning**: Trading cryptocurrencies involves significant risk. Use this bot at your own risk.
3. **Testing**: Always test with small amounts before using larger position sizes.
4. **MACD Configuration**: The bot uses MACD with parameters 5/13/1 (fast EMA period: 5, slow EMA period: 13, signal period: 1) which is more responsive than the traditional 12/26/9 settings. This helps catch trends earlier but may generate more false signals in choppy markets.
5. **Indicator Combination**: The bot uses a combination of 5 different indicators (RSI, candle patterns, EMA crossover, Bollinger Bands, and MACD) to generate stronger signals and reduce false positives.

## Testing

The bot includes a comprehensive test suite to ensure all components work correctly. To run the tests:

```
python run_tests.py
```

The test suite includes:

- **BinanceClient Tests**: Tests API interactions and data handling
- **Indicators Tests**: Tests technical indicators calculations (RSI, EMA, Bollinger Bands, MACD)
- **PositionManager Tests**: Tests position sizing, account management, and risk controls
- **TelegramNotifier Tests**: Tests notification functionality
- **TradingBot Tests**: Tests the main bot logic and signal processing

Always run the tests after making changes to ensure everything works as expected.

## Logs

The bot logs all activities to both the console and a `bot.log` file.

## License

MIT
