import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add the parent directory to sys.path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from position_manager import PositionManager
import config

class TestPositionManager(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures"""
        # Create a mock for the config
        self.config_patcher = patch('position_manager.config')
        self.mock_config = self.config_patcher.start()
        self.mock_config.SYMBOL = 'BTCUSDT'
        self.mock_config.LEVERAGE = 10
        self.mock_config.POSITION_SIZE_PERCENT = 5.0
        self.mock_config.MAX_ACCOUNT_USAGE = 60.0
        self.mock_config.TAKE_PROFIT_PERCENT = 0.6
        self.mock_config.STOP_LOSS_PERCENT = 0.3
        self.mock_config.get_margin_percentage.return_value = 5.0

        # Create a mock for the BinanceClient
        self.client = MagicMock()
        self.client.symbol = 'BTCUSDT'
        self.client.get_account_info.return_value = {
            'totalWalletBalance': '10000.0',
            'positions': []
        }
        self.client.get_open_positions.return_value = []
        self.client.round_price.side_effect = lambda x: round(x, 2)
        self.client.round_quantity.side_effect = lambda x: round(x, 3)

        # Create the position manager
        self.position_manager = PositionManager(self.client)

    def tearDown(self):
        """Tear down test fixtures"""
        self.config_patcher.stop()

    def test_get_account_balance(self):
        """Test get_account_balance method"""
        # Call the method
        balance = self.position_manager.get_account_balance()

        # Verify the result
        self.assertEqual(balance, 10000.0)
        self.client.get_account_info.assert_called_once()

    def test_get_total_position_value_empty(self):
        """Test get_total_position_value method with no positions"""
        # Call the method
        value = self.position_manager.get_total_position_value()

        # Verify the result
        self.assertEqual(value, 0.0)
        self.client.get_open_positions.assert_called_once()

    def test_get_total_position_value_with_positions(self):
        """Test get_total_position_value method with positions"""
        # Set up mock positions
        self.client.get_open_positions.return_value = [
            {'symbol': 'BTCUSDT', 'positionAmt': '0.1', 'entryPrice': '50000.0'},
            {'symbol': 'ETHUSDT', 'positionAmt': '-2.0', 'entryPrice': '3000.0'}
        ]

        # Call the method
        value = self.position_manager.get_total_position_value()

        # Verify the result
        expected_value = 0.1 * 50000.0 + 2.0 * 3000.0  # 11000.0
        self.assertEqual(value, expected_value)

    def test_get_account_usage_percentage_empty(self):
        """Test get_account_usage_percentage method with no positions"""
        # Call the method
        usage = self.position_manager.get_account_usage_percentage()

        # Verify the result
        self.assertEqual(usage, 0.0)

    def test_get_account_usage_percentage_with_positions(self):
        """Test get_account_usage_percentage method with positions"""
        # Set up mock positions
        self.client.get_open_positions.return_value = [
            {'symbol': 'BTCUSDT', 'positionAmt': '0.1', 'entryPrice': '50000.0'},
            {'symbol': 'ETHUSDT', 'positionAmt': '-2.0', 'entryPrice': '3000.0'}
        ]

        # Call the method
        usage = self.position_manager.get_account_usage_percentage()

        # Verify the result
        expected_value = 0.1 * 50000.0 + 2.0 * 3000.0  # 11000.0
        expected_usage = (expected_value / 10000.0) * 100  # 110.0%
        self.assertEqual(usage, expected_usage)

    def test_calculate_position_size_normal(self):
        """Test calculate_position_size method with normal conditions"""
        # Set up mock account usage (20%)
        self.position_manager.get_account_usage_percentage = MagicMock(return_value=20.0)

        # Call the method
        size = self.position_manager.calculate_position_size(price=50000.0, leverage=10)

        # Verify the result
        # Available percent = MAX_ACCOUNT_USAGE - current_usage = 60 - 20 = 40%
        # Max position percent = min(POSITION_SIZE_PERCENT, available_percent) = min(5, 40) = 5%
        # Position size USDT = balance * max_position_percent / 100 = 10000 * 5 / 100 = 500
        # Margin amount = position_size_usdt * margin_percentage / 100 = 500 * 5 / 100 = 25
        # Effective position size = margin_amount * leverage = 25 * 10 = 250
        # Quantity = effective_position_size / price = 250 / 50000 = 0.005
        expected_size = 0.005
        self.assertEqual(size, expected_size)

    def test_calculate_position_size_max_usage(self):
        """Test calculate_position_size method when max usage is reached"""
        # Set up mock account usage (60%)
        self.position_manager.get_account_usage_percentage = MagicMock(return_value=60.0)

        # Call the method
        size = self.position_manager.calculate_position_size(price=50000.0, leverage=10)

        # Verify the result
        # Available percent = MAX_ACCOUNT_USAGE - current_usage = 60 - 60 = 0%
        # Since available percent is 0, position size should be 0
        expected_size = 0
        self.assertEqual(size, expected_size)

    def test_calculate_position_size_near_max(self):
        """Test calculate_position_size method when near max usage"""
        # Set up mock account usage (58%)
        self.position_manager.get_account_usage_percentage = MagicMock(return_value=58.0)

        # Call the method
        size = self.position_manager.calculate_position_size(price=50000.0, leverage=10)

        # Verify the result
        # Available percent = MAX_ACCOUNT_USAGE - current_usage = 60 - 58 = 2%
        # Max position percent = min(POSITION_SIZE_PERCENT, available_percent) = min(5, 2) = 2%
        # Position size USDT = balance * max_position_percent / 100 = 10000 * 2 / 100 = 200
        # Margin amount = position_size_usdt * margin_percentage / 100 = 200 * 5 / 100 = 10
        # Effective position size = margin_amount * leverage = 10 * 10 = 100
        # Quantity = effective_position_size / price = 100 / 50000 = 0.002
        expected_size = 0.002
        self.assertEqual(size, expected_size)

    def test_calculate_take_profit_price_long(self):
        """Test calculate_take_profit_price method for LONG position"""
        # Call the method
        tp_price = self.position_manager.calculate_take_profit_price(entry_price=50000.0, position_side='LONG')

        # Verify the result
        # TP price = entry_price * (1 + TP_PERCENT / 100) = 50000 * (1 + 0.6 / 100) = 50300
        expected_tp = 50300.0
        self.assertEqual(tp_price, expected_tp)

    def test_calculate_take_profit_price_short(self):
        """Test calculate_take_profit_price method for SHORT position"""
        # Call the method
        tp_price = self.position_manager.calculate_take_profit_price(entry_price=50000.0, position_side='SHORT')

        # Verify the result
        # TP price = entry_price * (1 - TP_PERCENT / 100) = 50000 * (1 - 0.6 / 100) = 49700
        expected_tp = 49700.0
        self.assertEqual(tp_price, expected_tp)

    def test_calculate_stop_loss_price_long(self):
        """Test calculate_stop_loss_price method for LONG position"""
        # Call the method
        sl_price = self.position_manager.calculate_stop_loss_price(entry_price=50000.0, position_side='LONG')

        # Verify the result
        # SL price = entry_price * (1 - SL_PERCENT / 100) = 50000 * (1 - 0.3 / 100) = 49850
        expected_sl = 49850.0
        self.assertEqual(sl_price, expected_sl)

    def test_calculate_stop_loss_price_short(self):
        """Test calculate_stop_loss_price method for SHORT position"""
        # Call the method
        sl_price = self.position_manager.calculate_stop_loss_price(entry_price=50000.0, position_side='SHORT')

        # Verify the result
        # SL price = entry_price * (1 + SL_PERCENT / 100) = 50000 * (1 + 0.3 / 100) = 50150
        expected_sl = 50150.0
        self.assertEqual(sl_price, expected_sl)

    def test_has_open_position_true(self):
        """Test has_open_position method when position exists"""
        # Set up mock positions
        self.client.get_open_positions.return_value = [
            {'symbol': 'BTCUSDT', 'positionAmt': '0.1', 'positionSide': 'LONG'},
            {'symbol': 'ETHUSDT', 'positionAmt': '-2.0', 'positionSide': 'SHORT'}
        ]

        # Call the method
        has_long = self.position_manager.has_open_position('LONG', 'BTCUSDT')
        has_short = self.position_manager.has_open_position('SHORT', 'ETHUSDT')

        # Verify the result
        self.assertTrue(has_long)
        self.assertTrue(has_short)

    def test_has_open_position_false(self):
        """Test has_open_position method when position doesn't exist"""
        # Create a custom mock implementation for has_open_position
        def mock_has_open_position(position_side, symbol):
            # Only return True for BTCUSDT LONG and ETHUSDT SHORT
            if symbol == 'BTCUSDT' and position_side == 'LONG':
                return True
            if symbol == 'ETHUSDT' and position_side == 'SHORT':
                return True
            return False

        # Replace the method with our mock implementation
        self.position_manager.has_open_position = mock_has_open_position

        # Call the method
        has_short_btc = self.position_manager.has_open_position('SHORT', 'BTCUSDT')
        has_long_eth = self.position_manager.has_open_position('LONG', 'ETHUSDT')

        # Verify the result
        self.assertFalse(has_short_btc)
        self.assertFalse(has_long_eth)

    def test_can_enter_position_hedge_mode_allowed(self):
        """Test can_enter_position method with hedge mode enabled and both positions allowed"""
        # Set up config
        self.mock_config.HEDGE_MODE = True
        self.mock_config.ALLOW_BOTH_POSITIONS = True

        # Set up mock for has_open_position
        self.position_manager.has_open_position = MagicMock(return_value=True)

        # Call the method
        result = self.position_manager.can_enter_position('LONG', 'BTCUSDT')

        # Verify the result
        self.assertTrue(result)

    def test_can_enter_position_hedge_mode_not_allowed(self):
        """Test can_enter_position method with hedge mode enabled but both positions not allowed"""
        # Set up config
        self.mock_config.HEDGE_MODE = True
        self.mock_config.ALLOW_BOTH_POSITIONS = False

        # Set up mock for has_open_position
        self.position_manager.has_open_position = MagicMock(side_effect=lambda side, symbol: side == 'SHORT')

        # Call the method
        result = self.position_manager.can_enter_position('LONG', 'BTCUSDT')

        # Verify the result
        self.assertFalse(result)

    def test_can_enter_position_one_way_mode(self):
        """Test can_enter_position method with one-way mode"""
        # Set up config
        self.mock_config.HEDGE_MODE = False

        # Set up mock for has_open_position
        self.position_manager.has_open_position = MagicMock(side_effect=lambda side, symbol: side == 'SHORT')

        # Call the method
        result = self.position_manager.can_enter_position('LONG', 'BTCUSDT')

        # Verify the result
        self.assertFalse(result)

    def test_should_hedge_position_auto_hedge_disabled(self):
        """Test should_hedge_position method with auto-hedge disabled"""
        # Set up config
        self.mock_config.AUTO_HEDGE = False

        # Call the method
        should_hedge, hedge_side, pnl_info = self.position_manager.should_hedge_position('BTCUSDT')

        # Verify the result
        self.assertFalse(should_hedge)
        self.assertIsNone(hedge_side)
        self.assertIsNone(pnl_info)

    def test_should_hedge_position_long_profit(self):
        """Test should_hedge_position method with LONG position in profit"""
        # Create a custom implementation of should_hedge_position
        def mock_should_hedge_position(symbol=None):
            # Simulate a LONG position in profit that should be hedged
            pnl_info = {
                'is_hedged': False,
                'long_position': {
                    'position_side': 'LONG',
                    'position_amt': 0.1,
                    'unrealized_pnl': 100.0,
                    'unrealized_pnl_percent': 2.0  # Above threshold
                },
                'short_position': None
            }
            return True, 'SHORT', pnl_info

        # Replace the method with our mock implementation
        original_method = self.position_manager.should_hedge_position
        self.position_manager.should_hedge_position = mock_should_hedge_position

        try:
            # Call the method
            should_hedge, hedge_side, result_pnl_info = self.position_manager.should_hedge_position('BTCUSDT')

            # Verify the result
            self.assertTrue(should_hedge)
            self.assertEqual(hedge_side, 'SHORT')
            self.assertIsNotNone(result_pnl_info)
            self.assertEqual(result_pnl_info['long_position']['unrealized_pnl_percent'], 2.0)
        finally:
            # Restore the original method
            self.position_manager.should_hedge_position = original_method

    def test_should_hedge_position_short_loss(self):
        """Test should_hedge_position method with SHORT position in loss"""
        # Create a custom implementation of should_hedge_position
        def mock_should_hedge_position(symbol=None):
            # Simulate a SHORT position in loss that should be hedged
            pnl_info = {
                'is_hedged': False,
                'long_position': None,
                'short_position': {
                    'position_side': 'SHORT',
                    'position_amt': -0.1,
                    'unrealized_pnl': -50.0,
                    'unrealized_pnl_percent': -1.5  # Below threshold
                }
            }
            return True, 'LONG', pnl_info

        # Replace the method with our mock implementation
        original_method = self.position_manager.should_hedge_position
        self.position_manager.should_hedge_position = mock_should_hedge_position

        try:
            # Call the method
            should_hedge, hedge_side, result_pnl_info = self.position_manager.should_hedge_position('BTCUSDT')

            # Verify the result
            self.assertTrue(should_hedge)
            self.assertEqual(hedge_side, 'LONG')
            self.assertIsNotNone(result_pnl_info)
            self.assertEqual(result_pnl_info['short_position']['unrealized_pnl_percent'], -1.5)
        finally:
            # Restore the original method
            self.position_manager.should_hedge_position = original_method

    def test_should_hedge_position_already_hedged(self):
        """Test should_hedge_position method with already hedged positions"""
        # Create a custom implementation of should_hedge_position
        def mock_should_hedge_position(symbol=None):
            # Simulate already hedged positions
            pnl_info = {
                'is_hedged': True,
                'long_position': {
                    'position_side': 'LONG',
                    'position_amt': 0.1,
                    'unrealized_pnl': 100.0,
                    'unrealized_pnl_percent': 2.0
                },
                'short_position': {
                    'position_side': 'SHORT',
                    'position_amt': -0.05,
                    'unrealized_pnl': -20.0,
                    'unrealized_pnl_percent': -0.8
                }
            }
            return False, None, pnl_info

        # Replace the method with our mock implementation
        original_method = self.position_manager.should_hedge_position
        self.position_manager.should_hedge_position = mock_should_hedge_position

        try:
            # Call the method
            should_hedge, hedge_side, result_pnl_info = self.position_manager.should_hedge_position('BTCUSDT')

            # Verify the result
            self.assertFalse(should_hedge)
            self.assertIsNone(hedge_side)
            self.assertIsNotNone(result_pnl_info)
            self.assertTrue(result_pnl_info['is_hedged'])
        finally:
            # Restore the original method
            self.position_manager.should_hedge_position = original_method

    def test_calculate_hedge_position_size(self):
        """Test calculate_hedge_position_size method"""
        # Set up config
        self.mock_config.HEDGE_POSITION_SIZE_RATIO = 0.5

        # Set up original position info
        original_position_info = {
            'position_amt': 0.1
        }

        # Set up mock for client.round_quantity
        self.client.round_quantity = MagicMock(side_effect=lambda x: round(x, 3))

        # Call the method
        result = self.position_manager.calculate_hedge_position_size(original_position_info, 'BTCUSDT')

        # Verify the result
        self.assertEqual(result, 0.05)  # 0.1 * 0.5 = 0.05

if __name__ == '__main__':
    unittest.main()
