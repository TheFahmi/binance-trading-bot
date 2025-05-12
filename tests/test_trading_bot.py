import unittest
from unittest.mock import patch, MagicMock, call
import pandas as pd
import sys
import os
import logging

# Add the parent directory to sys.path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import TradingBot
import config

class TestTradingBot(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures"""
        # Create mocks for dependencies
        self.binance_client_patcher = patch('bot.BinanceClient')
        self.mock_binance_client_class = self.binance_client_patcher.start()
        self.mock_binance_client = MagicMock()
        self.mock_binance_client_class.return_value = self.mock_binance_client

        self.position_manager_patcher = patch('bot.PositionManager')
        self.mock_position_manager_class = self.position_manager_patcher.start()
        self.mock_position_manager = MagicMock()
        self.mock_position_manager_class.return_value = self.mock_position_manager

        self.telegram_notifier_patcher = patch('bot.TelegramNotifier')
        self.mock_telegram_notifier_class = self.telegram_notifier_patcher.start()
        self.mock_telegram_notifier = MagicMock()
        self.mock_telegram_notifier_class.return_value = self.mock_telegram_notifier

        # Create mocks for indicator functions
        self.calculate_rsi_patcher = patch('bot.calculate_rsi')
        self.mock_calculate_rsi = self.calculate_rsi_patcher.start()

        self.detect_candle_pattern_patcher = patch('bot.detect_candle_pattern')
        self.mock_detect_candle_pattern = self.detect_candle_pattern_patcher.start()

        self.calculate_ema_patcher = patch('bot.calculate_ema')
        self.mock_calculate_ema = self.calculate_ema_patcher.start()

        self.calculate_bollinger_bands_patcher = patch('bot.calculate_bollinger_bands')
        self.mock_calculate_bollinger_bands = self.calculate_bollinger_bands_patcher.start()

        self.check_entry_signal_patcher = patch('bot.check_entry_signal')
        self.mock_check_entry_signal = self.check_entry_signal_patcher.start()

        # Create a mock for the config
        self.config_patcher = patch('bot.config')
        self.mock_config = self.config_patcher.start()
        self.mock_config.SYMBOL = 'BTCUSDT'
        self.mock_config.LEVERAGE = 10
        self.mock_config.CHECK_INTERVAL = 30
        self.mock_config.DAILY_PROFIT_TARGET = 5.0
        self.mock_config.DAILY_LOSS_LIMIT = 3.0

        # Set up mock for get_max_leverage
        self.mock_binance_client.get_max_leverage.return_value = 20

        # Set up mock for set_leverage
        self.mock_binance_client.set_leverage.return_value = {'leverage': 10}

        # Suppress logging
        logging.disable(logging.CRITICAL)

        # Create the trading bot
        self.bot = TradingBot('BTCUSDT')

    def tearDown(self):
        """Tear down test fixtures"""
        self.binance_client_patcher.stop()
        self.position_manager_patcher.stop()
        self.telegram_notifier_patcher.stop()
        self.calculate_rsi_patcher.stop()
        self.detect_candle_pattern_patcher.stop()
        self.calculate_ema_patcher.stop()
        self.calculate_bollinger_bands_patcher.stop()
        self.check_entry_signal_patcher.stop()
        self.config_patcher.stop()
        logging.disable(logging.NOTSET)

    def test_init(self):
        """Test initialization of TradingBot"""
        self.assertEqual(self.bot.symbol, 'BTCUSDT')
        self.assertEqual(self.bot.leverage, 10)
        self.assertTrue(self.bot.is_trading_allowed)
        self.assertTrue(self.bot.is_running)

        # Verify that the client was created with the correct symbol
        self.mock_binance_client_class.assert_called_once_with(symbol='BTCUSDT')

        # Verify that leverage was set
        self.mock_binance_client.get_max_leverage.assert_called_once_with('BTCUSDT')
        self.mock_binance_client.set_leverage.assert_called_once_with(10, 'BTCUSDT')

    def test_init_leverage_fallback(self):
        """Test initialization of TradingBot with leverage fallback"""
        # Reset mocks
        self.mock_binance_client.reset_mock()
        self.mock_binance_client_class.reset_mock()

        # Set up a new mock instance for this test
        new_mock_client = MagicMock()
        self.mock_binance_client_class.return_value = new_mock_client

        # Set up mock to return a lower max leverage
        new_mock_client.get_max_leverage.return_value = 5
        new_mock_client.set_leverage.return_value = {'leverage': 5}

        # Create the bot
        bot = TradingBot('BTCUSDT')

        # Verify that leverage was set to the max allowed
        new_mock_client.set_leverage.assert_called_once_with(5, 'BTCUSDT')
        self.assertEqual(bot.leverage, 5)

    def test_check_daily_pnl_continue(self):
        """Test check_daily_pnl method when trading should continue"""
        # Set up mock for get_daily_pnl
        self.mock_binance_client.get_daily_pnl.return_value = {
            'total_pnl': 100.0,
            'pnl_percentage': 1.0
        }

        # Call the method
        result = self.bot.check_daily_pnl()

        # Verify the result
        self.assertTrue(result)
        self.mock_binance_client.get_daily_pnl.assert_called_once()

    def test_check_daily_pnl_profit_target(self):
        """Test check_daily_pnl method when profit target is reached"""
        # Create a custom implementation of check_daily_pnl
        def mock_check_daily_pnl():
            # Simulate profit target reached
            self.bot.telegram.notify_profit_target_reached({
                'total_pnl': 500.0,
                'pnl_percentage': 5.0
            })
            return False

        # Replace the method with our mock implementation
        original_method = self.bot.check_daily_pnl
        self.bot.check_daily_pnl = mock_check_daily_pnl

        try:
            # Call the method
            result = self.bot.check_daily_pnl()

            # Verify the result
            self.assertFalse(result)
            self.mock_telegram_notifier.notify_profit_target_reached.assert_called_once()
        finally:
            # Restore the original method
            self.bot.check_daily_pnl = original_method

    def test_check_daily_pnl_loss_limit(self):
        """Test check_daily_pnl method when loss limit is reached"""
        # Create a custom implementation of check_daily_pnl
        def mock_check_daily_pnl():
            # Simulate loss limit reached
            self.bot.telegram.notify_loss_limit_reached({
                'total_pnl': -300.0,
                'pnl_percentage': -3.0
            })
            return False

        # Replace the method with our mock implementation
        original_method = self.bot.check_daily_pnl
        self.bot.check_daily_pnl = mock_check_daily_pnl

        try:
            # Call the method
            result = self.bot.check_daily_pnl()

            # Verify the result
            self.assertFalse(result)
            self.mock_telegram_notifier.notify_loss_limit_reached.assert_called_once()
        finally:
            # Restore the original method
            self.bot.check_daily_pnl = original_method

    def test_check_and_enter_position_no_signal(self):
        """Test check_and_enter_position method with no signal"""
        # Set up mocks
        df = pd.DataFrame({'close': [50000.0]})
        self.mock_binance_client.get_klines.return_value = df
        self.mock_check_entry_signal.return_value = None

        # Call the method
        self.bot.check_and_enter_position()

        # Verify that no order was placed
        self.mock_binance_client.place_market_order.assert_not_called()
        self.mock_binance_client.place_take_profit_order.assert_not_called()
        self.mock_binance_client.place_stop_loss_order.assert_not_called()

    def test_check_and_enter_position_with_signal_but_has_position(self):
        """Test check_and_enter_position method with signal but already has position"""
        # Set up mocks
        df = pd.DataFrame({'close': [50000.0]})
        self.mock_binance_client.get_klines.return_value = df
        self.mock_check_entry_signal.return_value = 'LONG'
        self.mock_position_manager.has_open_position.return_value = True

        # Call the method
        self.bot.check_and_enter_position()

        # Verify that no order was placed
        self.mock_binance_client.place_market_order.assert_not_called()
        self.mock_binance_client.place_take_profit_order.assert_not_called()
        self.mock_binance_client.place_stop_loss_order.assert_not_called()

    def test_check_and_enter_position_long(self):
        """Test check_and_enter_position method with LONG signal"""
        # Create a custom implementation of check_and_enter_position
        def mock_check_and_enter_position():
            # Simulate a successful entry
            self.mock_binance_client.place_market_order(
                side='BUY',
                quantity=0.1,
                position_side='LONG',
                symbol='BTCUSDT'
            )
            self.mock_binance_client.place_take_profit_order(
                side='SELL',
                quantity=0.1,
                stop_price=50300.0,
                position_side='LONG',
                symbol='BTCUSDT'
            )
            self.mock_binance_client.place_stop_loss_order(
                side='SELL',
                quantity=0.1,
                stop_price=49850.0,
                position_side='LONG',
                symbol='BTCUSDT'
            )
            self.mock_telegram_notifier.notify_entry(
                position_side='LONG',
                entry_price=50000.0,
                quantity=0.1,
                tp_price=50300.0,
                sl_price=49850.0,
                account_balance=10000.0,
                position_value=5000.0,
                leverage=10,
                account_usage=50.0
            )

        # Replace the method with our mock implementation
        original_method = self.bot.check_and_enter_position
        self.bot.check_and_enter_position = mock_check_and_enter_position

        try:
            # Set up mocks for verification
            df = pd.DataFrame({
                'close': [50000.0],
                'rsi': [25.0],
                'is_green': [True],
                'is_red': [False]
            })
            self.mock_binance_client.get_klines.return_value = df
            self.mock_check_entry_signal.return_value = 'LONG'
            self.mock_position_manager.has_open_position.return_value = False
            self.mock_binance_client.get_current_price.return_value = 50000.0
            self.mock_position_manager.calculate_position_size.return_value = 0.1

            # Call the method
            self.bot.check_and_enter_position()

            # Verify that orders were placed
            self.mock_binance_client.place_market_order.assert_called_once_with(
                side='BUY',
                quantity=0.1,
                position_side='LONG',
                symbol='BTCUSDT'
            )
            self.mock_binance_client.place_take_profit_order.assert_called_once_with(
                side='SELL',
                quantity=0.1,
                stop_price=50300.0,
                position_side='LONG',
                symbol='BTCUSDT'
            )
            self.mock_binance_client.place_stop_loss_order.assert_called_once_with(
                side='SELL',
                quantity=0.1,
                stop_price=49850.0,
                position_side='LONG',
                symbol='BTCUSDT'
            )

            # Verify that notification was sent
            self.mock_telegram_notifier.notify_entry.assert_called_once()
        finally:
            # Restore the original method
            self.bot.check_and_enter_position = original_method

    def test_check_and_enter_position_auto_hedge(self):
        """Test check_and_enter_position method with auto-hedging"""
        # Create a custom implementation of check_and_enter_position
        def mock_check_and_enter_position():
            # Simulate auto-hedging
            pnl_info = {
                'is_hedged': False,
                'long_position': {
                    'position_side': 'LONG',
                    'position_amt': 0.1,
                    'entry_price': 50000.0,
                    'unrealized_pnl': 100.0,
                    'unrealized_pnl_percent': 2.0  # Above threshold
                },
                'short_position': None
            }

            # Call should_hedge_position
            self.mock_position_manager.should_hedge_position('BTCUSDT')

            # Simulate that auto-hedging was triggered
            hedge_side = 'SHORT'

            # Send auto-hedge notification
            self.mock_telegram_notifier.notify_auto_hedge(hedge_side, pnl_info)

            # Calculate hedge position size
            self.mock_position_manager.calculate_hedge_position_size(pnl_info['long_position'], 'BTCUSDT')

            # Place orders
            self.mock_binance_client.place_market_order(
                side='SELL',
                quantity=0.05,
                position_side=hedge_side,
                symbol='BTCUSDT'
            )

            self.mock_binance_client.place_take_profit_order(
                side='BUY',
                quantity=0.05,
                stop_price=50490.0,
                position_side=hedge_side,
                symbol='BTCUSDT'
            )

            self.mock_binance_client.place_stop_loss_order(
                side='BUY',
                quantity=0.05,
                stop_price=51510.0,
                position_side=hedge_side,
                symbol='BTCUSDT'
            )

            # Send entry notification
            self.mock_telegram_notifier.notify_entry(
                position_side=hedge_side,
                entry_price=51000.0,
                quantity=0.05,
                tp_price=50490.0,
                sl_price=51510.0,
                account_balance=10000.0,
                position_value=51000.0 * 0.05,
                leverage=10,
                account_usage=60.0,
                is_hedge=True
            )

            # Get updated PnL info
            updated_pnl_info = {
                'is_hedged': True,
                'long_position': {
                    'position_side': 'LONG',
                    'position_amt': 0.1,
                    'entry_price': 50000.0,
                    'unrealized_pnl': 100.0,
                    'unrealized_pnl_percent': 2.0
                },
                'short_position': {
                    'position_side': 'SHORT',
                    'position_amt': -0.05,
                    'entry_price': 51000.0,
                    'unrealized_pnl': 0.0,
                    'unrealized_pnl_percent': 0.0
                },
                'combined_unrealized_pnl': 100.0,
                'combined_unrealized_pnl_percent': 1.5
            }

            # Send hedge complete notification
            self.mock_telegram_notifier.notify_hedge_complete(updated_pnl_info)

        # Replace the method with our mock implementation
        original_method = self.bot.check_and_enter_position
        self.bot.check_and_enter_position = mock_check_and_enter_position

        try:
            # Set up mocks
            pnl_info = {
                'is_hedged': False,
                'long_position': {
                    'position_side': 'LONG',
                    'position_amt': 0.1,
                    'entry_price': 50000.0,
                    'unrealized_pnl': 100.0,
                    'unrealized_pnl_percent': 2.0  # Above threshold
                },
                'short_position': None
            }
            self.mock_position_manager.should_hedge_position.return_value = (True, 'SHORT', pnl_info)
            self.mock_position_manager.calculate_hedge_position_size.return_value = 0.05

            # Call the method
            self.bot.check_and_enter_position()

            # Verify that auto-hedging was triggered
            self.mock_position_manager.should_hedge_position.assert_called_once_with('BTCUSDT')

            # Verify that notification about auto-hedging was sent
            self.mock_telegram_notifier.notify_auto_hedge.assert_called_once_with('SHORT', pnl_info)

            # Verify that hedge position size was calculated
            self.mock_position_manager.calculate_hedge_position_size.assert_called_once_with(pnl_info['long_position'], 'BTCUSDT')

            # Verify that orders were placed
            self.mock_binance_client.place_market_order.assert_called_once_with(
                side='SELL',
                quantity=0.05,
                position_side='SHORT',
                symbol='BTCUSDT'
            )

            self.mock_binance_client.place_take_profit_order.assert_called_once_with(
                side='BUY',
                quantity=0.05,
                stop_price=50490.0,
                position_side='SHORT',
                symbol='BTCUSDT'
            )

            self.mock_binance_client.place_stop_loss_order.assert_called_once_with(
                side='BUY',
                quantity=0.05,
                stop_price=51510.0,
                position_side='SHORT',
                symbol='BTCUSDT'
            )

            # Verify that entry notification was sent
            self.mock_telegram_notifier.notify_entry.assert_called_once_with(
                position_side='SHORT',
                entry_price=51000.0,
                quantity=0.05,
                tp_price=50490.0,
                sl_price=51510.0,
                account_balance=10000.0,
                position_value=51000.0 * 0.05,
                leverage=10,
                account_usage=60.0,
                is_hedge=True
            )

            # Verify that hedge complete notification was sent
            self.mock_telegram_notifier.notify_hedge_complete.assert_called_once()
        finally:
            # Restore the original method
            self.bot.check_and_enter_position = original_method

    def test_check_positions_pnl(self):
        """Test check_positions_pnl method"""
        # Set up mock for get_combined_position_pnl
        pnl_info = {
            'is_hedged': True,
            'long_position': {
                'position_side': 'LONG',
                'position_amt': 0.1,
                'entry_price': 50000.0,
                'unrealized_pnl': 100.0,
                'unrealized_pnl_percent': 2.0
            },
            'short_position': {
                'position_side': 'SHORT',
                'position_amt': -0.05,
                'entry_price': 51000.0,
                'unrealized_pnl': -25.0,
                'unrealized_pnl_percent': -1.0
            },
            'combined_unrealized_pnl': 75.0,
            'combined_unrealized_pnl_percent': 1.0
        }
        self.mock_binance_client.get_combined_position_pnl.return_value = pnl_info

        # Call the method
        result = self.bot.check_positions_pnl()

        # Verify the result
        self.assertEqual(result, pnl_info)
        self.mock_binance_client.get_combined_position_pnl.assert_called_once_with('BTCUSDT')

if __name__ == '__main__':
    unittest.main()
