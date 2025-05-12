import logging
import time
import traceback
from datetime import datetime

import config
from binance_client import BinanceClient
from telegram_notifier import TelegramNotifier

logger = logging.getLogger(__name__)

class GridTradingBot:
    def __init__(self, symbol=None):
        self.symbol = symbol or config.SYMBOL
        self.client = BinanceClient(symbol=self.symbol)
        self.telegram = TelegramNotifier()

        # Initialize state variables
        self.last_buy_price = None
        self.lowest_price = None
        self.current_grid_buy_index = 0  # Current buy grid index (0-based)
        self.current_grid_sell_index = 0  # Current sell grid index (0-based)
        self.active_buy_order_id = None
        self.active_sell_order_id = None

        # Set position mode to hedge mode if enabled
        if config.HEDGE_MODE:
            try:
                self.client.set_position_mode(True)
                logger.info(f"Position mode set to hedge mode for {self.symbol}")
            except Exception as e:
                error_msg = f"Failed to set position mode: {str(e)}"
                logger.error(error_msg)
                self.telegram.notify_error(error_msg)

    def get_coin_balance(self):
        """
        Get the current balance of the coin

        Returns:
            Coin balance
        """
        try:
            # Get account information
            account_info = self.client.get_account_info()

            # Extract the base asset from the symbol (e.g., BTC from BTCUSDT)
            base_asset = self.symbol[:-4] if self.symbol.endswith('USDT') else self.symbol[:-3]

            # Find the asset in the account balances
            for asset in account_info['assets']:
                if asset['asset'] == base_asset:
                    return float(asset['walletBalance'])

            return 0.0
        except Exception as e:
            logger.error(f"Error getting coin balance: {str(e)}")
            return 0.0

    def get_coin_value_in_usdt(self):
        """
        Calculate the value of the coin balance in USDT

        Returns:
            Value in USDT
        """
        coin_balance = self.get_coin_balance()
        current_price = self.client.get_current_price(self.symbol)
        return coin_balance * current_price

    def should_remove_last_buy_price(self):
        """
        Check if the last buy price should be removed based on the threshold

        Returns:
            Boolean indicating if last buy price should be removed
        """
        if self.last_buy_price is None:
            return False

        coin_value = self.get_coin_value_in_usdt()
        return coin_value < config.GRID_LAST_BUY_PRICE_REMOVAL_THRESHOLD

    def update_lowest_price(self, current_price):
        """
        Update the lowest observed price

        Args:
            current_price: Current market price
        """
        if self.lowest_price is None or current_price < self.lowest_price:
            self.lowest_price = current_price
            logger.info(f"Updated lowest price to {self.lowest_price}")

    def check_and_place_buy_order(self, current_price):
        """
        Check if we should place a buy order and place it if conditions are met

        Args:
            current_price: Current market price
        """
        # If we already have an active buy order, check if we need to update it
        if self.active_buy_order_id:
            try:
                # Get the order details
                order = self.client.get_order(self.active_buy_order_id, self.symbol)

                # If the order is still active and the price has fallen significantly, cancel and replace
                if order['status'] == 'NEW' and current_price < self.lowest_price * 0.99:  # 1% price drop
                    logger.info(f"Price dropped significantly. Cancelling order {self.active_buy_order_id} and placing new one.")
                    self.client.cancel_order(self.active_buy_order_id, self.symbol)
                    self.active_buy_order_id = None
                    self.update_lowest_price(current_price)
                else:
                    # Order is still valid, no need to do anything
                    return
            except Exception as e:
                logger.error(f"Error checking active buy order: {str(e)}")
                self.active_buy_order_id = None  # Reset to allow placing a new order

        # If we have enough coin balance, don't place a buy order for grid #1
        if self.current_grid_buy_index == 0:
            coin_value = self.get_coin_value_in_usdt()
            if coin_value >= 10.0:  # $10 worth of coin
                logger.info(f"Already have ${coin_value:.2f} worth of coin. Skipping buy grid #1.")
                return

        # Check if we've reached the lowest price for the current grid
        grid_trigger_percentage = config.GRID_BUY_TRIGGER_PERCENTAGES[self.current_grid_buy_index]

        # For first grid, compare with lowest observed price
        if self.current_grid_buy_index == 0:
            trigger_price = self.lowest_price
        # For subsequent grids, compare with last buy price
        else:
            if self.last_buy_price is None:
                logger.warning("Cannot place grid buy order: No last buy price available")
                return
            trigger_price = self.last_buy_price * grid_trigger_percentage

        if current_price <= trigger_price:
            # Calculate stop and limit prices
            stop_percentage = config.GRID_BUY_STOP_PERCENTAGES[self.current_grid_buy_index]
            limit_percentage = config.GRID_BUY_LIMIT_PERCENTAGES[self.current_grid_buy_index]

            stop_price = current_price * stop_percentage
            limit_price = current_price * limit_percentage

            # Calculate quantity based on USDT amount
            usdt_amount = config.GRID_BUY_QUANTITIES_USDT[self.current_grid_buy_index]
            quantity = usdt_amount / limit_price
            quantity = self.client.round_quantity(quantity)

            try:
                # Place stop-limit order
                order = self.client.place_stop_limit_order(
                    side='BUY',
                    quantity=quantity,
                    stop_price=stop_price,
                    limit_price=limit_price,
                    position_side='LONG',
                    symbol=self.symbol
                )

                self.active_buy_order_id = order['orderId']

                logger.info(f"Placed grid buy #{self.current_grid_buy_index + 1} order: Stop price: {stop_price}, Limit price: {limit_price}, Quantity: {quantity}")
                self.telegram.send_message(f"🔵 Grid Buy #{self.current_grid_buy_index + 1} order placed for {self.symbol}\nStop price: {stop_price}\nLimit price: {limit_price}\nQuantity: {quantity}")

            except Exception as e:
                error_msg = f"Error placing grid buy order: {str(e)}"
                logger.error(error_msg)
                self.telegram.notify_error(error_msg)

    def check_and_place_sell_order(self, current_price):
        """
        Check if we should place a sell order and place it if conditions are met

        Args:
            current_price: Current market price
        """
        # If we don't have a last buy price, we can't sell
        if self.last_buy_price is None:
            return

        # If we already have an active sell order, check if we need to update it
        if self.active_sell_order_id:
            try:
                # Get the order details
                order = self.client.get_order(self.active_sell_order_id, self.symbol)

                # If the order is still active and the price has risen significantly, cancel and replace
                if order['status'] == 'NEW' and current_price > self.last_buy_price * 1.01:  # 1% price increase
                    logger.info(f"Price increased significantly. Cancelling order {self.active_sell_order_id} and placing new one.")
                    self.client.cancel_order(self.active_sell_order_id, self.symbol)
                    self.active_sell_order_id = None
                else:
                    # Order is still valid, no need to do anything
                    return
            except Exception as e:
                logger.error(f"Error checking active sell order: {str(e)}")
                self.active_sell_order_id = None  # Reset to allow placing a new order

        # Check if we have enough coin balance to sell
        coin_balance = self.get_coin_balance()
        if coin_balance <= 0:
            logger.info("No coin balance available for selling")
            return

        # Check if the current price has reached the trigger price for the current grid
        grid_trigger_percentage = config.GRID_SELL_TRIGGER_PERCENTAGES[self.current_grid_sell_index]
        trigger_price = self.last_buy_price * grid_trigger_percentage

        if current_price >= trigger_price:
            # Calculate stop and limit prices
            stop_percentage = config.GRID_SELL_STOP_PERCENTAGES[self.current_grid_sell_index]
            limit_percentage = config.GRID_SELL_LIMIT_PERCENTAGES[self.current_grid_sell_index]

            stop_price = current_price * stop_percentage
            limit_price = current_price * limit_percentage

            # Calculate quantity based on percentage of available balance
            quantity_percentage = config.GRID_SELL_QUANTITIES_PERCENTAGES[self.current_grid_sell_index]
            quantity = coin_balance * quantity_percentage
            quantity = self.client.round_quantity(quantity)

            try:
                # Place stop-limit order
                order = self.client.place_stop_limit_order(
                    side='SELL',
                    quantity=quantity,
                    stop_price=stop_price,
                    limit_price=limit_price,
                    position_side='LONG',
                    symbol=self.symbol
                )

                self.active_sell_order_id = order['orderId']

                logger.info(f"Placed grid sell #{self.current_grid_sell_index + 1} order: Stop price: {stop_price}, Limit price: {limit_price}, Quantity: {quantity}")
                self.telegram.send_message(f"🔴 Grid Sell #{self.current_grid_sell_index + 1} order placed for {self.symbol}\nStop price: {stop_price}\nLimit price: {limit_price}\nQuantity: {quantity}")

            except Exception as e:
                error_msg = f"Error placing grid sell order: {str(e)}"
                logger.error(error_msg)
                self.telegram.notify_error(error_msg)

    def check_order_executions(self):
        """
        Check if any orders have been executed and update state accordingly
        """
        try:
            # Get recent trades
            trades = self.client.get_recent_trades(self.symbol)

            # Check if any trades match our active orders
            for trade in trades:
                # If we have an active buy order that was executed
                if self.active_buy_order_id and trade['orderId'] == self.active_buy_order_id:
                    # Update last buy price
                    executed_price = float(trade['price'])
                    executed_qty = float(trade['qty'])

                    # If this is the first buy, set the last buy price directly
                    if self.last_buy_price is None:
                        self.last_buy_price = executed_price
                    else:
                        # Calculate weighted average price for subsequent buys
                        previous_value = config.GRID_BUY_QUANTITIES_USDT[self.current_grid_buy_index - 1]
                        current_value = config.GRID_BUY_QUANTITIES_USDT[self.current_grid_buy_index]

                        # Calculate new average price
                        self.last_buy_price = (previous_value + current_value) / (previous_value / self.last_buy_price + current_value / executed_price)

                    logger.info(f"Buy order executed at {executed_price}. Updated last buy price to {self.last_buy_price}")
                    self.telegram.send_message(f"✅ Grid Buy #{self.current_grid_buy_index + 1} executed for {self.symbol}\nPrice: {executed_price}\nQuantity: {executed_qty}\nNew average buy price: {self.last_buy_price}")

                    # Move to next buy grid
                    self.active_buy_order_id = None
                    self.current_grid_buy_index = min(self.current_grid_buy_index + 1, len(config.GRID_BUY_TRIGGER_PERCENTAGES) - 1)

                # If we have an active sell order that was executed
                elif self.active_sell_order_id and trade['orderId'] == self.active_sell_order_id:
                    executed_price = float(trade['price'])
                    executed_qty = float(trade['qty'])

                    # Calculate profit
                    profit_percentage = ((executed_price / self.last_buy_price) - 1) * 100

                    logger.info(f"Sell order executed at {executed_price}. Profit: {profit_percentage:.2f}%")
                    self.telegram.send_message(f"💰 Grid Sell #{self.current_grid_sell_index + 1} executed for {self.symbol}\nPrice: {executed_price}\nQuantity: {executed_qty}\nProfit: {profit_percentage:.2f}%")

                    # Move to next sell grid
                    self.active_sell_order_id = None
                    self.current_grid_sell_index = min(self.current_grid_sell_index + 1, len(config.GRID_SELL_TRIGGER_PERCENTAGES) - 1)

                    # If we've sold all our coins, reset the last buy price
                    remaining_balance = self.get_coin_balance()
                    if remaining_balance <= 0.0001:  # Small threshold to account for dust
                        self.last_buy_price = None
                        self.current_grid_sell_index = 0
                        logger.info("All coins sold. Resetting last buy price and sell grid index.")

        except Exception as e:
            logger.error(f"Error checking order executions: {str(e)}")

    def run(self):
        """
        Main bot loop
        """
        logger.info(f"Starting grid trading bot for {self.symbol}")
        self.telegram.send_message(f"🤖 Grid trading bot started for {self.symbol}")

        # No initial PnL notification for grid trading

        while True:
            try:
                # Get current price
                current_price = self.client.get_current_price(self.symbol)

                # Update lowest price
                self.update_lowest_price(current_price)

                # Check if we should remove the last buy price
                if self.should_remove_last_buy_price():
                    logger.info(f"Coin value below threshold. Removing last buy price.")
                    self.last_buy_price = None
                    self.current_grid_sell_index = 0

                # Check for order executions
                self.check_order_executions()

                # Check and place buy order if needed
                self.check_and_place_buy_order(current_price)

                # Check and place sell order if needed
                self.check_and_place_sell_order(current_price)

                # Sleep for the configured interval
                time.sleep(config.CHECK_INTERVAL)

            except Exception as e:
                error_msg = f"Error in grid trading bot run loop: {str(e)}\n{traceback.format_exc()}"
                logger.error(error_msg)
                self.telegram.notify_error(error_msg)

                # Sleep for a bit before retrying
                time.sleep(10)


class GridTradingManager:
    def __init__(self, symbols=None):
        self.symbols = symbols or [config.SYMBOL]
        self.bots = {}
        self.threads = {}

    def start_bot(self, symbol):
        """
        Start a grid trading bot for a symbol
        """
        import threading

        bot = GridTradingBot(symbol)
        self.bots[symbol] = bot

        # Create and start thread
        thread = threading.Thread(target=bot.run, daemon=True)
        thread.start()

        self.threads[symbol] = thread

        logger.info(f"Started grid trading bot for {symbol}")

    def start_all(self):
        """
        Start grid trading bots for all configured symbols
        """
        for symbol in self.symbols:
            self.start_bot(symbol)
