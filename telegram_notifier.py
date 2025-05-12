import requests
import config
import logging

class TelegramNotifier:
    def __init__(self, token=None, chat_id=None):
        self.token = token or config.TELEGRAM_TOKEN
        self.chat_id = chat_id or config.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"

        # Check if Telegram credentials are configured
        self.enabled = bool(self.token and self.chat_id)

        if not self.enabled:
            logging.warning("Telegram notifications are disabled. Set TELEGRAM_TOKEN and TELEGRAM_CHAT_ID in config.")

    def send_message(self, message):
        """
        Send a message to the configured Telegram chat

        Args:
            message: Message text to send

        Returns:
            Response from Telegram API or None if disabled
        """
        if not self.enabled:
            logging.info(f"Telegram notification (disabled): {message}")
            return None

        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML"
            }

            response = requests.post(url, data=data)

            if response.status_code == 200:
                return response.json()
            else:
                logging.error(f"Failed to send Telegram message: {response.text}")
                return None

        except Exception as e:
            logging.error(f"Error sending Telegram message: {str(e)}")
            return None

    def notify_entry(self, position_side, entry_price, quantity, tp_price, sl_price,
                  account_balance=None, position_value=None, leverage=None, account_usage=None, is_hedge=False):
        """
        Send notification about new position entry

        Args:
            position_side: 'LONG' or 'SHORT'
            entry_price: Entry price
            quantity: Position size
            tp_price: Take profit price
            sl_price: Stop loss price
            account_balance: Total account balance (optional)
            position_value: Position value in USDT (optional)
            leverage: Actual leverage used (optional)
            account_usage: Current account usage percentage (optional)
            is_hedge: Whether this is a hedge position (optional)
        """
        # Use actual leverage if provided, otherwise use config value
        actual_leverage = leverage or config.LEVERAGE
        margin_percentage = config.get_margin_percentage(actual_leverage)

        # Basic position information
        if is_hedge:
            message_parts = [
                f"🛡️ <b>NEW HEDGE {position_side} POSITION</b> 🛡️\n\n"
                f"Symbol: {config.SYMBOL}\n"
                f"Entry Price: {entry_price}\n"
                f"Quantity: {quantity}\n"
                f"Take Profit: {tp_price}\n"
                f"Stop Loss: {sl_price}\n"
                f"Leverage: {actual_leverage}x\n"
                f"Margin: {margin_percentage}%\n"
                f"Mode: {'Hedge' if config.HEDGE_MODE else 'One-way'}"
            ]
        else:
            message_parts = [
                f"🚀 <b>NEW {position_side} POSITION</b> 🚀\n\n"
                f"Symbol: {config.SYMBOL}\n"
                f"Entry Price: {entry_price}\n"
                f"Quantity: {quantity}\n"
                f"Take Profit: {tp_price}\n"
                f"Stop Loss: {sl_price}\n"
                f"Leverage: {actual_leverage}x\n"
                f"Margin: {margin_percentage}%\n"
                f"Mode: {'Hedge' if config.HEDGE_MODE else 'One-way'}"
            ]

        # Add account balance and position size information if provided
        if account_balance is not None and position_value is not None:
            position_percent = (position_value / account_balance) * 100
            message_parts.append(
                f"\n\n<b>Account Information</b>\n"
                f"Balance: {account_balance:.2f} USDT\n"
                f"Position Value: {position_value:.2f} USDT\n"
                f"Position Size: {position_percent:.2f}% of balance"
            )

            # Add account usage information if provided
            if account_usage is not None:
                message_parts.append(
                    f"\nAccount Usage: {account_usage:.2f}% / {config.MAX_ACCOUNT_USAGE}%"
                )

        message = "".join(message_parts)

        return self.send_message(message)

    def notify_tp_hit(self, position_side, entry_price, exit_price, profit_percent):
        """
        Send notification about take profit hit

        Args:
            position_side: 'LONG' or 'SHORT'
            entry_price: Entry price
            exit_price: Exit price
            profit_percent: Profit percentage
        """
        message = (
            f"💰 <b>TAKE PROFIT HIT</b> 💰\n\n"
            f"Symbol: {config.SYMBOL}\n"
            f"Position: {position_side}\n"
            f"Entry: {entry_price}\n"
            f"Exit: {exit_price}\n"
            f"Profit: +{profit_percent:.2f}%"
        )

        return self.send_message(message)

    def notify_sl_hit(self, position_side, entry_price, exit_price, loss_percent):
        """
        Send notification about stop loss hit

        Args:
            position_side: 'LONG' or 'SHORT'
            entry_price: Entry price
            exit_price: Exit price
            loss_percent: Loss percentage
        """
        message = (
            f"🛑 <b>STOP LOSS HIT</b> 🛑\n\n"
            f"Symbol: {config.SYMBOL}\n"
            f"Position: {position_side}\n"
            f"Entry: {entry_price}\n"
            f"Exit: {exit_price}\n"
            f"Loss: -{loss_percent:.2f}%"
        )

        return self.send_message(message)

    def notify_error(self, error_message):
        """
        Send notification about an error

        Args:
            error_message: Error message
        """
        message = (
            f"⚠️ <b>ERROR</b> ⚠️\n\n"
            f"{error_message}"
        )

        return self.send_message(message)

    def notify_signal(self, signal, indicators=None):
        """
        Send notification about a detected signal

        Args:
            signal: Signal type ('LONG', 'SHORT', or 'WAIT')
            indicators: Dictionary with indicator values
        """
        if signal == 'WAIT':
            return None

        emoji = "🟢" if signal == "LONG" else "🔴"

        # Basic message without indicator details
        if indicators is None:
            message = (
                f"{emoji} <b>SIGNAL DETECTED: {signal}</b> {emoji}\n\n"
                f"Symbol: {config.SYMBOL}\n"
                f"RSI: {'<30' if signal == 'LONG' else '>70'}\n"
                f"Candle: {'Green' if signal == 'LONG' else 'Red'}"
            )
        else:
            # Detailed message with all indicators
            message = (
                f"{emoji} <b>SIGNAL DETECTED: {signal}</b> {emoji}\n\n"
                f"Symbol: {config.SYMBOL}\n"
                f"RSI: {indicators['rsi']:.2f}\n"
                f"Candle: {'Green' if indicators['is_green'] else 'Red' if indicators['is_red'] else 'Neutral'}\n"
                f"EMA {config.EMA_SHORT_PERIOD}: {indicators[f'ema_{config.EMA_SHORT_PERIOD}']:.2f}\n"
                f"EMA {config.EMA_LONG_PERIOD}: {indicators[f'ema_{config.EMA_LONG_PERIOD}']:.2f}\n"
                f"BB Upper: {indicators['bb_upper']:.2f}\n"
                f"BB Middle: {indicators['bb_middle']:.2f}\n"
                f"BB Lower: {indicators['bb_lower']:.2f}\n"
                f"BB %B: {indicators['bb_percent_b']:.2f}\n\n"
                f"Signal Strength: {indicators['signal_strength']}/3"
            )

        return self.send_message(message)

    def notify_daily_pnl(self, pnl_summary):
        """
        Send notification about daily PnL

        Args:
            pnl_summary: Dictionary with PnL summary data
        """
        # Format PnL values with 2 decimal places and + sign for positive values
        total_pnl = f"{'+' if pnl_summary['total_pnl'] > 0 else ''}{pnl_summary['total_pnl']:.2f}"
        realized_pnl = f"{'+' if pnl_summary['realized_pnl'] > 0 else ''}{pnl_summary['realized_pnl']:.2f}"
        funding_fee = f"{'+' if pnl_summary['funding_fee'] > 0 else ''}{pnl_summary['funding_fee']:.2f}"
        commission = f"{pnl_summary['commission']:.2f}"  # Commission is always negative
        pnl_percentage = f"{'+' if pnl_summary['pnl_percentage'] > 0 else ''}{pnl_summary['pnl_percentage']:.2f}%"

        # Determine emoji based on total PnL
        if pnl_summary['total_pnl'] > 0:
            emoji = "💰"
        elif pnl_summary['total_pnl'] < 0:
            emoji = "📉"
        else:
            emoji = "⚖️"

        message = (
            f"{emoji} <b>DAILY PNL REPORT</b> {emoji}\n\n"
            f"Total PnL: {total_pnl} USDT ({pnl_percentage})\n"
            f"Realized PnL: {realized_pnl} USDT\n"
            f"Funding Fee: {funding_fee} USDT\n"
            f"Commission: {commission} USDT\n\n"
            f"Trades: {pnl_summary['trades_count']}\n"
            f"Win Rate: {pnl_summary['win_rate']:.1f}%\n"
            f"Winning Trades: {pnl_summary['winning_trades']}\n"
            f"Losing Trades: {pnl_summary['losing_trades']}"
        )

        return self.send_message(message)

    def notify_profit_target_reached(self, pnl_summary):
        """
        Send notification that daily profit target has been reached

        Args:
            pnl_summary: Dictionary with PnL summary data
        """
        message = (
            f"🎯 <b>DAILY PROFIT TARGET REACHED</b> 🎯\n\n"
            f"Target: +{config.DAILY_PROFIT_TARGET:.2f}%\n"
            f"Current PnL: +{pnl_summary['pnl_percentage']:.2f}%\n"
            f"Amount: +{pnl_summary['total_pnl']:.2f} USDT\n\n"
            f"Trading has been stopped for today. Bot will resume tomorrow."
        )

        return self.send_message(message)

    def notify_loss_limit_reached(self, pnl_summary):
        """
        Send notification that daily loss limit has been reached

        Args:
            pnl_summary: Dictionary with PnL summary data
        """
        message = (
            f"🛑 <b>DAILY LOSS LIMIT REACHED</b> 🛑\n\n"
            f"Limit: -{config.DAILY_LOSS_LIMIT:.2f}%\n"
            f"Current PnL: {pnl_summary['pnl_percentage']:.2f}%\n"
            f"Amount: {pnl_summary['total_pnl']:.2f} USDT\n\n"
            f"Trading has been stopped for today. Bot will resume tomorrow."
        )

        return self.send_message(message)

    def notify_bot_stopped(self, reason):
        """
        Send notification that the bot has been stopped

        Args:
            reason: Reason for stopping the bot
        """
        message = (
            f"⏹️ <b>BOT STOPPED</b> ⏹️\n\n"
            f"Reason: {reason}\n\n"
            f"The bot will not trade until restarted."
        )

        return self.send_message(message)

    def notify_auto_hedge(self, hedge_side, pnl_info):
        """
        Send notification about auto-hedging

        Args:
            hedge_side: 'LONG' or 'SHORT'
            pnl_info: Dictionary with PnL information
        """
        if not self.enabled:
            return

        # Get the original position information
        original_side = 'LONG' if hedge_side == 'SHORT' else 'SHORT'
        original_position = pnl_info['long_position'] if original_side == 'LONG' else pnl_info['short_position']

        # Format the message
        message = (
            f"🛡️ <b>AUTO-HEDGING TRIGGERED</b> 🛡️\n\n"
            f"Symbol: {config.SYMBOL}\n"
            f"Original Position: {original_side}\n"
            f"Original Entry Price: {original_position['entry_price']}\n"
            f"Original Quantity: {abs(original_position['position_amt'])}\n"
            f"Current PnL: {original_position['unrealized_pnl']:.2f} USDT ({original_position['unrealized_pnl_percent']:.2f}%)\n"
            f"Hedge Action: Opening {hedge_side} position\n"
            f"Hedge Size Ratio: {config.HEDGE_POSITION_SIZE_RATIO * 100:.0f}% of original position"
        )

        return self.send_message(message)

    def notify_hedge_complete(self, pnl_info):
        """
        Send notification about completed hedge position

        Args:
            pnl_info: Dictionary with combined PnL information
        """
        if not self.enabled:
            return

        # Format the message
        message = (
            f"✅ <b>HEDGE POSITION COMPLETE</b> ✅\n\n"
            f"Symbol: {config.SYMBOL}\n"
            f"LONG Position: {abs(pnl_info['long_position']['position_amt'])} @ {pnl_info['long_position']['entry_price']}\n"
            f"LONG PnL: {pnl_info['long_position']['unrealized_pnl']:.2f} USDT ({pnl_info['long_position']['unrealized_pnl_percent']:.2f}%)\n"
            f"SHORT Position: {abs(pnl_info['short_position']['position_amt'])} @ {pnl_info['short_position']['entry_price']}\n"
            f"SHORT PnL: {pnl_info['short_position']['unrealized_pnl']:.2f} USDT ({pnl_info['short_position']['unrealized_pnl_percent']:.2f}%)\n"
            f"Combined PnL: {pnl_info['combined_unrealized_pnl']:.2f} USDT ({pnl_info['combined_unrealized_pnl_percent']:.2f}%)"
        )

        return self.send_message(message)
