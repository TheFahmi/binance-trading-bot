import unittest
import pandas as pd
import numpy as np
import sys
import os

# Add the parent directory to sys.path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import smc_indicators

class TestSMCIndicators(unittest.TestCase):

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

        # Create a specific pattern for testing market structure
        # Create an uptrend pattern
        uptrend_df = pd.DataFrame({
            'open_time': range(20),
            'open': [50000, 50100, 50200, 50150, 50250, 50300, 50250, 50350, 50400, 50350,
                     50450, 50500, 50450, 50550, 50600, 50550, 50650, 50700, 50650, 50750],
            'high': [50100, 50200, 50300, 50250, 50350, 50400, 50350, 50450, 50500, 50450,
                     50550, 50600, 50550, 50650, 50700, 50650, 50750, 50800, 50750, 50850],
            'low': [49950, 50050, 50150, 50100, 50200, 50250, 50200, 50300, 50350, 50300,
                    50400, 50450, 50400, 50500, 50550, 50500, 50600, 50650, 50600, 50700],
            'close': [50100, 50200, 50250, 50250, 50300, 50350, 50350, 50400, 50450, 50450,
                      50500, 50550, 50550, 50600, 50650, 50650, 50700, 50750, 50750, 50800],
            'volume': np.random.rand(20) * 1000
        })
        self.uptrend_df = uptrend_df

        # Create a downtrend pattern
        downtrend_df = pd.DataFrame({
            'open_time': range(20),
            'open': [50000, 49900, 49800, 49850, 49750, 49700, 49750, 49650, 49600, 49650,
                     49550, 49500, 49550, 49450, 49400, 49450, 49350, 49300, 49350, 49250],
            'high': [50050, 49950, 49850, 49900, 49800, 49750, 49800, 49700, 49650, 49700,
                     49600, 49550, 49600, 49500, 49450, 49500, 49400, 49350, 49400, 49300],
            'low': [49950, 49850, 49750, 49800, 49700, 49650, 49700, 49600, 49550, 49600,
                    49500, 49450, 49500, 49400, 49350, 49400, 49300, 49250, 49300, 49200],
            'close': [49900, 49800, 49750, 49750, 49700, 49650, 49650, 49600, 49550, 49550,
                      49500, 49450, 49450, 49400, 49350, 49350, 49300, 49250, 49250, 49200],
            'volume': np.random.rand(20) * 1000
        })
        self.downtrend_df = downtrend_df

        # Create a pattern with Fair Value Gaps
        fvg_df = pd.DataFrame({
            'open_time': range(10),
            'open': [50000, 50100, 50300, 50400, 50350, 50000, 49800, 49700, 49900, 50000],
            'high': [50100, 50200, 50400, 50500, 50450, 50100, 49900, 49800, 50000, 50100],
            'low': [49950, 50050, 50250, 50350, 50300, 49950, 49750, 49650, 49850, 49950],
            'close': [50100, 50150, 50400, 50350, 50000, 49800, 49750, 49900, 50000, 50050],
            'volume': np.random.rand(10) * 1000
        })
        self.fvg_df = fvg_df

    def test_detect_market_structure(self):
        """Test detect_market_structure function"""
        # Test with random data
        result_df = smc_indicators.detect_market_structure(self.df)

        # Verify the result has the expected columns
        self.assertIn('swing_high', result_df.columns)
        self.assertIn('swing_low', result_df.columns)
        self.assertIn('higher_high', result_df.columns)
        self.assertIn('higher_low', result_df.columns)
        self.assertIn('lower_high', result_df.columns)
        self.assertIn('lower_low', result_df.columns)
        self.assertIn('bos_bullish', result_df.columns)
        self.assertIn('bos_bearish', result_df.columns)
        self.assertIn('market_structure', result_df.columns)

        # Test with uptrend data - use a smaller lookback for test data
        uptrend_result = smc_indicators.detect_market_structure(self.uptrend_df, lookback=1)

        # Print debug info if the test fails
        if not uptrend_result['higher_high'].any():
            print("Debug: No higher highs found in uptrend data")
            print(f"Swing highs: {uptrend_result['swing_high'].sum()}")
            print(f"First price: {self.uptrend_df.iloc[0]['close']}, Last price: {self.uptrend_df.iloc[-1]['close']}")

        # Verify that we have some higher highs and higher lows in an uptrend
        self.assertTrue(uptrend_result['higher_high'].any(), "No higher highs detected in uptrend data")

        # For higher lows, we'll check if there are any swing lows first
        if uptrend_result['swing_low'].any():
            self.assertTrue(uptrend_result['higher_low'].any(), "No higher lows detected in uptrend data")

        # Test with downtrend data - use a smaller lookback for test data
        downtrend_result = smc_indicators.detect_market_structure(self.downtrend_df, lookback=1)

        # Print debug info if the test fails
        if not downtrend_result['lower_high'].any():
            print("Debug: No lower highs found in downtrend data")
            print(f"Swing highs: {downtrend_result['swing_high'].sum()}")
            print(f"First price: {self.downtrend_df.iloc[0]['close']}, Last price: {self.downtrend_df.iloc[-1]['close']}")

        # Verify that we have some lower highs and lower lows in a downtrend
        self.assertTrue(downtrend_result['lower_high'].any() or downtrend_result['lower_low'].any(),
                        "No lower highs or lower lows detected in downtrend data")

    def test_detect_fair_value_gaps(self):
        """Test detect_fair_value_gaps function"""
        # Test with random data
        result_df = smc_indicators.detect_fair_value_gaps(self.df)

        # Verify the result has the expected columns
        self.assertIn('bullish_fvg', result_df.columns)
        self.assertIn('bearish_fvg', result_df.columns)
        self.assertIn('fvg_top', result_df.columns)
        self.assertIn('fvg_bottom', result_df.columns)
        self.assertIn('fvg_size', result_df.columns)
        self.assertIn('fvg_filled', result_df.columns)

        # Test with specific FVG data
        fvg_result = smc_indicators.detect_fair_value_gaps(self.fvg_df)

        # In our test data, there should be a bullish FVG at index 2
        # (candle 2's low is higher than candle 0's high)
        self.assertTrue(fvg_result.loc[2, 'bullish_fvg'])

        # And there should be a bearish FVG at index 6
        # (candle 6's high is lower than candle 4's low)
        self.assertTrue(fvg_result.loc[6, 'bearish_fvg'])

        # Check FVG size calculations
        bullish_fvg_idx = fvg_result[fvg_result['bullish_fvg']].index[0]
        self.assertGreater(fvg_result.loc[bullish_fvg_idx, 'fvg_size'], 0)

        bearish_fvg_idx = fvg_result[fvg_result['bearish_fvg']].index[0]
        self.assertGreater(fvg_result.loc[bearish_fvg_idx, 'fvg_size'], 0)

if __name__ == '__main__':
    unittest.main()
