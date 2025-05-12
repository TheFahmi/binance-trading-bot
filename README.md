# Binance Trading Bot

A Python-based trading bot for Binance Futures with multiple technical indicators including RSI, EMA, Bollinger Bands, MACD (5/13/1), and Smart Money Concept (SMC) analysis.

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
   - MACD (5/13/1) provides early trend detection with prioritized crossing signals
   - RSI identifies overbought/oversold conditions
   - EMA crossovers confirm trend direction
   - Bollinger Bands identify volatility breakouts
   - Smart Money Concept (SMC) analysis for market structure
   - Break of Structure (BOS) detection for trend reversals
   - Fair Value Gap (FVG) identification for support/resistance levels
   - Signal strength scoring system with weighted indicators

9. **24/7 Automatic Operation**
   - All bots run as threads
   - Main loop keeps the program running indefinitely

10. **Web Dashboard Interface**
   - Real-time monitoring of bot status and performance
   - View account balance, open positions, and recent trades
   - Start and stop the bot from the web interface
   - Configure trading mode and symbols through the UI
   - Responsive design works on desktop and mobile devices

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

Run the trading bot:
```
python main.py
```

Run the web dashboard:
```
python web_app.py
```

Then open your browser and navigate to `http://localhost:5000` to access the dashboard.

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
- `SMC_ENABLED`: Whether to use Smart Money Concept indicators (default: TRUE)
- `SMC_LOOKBACK`: Lookback period for market structure analysis (default: 10)
- `FVG_ENTRY_THRESHOLD`: Threshold for FVG-based entries (default: 0.01 or 1% of price)
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
5. **Indicator Combination**: The bot uses a combination of multiple indicators (RSI, candle patterns, EMA crossover, Bollinger Bands, MACD, and Smart Money Concept) to generate stronger signals and reduce false positives.
6. **Smart Money Concept (SMC)**: The bot analyzes market structure to identify trends, reversals, and key price levels using SMC principles. This includes Break of Structure (BOS) detection and Fair Value Gap (FVG) identification.

## Testing

The bot includes a comprehensive test suite to ensure all components work correctly. To run the tests:

```
python run_tests.py
```

The test suite includes:

- **BinanceClient Tests**: Tests API interactions and data handling
- **Indicators Tests**: Tests technical indicators calculations (RSI, EMA, Bollinger Bands, MACD, SMC)
- **PositionManager Tests**: Tests position sizing, account management, and risk controls
- **TelegramNotifier Tests**: Tests notification functionality
- **TradingBot Tests**: Tests the main bot logic and signal processing

Always run the tests after making changes to ensure everything works as expected.

## Logs

The bot logs all activities to both the console and a `bot.log` file.

## Troubleshooting

### Connection Issues

If you experience connection issues with the Binance API, try the following solutions:

1. **Check your internet connection**: Make sure you have a stable internet connection.

2. **Use a proxy**: If you're behind a firewall or in a region with restricted access, you can use a proxy:
   ```
   USE_PROXY=TRUE
   PROXY_URL=http://your-proxy-server:port
   ```

3. **Try fallback endpoints**: The bot automatically tries multiple Binance API endpoints if the primary one fails.

4. **Increase timeouts**: If you have a slow connection, you might need to increase the connection timeouts in the code.

5. **Check Binance API status**: Verify that the Binance API is operational by visiting their status page.

6. **VPN issues**: If you're using a VPN, try connecting without it or switch to a different server.

### Other Common Issues

1. **API key permissions**: Make sure your Binance API key has the correct permissions (Futures trading enabled).

2. **Insufficient balance**: Ensure you have enough balance in your Futures account.

3. **Symbol not found**: Verify that the trading symbol exists and is available for Futures trading.

4. **Rate limiting**: If you're making too many requests, you might get rate-limited. The bot implements exponential backoff to handle this.

## License

MIT
