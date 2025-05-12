import unittest
from unittest.mock import patch, MagicMock
import logging

import config
from grid_trading import GridTradingBot

class TestGridTradingBot(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        # Create mocks
        self.binance_client_patcher = patch('grid_trading.BinanceClient')
        self.mock_binance_client = self.binance_client_patcher.start()
        
        # Mock the client instance
        self.mock_client_instance = MagicMock()
        self.mock_binance_client.return_value = self.mock_client_instance
        
        self.telegram_notifier_patcher = patch('grid_trading.TelegramNotifier')
        self.mock_telegram_notifier = self.telegram_notifier_patcher.start()
        
        # Mock the telegram instance
        self.mock_telegram_instance = MagicMock()
        self.mock_telegram_notifier.return_value = self.mock_telegram_instance
        
        # Create a mock for the config
        self.config_patcher = patch('grid_trading.config')
        self.mock_config = self.config_patcher.start()
        self.mock_config.SYMBOL = 'BTCUSDT'
        self.mock_config.HEDGE_MODE = True
        self.mock_config.GRID_BUY_COUNT = 2
        self.mock_config.GRID_SELL_COUNT = 2
        self.mock_config.GRID_BUY_TRIGGER_PERCENTAGES = [1.0, 0.8]
        self.mock_config.GRID_BUY_STOP_PERCENTAGES = [1.05, 1.03]
        self.mock_config.GRID_BUY_LIMIT_PERCENTAGES = [1.051, 1.031]
        self.mock_config.GRID_BUY_QUANTITIES_USDT = [50, 100]
        self.mock_config.GRID_SELL_TRIGGER_PERCENTAGES = [1.05, 1.08]
        self.mock_config.GRID_SELL_STOP_PERCENTAGES = [0.97, 0.95]
        self.mock_config.GRID_SELL_LIMIT_PERCENTAGES = [0.969, 0.949]
        self.mock_config.GRID_SELL_QUANTITIES_PERCENTAGES = [0.5, 1.0]
        self.mock_config.GRID_LAST_BUY_PRICE_REMOVAL_THRESHOLD = 10.0
        
        # Suppress logging
        logging.disable(logging.CRITICAL)
        
        # Create the grid trading bot
        self.bot = GridTradingBot('BTCUSDT')
        
    def tearDown(self):
        """Tear down test fixtures"""
        self.binance_client_patcher.stop()
        self.telegram_notifier_patcher.stop()
        self.config_patcher.stop()
        logging.disable(logging.NOTSET)
        
    def test_init(self):
        """Test initialization"""
        self.assertEqual(self.bot.symbol, 'BTCUSDT')
        self.assertEqual(self.bot.last_buy_price, None)
        self.assertEqual(self.bot.lowest_price, None)
        self.assertEqual(self.bot.current_grid_buy_index, 0)
        self.assertEqual(self.bot.current_grid_sell_index, 0)
        self.assertEqual(self.bot.active_buy_order_id, None)
        self.assertEqual(self.bot.active_sell_order_id, None)
        
        # Check if position mode was set
        self.mock_client_instance.set_position_mode.assert_called_once_with(True)
        
    def test_get_coin_balance(self):
        """Test get_coin_balance method"""
        # Mock account info
        self.mock_client_instance.get_account_info.return_value = {
            'assets': [
                {'asset': 'BTC', 'walletBalance': '0.5'},
                {'asset': 'ETH', 'walletBalance': '10.0'}
            ]
        }
        
        # Test with BTC
        self.bot.symbol = 'BTCUSDT'
        self.assertEqual(self.bot.get_coin_balance(), 0.5)
        
        # Test with ETH
        self.bot.symbol = 'ETHUSDT'
        self.assertEqual(self.bot.get_coin_balance(), 10.0)
        
        # Test with non-existent asset
        self.bot.symbol = 'XRPUSDT'
        self.assertEqual(self.bot.get_coin_balance(), 0.0)
        
    def test_get_coin_value_in_usdt(self):
        """Test get_coin_value_in_usdt method"""
        # Mock get_coin_balance
        self.bot.get_coin_balance = MagicMock(return_value=0.5)
        
        # Mock current price
        self.mock_client_instance.get_current_price.return_value = 50000.0
        
        # Test
        self.assertEqual(self.bot.get_coin_value_in_usdt(), 25000.0)
        
    def test_should_remove_last_buy_price(self):
        """Test should_remove_last_buy_price method"""
        # Mock get_coin_value_in_usdt
        self.bot.get_coin_value_in_usdt = MagicMock()
        
        # Test with no last buy price
        self.bot.last_buy_price = None
        self.assertFalse(self.bot.should_remove_last_buy_price())
        
        # Test with value above threshold
        self.bot.last_buy_price = 50000.0
        self.bot.get_coin_value_in_usdt.return_value = 20.0
        self.assertFalse(self.bot.should_remove_last_buy_price())
        
        # Test with value below threshold
        self.bot.get_coin_value_in_usdt.return_value = 5.0
        self.assertTrue(self.bot.should_remove_last_buy_price())
        
    def test_update_lowest_price(self):
        """Test update_lowest_price method"""
        # Test with no previous lowest price
        self.bot.lowest_price = None
        self.bot.update_lowest_price(50000.0)
        self.assertEqual(self.bot.lowest_price, 50000.0)
        
        # Test with higher price
        self.bot.update_lowest_price(60000.0)
        self.assertEqual(self.bot.lowest_price, 50000.0)
        
        # Test with lower price
        self.bot.update_lowest_price(40000.0)
        self.assertEqual(self.bot.lowest_price, 40000.0)
        
    def test_check_and_place_buy_order(self):
        """Test check_and_place_buy_order method"""
        # Mock methods
        self.bot.get_coin_value_in_usdt = MagicMock(return_value=5.0)
        self.mock_client_instance.round_quantity.return_value = 0.001
        
        # Set lowest price
        self.bot.lowest_price = 50000.0
        
        # Test with price above lowest price
        self.bot.check_and_place_buy_order(51000.0)
        self.mock_client_instance.place_stop_limit_order.assert_not_called()
        
        # Test with price at lowest price
        self.mock_client_instance.place_stop_limit_order.return_value = {'orderId': 12345}
        self.bot.check_and_place_buy_order(50000.0)
        self.mock_client_instance.place_stop_limit_order.assert_called_once()
        self.assertEqual(self.bot.active_buy_order_id, 12345)
        
    def test_check_and_place_sell_order(self):
        """Test check_and_place_sell_order method"""
        # Mock methods
        self.bot.get_coin_balance = MagicMock(return_value=0.5)
        self.mock_client_instance.round_quantity.return_value = 0.25
        
        # Test with no last buy price
        self.bot.last_buy_price = None
        self.bot.check_and_place_sell_order(60000.0)
        self.mock_client_instance.place_stop_limit_order.assert_not_called()
        
        # Set last buy price
        self.bot.last_buy_price = 50000.0
        
        # Test with price below trigger
        self.bot.check_and_place_sell_order(51000.0)
        self.mock_client_instance.place_stop_limit_order.assert_not_called()
        
        # Test with price at trigger
        self.mock_client_instance.place_stop_limit_order.return_value = {'orderId': 67890}
        self.bot.check_and_place_sell_order(52500.0)  # 1.05 * 50000
        self.mock_client_instance.place_stop_limit_order.assert_called_once()
        self.assertEqual(self.bot.active_sell_order_id, 67890)
        
    def test_check_order_executions(self):
        """Test check_order_executions method"""
        # Mock get_recent_trades
        self.mock_client_instance.get_recent_trades.return_value = [
            {'orderId': 12345, 'price': '50000.0', 'qty': '0.001'},
            {'orderId': 67890, 'price': '52500.0', 'qty': '0.25'}
        ]
        
        # Set active order IDs
        self.bot.active_buy_order_id = 12345
        self.bot.active_sell_order_id = 67890
        
        # Test
        self.bot.check_order_executions()
        
        # Check if last buy price was updated
        self.assertEqual(self.bot.last_buy_price, 50000.0)
        
        # Check if active order IDs were reset
        self.assertIsNone(self.bot.active_buy_order_id)
        self.assertIsNone(self.bot.active_sell_order_id)
        
        # Check if grid indices were updated
        self.assertEqual(self.bot.current_grid_buy_index, 1)
        self.assertEqual(self.bot.current_grid_sell_index, 1)

if __name__ == '__main__':
    unittest.main()
