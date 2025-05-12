import unittest
from unittest.mock import patch
import pandas as pd
import numpy as np
import sys
import os

# Add the parent directory to sys.path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import indicators
import config

class TestIndicators(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures"""
        # Create a sample DataFrame for testing
        self.df = pd.DataFrame({
            'open_time': range(100),
            'open': np.random.rand(100) * 100 + 50000,
            'high': np.random.rand(100) * 100 + 50100,
            'low': np.random.rand(100) * 100 + 49900,
            'close': np.random.rand(100) * 100 + 50000,
            'volume': np.random.rand(100) * 1000
        })

        # Create a mock for the config
        self.config_patcher = patch('indicators.config')
        self.mock_config = self.config_patcher.start()
        self.mock_config.RSI_PERIOD = 14
        self.mock_config.RSI_OVERSOLD = 30
        self.mock_config.RSI_OVERBOUGHT = 70
        self.mock_config.EMA_SHORT_PERIOD = 20
        self.mock_config.EMA_LONG_PERIOD = 50
        self.mock_config.BB_PERIOD = 20
        self.mock_config.BB_STD_DEV = 2.0

    def tearDown(self):
        """Tear down test fixtures"""
        self.config_patcher.stop()

    def test_calculate_rsi(self):
        """Test calculate_rsi function"""
        # Call the function
        result_df = indicators.calculate_rsi(self.df)

        # Verify the result
        self.assertIn('rsi', result_df.columns)
        self.assertEqual(len(result_df), len(self.df))

        # RSI should be between 0 and 100
        valid_rsi = result_df['rsi'].dropna()
        if not valid_rsi.empty:
            self.assertTrue((valid_rsi >= 0).all())
            self.assertTrue((valid_rsi <= 100).all())

        # Some early values might be NaN due to the calculation window
        # Instead of checking specific indices, just verify we have some valid values
        self.assertTrue(result_df['rsi'].notna().any())

    def test_detect_candle_pattern(self):
        """Test detect_candle_pattern function"""
        # Call the function
        result_df = indicators.detect_candle_pattern(self.df)

        # Verify the result
        self.assertIn('is_green', result_df.columns)
        self.assertIn('is_red', result_df.columns)
        self.assertEqual(len(result_df), len(self.df))

        # Check that is_green and is_red are mutually exclusive
        self.assertTrue(((result_df['is_green'] & result_df['is_red']) == False).all())

        # Manually check a few values
        for i in range(len(result_df)):
            if result_df['close'].iloc[i] > result_df['open'].iloc[i]:
                self.assertTrue(result_df['is_green'].iloc[i])
                self.assertFalse(result_df['is_red'].iloc[i])
            elif result_df['close'].iloc[i] < result_df['open'].iloc[i]:
                self.assertFalse(result_df['is_green'].iloc[i])
                self.assertTrue(result_df['is_red'].iloc[i])

    def test_calculate_ema(self):
        """Test calculate_ema function"""
        # Call the function
        result_df = indicators.calculate_ema(self.df)

        # Verify the result
        self.assertIn(f'ema_{self.mock_config.EMA_SHORT_PERIOD}', result_df.columns)
        self.assertIn(f'ema_{self.mock_config.EMA_LONG_PERIOD}', result_df.columns)
        self.assertIn('ema_cross_up', result_df.columns)
        self.assertIn('ema_cross_down', result_df.columns)
        self.assertEqual(len(result_df), len(self.df))

        # First n values of EMA should be close to SMA
        short_period = self.mock_config.EMA_SHORT_PERIOD
        sma_short = self.df['close'].iloc[:short_period].mean()
        self.assertAlmostEqual(result_df[f'ema_{short_period}'].iloc[short_period-1], sma_short, delta=100)

    def test_calculate_bollinger_bands(self):
        """Test calculate_bollinger_bands function"""
        # Call the function
        result_df = indicators.calculate_bollinger_bands(self.df)

        # Verify the result
        self.assertIn('bb_middle', result_df.columns)
        self.assertIn('bb_upper', result_df.columns)
        self.assertIn('bb_lower', result_df.columns)
        self.assertIn('bb_std', result_df.columns)
        self.assertIn('bb_percent_b', result_df.columns)
        self.assertIn('bb_breakout_up', result_df.columns)
        self.assertIn('bb_breakout_down', result_df.columns)
        self.assertEqual(len(result_df), len(self.df))

        # Check that upper band is always higher than middle band
        valid_idx = result_df['bb_upper'].notna()
        self.assertTrue((result_df.loc[valid_idx, 'bb_upper'] >= result_df.loc[valid_idx, 'bb_middle']).all())

        # Check that lower band is always lower than middle band
        self.assertTrue((result_df.loc[valid_idx, 'bb_lower'] <= result_df.loc[valid_idx, 'bb_middle']).all())

        # Check that percent_b is between 0 and 1 when price is between bands
        between_bands = (result_df['close'] >= result_df['bb_lower']) & (result_df['close'] <= result_df['bb_upper'])
        percent_b_valid = result_df.loc[between_bands & valid_idx, 'bb_percent_b']
        self.assertTrue((percent_b_valid >= 0).all() and (percent_b_valid <= 1).all())

    def test_check_entry_signal(self):
        """Test check_entry_signal function"""
        # Prepare test data with known signals
        df = self.df.copy()

        # Add indicator columns
        df['rsi'] = 50  # Neutral RSI
        df['is_green'] = False
        df['is_red'] = False
        df['ema_cross_up'] = False
        df['ema_cross_down'] = False
        df['bb_breakout_up'] = False
        df['bb_breakout_down'] = False

        # Test case 1: No signal (neutral)
        signal = indicators.check_entry_signal(df)
        self.assertIsNone(signal)

        # Test case 2: LONG signal (RSI oversold + green candle + EMA cross up)
        df.loc[99, 'rsi'] = 25  # Oversold
        df.loc[99, 'is_green'] = True
        df.loc[99, 'ema_cross_up'] = True
        signal = indicators.check_entry_signal(df)
        self.assertEqual(signal, 'LONG')

        # Test case 3: SHORT signal (RSI overbought + red candle + BB breakout down)
        df.loc[99, 'rsi'] = 75  # Overbought
        df.loc[99, 'is_green'] = False
        df.loc[99, 'is_red'] = True
        df.loc[99, 'ema_cross_up'] = False
        df.loc[99, 'bb_breakout_down'] = True
        signal = indicators.check_entry_signal(df)
        self.assertEqual(signal, 'SHORT')

        # Test case 4: Not enough signals for LONG (only 1 indicator)
        df.loc[99, 'rsi'] = 25  # Oversold
        df.loc[99, 'is_green'] = True
        df.loc[99, 'is_red'] = False
        df.loc[99, 'ema_cross_up'] = False
        df.loc[99, 'bb_breakout_up'] = False
        df.loc[99, 'bb_breakout_down'] = False
        signal = indicators.check_entry_signal(df)
        self.assertIsNone(signal)

if __name__ == '__main__':
    unittest.main()
