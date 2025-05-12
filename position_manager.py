import config

class PositionManager:
    def __init__(self, binance_client):
        self.client = binance_client

    def get_total_position_value(self):
        """
        Calculate total value of all open positions

        Returns:
            Total position value in USDT
        """
        try:
            # Get all open positions
            positions = self.client.get_open_positions()

            # Calculate total position value
            total_value = 0.0
            for position in positions:
                position_amt = abs(float(position['positionAmt']))
                entry_price = float(position['entryPrice'])
                position_value = position_amt * entry_price
                total_value += position_value

            return total_value

        except Exception as e:
            import logging
            logging.error(f"Error calculating total position value: {str(e)}")
            return 0.0

    def get_account_balance(self):
        """
        Get total wallet balance

        Returns:
            Total wallet balance in USDT
        """
        try:
            account_info = self.client.get_account_info()
            return float(account_info['totalWalletBalance'])
        except Exception as e:
            import logging
            logging.error(f"Error getting account balance: {str(e)}")
            return 0.0

    def get_account_usage_percentage(self):
        """
        Calculate current account usage as a percentage

        Returns:
            Percentage of account balance used by open positions
        """
        balance = self.get_account_balance()
        if balance <= 0:
            return 0.0

        total_position_value = self.get_total_position_value()
        return (total_position_value / balance) * 100

    def calculate_position_size(self, price, symbol=None, leverage=None):
        """
        Calculate position size based on account balance, margin percentage, leverage, and current price
        with respect to maximum account usage limit.

        Formula:
        1. Get account balance
        2. Check current account usage
        3. Calculate available balance for new position
        4. Calculate position size based on percentage of account balance
        5. Calculate margin amount based on margin percentage
        6. Apply leverage to get effective position size in USDT
        7. Convert to quantity: effective_position_size / price

        Margin percentage rules:
        - lev ≤ 25x: margin 5%
        - lev 50x: margin 4%
        - lev 75x: margin 3%
        - lev 100x: margin 2%
        - lev > 100x: margin 1%

        Args:
            price: Current market price
            symbol: Trading symbol (default from config)
            leverage: Leverage to use (default from config)

        Returns:
            Rounded position size
        """
        import logging

        symbol = symbol or config.SYMBOL
        leverage = leverage or config.LEVERAGE

        # Get account balance
        total_balance = self.get_account_balance()
        if total_balance <= 0:
            logging.warning(f"Account balance is zero or negative: {total_balance}")
            return 0

        # Check current account usage
        current_usage_percent = self.get_account_usage_percentage()
        logging.info(f"Current account usage: {current_usage_percent:.2f}% of {total_balance:.2f} USDT")

        # Calculate available balance percentage
        available_percent = max(0, config.MAX_ACCOUNT_USAGE - current_usage_percent)

        # If we've reached the maximum account usage, return 0
        if available_percent <= 0:
            logging.warning(f"Maximum account usage reached ({config.MAX_ACCOUNT_USAGE}%). Cannot open new positions.")
            return 0

        # Calculate maximum position size based on available balance percentage
        max_position_percent = min(config.POSITION_SIZE_PERCENT, available_percent)

        # Calculate position size based on percentage of account balance
        position_size_usdt = total_balance * (max_position_percent / 100)

        # Calculate margin amount based on margin percentage
        margin_percentage = config.get_margin_percentage(leverage)
        margin_amount = position_size_usdt * (margin_percentage / 100)

        # Calculate effective position size with leverage
        effective_position_size = margin_amount * leverage

        # Calculate quantity
        quantity = effective_position_size / price

        logging.info(f"Calculated position size for {symbol}: {quantity} (value: {effective_position_size:.2f} USDT, {max_position_percent:.2f}% of balance)")

        # Round according to symbol precision
        return self.client.round_quantity(quantity)

    def calculate_take_profit_price(self, entry_price, position_side):
        """
        Calculate take profit price

        Args:
            entry_price: Entry price
            position_side: 'LONG' or 'SHORT'

        Returns:
            Rounded take profit price
        """
        if position_side == 'LONG':
            # For LONG positions, TP is above entry price
            tp_price = entry_price * (1 + config.TAKE_PROFIT_PERCENT / 100)
        else:
            # For SHORT positions, TP is below entry price
            tp_price = entry_price * (1 - config.TAKE_PROFIT_PERCENT / 100)

        # Round according to symbol precision
        return self.client.round_price(tp_price)

    def calculate_stop_loss_price(self, entry_price, position_side):
        """
        Calculate stop loss price

        Args:
            entry_price: Entry price
            position_side: 'LONG' or 'SHORT'

        Returns:
            Rounded stop loss price
        """
        if position_side == 'LONG':
            # For LONG positions, SL is below entry price
            sl_price = entry_price * (1 - config.STOP_LOSS_PERCENT / 100)
        else:
            # For SHORT positions, SL is above entry price
            sl_price = entry_price * (1 + config.STOP_LOSS_PERCENT / 100)

        # Round according to symbol precision
        return self.client.round_price(sl_price)

    def has_open_position(self, position_side, symbol=None):
        """
        Check if there is an open position for the given side

        Args:
            position_side: 'LONG' or 'SHORT'
            symbol: Trading symbol (default from config)

        Returns:
            Boolean indicating if position exists
        """
        symbol = symbol or config.SYMBOL

        # Get open positions
        positions = self.client.get_open_positions(symbol)

        # Check if there's an open position for the given side
        for position in positions:
            if (position['positionSide'] == position_side and
                float(position['positionAmt']) != 0):
                return True

        return False

    def can_enter_position(self, position_side, symbol=None):
        """
        Check if we can enter a position for the given side based on hedge mode settings

        Args:
            position_side: 'LONG' or 'SHORT'
            symbol: Trading symbol (default from config)

        Returns:
            Boolean indicating if we can enter the position
        """
        symbol = symbol or config.SYMBOL

        # If hedge mode is enabled and we allow both positions, we can always enter
        if config.HEDGE_MODE and config.ALLOW_BOTH_POSITIONS:
            return True

        # If we already have a position on this side, we can't enter
        if self.has_open_position(position_side, symbol):
            return False

        # If hedge mode is disabled, check if we have a position on the opposite side
        if not config.HEDGE_MODE:
            opposite_side = 'SHORT' if position_side == 'LONG' else 'LONG'
            if self.has_open_position(opposite_side, symbol):
                return False

        # If we don't allow both positions, check if we have a position on the opposite side
        if not config.ALLOW_BOTH_POSITIONS:
            opposite_side = 'SHORT' if position_side == 'LONG' else 'LONG'
            if self.has_open_position(opposite_side, symbol):
                return False

        return True

    def should_hedge_position(self, symbol=None):
        """
        Check if we should hedge an existing position based on PnL thresholds

        Args:
            symbol: Trading symbol (default from config)

        Returns:
            Tuple (should_hedge, position_side_to_hedge, pnl_info)
        """
        import logging

        if not config.AUTO_HEDGE:
            return False, None, None

        symbol = symbol or config.SYMBOL

        # Get PnL information for both positions
        pnl_info = self.client.get_combined_position_pnl(symbol)

        # If already hedged, no need to hedge again
        if pnl_info['is_hedged']:
            return False, None, pnl_info

        # Check if we have a LONG position that needs hedging
        if pnl_info['long_position'] and pnl_info['long_position']['position_amt'] != 0:
            pnl_percent = pnl_info['long_position']['unrealized_pnl_percent']

            # If profit exceeds threshold, hedge with a SHORT position
            if pnl_percent >= config.AUTO_HEDGE_PROFIT_THRESHOLD:
                logging.info(f"LONG position profit ({pnl_percent:.2f}%) exceeds threshold ({config.AUTO_HEDGE_PROFIT_THRESHOLD}%). Hedging with SHORT position.")
                return True, 'SHORT', pnl_info

            # If loss exceeds threshold, hedge with a SHORT position
            if pnl_percent <= -config.AUTO_HEDGE_LOSS_THRESHOLD:
                logging.info(f"LONG position loss ({pnl_percent:.2f}%) exceeds threshold ({config.AUTO_HEDGE_LOSS_THRESHOLD}%). Hedging with SHORT position.")
                return True, 'SHORT', pnl_info

        # Check if we have a SHORT position that needs hedging
        if pnl_info['short_position'] and pnl_info['short_position']['position_amt'] != 0:
            pnl_percent = pnl_info['short_position']['unrealized_pnl_percent']

            # If profit exceeds threshold, hedge with a LONG position
            if pnl_percent >= config.AUTO_HEDGE_PROFIT_THRESHOLD:
                logging.info(f"SHORT position profit ({pnl_percent:.2f}%) exceeds threshold ({config.AUTO_HEDGE_PROFIT_THRESHOLD}%). Hedging with LONG position.")
                return True, 'LONG', pnl_info

            # If loss exceeds threshold, hedge with a LONG position
            if pnl_percent <= -config.AUTO_HEDGE_LOSS_THRESHOLD:
                logging.info(f"SHORT position loss ({pnl_percent:.2f}%) exceeds threshold ({config.AUTO_HEDGE_LOSS_THRESHOLD}%). Hedging with LONG position.")
                return True, 'LONG', pnl_info

        return False, None, pnl_info

    def calculate_hedge_position_size(self, original_position_info, symbol=None):
        """
        Calculate the size for a hedge position

        Args:
            original_position_info: Dictionary with original position information
            symbol: Trading symbol (default from config)

        Returns:
            Hedge position size
        """
        symbol = symbol or config.SYMBOL

        # Get the original position amount
        original_position_amt = abs(original_position_info['position_amt'])

        # Calculate hedge position size based on the ratio
        hedge_position_size = original_position_amt * config.HEDGE_POSITION_SIZE_RATIO

        # Round according to symbol precision
        return self.client.round_quantity(hedge_position_size)
