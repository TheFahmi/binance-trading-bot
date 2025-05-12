import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import logging

# Add the parent directory to sys.path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram_notifier import TelegramNotifier
import config

class TestTelegramNotifier(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures"""
        # Create a mock for the config
        self.config_patcher = patch('telegram_notifier.config')
        self.mock_config = self.config_patcher.start()
        self.mock_config.TELEGRAM_TOKEN = 'test_token'
        self.mock_config.TELEGRAM_CHAT_ID = 'test_chat_id'
        self.mock_config.SYMBOL = 'BTCUSDT'
        self.mock_config.LEVERAGE = 10
        self.mock_config.DAILY_PROFIT_TARGET = 5.0
        self.mock_config.DAILY_LOSS_LIMIT = 3.0
        self.mock_config.MAX_ACCOUNT_USAGE = 60.0
        self.mock_config.get_margin_percentage.return_value = 5.0

        # Create a mock for the requests module
        self.requests_patcher = patch('telegram_notifier.requests')
        self.mock_requests = self.requests_patcher.start()

        # Set up mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'ok': True, 'result': {'message_id': 123}}
        self.mock_requests.post.return_value = mock_response

        # Create the notifier
        self.notifier = TelegramNotifier()

        # Suppress logging
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        """Tear down test fixtures"""
        self.config_patcher.stop()
        self.requests_patcher.stop()
        logging.disable(logging.NOTSET)

    def test_init(self):
        """Test initialization of TelegramNotifier"""
        self.assertEqual(self.notifier.token, 'test_token')
        self.assertEqual(self.notifier.chat_id, 'test_chat_id')
        self.assertEqual(self.notifier.base_url, 'https://api.telegram.org/bottest_token')
        self.assertTrue(self.notifier.enabled)

    def test_init_disabled(self):
        """Test initialization of TelegramNotifier when disabled"""
        # Set token and chat_id to empty
        self.mock_config.TELEGRAM_TOKEN = ''
        self.mock_config.TELEGRAM_CHAT_ID = ''

        # Create the notifier
        notifier = TelegramNotifier()

        # Verify it's disabled
        self.assertFalse(notifier.enabled)

    def test_send_message(self):
        """Test send_message method"""
        # Call the method
        result = self.notifier.send_message('Test message')

        # Verify the result
        self.assertEqual(result, {'ok': True, 'result': {'message_id': 123}})

        # Verify the request was made correctly
        self.mock_requests.post.assert_called_once_with(
            'https://api.telegram.org/bottest_token/sendMessage',
            data={
                'chat_id': 'test_chat_id',
                'text': 'Test message',
                'parse_mode': 'HTML'
            }
        )

    def test_send_message_disabled(self):
        """Test send_message method when disabled"""
        # Disable the notifier
        self.notifier.enabled = False

        # Call the method
        result = self.notifier.send_message('Test message')

        # Verify the result
        self.assertIsNone(result)

        # Verify no request was made
        self.mock_requests.post.assert_not_called()

    def test_notify_entry(self):
        """Test notify_entry method"""
        # Call the method
        self.notifier.notify_entry(
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

        # Verify the request was made
        self.mock_requests.post.assert_called_once()

        # Check that the message contains key information
        args, kwargs = self.mock_requests.post.call_args
        message_text = kwargs['data']['text']

        # Check for essential information
        self.assertIn('LONG', message_text)
        self.assertIn('50000.0', message_text)
        self.assertIn('0.1', message_text)
        self.assertIn('50300.0', message_text)
        self.assertIn('49850.0', message_text)
        self.assertIn('10x', message_text)

        # Check for account information
        self.assertIn('10000.00', message_text)  # Account balance
        self.assertIn('5000.00', message_text)   # Position value
        self.assertIn('50.00%', message_text)    # Position size percentage

        # Check for account usage
        self.assertIn('Account Usage', message_text)
        self.assertIn('50.00%', message_text)    # Account usage percentage

    def test_notify_daily_pnl(self):
        """Test notify_daily_pnl method"""
        # Create a sample PnL summary
        pnl_summary = {
            'total_pnl': 500.0,
            'realized_pnl': 400.0,
            'funding_fee': 50.0,
            'commission': -50.0,
            'other': 100.0,
            'trades_count': 10,
            'winning_trades': 7,
            'losing_trades': 3,
            'win_rate': 70.0,
            'pnl_percentage': 5.0
        }

        # Call the method
        self.notifier.notify_daily_pnl(pnl_summary)

        # Verify the request was made
        self.mock_requests.post.assert_called_once()

        # Check that the message contains key information
        args, kwargs = self.mock_requests.post.call_args
        self.assertIn('DAILY PNL REPORT', kwargs['data']['text'])
        self.assertIn('+500.00', kwargs['data']['text'])
        self.assertIn('+5.00%', kwargs['data']['text'])
        self.assertIn('70.0%', kwargs['data']['text'])

    def test_notify_profit_target_reached(self):
        """Test notify_profit_target_reached method"""
        # Create a sample PnL summary
        pnl_summary = {
            'total_pnl': 500.0,
            'pnl_percentage': 5.0
        }

        # Call the method
        self.notifier.notify_profit_target_reached(pnl_summary)

        # Verify the request was made
        self.mock_requests.post.assert_called_once()

        # Check that the message contains key information
        args, kwargs = self.mock_requests.post.call_args
        self.assertIn('DAILY PROFIT TARGET REACHED', kwargs['data']['text'])
        self.assertIn('5.00%', kwargs['data']['text'])
        self.assertIn('5.00%', kwargs['data']['text'])
        self.assertIn('500.00', kwargs['data']['text'])

    def test_notify_loss_limit_reached(self):
        """Test notify_loss_limit_reached method"""
        # Create a sample PnL summary
        pnl_summary = {
            'total_pnl': -300.0,
            'pnl_percentage': -3.0
        }

        # Call the method
        self.notifier.notify_loss_limit_reached(pnl_summary)

        # Verify the request was made
        self.mock_requests.post.assert_called_once()

        # Check that the message contains key information
        args, kwargs = self.mock_requests.post.call_args
        self.assertIn('DAILY LOSS LIMIT REACHED', kwargs['data']['text'])
        self.assertIn('3.00%', kwargs['data']['text'])
        self.assertIn('-3.00%', kwargs['data']['text'])
        self.assertIn('-300.00', kwargs['data']['text'])

    def test_notify_error(self):
        """Test notify_error method"""
        # Call the method
        self.notifier.notify_error('Test error message')

        # Verify the request was made
        self.mock_requests.post.assert_called_once()

        # Check that the message contains key information
        args, kwargs = self.mock_requests.post.call_args
        self.assertIn('ERROR', kwargs['data']['text'])
        self.assertIn('Test error message', kwargs['data']['text'])

    def test_notify_entry_hedge(self):
        """Test notify_entry method with hedge position"""
        # Call the method
        self.notifier.notify_entry(
            position_side='SHORT',
            entry_price=50000.0,
            quantity=0.05,
            tp_price=49700.0,
            sl_price=50150.0,
            account_balance=10000.0,
            position_value=2500.0,
            leverage=10,
            account_usage=50.0,
            is_hedge=True
        )

        # Verify the request was made
        self.mock_requests.post.assert_called_once()

        # Check that the message contains key information
        args, kwargs = self.mock_requests.post.call_args
        message_text = kwargs['data']['text']

        # Check for hedge-specific information
        self.assertIn('HEDGE', message_text)
        self.assertIn('SHORT', message_text)

        # Check for essential information
        self.assertIn('50000.0', message_text)
        self.assertIn('0.05', message_text)
        self.assertIn('49700.0', message_text)
        self.assertIn('50150.0', message_text)
        self.assertIn('10x', message_text)

        # Check for account information
        self.assertIn('10000.00', message_text)  # Account balance
        self.assertIn('2500.00', message_text)   # Position value

    def test_notify_auto_hedge(self):
        """Test notify_auto_hedge method"""
        # Create PnL info
        pnl_info = {
            'long_position': {
                'position_side': 'LONG',
                'position_amt': 0.1,
                'entry_price': 50000.0,
                'unrealized_pnl': 100.0,
                'unrealized_pnl_percent': 2.0
            }
        }

        # Reset mock
        self.mock_requests.reset_mock()

        # Set up mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {'ok': True, 'result': {'message_id': 123}}
        self.mock_requests.post.return_value = mock_response

        # Mock config.HEDGE_POSITION_SIZE_RATIO to be a float instead of a MagicMock
        with patch('telegram_notifier.config') as mock_config:
            mock_config.SYMBOL = 'BTCUSDT'
            mock_config.HEDGE_POSITION_SIZE_RATIO = 0.5  # Set to a real float value

            # Mock send_message to avoid actual API calls
            self.notifier.send_message = MagicMock(return_value={'ok': True, 'result': {'message_id': 123}})

            # Call the method
            result = self.notifier.notify_auto_hedge('SHORT', pnl_info)

            # Verify the result
            self.assertEqual(result, {'ok': True, 'result': {'message_id': 123}})

            # Verify send_message was called
            self.notifier.send_message.assert_called_once()

    def test_notify_hedge_complete(self):
        """Test notify_hedge_complete method"""
        # Create PnL info
        pnl_info = {
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

        # Reset mock
        self.mock_requests.reset_mock()

        # Set up mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {'ok': True, 'result': {'message_id': 123}}
        self.mock_requests.post.return_value = mock_response

        # Mock config to avoid issues with MagicMock in format strings
        with patch('telegram_notifier.config') as mock_config:
            mock_config.SYMBOL = 'BTCUSDT'

            # Mock send_message to avoid actual API calls
            self.notifier.send_message = MagicMock(return_value={'ok': True, 'result': {'message_id': 123}})

            # Call the method
            result = self.notifier.notify_hedge_complete(pnl_info)

            # Verify the result
            self.assertEqual(result, {'ok': True, 'result': {'message_id': 123}})

            # Verify send_message was called
            self.notifier.send_message.assert_called_once()

    def test_notify_signal(self):
        """Test notify_signal method"""
        # Create sample indicators
        indicators = {
            'rsi': 25.0,
            'is_green': True,
            'is_red': False,
            f'ema_{self.mock_config.EMA_SHORT_PERIOD}': 49000.0,
            f'ema_{self.mock_config.EMA_LONG_PERIOD}': 48000.0,
            'bb_upper': 51000.0,
            'bb_middle': 50000.0,
            'bb_lower': 49000.0,
            'bb_percent_b': 0.8,
            'macd_line': 25.5,
            'macd_signal': 20.3,
            'macd_histogram': 5.2,
            'signal_strength': 3
        }

        # Call the method
        self.notifier.notify_signal('LONG', indicators)

        # Verify the request was made
        self.mock_requests.post.assert_called_once()

        # Check that the message contains key information
        args, kwargs = self.mock_requests.post.call_args
        self.assertIn('SIGNAL DETECTED: LONG', kwargs['data']['text'])
        self.assertIn('25.00', kwargs['data']['text'])
        self.assertIn('Green', kwargs['data']['text'])
        self.assertIn('49000.00', kwargs['data']['text'])
        self.assertIn('48000.00', kwargs['data']['text'])
        self.assertIn('25.5000', kwargs['data']['text'])  # MACD line
        self.assertIn('20.3000', kwargs['data']['text'])  # MACD signal
        self.assertIn('5.2000', kwargs['data']['text'])   # MACD histogram
        self.assertIn('Signal Strength: 3/5', kwargs['data']['text'])

if __name__ == '__main__':
    unittest.main()
