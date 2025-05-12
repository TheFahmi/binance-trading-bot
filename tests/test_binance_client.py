import unittest
from unittest.mock import patch, MagicMock
import json
import pandas as pd
import sys
import os

# Add the parent directory to sys.path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from binance_client import BinanceClient
import config

class TestBinanceClient(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures"""
        # Create a mock for the config
        self.config_patcher = patch('binance_client.config')
        self.mock_config = self.config_patcher.start()
        self.mock_config.API_KEY = 'test_api_key'
        self.mock_config.API_SECRET = 'test_api_secret'
        self.mock_config.BASE_URL = 'https://testnet.binance.com'
        self.mock_config.SYMBOL = 'BTCUSDT'
        self.mock_config.RECV_WINDOW = 5000
        self.mock_config.API_RETRY_COUNT = 3
        self.mock_config.API_TIMEOUT = 30
        self.mock_config.API_CONNECT_TIMEOUT = 10
        self.mock_config.USE_PROXY = False
        self.mock_config.PROXY_URL = None

        # Create a mock for the requests module
        self.requests_patcher = patch('binance_client.requests')
        self.mock_requests = self.requests_patcher.start()

        # Set up mock response for exchange info
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'symbols': [
                {
                    'symbol': 'BTCUSDT',
                    'pricePrecision': 2,
                    'quantityPrecision': 3
                }
            ]
        }
        self.mock_requests.request.return_value = mock_response

        # Create the client
        self.client = BinanceClient()

    def tearDown(self):
        """Tear down test fixtures"""
        self.config_patcher.stop()
        self.requests_patcher.stop()

    def test_init(self):
        """Test initialization of BinanceClient"""
        self.assertEqual(self.client.api_key, 'test_api_key')
        self.assertEqual(self.client.api_secret, 'test_api_secret')
        self.assertEqual(self.client.base_url, 'https://testnet.binance.com')
        self.assertEqual(self.client.symbol, 'BTCUSDT')

    def test_get_timestamp(self):
        """Test _get_timestamp method"""
        timestamp = self.client._get_timestamp()
        self.assertIsInstance(timestamp, int)

    def test_generate_signature(self):
        """Test _generate_signature method"""
        query_string = 'symbol=BTCUSDT&timestamp=1234567890'
        signature = self.client._generate_signature(query_string)
        self.assertIsInstance(signature, str)
        self.assertEqual(len(signature), 64)  # SHA256 hex digest is 64 characters

    def test_send_request_unsigned(self):
        """Test _send_request method for unsigned requests"""
        # Reset the mock to clear previous calls
        self.mock_requests.reset_mock()

        # Set up mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'price': '50000.00'}
        self.mock_requests.request.return_value = mock_response

        # Call the method
        result = self.client._send_request('GET', '/api/v3/ticker/price', {'symbol': 'BTCUSDT'})

        # Verify the result
        self.assertEqual(result, {'price': '50000.00'})

        # Verify the last request was made correctly
        args, kwargs = self.mock_requests.request.call_args
        self.assertEqual(kwargs['method'], 'GET')
        self.assertEqual(kwargs['url'], 'https://testnet.binance.com/api/v3/ticker/price')
        self.assertEqual(kwargs['headers'], {'X-MBX-APIKEY': 'test_api_key'})
        self.assertEqual(kwargs['params'], {'symbol': 'BTCUSDT'})
        self.assertEqual(kwargs['timeout'], (self.mock_config.API_CONNECT_TIMEOUT, self.mock_config.API_TIMEOUT))

    def test_send_request_signed(self):
        """Test _send_request method for signed requests"""
        # Set up mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'positions': []}
        self.mock_requests.request.return_value = mock_response

        # Call the method
        result = self.client._send_request('GET', '/fapi/v2/account', {}, signed=True)

        # Verify the result
        self.assertEqual(result, {'positions': []})

        # Verify the request was made with timestamp, recvWindow, and signature
        args, kwargs = self.mock_requests.request.call_args
        self.assertEqual(kwargs['method'], 'GET')
        self.assertEqual(kwargs['url'], 'https://testnet.binance.com/fapi/v2/account')
        self.assertEqual(kwargs['headers'], {'X-MBX-APIKEY': 'test_api_key'})
        self.assertIn('timestamp', kwargs['params'])
        self.assertIn('recvWindow', kwargs['params'])
        self.assertIn('signature', kwargs['params'])

    def test_get_price_precision(self):
        """Test get_price_precision method"""
        precision = self.client.get_price_precision()
        self.assertEqual(precision, 2)

    def test_get_quantity_precision(self):
        """Test get_quantity_precision method"""
        precision = self.client.get_quantity_precision()
        self.assertEqual(precision, 3)

    def test_round_price(self):
        """Test round_price method"""
        rounded_price = self.client.round_price(50000.12345)
        self.assertEqual(rounded_price, 50000.12)

    def test_round_quantity(self):
        """Test round_quantity method"""
        rounded_quantity = self.client.round_quantity(1.12345)
        self.assertEqual(rounded_quantity, 1.123)

    @patch('binance_client.BinanceClient.get_max_leverage')
    def test_set_leverage(self, mock_get_max_leverage):
        """Test set_leverage method"""
        # Set up mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'leverage': 10, 'symbol': 'BTCUSDT'}
        self.mock_requests.request.return_value = mock_response

        # Mock get_max_leverage to return 20
        mock_get_max_leverage.return_value = 20

        # Call the method
        result = self.client.set_leverage(10)

        # Verify the result
        self.assertEqual(result, {'leverage': 10, 'symbol': 'BTCUSDT'})

        # Verify the request was made correctly
        args, kwargs = self.mock_requests.request.call_args
        self.assertEqual(kwargs['method'], 'POST')
        self.assertEqual(kwargs['url'], 'https://testnet.binance.com/fapi/v1/leverage')
        self.assertEqual(kwargs['params']['symbol'], 'BTCUSDT')
        self.assertEqual(kwargs['params']['leverage'], 10)

    def test_set_position_mode_hedge(self):
        """Test set_position_mode method with hedge mode"""
        # Reset mock
        self.mock_requests.reset_mock()

        # Set up mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'dualSidePosition': True}
        self.mock_requests.request.return_value = mock_response

        # Call the method
        result = self.client.set_position_mode(True)

        # Verify the result
        self.assertEqual(result, {'dualSidePosition': True})

        # Verify the request was made correctly
        args, kwargs = self.mock_requests.request.call_args
        self.assertEqual(kwargs['method'], 'POST')
        self.assertEqual(kwargs['url'], 'https://testnet.binance.com/fapi/v1/positionSide/dual')
        self.assertEqual(kwargs['headers'], {'X-MBX-APIKEY': 'test_api_key'})
        self.assertEqual(kwargs['params']['dualSidePosition'], 'true')
        self.assertIn('timestamp', kwargs['params'])
        self.assertEqual(kwargs['params']['recvWindow'], 60000)
        self.assertIn('signature', kwargs['params'])
        self.assertEqual(kwargs['timeout'], (self.mock_config.API_CONNECT_TIMEOUT, self.mock_config.API_TIMEOUT))

    def test_set_position_mode_one_way(self):
        """Test set_position_mode method with one-way mode"""
        # Reset mock
        self.mock_requests.reset_mock()

        # Set up mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'dualSidePosition': False}
        self.mock_requests.request.return_value = mock_response

        # Call the method
        result = self.client.set_position_mode(False)

        # Verify the result
        self.assertEqual(result, {'dualSidePosition': False})

        # Verify the request was made correctly
        args, kwargs = self.mock_requests.request.call_args
        self.assertEqual(kwargs['method'], 'POST')
        self.assertEqual(kwargs['url'], 'https://testnet.binance.com/fapi/v1/positionSide/dual')
        self.assertEqual(kwargs['headers'], {'X-MBX-APIKEY': 'test_api_key'})
        self.assertEqual(kwargs['params']['dualSidePosition'], 'false')
        self.assertIn('timestamp', kwargs['params'])
        self.assertEqual(kwargs['params']['recvWindow'], 60000)
        self.assertIn('signature', kwargs['params'])
        self.assertEqual(kwargs['timeout'], (self.mock_config.API_CONNECT_TIMEOUT, self.mock_config.API_TIMEOUT))

    def test_get_position_mode(self):
        """Test get_position_mode method"""
        # Reset mock
        self.mock_requests.reset_mock()

        # Set up mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'dualSidePosition': True}
        self.mock_requests.request.return_value = mock_response

        # Call the method
        result = self.client.get_position_mode()

        # Verify the result
        self.assertTrue(result)

        # Verify the request was made correctly
        args, kwargs = self.mock_requests.request.call_args
        self.assertEqual(kwargs['method'], 'GET')
        self.assertEqual(kwargs['url'], 'https://testnet.binance.com/fapi/v1/positionSide/dual')
        self.assertEqual(kwargs['headers'], {'X-MBX-APIKEY': 'test_api_key'})
        self.assertIn('timestamp', kwargs['params'])
        self.assertEqual(kwargs['params']['recvWindow'], 60000)
        self.assertIn('signature', kwargs['params'])
        self.assertEqual(kwargs['timeout'], (self.mock_config.API_CONNECT_TIMEOUT, self.mock_config.API_TIMEOUT))

    def test_get_position_pnl_long(self):
        """Test get_position_pnl method for LONG position"""
        # Reset mock
        self.mock_requests.reset_mock()

        # Set up mock for get_open_positions
        self.client.get_open_positions = MagicMock(return_value=[
            {
                'symbol': 'BTCUSDT',
                'positionSide': 'LONG',
                'positionAmt': '0.1',
                'entryPrice': '50000.0',
                'leverage': '10',
                'marginType': 'isolated'
            }
        ])

        # Set up mock for get_current_price
        self.client.get_current_price = MagicMock(return_value=51000.0)

        # Call the method
        result = self.client.get_position_pnl('BTCUSDT', 'LONG')

        # Verify the result
        self.assertEqual(result['symbol'], 'BTCUSDT')
        self.assertEqual(result['position_side'], 'LONG')
        self.assertEqual(result['entry_price'], 50000.0)
        self.assertEqual(result['mark_price'], 51000.0)
        self.assertEqual(result['position_amt'], 0.1)
        self.assertEqual(result['unrealized_pnl'], 100.0)  # (51000 - 50000) * 0.1
        self.assertAlmostEqual(result['unrealized_pnl_percent'], 20.0, places=2)  # ((51000/50000) - 1) * 100 * 10
        self.assertEqual(result['leverage'], 10)
        self.assertEqual(result['margin_type'], 'isolated')

    def test_get_position_pnl_short(self):
        """Test get_position_pnl method for SHORT position"""
        # Reset mock
        self.mock_requests.reset_mock()

        # Set up mock for get_open_positions
        self.client.get_open_positions = MagicMock(return_value=[
            {
                'symbol': 'BTCUSDT',
                'positionSide': 'SHORT',
                'positionAmt': '-0.1',
                'entryPrice': '50000.0',
                'leverage': '10',
                'marginType': 'isolated'
            }
        ])

        # Set up mock for get_current_price
        self.client.get_current_price = MagicMock(return_value=49000.0)

        # Call the method
        result = self.client.get_position_pnl('BTCUSDT', 'SHORT')

        # Verify the result
        self.assertEqual(result['symbol'], 'BTCUSDT')
        self.assertEqual(result['position_side'], 'SHORT')
        self.assertEqual(result['entry_price'], 50000.0)
        self.assertEqual(result['mark_price'], 49000.0)
        self.assertEqual(result['position_amt'], -0.1)
        self.assertEqual(result['unrealized_pnl'], 100.0)  # (50000 - 49000) * 0.1
        self.assertAlmostEqual(result['unrealized_pnl_percent'], 20.41, places=2)  # ((50000/49000) - 1) * 100 * 10
        self.assertEqual(result['leverage'], 10)
        self.assertEqual(result['margin_type'], 'isolated')

    def test_get_position_pnl_no_position(self):
        """Test get_position_pnl method with no position"""
        # Reset mock
        self.mock_requests.reset_mock()

        # Set up mock for get_open_positions
        self.client.get_open_positions = MagicMock(return_value=[])

        # Call the method
        result = self.client.get_position_pnl('BTCUSDT', 'LONG')

        # Verify the result
        self.assertEqual(result['symbol'], 'BTCUSDT')
        self.assertEqual(result['position_side'], 'LONG')
        self.assertEqual(result['entry_price'], 0)
        self.assertEqual(result['mark_price'], 0)
        self.assertEqual(result['position_amt'], 0)
        self.assertEqual(result['unrealized_pnl'], 0)
        self.assertEqual(result['unrealized_pnl_percent'], 0)
        self.assertEqual(result['leverage'], 0)
        self.assertEqual(result['margin_type'], 'NONE')

    def test_get_combined_position_pnl_hedged(self):
        """Test get_combined_position_pnl method with hedged positions"""
        # Reset mock
        self.mock_requests.reset_mock()

        # Set up mock for get_position_pnl
        long_pnl = {
            'symbol': 'BTCUSDT',
            'position_side': 'LONG',
            'entry_price': 50000.0,
            'mark_price': 51000.0,
            'position_amt': 0.1,
            'unrealized_pnl': 100.0,
            'unrealized_pnl_percent': 20.0,
            'leverage': 10,
            'margin_type': 'isolated'
        }

        short_pnl = {
            'symbol': 'BTCUSDT',
            'position_side': 'SHORT',
            'entry_price': 52000.0,
            'mark_price': 51000.0,
            'position_amt': -0.05,
            'unrealized_pnl': 50.0,
            'unrealized_pnl_percent': 10.0,
            'leverage': 10,
            'margin_type': 'isolated'
        }

        self.client.get_position_pnl = MagicMock(side_effect=lambda _symbol, position_side:
                                                long_pnl if position_side == 'LONG' else short_pnl)

        # Call the method
        result = self.client.get_combined_position_pnl('BTCUSDT')

        # Verify the result
        self.assertEqual(result['symbol'], 'BTCUSDT')
        self.assertEqual(result['long_position'], long_pnl)
        self.assertEqual(result['short_position'], short_pnl)
        self.assertEqual(result['combined_unrealized_pnl'], 150.0)  # 100 + 50
        self.assertTrue(result['is_hedged'])

        # Combined PnL percentage calculation:
        # long_value = 0.1 * 50000 = 5000
        # short_value = 0.05 * 52000 = 2600
        # total_value = 5000 + 2600 = 7600
        # combined_pnl_percent = (150 / 7600) * 100 = 1.97%
        self.assertAlmostEqual(result['combined_unrealized_pnl_percent'], 1.97, places=2)

    def test_get_combined_position_pnl_long_only(self):
        """Test get_combined_position_pnl method with only LONG position"""
        # Reset mock
        self.mock_requests.reset_mock()

        # Set up mock for get_position_pnl
        long_pnl = {
            'symbol': 'BTCUSDT',
            'position_side': 'LONG',
            'entry_price': 50000.0,
            'mark_price': 51000.0,
            'position_amt': 0.1,
            'unrealized_pnl': 100.0,
            'unrealized_pnl_percent': 20.0,
            'leverage': 10,
            'margin_type': 'isolated'
        }

        empty_pnl = {
            'symbol': 'BTCUSDT',
            'position_side': 'SHORT',
            'entry_price': 0,
            'mark_price': 0,
            'position_amt': 0,
            'unrealized_pnl': 0,
            'unrealized_pnl_percent': 0,
            'leverage': 0,
            'margin_type': 'NONE'
        }

        self.client.get_position_pnl = MagicMock(side_effect=lambda _symbol, position_side:
                                                long_pnl if position_side == 'LONG' else empty_pnl)

        # Call the method
        result = self.client.get_combined_position_pnl('BTCUSDT')

        # Verify the result
        self.assertEqual(result['symbol'], 'BTCUSDT')
        self.assertEqual(result['long_position'], long_pnl)
        self.assertIsNone(result['short_position'])
        self.assertEqual(result['combined_unrealized_pnl'], 100.0)
        self.assertEqual(result['combined_unrealized_pnl_percent'], 20.0)
        self.assertFalse(result['is_hedged'])

if __name__ == '__main__':
    unittest.main()
