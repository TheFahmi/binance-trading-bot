import time
import logging
import threading
import traceback
from datetime import datetime
import pandas as pd

import config
from binance_client import BinanceClient
from indicators import (
    calculate_rsi, detect_candle_pattern, calculate_ema,
    calculate_bollinger_bands, calculate_macd, check_entry_signal
)
from smc_indicators import (
    detect_market_structure, detect_fair_value_gaps
)
from position_manager import PositionManager
from telegram_notifier import TelegramNotifier

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

class TradingBot:
    def __init__(self, symbol=None):
        self.symbol = symbol or config.SYMBOL
        self.client = BinanceClient(symbol=self.symbol)
        self.position_manager = PositionManager(self.client)
        self.telegram = TelegramNotifier()

        # Trading state
        self.is_trading_allowed = True
        self.is_running = True  # Flag to control bot lifecycle
        self.daily_pnl_last_check = 0
        self.start_of_day = self._get_start_of_day()

        # Set position mode (hedge or one-way)
        try:
            if config.HEDGE_MODE:
                logger.info(f"Setting position mode to hedge mode for {self.symbol}")
                self.client.set_position_mode(True)
            else:
                logger.info(f"Setting position mode to one-way mode for {self.symbol}")
                self.client.set_position_mode(False)

            # Verify position mode
            is_hedge_mode = self.client.get_position_mode()
            logger.info(f"Position mode for {self.symbol}: {'Hedge' if is_hedge_mode else 'One-way'}")
        except Exception as e:
            error_msg = f"Failed to set position mode for {self.symbol}: {str(e)}"
            logger.error(error_msg)
            self.telegram.notify_error(error_msg)

        # Get maximum allowed leverage and set it
        try:
            max_leverage = self.client.get_max_leverage(self.symbol)
            target_leverage = min(config.LEVERAGE, max_leverage)

            # Set leverage with fallback to lower values if needed
            leverage_response = self.client.set_leverage(target_leverage, self.symbol)
            actual_leverage = leverage_response.get('leverage', target_leverage)

            logger.info(f"Leverage set to {actual_leverage}x for {self.symbol} (requested: {config.LEVERAGE}x, max allowed: {max_leverage}x)")

            # Store the actual leverage for later use
            self.leverage = actual_leverage
        except Exception as e:
            error_msg = f"Failed to set leverage for {self.symbol}: {str(e)}"
            logger.error(error_msg)
            self.telegram.notify_error(error_msg)

            # Default to a safe leverage value
            self.leverage = 1
            logger.info(f"Using default leverage of 1x for {self.symbol} due to error")

    def _get_start_of_day(self):
        """Get the timestamp for the start of the current day in milliseconds"""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        return int(datetime(now.year, now.month, now.day, tzinfo=timezone.utc).timestamp() * 1000)

    def check_daily_pnl(self):
        """
        Check daily PnL and take action if profit target or loss limit is reached

        Returns:
            bool: True if trading should continue, False if it should stop
        """
        try:
            # Get daily PnL with error handling
            pnl_summary = self.client.get_daily_pnl(self.start_of_day)

            # Check if it's time to send a periodic PnL report
            current_time = int(time.time())
            if current_time - self.daily_pnl_last_check >= config.PNL_REPORT_INTERVAL:
                self.telegram.notify_daily_pnl(pnl_summary)
                self.daily_pnl_last_check = current_time
                logger.info(f"Daily PnL report sent for {self.symbol}: {pnl_summary['pnl_percentage']:.2f}%")

            # Check if profit target is reached
            if pnl_summary['pnl_percentage'] >= config.DAILY_PROFIT_TARGET:
                logger.info(f"Daily profit target reached for {self.symbol}: {pnl_summary['pnl_percentage']:.2f}% >= {config.DAILY_PROFIT_TARGET}%")

                # Add warning if the percentage is exactly equal to the target (might be capped)
                if pnl_summary['pnl_percentage'] == config.DAILY_PROFIT_TARGET:
                    logger.warning(f"PnL percentage is exactly equal to the target. This might be due to capping in the get_daily_pnl method.")

                self.telegram.notify_profit_target_reached(pnl_summary)
                return False

            # Check if loss limit is reached
            if pnl_summary['pnl_percentage'] <= -config.DAILY_LOSS_LIMIT:
                logger.info(f"Daily loss limit reached for {self.symbol}: {pnl_summary['pnl_percentage']:.2f}% <= -{config.DAILY_LOSS_LIMIT}%")
                self.telegram.notify_loss_limit_reached(pnl_summary)
                return False

            return True

        except Exception as e:
            error_msg = f"Error checking daily PnL for {self.symbol}: {str(e)}"
            logger.error(error_msg)

            # Only notify about serious errors, not recvWindow issues
            if "recvWindow" not in str(e):
                self.telegram.notify_error(error_msg)

            return True  # Continue trading if there's an error checking PnL

    def check_for_new_day(self):
        """
        Check if a new day has started and reset daily tracking if needed
        """
        new_day_start = self._get_start_of_day()

        if new_day_start > self.start_of_day:
            logger.info("New day detected, resetting daily PnL tracking")
            self.start_of_day = new_day_start
            self.is_trading_allowed = True
            self.daily_pnl_last_check = 0

            # Send a message that trading is resumed for the new day
            self.telegram.send_message("🔄 <b>NEW DAY</b> - Trading resumed with fresh PnL tracking")

            # Send initial PnL report for the new day if configured to do so
            if config.SEND_INITIAL_PNL_REPORT:
                try:
                    pnl_summary = self.client.get_daily_pnl(self.start_of_day)
                    self.telegram.notify_daily_pnl(pnl_summary)
                except Exception as e:
                    logger.error(f"Error getting initial PnL for new day: {str(e)}")

            # Reset PnL check time
            self.daily_pnl_last_check = int(time.time())

    def check_and_enter_position(self):
        """
        Check for entry signals and enter positions if conditions are met
        """
        try:
            # Get market data with enhanced error handling
            try:
                df = self.client.get_klines(self.symbol)

                # Check if we got valid data
                if df.empty or len(df) < config.KLINE_LIMIT * 0.5:  # If we got less than half the requested candles
                    logger.warning(f"Received incomplete klines data for {self.symbol}. Got {len(df)} candles, expected {config.KLINE_LIMIT}.")
                    # If we have too few candles, skip this cycle
                    if len(df) < 30:  # Need at least 30 candles for reliable indicators
                        logger.error(f"Insufficient data for {self.symbol}. Skipping this cycle.")
                        return

            except Exception as e:
                logger.error(f"Failed to get klines data for {self.symbol}: {str(e)}")
                # Notify about the error but don't raise, so the bot can continue running
                self.telegram.notify_error(f"Failed to get market data for {self.symbol}: {str(e)}\nBot will retry on next cycle.")
                return

            # Calculate traditional indicators
            try:
                df = calculate_rsi(df)
                df = detect_candle_pattern(df)
                df = calculate_ema(df)
                df = calculate_bollinger_bands(df)
                df = calculate_macd(df)

                # Calculate Smart Money Concept (SMC) indicators
                df = detect_market_structure(df)
                df = detect_fair_value_gaps(df)
            except Exception as e:
                logger.error(f"Error calculating indicators for {self.symbol}: {str(e)}")
                self.telegram.notify_error(f"Error calculating indicators for {self.symbol}: {str(e)}")
                return

            # Check for entry signal with SMC indicators
            try:
                signal = check_entry_signal(df, use_smc=True)
            except Exception as e:
                logger.error(f"Error checking entry signal for {self.symbol}: {str(e)}")
                self.telegram.notify_error(f"Error checking entry signal for {self.symbol}: {str(e)}")
                return

            # Log the current state
            latest = df.iloc[-1]

            # Basic indicators log
            basic_log = (
                f"Symbol: {self.symbol}, RSI: {latest['rsi']:.2f}, "
                f"Candle: {'Green' if latest['is_green'] else 'Red' if latest['is_red'] else 'Neutral'}, "
                f"EMA: {latest[f'ema_{config.EMA_SHORT_PERIOD}']:.2f}/{latest[f'ema_{config.EMA_LONG_PERIOD}']:.2f}, "
                f"BB: {latest['bb_percent_b']:.2f}, "
                f"MACD: {latest['macd_line']:.4f}/{latest['macd_signal']:.4f}"
            )

            # SMC indicators log
            # Check for nearest FVGs
            has_bullish_fvg = not pd.isna(latest.get('nearest_bullish_fvg', pd.NA))
            has_bearish_fvg = not pd.isna(latest.get('nearest_bearish_fvg', pd.NA))

            fvg_status = "None"
            if has_bullish_fvg and has_bearish_fvg:
                fvg_status = "Both"
            elif has_bullish_fvg:
                fvg_status = "Bullish"
            elif has_bearish_fvg:
                fvg_status = "Bearish"

            smc_log = (
                f"Market Structure: {latest['market_structure']}, "
                f"BOS: {'Bullish' if latest['bos_bullish'] else 'Bearish' if latest['bos_bearish'] else 'None'}, "
                f"FVG: {fvg_status}"
            )

            # Log everything
            logger.info(f"{basic_log}, {smc_log}, Signal: {signal or 'WAIT'}")

            # Check if we should hedge an existing position
            should_hedge, hedge_side, pnl_info = self.position_manager.should_hedge_position(self.symbol)

            # If we should hedge, override the signal
            if should_hedge and hedge_side:
                logger.info(f"Auto-hedging triggered for {self.symbol}. Entering {hedge_side} position.")
                signal = hedge_side

                # Notify about auto-hedging
                self.telegram.notify_auto_hedge(hedge_side, pnl_info)

            # If no signal, do nothing
            if not signal:
                return

            # Prepare indicator values for notification
            indicator_values = latest.to_dict()

            # Add signal strength information
            long_signals = 0
            short_signals = 0

            # Count signal strengths (same logic as in check_entry_signal)
            if latest['rsi'] < config.RSI_OVERSOLD and latest['is_green']:
                long_signals += 1
            elif latest['rsi'] > config.RSI_OVERBOUGHT and latest['is_red']:
                short_signals += 1

            if latest['ema_cross_up']:
                long_signals += 1
            elif latest['ema_cross_down']:
                short_signals += 1

            if latest['bb_breakout_up']:
                long_signals += 1
            elif latest['bb_breakout_down']:
                short_signals += 1

            # Check MACD crossover
            if 'macd_cross_up' in latest and latest['macd_cross_up']:
                long_signals += 1
            elif 'macd_cross_down' in latest and latest['macd_cross_down']:
                short_signals += 1

            # Check MACD zero line crossover
            if 'macd_zero_cross_up' in latest and latest['macd_zero_cross_up']:
                long_signals += 1
            elif 'macd_zero_cross_down' in latest and latest['macd_zero_cross_down']:
                short_signals += 1

            indicator_values['signal_strength'] = long_signals if signal == 'LONG' else short_signals

            # Notify about the signal with indicator details (only if not auto-hedging)
            if not should_hedge:
                self.telegram.notify_signal(signal, indicator_values)

            # Check if we can enter a position for this side
            if not self.position_manager.can_enter_position(signal, self.symbol):
                if self.position_manager.has_open_position(signal, self.symbol):
                    logger.info(f"Already have an open {signal} position for {self.symbol}. Skipping.")
                else:
                    opposite_side = 'SHORT' if signal == 'LONG' else 'LONG'
                    if self.position_manager.has_open_position(opposite_side, self.symbol):
                        if config.HEDGE_MODE and not config.ALLOW_BOTH_POSITIONS:
                            logger.info(f"Already have an open {opposite_side} position for {self.symbol} and ALLOW_BOTH_POSITIONS is disabled. Skipping.")
                        elif not config.HEDGE_MODE:
                            logger.info(f"Already have an open {opposite_side} position for {self.symbol} and hedge mode is disabled. Skipping.")
                return

            # Get current price
            current_price = self.client.get_current_price(self.symbol)

            # Calculate position size
            if should_hedge:
                # For auto-hedging, calculate size based on the original position
                original_position = pnl_info['long_position'] if hedge_side == 'SHORT' else pnl_info['short_position']
                quantity = self.position_manager.calculate_hedge_position_size(original_position, self.symbol)
            else:
                # For normal entry, calculate size based on account balance
                quantity = self.position_manager.calculate_position_size(
                    price=current_price,
                    symbol=self.symbol,
                    leverage=self.leverage
                )

            # If quantity is 0, we can't enter the position
            if quantity == 0:
                logger.info(f"Calculated position size is 0 for {self.symbol}. Skipping.")
                return

            # Determine order side based on position side
            order_side = 'BUY' if signal == 'LONG' else 'SELL'

            # Place market order with error handling
            try:
                order = self.client.place_market_order(
                    side=order_side,
                    quantity=quantity,
                    position_side=signal,
                    symbol=self.symbol
                )
                logger.info(f"Placed {signal} order: {order}")
            except Exception as e:
                error_msg = f"Failed to place {signal} market order: {str(e)}"
                logger.error(error_msg)
                self.telegram.notify_error(error_msg)
                return  # Don't continue if market order fails

            # Calculate TP and SL prices
            tp_price = self.position_manager.calculate_take_profit_price(current_price, signal)
            sl_price = self.position_manager.calculate_stop_loss_price(current_price, signal)

            # Create position info dictionary for fee calculation
            position_info = {
                'entry_price': current_price,
                'position_amt': quantity,
                'position_side': signal
            }

            # Check if the take profit price would be profitable after fees
            is_profitable, profit_info = self.position_manager.is_profitable_after_fees(
                position_info=position_info,
                current_price=tp_price,
                symbol=self.symbol
            )

            # If not profitable after fees, adjust the take profit price
            if not is_profitable and profit_info:
                # Store the original TP price for notification
                original_tp_price = tp_price

                logger.warning(
                    f"Take profit price {tp_price} would not be profitable after fees. "
                    f"Raw profit: {profit_info['raw_profit']:.6f}, Fees: {profit_info['total_fees']:.6f}, "
                    f"Net profit: {profit_info['net_profit']:.6f}"
                )

                # Calculate a new take profit price that would be profitable after fees
                # For LONG positions, we need a higher price; for SHORT positions, we need a lower price
                if signal == 'LONG':
                    # Increase the take profit percentage
                    adjusted_tp_percent = config.TAKE_PROFIT_PERCENT + config.MIN_PROFIT_AFTER_FEES + (config.TAKER_FEE_RATE * 200)
                    tp_price = current_price * (1 + adjusted_tp_percent / 100)
                else:  # SHORT
                    # Increase the take profit percentage (for shorts, this means a lower price)
                    adjusted_tp_percent = config.TAKE_PROFIT_PERCENT + config.MIN_PROFIT_AFTER_FEES + (config.TAKER_FEE_RATE * 200)
                    tp_price = current_price * (1 - adjusted_tp_percent / 100)

                # Round according to symbol precision
                tp_price = self.client.round_price(tp_price)

                logger.info(
                    f"Adjusted take profit price to {tp_price} to ensure profitability after fees. "
                    f"Original TP percent: {config.TAKE_PROFIT_PERCENT}%, "
                    f"Adjusted TP percent: {adjusted_tp_percent}%"
                )

                # Send notification about the adjusted TP price
                self.telegram.notify_fee_adjusted_tp(
                    position_side=signal,
                    original_tp_price=original_tp_price,
                    adjusted_tp_price=tp_price,
                    profit_info=profit_info
                )

            # Place take profit order with error handling
            tp_side = 'SELL' if signal == 'LONG' else 'BUY'
            try:
                tp_order = self.client.place_take_profit_order(
                    side=tp_side,
                    quantity=quantity,
                    stop_price=tp_price,
                    position_side=signal,
                    symbol=self.symbol
                )
                logger.info(f"Placed take profit order: {tp_order}")
            except Exception as e:
                error_msg = f"Failed to place take profit order: {str(e)}"
                logger.error(error_msg)
                self.telegram.notify_error(error_msg)
                # Continue to place SL order even if TP order fails

            # Place stop loss order with error handling
            sl_side = 'SELL' if signal == 'LONG' else 'BUY'
            try:
                sl_order = self.client.place_stop_loss_order(
                    side=sl_side,
                    quantity=quantity,
                    stop_price=sl_price,
                    position_side=signal,
                    symbol=self.symbol
                )
                logger.info(f"Placed stop loss order: {sl_order}")
            except Exception as e:
                error_msg = f"Failed to place stop loss order: {str(e)}"
                logger.error(error_msg)
                self.telegram.notify_error(error_msg)
                # Continue even if SL order fails, as we already have a position

            # Get account information for notification with error handling
            try:
                account_info = self.client.get_account_info()
                total_balance = float(account_info['totalWalletBalance'])
                position_value = current_price * quantity

                # Get account usage information
                account_usage = self.position_manager.get_account_usage_percentage()

                # Send notification with account balance and position information
                self.telegram.notify_entry(
                    position_side=signal,
                    entry_price=current_price,
                    quantity=quantity,
                    tp_price=tp_price,
                    sl_price=sl_price,
                    account_balance=total_balance,
                    position_value=position_value,
                    leverage=self.leverage,
                    account_usage=account_usage,
                    is_hedge=should_hedge
                )
            except Exception as e:
                error_msg = f"Error getting account info or sending notification: {str(e)}"
                logger.error(error_msg)
                # Don't send notification about this error since we're already having notification issues
                # Just log it and continue

            # If this was a hedge position, update the combined PnL
            if should_hedge:
                try:
                    # Get updated PnL information
                    updated_pnl = self.client.get_combined_position_pnl(self.symbol)

                    # Notify about the combined position
                    self.telegram.notify_hedge_complete(updated_pnl)
                except Exception as e:
                    error_msg = f"Error getting combined PnL for hedge position: {str(e)}"
                    logger.error(error_msg)
                    # Don't send notification about this error since we're already having notification issues

        except Exception as e:
            error_msg = f"Error in check_and_enter_position: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            self.telegram.notify_error(error_msg)

    def check_positions_pnl(self):
        """
        Check PnL for open positions and send notifications
        """
        try:
            # Get combined PnL information
            pnl_info = self.client.get_combined_position_pnl(self.symbol)

            # If we have positions, log the PnL
            if pnl_info['is_hedged'] or pnl_info['long_position'] or pnl_info['short_position']:
                if pnl_info['is_hedged']:
                    logger.info(
                        f"Hedged position for {self.symbol}: "
                        f"Combined PnL: {pnl_info['combined_unrealized_pnl']:.2f} USDT "
                        f"({pnl_info['combined_unrealized_pnl_percent']:.2f}%)"
                    )
                else:
                    position_side = 'LONG' if pnl_info['long_position'] else 'SHORT'
                    position_info = pnl_info['long_position'] if position_side == 'LONG' else pnl_info['short_position']
                    logger.info(
                        f"{position_side} position for {self.symbol}: "
                        f"PnL: {position_info['unrealized_pnl']:.2f} USDT "
                        f"({position_info['unrealized_pnl_percent']:.2f}%)"
                    )

            return pnl_info

        except Exception as e:
            error_msg = f"Error checking positions PnL: {str(e)}"
            logger.error(error_msg)
            return None

    def run(self):
        """
        Main bot loop
        """
        logger.info(f"Starting trading bot for {self.symbol}")
        self.telegram.send_message(f"🤖 Trading bot started for {self.symbol}")

        # Send initial PnL report if configured to do so
        if config.SEND_INITIAL_PNL_REPORT:
            try:
                pnl_summary = self.client.get_daily_pnl(self.start_of_day)
                self.telegram.notify_daily_pnl(pnl_summary)
            except Exception as e:
                logger.error(f"Error getting initial PnL: {str(e)}")

        # Initialize the daily PnL check time
        self.daily_pnl_last_check = int(time.time())

        while self.is_running:
            try:
                # Check if a new day has started
                self.check_for_new_day()

                # Check daily PnL and update trading status
                if self.is_trading_allowed:
                    self.is_trading_allowed = self.check_daily_pnl()

                    if not self.is_trading_allowed:
                        logger.info(f"Trading stopped for {self.symbol} due to daily PnL target/limit")

                # Only check for signals and enter positions if trading is allowed
                if self.is_trading_allowed:
                    self.check_and_enter_position()

                # Sleep for the configured interval
                time.sleep(config.CHECK_INTERVAL)

            except Exception as e:
                error_msg = f"Error in bot run loop for {self.symbol}: {str(e)}\n{traceback.format_exc()}"
                logger.error(error_msg)
                self.telegram.notify_error(error_msg)

                # Sleep for a bit before retrying
                time.sleep(10)

        logger.info(f"Bot for {self.symbol} has been stopped")
        self.telegram.send_message(f"🛑 Bot for {self.symbol} has been stopped")

