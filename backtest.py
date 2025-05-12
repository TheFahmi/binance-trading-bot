import os
import time
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import json
from tqdm import tqdm

import config
from binance_client import BinanceClient
from indicators import (
    calculate_rsi, detect_candle_pattern, calculate_ema,
    calculate_bollinger_bands, calculate_macd, check_entry_signal
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("backtest.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class Backtester:
    """Class to run backtests on historical data"""

    def __init__(self, symbol=None, start_date=None, end_date=None, initial_balance=10000):
        """
        Initialize the backtester

        Args:
            symbol: Trading symbol (default from config)
            start_date: Start date for backtest (datetime or string 'YYYY-MM-DD')
            end_date: End date for backtest (datetime or string 'YYYY-MM-DD')
            initial_balance: Initial account balance in USDT
        """
        self.symbol = symbol or config.SYMBOL
        self.client = BinanceClient(symbol=self.symbol)

        # Convert string dates to datetime if needed
        if isinstance(start_date, str):
            self.start_date = datetime.strptime(start_date, '%Y-%m-%d')
        else:
            self.start_date = start_date or (datetime.now() - timedelta(days=30))

        if isinstance(end_date, str):
            self.end_date = datetime.strptime(end_date, '%Y-%m-%d')
        else:
            self.end_date = end_date or datetime.now()

        self.initial_balance = initial_balance
        self.current_balance = initial_balance

        # Trading parameters
        self.leverage = config.LEVERAGE
        self.take_profit_pct = config.TAKE_PROFIT_PERCENT
        self.stop_loss_pct = config.STOP_LOSS_PERCENT

        # State variables
        self.current_position = None  # None, 'LONG', or 'SHORT'
        self.position_size = 0
        self.entry_price = 0
        self.entry_time = None

        # Results
        self.result = BacktestResult(self.symbol, self.start_date, self.end_date, initial_balance)

    def fetch_historical_data(self, interval=None):
        """
        Fetch historical klines data for the specified period

        Args:
            interval: Kline interval (default from config)

        Returns:
            DataFrame with historical data
        """
        interval = interval or config.KLINE_INTERVAL

        logger.info(f"Fetching historical data for {self.symbol} from {self.start_date} to {self.end_date}")

        # Convert dates to milliseconds timestamp
        start_ts = int(self.start_date.timestamp() * 1000)
        end_ts = int(self.end_date.timestamp() * 1000)

        # Fetch data in chunks to avoid API limitations
        all_klines = []
        current_ts = start_ts

        with tqdm(total=end_ts-start_ts, desc="Fetching data") as pbar:
            while current_ts < end_ts:
                try:
                    # Fetch a chunk of data (max 1000 candles per request)
                    params = {
                        'symbol': self.symbol,
                        'interval': interval,
                        'startTime': current_ts,
                        'endTime': end_ts,
                        'limit': 1000
                    }

                    klines = self.client._send_request('GET', '/fapi/v1/klines', params)

                    if not klines or len(klines) == 0:
                        break

                    all_klines.extend(klines)

                    # Update current timestamp for next chunk
                    current_ts = klines[-1][0] + 1

                    # Update progress bar
                    pbar.update(current_ts - pbar.n)

                    # Add a small delay to avoid rate limits
                    time.sleep(0.5)

                except Exception as e:
                    logger.error(f"Error fetching historical data: {str(e)}")
                    time.sleep(5)  # Longer delay on error

        if not all_klines:
            logger.error("Failed to fetch historical data")
            return None

        # Convert to DataFrame
        df = pd.DataFrame(all_klines, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])

        # Convert types
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')
        df['open'] = pd.to_numeric(df['open'])
        df['high'] = pd.to_numeric(df['high'])
        df['low'] = pd.to_numeric(df['low'])
        df['close'] = pd.to_numeric(df['close'])
        df['volume'] = pd.to_numeric(df['volume'])

        logger.info(f"Fetched {len(df)} candles for {self.symbol}")
        return df

    def calculate_position_size(self, price, risk_pct=None):
        """
        Calculate position size based on risk percentage

        Args:
            price: Current price
            risk_pct: Risk percentage (default from config)

        Returns:
            Position size in base currency
        """
        risk_pct = risk_pct or config.RISK_PERCENTAGE

        # Calculate risk amount in USDT
        risk_amount = self.current_balance * (risk_pct / 100)

        # Calculate position size with leverage
        position_size_usdt = risk_amount * self.leverage

        # Convert to base currency
        position_size = position_size_usdt / price

        return position_size

    def enter_position(self, timestamp, side, price, size):
        """
        Enter a trading position

        Args:
            timestamp: Entry timestamp
            side: Position side ('LONG' or 'SHORT')
            price: Entry price
            size: Position size
        """
        if self.current_position is not None:
            logger.warning(f"Already in {self.current_position} position, cannot enter {side}")
            return

        self.current_position = side
        self.position_size = size
        self.entry_price = price
        self.entry_time = timestamp

        # Calculate position value
        position_value = price * size

        # Log entry
        logger.info(f"Entered {side} position at {price} with size {size} ({position_value} USDT)")

        # Add to result
        self.result.add_position(timestamp, side, price, size)

    def exit_position(self, timestamp, price, reason=""):
        """
        Exit the current position

        Args:
            timestamp: Exit timestamp
            price: Exit price
            reason: Reason for exit

        Returns:
            PnL from the trade
        """
        if self.current_position is None:
            logger.warning("No position to exit")
            return 0

        # Calculate PnL
        if self.current_position == 'LONG':
            pnl_pct = ((price - self.entry_price) / self.entry_price) * 100 * self.leverage
            pnl = (price - self.entry_price) * self.position_size * self.leverage
        else:  # SHORT
            pnl_pct = ((self.entry_price - price) / self.entry_price) * 100 * self.leverage
            pnl = (self.entry_price - price) * self.position_size * self.leverage

        # Update balance
        self.current_balance += pnl

        # Log exit
        logger.info(f"Exited {self.current_position} position at {price} with PnL: {pnl:.2f} USDT ({pnl_pct:.2f}%) - {reason}")

        # Add trade to result
        self.result.add_trade(
            self.entry_time, self.entry_price,
            timestamp, price,
            self.position_size, self.current_position,
            pnl, pnl_pct, self.current_balance
        )

        # Reset position
        self.current_position = None
        self.position_size = 0
        self.entry_price = 0
        self.entry_time = None

        return pnl

    def check_take_profit_stop_loss(self, timestamp, price):
        """
        Check if take profit or stop loss has been hit

        Args:
            timestamp: Current timestamp
            price: Current price

        Returns:
            True if position was closed, False otherwise
        """
        if self.current_position is None:
            return False

        # Calculate take profit and stop loss prices
        if self.current_position == 'LONG':
            take_profit_price = self.entry_price * (1 + self.take_profit_pct / 100)
            stop_loss_price = self.entry_price * (1 - self.stop_loss_pct / 100)

            # Check if take profit or stop loss hit
            if price >= take_profit_price:
                self.exit_position(timestamp, take_profit_price, "Take Profit")
                return True
            elif price <= stop_loss_price:
                self.exit_position(timestamp, stop_loss_price, "Stop Loss")
                return True

        else:  # SHORT
            take_profit_price = self.entry_price * (1 - self.take_profit_pct / 100)
            stop_loss_price = self.entry_price * (1 + self.stop_loss_pct / 100)

            # Check if take profit or stop loss hit
            if price <= take_profit_price:
                self.exit_position(timestamp, take_profit_price, "Take Profit")
                return True
            elif price >= stop_loss_price:
                self.exit_position(timestamp, stop_loss_price, "Stop Loss")
                return True

        return False

    def run_backtest(self):
        """
        Run the backtest on historical data

        Returns:
            BacktestResult object with results
        """
        # Fetch historical data
        df = self.fetch_historical_data()

        if df is None or len(df) == 0:
            logger.error("No data available for backtest")
            return self.result

        # Calculate indicators
        logger.info("Calculating indicators...")
        df = calculate_rsi(df)
        df = detect_candle_pattern(df)
        df = calculate_ema(df)
        df = calculate_bollinger_bands(df)
        df = calculate_macd(df)

        # Log indicator values for the last few candles to verify they're calculated correctly
        logger.info("Sample indicator values for the last 3 candles:")
        for i in range(-3, 0):
            candle = df.iloc[i]
            rsi_val = candle.get('rsi', np.nan)
            macd_line_val = candle.get('macd_line', np.nan)
            macd_signal_val = candle.get('macd_signal', np.nan)
            bb_upper_val = candle.get('bb_upper', np.nan)
            bb_lower_val = candle.get('bb_lower', np.nan)

            rsi_str = f"{rsi_val:.2f}" if not pd.isna(rsi_val) else "N/A"
            macd_line_str = f"{macd_line_val:.6f}" if not pd.isna(macd_line_val) else "N/A"
            macd_signal_str = f"{macd_signal_val:.6f}" if not pd.isna(macd_signal_val) else "N/A"
            bb_upper_str = f"{bb_upper_val:.2f}" if not pd.isna(bb_upper_val) else "N/A"
            bb_lower_str = f"{bb_lower_val:.2f}" if not pd.isna(bb_lower_val) else "N/A"

            logger.info(f"Candle {i}: Time={candle['open_time']}, Close={candle['close']:.2f}, "
                       f"RSI={rsi_str}, MACD Line={macd_line_str}, MACD Signal={macd_signal_str}, "
                       f"EMA Cross Up={candle.get('ema_cross_up', False)}, "
                       f"EMA Cross Down={candle.get('ema_cross_down', False)}, "
                       f"BB Upper={bb_upper_str}, BB Lower={bb_lower_str}")

        # Initialize equity curve with initial balance
        self.result.add_equity_point(df.iloc[0]['open_time'], self.current_balance)

        # Iterate through each candle
        logger.info(f"Running backtest on {len(df)} candles")

        # Track signal counts for debugging
        signal_counts = {'LONG': 0, 'SHORT': 0, 'NONE': 0}

        for i in tqdm(range(1, len(df)), desc="Backtesting"):
            try:
                # Get current candle
                candle = df.iloc[i]

                # Update timestamp
                timestamp = candle['open_time']

                # Check for take profit or stop loss if in a position
                if self.current_position is not None:
                    # Use high/low prices to check for TP/SL hits
                    if self.current_position == 'LONG':
                        # For long positions, check high for TP and low for SL
                        if candle['high'] >= self.entry_price * (1 + self.take_profit_pct / 100):
                            # Take profit hit
                            self.exit_position(timestamp, self.entry_price * (1 + self.take_profit_pct / 100), "Take Profit")
                        elif candle['low'] <= self.entry_price * (1 - self.stop_loss_pct / 100):
                            # Stop loss hit
                            self.exit_position(timestamp, self.entry_price * (1 - self.stop_loss_pct / 100), "Stop Loss")
                    else:  # SHORT
                        # For short positions, check low for TP and high for SL
                        if candle['low'] <= self.entry_price * (1 - self.take_profit_pct / 100):
                            # Take profit hit
                            self.exit_position(timestamp, self.entry_price * (1 - self.take_profit_pct / 100), "Take Profit")
                        elif candle['high'] >= self.entry_price * (1 + self.stop_loss_pct / 100):
                            # Stop loss hit
                            self.exit_position(timestamp, self.entry_price * (1 + self.stop_loss_pct / 100), "Stop Loss")

                # Check for entry signals if not in a position
                if self.current_position is None:
                    # Create a subset of data up to the current candle for signal checking
                    df_subset = df.iloc[:i+1].copy()

                    # Check for entry signal
                    signal = check_entry_signal(df_subset)

                    # Track signal counts
                    if signal == 'LONG':
                        signal_counts['LONG'] += 1
                    elif signal == 'SHORT':
                        signal_counts['SHORT'] += 1
                    else:
                        signal_counts['NONE'] += 1

                    # Log signal for debugging (every 50 candles to avoid excessive logging)
                    if i % 50 == 0 or signal is not None:
                        rsi_val = candle.get('rsi', np.nan)
                        rsi_str = f"{rsi_val:.2f}" if not pd.isna(rsi_val) else "N/A"
                        logger.debug(f"Candle {i} ({timestamp}): Signal = {signal}, "
                                    f"RSI = {rsi_str}, "
                                    f"MACD Cross Up = {candle.get('macd_cross_up', False)}, "
                                    f"MACD Cross Down = {candle.get('macd_cross_down', False)}, "
                                    f"EMA Cross Up = {candle.get('ema_cross_up', False)}, "
                                    f"EMA Cross Down = {candle.get('ema_cross_down', False)}")

                    if signal in ['LONG', 'SHORT']:
                        # Calculate position size
                        price = candle['close']
                        size = self.calculate_position_size(price)

                        # Enter position
                        self.enter_position(timestamp, signal, price, size)

                # Add equity point at the end of each day (using close time)
                if i == len(df) - 1 or df.iloc[i+1]['open_time'].day != candle['open_time'].day:
                    # Calculate current equity
                    if self.current_position is None:
                        equity = self.current_balance
                    else:
                        # Add unrealized PnL
                        if self.current_position == 'LONG':
                            unrealized_pnl = (candle['close'] - self.entry_price) * self.position_size * self.leverage
                        else:  # SHORT
                            unrealized_pnl = (self.entry_price - candle['close']) * self.position_size * self.leverage
                        equity = self.current_balance + unrealized_pnl

                    self.result.add_equity_point(candle['close_time'], equity)

            except Exception as e:
                logger.error(f"Error in backtest at candle {i}: {str(e)}")
                continue

        # Close any open position at the end
        if self.current_position is not None:
            last_candle = df.iloc[-1]
            self.exit_position(last_candle['close_time'], last_candle['close'], "End of Backtest")

        # Calculate performance metrics
        self.result.calculate_metrics()

        # Log signal counts
        logger.info(f"Signal counts - LONG: {signal_counts['LONG']}, SHORT: {signal_counts['SHORT']}, NONE: {signal_counts['NONE']}")

        logger.info(f"Backtest completed with {self.result.total_trades} trades")
        logger.info(f"Final balance: {self.current_balance:.2f} USDT")
        logger.info(f"Total profit: {self.result.total_profit:.2f} USDT ({self.result.total_profit_pct:.2f}%)")
        logger.info(f"Win rate: {self.result.win_rate:.2f}")
        logger.info(f"Max drawdown: {self.result.max_drawdown:.2f} USDT ({self.result.max_drawdown_pct*100:.2f}%)")

        return self.result

class BacktestResult:
    """Class to store and analyze backtest results"""

    def __init__(self, symbol, start_date, end_date, initial_balance):
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.initial_balance = initial_balance
        self.final_balance = initial_balance
        self.trades = []
        self.balance_history = [(start_date, initial_balance)]
        self.positions = []
        self.equity_curve = []

        # Performance metrics
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.win_rate = 0
        self.profit_factor = 0
        self.max_drawdown = 0
        self.max_drawdown_pct = 0
        self.total_profit = 0
        self.total_profit_pct = 0
        self.sharpe_ratio = 0

    def add_trade(self, entry_time, entry_price, exit_time, exit_price,
                  position_size, side, pnl, pnl_pct, balance_after):
        """Add a trade to the results"""
        trade = {
            'entry_time': entry_time,
            'entry_price': entry_price,
            'exit_time': exit_time,
            'exit_price': exit_price,
            'position_size': position_size,
            'side': side,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'balance_after': balance_after
        }
        self.trades.append(trade)
        self.balance_history.append((exit_time, balance_after))
        self.final_balance = balance_after

    def add_position(self, timestamp, side, price, size):
        """Add a position to the history"""
        self.positions.append({
            'timestamp': timestamp,
            'side': side,
            'price': price,
            'size': size
        })

    def add_equity_point(self, timestamp, equity):
        """Add a point to the equity curve"""
        self.equity_curve.append((timestamp, equity))

    def calculate_metrics(self):
        """Calculate performance metrics"""
        self.total_trades = len(self.trades)

        if self.total_trades == 0:
            logger.warning("No trades executed in backtest")
            return

        # Calculate win rate
        self.winning_trades = sum(1 for trade in self.trades if trade['pnl'] > 0)
        self.losing_trades = sum(1 for trade in self.trades if trade['pnl'] <= 0)
        self.win_rate = self.winning_trades / self.total_trades if self.total_trades > 0 else 0

        # Calculate profit factor
        total_gains = sum(trade['pnl'] for trade in self.trades if trade['pnl'] > 0)
        total_losses = sum(abs(trade['pnl']) for trade in self.trades if trade['pnl'] < 0)
        self.profit_factor = total_gains / total_losses if total_losses > 0 else float('inf')

        # Calculate drawdown
        peak_balance = self.initial_balance
        max_drawdown = 0
        max_drawdown_pct = 0

        for _, balance in self.balance_history:
            if balance > peak_balance:
                peak_balance = balance
            else:
                drawdown = peak_balance - balance
                drawdown_pct = drawdown / peak_balance if peak_balance > 0 else 0
                max_drawdown = max(max_drawdown, drawdown)
                max_drawdown_pct = max(max_drawdown_pct, drawdown_pct)

        self.max_drawdown = max_drawdown
        self.max_drawdown_pct = max_drawdown_pct

        # Calculate total profit
        self.total_profit = self.final_balance - self.initial_balance
        self.total_profit_pct = (self.total_profit / self.initial_balance) * 100

        # Calculate Sharpe ratio (simplified)
        if len(self.trades) > 1:
            returns = [trade['pnl_pct'] for trade in self.trades]
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            self.sharpe_ratio = mean_return / std_return if std_return > 0 else 0

    def save_results(self, output_dir='backtest_results'):
        """Save backtest results to files"""
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Create a timestamp for the filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_filename = f"{self.symbol}_{timestamp}"

        # Save trades to CSV
        trades_df = pd.DataFrame(self.trades)
        trades_df.to_csv(f"{output_dir}/{base_filename}_trades.csv", index=False)

        # Save metrics to JSON
        metrics = {
            'symbol': self.symbol,
            'start_date': self.start_date.strftime('%Y-%m-%d'),
            'end_date': self.end_date.strftime('%Y-%m-%d'),
            'initial_balance': self.initial_balance,
            'final_balance': self.final_balance,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'max_drawdown': self.max_drawdown,
            'max_drawdown_pct': self.max_drawdown_pct,
            'total_profit': self.total_profit,
            'total_profit_pct': self.total_profit_pct,
            'sharpe_ratio': self.sharpe_ratio
        }

        with open(f"{output_dir}/{base_filename}_metrics.json", 'w') as f:
            json.dump(metrics, f, indent=4)

        logger.info(f"Backtest results saved to {output_dir}/{base_filename}")
        return f"{output_dir}/{base_filename}"

    def plot_results(self, output_dir='backtest_results'):
        """Plot backtest results"""
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Create a timestamp for the filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_filename = f"{self.symbol}_{timestamp}"

        # Plot equity curve
        plt.figure(figsize=(12, 6))
        dates = [x[0] for x in self.equity_curve]
        equity = [x[1] for x in self.equity_curve]
        plt.plot(dates, equity)
        plt.title(f'Equity Curve - {self.symbol}')
        plt.xlabel('Date')
        plt.ylabel('Equity (USDT)')
        plt.grid(True)
        plt.savefig(f"{output_dir}/{base_filename}_equity.png")

        # Plot drawdown
        plt.figure(figsize=(12, 6))
        peak = self.initial_balance
        drawdown = []
        for _, balance in self.balance_history:
            if balance > peak:
                peak = balance
                drawdown.append(0)
            else:
                dd_pct = (peak - balance) / peak * 100
                drawdown.append(dd_pct)

        plt.plot(range(len(drawdown)), drawdown)
        plt.title(f'Drawdown - {self.symbol}')
        plt.xlabel('Trade Number')
        plt.ylabel('Drawdown (%)')
        plt.grid(True)
        plt.savefig(f"{output_dir}/{base_filename}_drawdown.png")

        logger.info(f"Backtest plots saved to {output_dir}/{base_filename}")
        return f"{output_dir}/{base_filename}"

def run_backtest_for_symbol(symbol, start_date, end_date, initial_balance=10000):
    """
    Run a backtest for a specific symbol

    Args:
        symbol: Trading symbol
        start_date: Start date (string 'YYYY-MM-DD' or datetime)
        end_date: End date (string 'YYYY-MM-DD' or datetime)
        initial_balance: Initial account balance in USDT

    Returns:
        BacktestResult object
    """
    backtester = Backtester(symbol, start_date, end_date, initial_balance)
    result = backtester.run_backtest()

    # Save and plot results
    result.save_results()
    result.plot_results()

    return result

def run_backtest_for_multiple_symbols(symbols, start_date, end_date, initial_balance=10000):
    """
    Run backtests for multiple symbols

    Args:
        symbols: List of trading symbols
        start_date: Start date (string 'YYYY-MM-DD' or datetime)
        end_date: End date (string 'YYYY-MM-DD' or datetime)
        initial_balance: Initial account balance in USDT

    Returns:
        Dictionary of symbol -> BacktestResult
    """
    results = {}

    for symbol in symbols:
        logger.info(f"Running backtest for {symbol}")
        result = run_backtest_for_symbol(symbol, start_date, end_date, initial_balance)
        results[symbol] = result

    return results

def compare_backtest_results(results):
    """
    Compare backtest results for multiple symbols

    Args:
        results: Dictionary of symbol -> BacktestResult

    Returns:
        DataFrame with comparison metrics
    """
    comparison = []

    for symbol, result in results.items():
        comparison.append({
            'symbol': symbol,
            'total_trades': result.total_trades,
            'win_rate': result.win_rate,
            'profit_factor': result.profit_factor,
            'total_profit': result.total_profit,
            'total_profit_pct': result.total_profit_pct,
            'max_drawdown_pct': result.max_drawdown_pct * 100,
            'sharpe_ratio': result.sharpe_ratio
        })

    df = pd.DataFrame(comparison)

    # Sort by total profit percentage
    df = df.sort_values('total_profit_pct', ascending=False)

    return df

def main():
    """
    Main function to run backtest from command line
    """
    import argparse

    parser = argparse.ArgumentParser(description='Run backtest for trading strategy')
    parser.add_argument('--symbol', type=str, default=config.SYMBOL, help='Trading symbol')
    parser.add_argument('--start', type=str, required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, default=None, help='End date (YYYY-MM-DD), defaults to today')
    parser.add_argument('--balance', type=float, default=10000, help='Initial balance in USDT')
    parser.add_argument('--multi', action='store_true', help='Run backtest for multiple symbols')
    parser.add_argument('--min-volume', type=float, default=config.MIN_VOLUME_USDT, help='Minimum 24h volume in USDT for symbol selection')
    parser.add_argument('--limit', type=int, default=5, help='Maximum number of symbols to test in multi mode')

    args = parser.parse_args()

    if args.multi:
        # Get high volume pairs
        client = BinanceClient()
        symbols = client.get_high_volume_pairs(args.min_volume, args.limit)

        if not symbols:
            logger.error("Failed to get high volume pairs")
            return

        logger.info(f"Running backtest for {len(symbols)} symbols: {', '.join(symbols)}")

        results = run_backtest_for_multiple_symbols(symbols, args.start, args.end, args.balance)

        # Compare results
        comparison = compare_backtest_results(results)
        print("\nBacktest Results Comparison:")
        print(comparison.to_string(index=False))

    else:
        # Run backtest for single symbol
        logger.info(f"Running backtest for {args.symbol}")

        result = run_backtest_for_symbol(args.symbol, args.start, args.end, args.balance)

        # Print summary
        print("\nBacktest Summary:")
        print(f"Symbol: {args.symbol}")
        print(f"Period: {args.start} to {args.end or 'today'}")
        print(f"Initial Balance: {args.balance} USDT")
        print(f"Final Balance: {result.final_balance:.2f} USDT")
        print(f"Total Profit: {result.total_profit:.2f} USDT ({result.total_profit_pct:.2f}%)")
        print(f"Total Trades: {result.total_trades}")
        print(f"Win Rate: {result.win_rate:.2f}")
        print(f"Profit Factor: {result.profit_factor:.2f}")
        print(f"Max Drawdown: {result.max_drawdown:.2f} USDT ({result.max_drawdown_pct*100:.2f}%)")
        print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")

if __name__ == "__main__":
    main()