class BotManager:
    def __init__(self, symbols=None):
        print("Initializing BotManager...")
        self.client = BinanceClient()

        # Track closed symbols to avoid repeatedly trying them
        self.closed_symbols = set()

        # If USE_HIGH_VOLUME_PAIRS is enabled, get high volume pairs
        if config.USE_HIGH_VOLUME_PAIRS:
            print(f"Finding trading pairs with 24h volume >= {config.MIN_VOLUME_USDT:,.0f} USDT")
            logger.info(f"Finding trading pairs with 24h volume >= {config.MIN_VOLUME_USDT:,.0f} USDT")
            self.symbols = self.client.get_high_volume_pairs()
            if not self.symbols:
                print("No high volume pairs found. Using default symbol.")
                logger.warning("No high volume pairs found. Using default symbol.")
                self.symbols = [config.SYMBOL]
        else:
            # Use provided symbols or default
            self.symbols = symbols or [config.SYMBOL]

        # Filter out any known closed symbols
        self.filter_closed_symbols()

        print(f"Trading on {len(self.symbols)} pairs: {', '.join(self.symbols)}")
        logger.info(f"Trading on {len(self.symbols)} pairs: {', '.join(self.symbols)}")

        self.bots = {}
        self.threads = {}

    def filter_closed_symbols(self):
        """Filter out symbols that are known to be closed"""
        active_symbols = []
        for symbol in self.symbols:
            try:
                # Try to get current price to check if symbol is active
                self.client.get_current_price(symbol)
                active_symbols.append(symbol)
            except Exception as e:
                if "Symbol is closed" in str(e):
                    logger.warning(f"Symbol {symbol} is closed. Skipping.")
                    self.closed_symbols.add(symbol)
                else:
                    # If it's another error, keep the symbol and try again later
                    logger.warning(f"Error checking {symbol}: {str(e)}. Will try again.")
                    active_symbols.append(symbol)

        self.symbols = active_symbols

    def start_bot(self, symbol):
        """
        Start a trading bot for a symbol
        """
        # Skip if symbol is in the closed list
        if symbol in self.closed_symbols:
            logger.warning(f"Not starting bot for {symbol} as it is marked as closed")
            return False

        try:
            # Check if symbol is active before starting the bot
            self.client.get_current_price(symbol)

            bot = TradingBot(symbol)
            self.bots[symbol] = bot

            # Create and start thread
            thread = threading.Thread(target=bot.run, daemon=True)
            thread.start()

            self.threads[symbol] = thread

            logger.info(f"Started bot for {symbol}")
            return True

        except Exception as e:
            if "Symbol is closed" in str(e):
                logger.warning(f"Symbol {symbol} is closed. Marking as closed and skipping.")
                self.closed_symbols.add(symbol)
                if symbol in self.symbols:
                    self.symbols.remove(symbol)
                return False
            else:
                logger.error(f"Error starting bot for {symbol}: {str(e)}")
                return False

    def start_all(self):
        """
        Start trading bots for all configured symbols
        """
        started_count = 0
        skipped_count = 0

        for symbol in self.symbols[:]:  # Create a copy of the list to iterate over
            result = self.start_bot(symbol)
            if result:
                started_count += 1
            else:
                skipped_count += 1

            # Small delay between starting bots to avoid rate limits
            time.sleep(1)

        logger.info(f"Started {started_count} bots, skipped {skipped_count} closed symbols")

        # If all symbols were closed, try to find new ones
        if started_count == 0 and config.USE_HIGH_VOLUME_PAIRS:
            logger.warning("All symbols were closed. Trying to find new high volume pairs...")
            self.update_trading_pairs(force=True)

    def monitor(self):
        """
        Monitor bot threads and restart if needed
        """
        while True:
            for symbol, thread in self.threads.items():
                if not thread.is_alive():
                    logger.warning(f"Bot thread for {symbol} died. Restarting...")
                    self.start_bot(symbol)

            time.sleep(60)

    def update_trading_pairs(self, force=False):
        """
        Update the list of trading pairs based on current volume

        Args:
            force: If True, force update even if USE_HIGH_VOLUME_PAIRS is disabled
        """
        if not config.USE_HIGH_VOLUME_PAIRS and not force:
            return

        logger.info("Updating high volume trading pairs...")
        new_symbols = self.client.get_high_volume_pairs()

        if not new_symbols:
            logger.warning("No high volume pairs found. Keeping current symbols.")
            return

        # Filter out closed symbols
        new_symbols = [s for s in new_symbols if s not in self.closed_symbols]

        if not new_symbols:
            logger.warning("All high volume pairs are closed. No symbols to trade.")
            return

        # Stop bots for symbols that are no longer in the list
        for symbol in list(self.threads.keys()):
            if symbol not in new_symbols:
                logger.info(f"Stopping bot for {symbol} (no longer high volume)")
                # Signal the bot to stop
                self.bots[symbol].is_running = False
                # Remove from dictionaries
                del self.bots[symbol]
                del self.threads[symbol]

        # Update the symbols list
        self.symbols = new_symbols

        # Start bots for new symbols
        for symbol in new_symbols:
            if symbol not in self.threads:
                logger.info(f"Starting bot for new high volume pair: {symbol}")
                self.start_bot(symbol)
                time.sleep(1)  # Small delay to avoid rate limits
