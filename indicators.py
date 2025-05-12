import numpy as np
import pandas as pd
import config
import math

def calculate_rsi(df, period=None):
    """
    Calculate RSI (Relative Strength Index)

    Args:
        df: DataFrame with OHLC data
        period: RSI period (default from config)

    Returns:
        DataFrame with RSI values
    """
    period = period or config.RSI_PERIOD

    # Make a copy of the dataframe to avoid modifying the original
    df = df.copy()

    # Calculate price changes
    delta = df['close'].diff()

    # Separate gains and losses
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    # Calculate average gain and loss
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    # Calculate RS (Relative Strength)
    rs = avg_gain / avg_loss

    # Calculate RSI
    rsi = 100 - (100 / (1 + rs))

    # Add RSI to dataframe
    df['rsi'] = rsi

    return df

def detect_candle_pattern(df):
    """
    Detect candle patterns (green/red candles)

    Args:
        df: DataFrame with OHLC data

    Returns:
        DataFrame with candle pattern information
    """
    # Make a copy of the dataframe to avoid modifying the original
    df = df.copy()

    # Determine if candle is green (bullish) or red (bearish)
    df['is_green'] = df['close'] > df['open']
    df['is_red'] = df['close'] < df['open']

    return df

def calculate_ema(df, short_period=None, long_period=None):
    """
    Calculate Exponential Moving Averages (EMA)

    Args:
        df: DataFrame with OHLC data
        short_period: Short EMA period (default from config)
        long_period: Long EMA period (default from config)

    Returns:
        DataFrame with EMA values
    """
    short_period = short_period or config.EMA_SHORT_PERIOD
    long_period = long_period or config.EMA_LONG_PERIOD

    # Make a copy of the dataframe to avoid modifying the original
    df = df.copy()

    # Calculate EMAs
    df[f'ema_{short_period}'] = df['close'].ewm(span=short_period, adjust=False).mean()
    df[f'ema_{long_period}'] = df['close'].ewm(span=long_period, adjust=False).mean()

    # Calculate EMA crossover signals
    df['ema_cross_up'] = (df[f'ema_{short_period}'] > df[f'ema_{long_period}']) & (df[f'ema_{short_period}'].shift(1) <= df[f'ema_{long_period}'].shift(1))
    df['ema_cross_down'] = (df[f'ema_{short_period}'] < df[f'ema_{long_period}']) & (df[f'ema_{short_period}'].shift(1) >= df[f'ema_{long_period}'].shift(1))

    return df

def calculate_bollinger_bands(df, period=None, std_dev=None):
    """
    Calculate Bollinger Bands

    Args:
        df: DataFrame with OHLC data
        period: Bollinger Bands period (default from config)
        std_dev: Number of standard deviations (default from config)

    Returns:
        DataFrame with Bollinger Bands values
    """
    period = period or config.BB_PERIOD
    std_dev = std_dev or config.BB_STD_DEV

    # Make a copy of the dataframe to avoid modifying the original
    df = df.copy()

    # Calculate middle band (SMA)
    df['bb_middle'] = df['close'].rolling(window=period).mean()

    # Calculate standard deviation
    df['bb_std'] = df['close'].rolling(window=period).std()

    # Calculate upper and lower bands
    df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * std_dev)
    df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * std_dev)

    # Calculate Bollinger Band breakout signals
    df['bb_breakout_up'] = df['close'] > df['bb_upper']
    df['bb_breakout_down'] = df['close'] < df['bb_lower']

    # Calculate percentage B (position within the bands)
    df['bb_percent_b'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])

    return df

def calculate_macd(df, fast_period=None, slow_period=None, signal_period=None):
    """
    Calculate MACD (Moving Average Convergence Divergence)

    Args:
        df: DataFrame with OHLC data
        fast_period: Fast EMA period (default from config)
        slow_period: Slow EMA period (default from config)
        signal_period: Signal EMA period (default from config)

    Returns:
        DataFrame with MACD values
    """
    fast_period = fast_period or config.MACD_FAST_PERIOD
    slow_period = slow_period or config.MACD_SLOW_PERIOD
    signal_period = signal_period or config.MACD_SIGNAL_PERIOD

    # Make a copy of the dataframe to avoid modifying the original
    df = df.copy()

    # Calculate fast and slow EMAs
    df['macd_fast_ema'] = df['close'].ewm(span=fast_period, adjust=False).mean()
    df['macd_slow_ema'] = df['close'].ewm(span=slow_period, adjust=False).mean()

    # Calculate MACD line
    df['macd_line'] = df['macd_fast_ema'] - df['macd_slow_ema']

    # Calculate signal line
    df['macd_signal'] = df['macd_line'].ewm(span=signal_period, adjust=False).mean()

    # Calculate histogram
    df['macd_histogram'] = df['macd_line'] - df['macd_signal']

    # Calculate MACD crossover signals
    df['macd_cross_up'] = (df['macd_line'] > df['macd_signal']) & (df['macd_line'].shift(1) <= df['macd_signal'].shift(1))
    df['macd_cross_down'] = (df['macd_line'] < df['macd_signal']) & (df['macd_line'].shift(1) >= df['macd_signal'].shift(1))

    # Calculate zero line crossover signals
    df['macd_zero_cross_up'] = (df['macd_line'] > 0) & (df['macd_line'].shift(1) <= 0)
    df['macd_zero_cross_down'] = (df['macd_line'] < 0) & (df['macd_line'].shift(1) >= 0)

    # Calculate MACD divergence
    df['macd_bullish_divergence'] = False
    df['macd_bearish_divergence'] = False

    # Look for regular bullish divergence: price makes lower low but MACD makes higher low
    for i in range(5, len(df)):
        # Find local price lows in the last 10 candles
        if df.iloc[i]['low'] == df.iloc[i-5:i+1]['low'].min():
            # Look back for previous low
            for j in range(i-5, max(0, i-20), -1):
                if df.iloc[j]['low'] == df.iloc[max(0, j-5):j+1]['low'].min():
                    # Check for bullish divergence
                    if df.iloc[i]['low'] < df.iloc[j]['low'] and df.iloc[i]['macd_line'] > df.iloc[j]['macd_line']:
                        df.loc[df.index[i], 'macd_bullish_divergence'] = True
                    break

    # Look for regular bearish divergence: price makes higher high but MACD makes lower high
    for i in range(5, len(df)):
        # Find local price highs in the last 10 candles
        if df.iloc[i]['high'] == df.iloc[i-5:i+1]['high'].max():
            # Look back for previous high
            for j in range(i-5, max(0, i-20), -1):
                if df.iloc[j]['high'] == df.iloc[max(0, j-5):j+1]['high'].max():
                    # Check for bearish divergence
                    if df.iloc[i]['high'] > df.iloc[j]['high'] and df.iloc[i]['macd_line'] < df.iloc[j]['macd_line']:
                        df.loc[df.index[i], 'macd_bearish_divergence'] = True
                    break

    return df

def check_entry_signal(df, use_smc=True):
    """
    Check for entry signals based on multiple indicators:
    - RSI and candle patterns
    - EMA crossovers
    - Bollinger Band breakouts
    - MACD crossovers (prioritized)
    - Smart Money Concept (SMC) market structure
    - Fair Value Gaps (FVG)

    Args:
        df: DataFrame with OHLC and indicator data
        use_smc: Whether to use Smart Money Concept indicators

    Returns:
        Signal: 'LONG', 'SHORT', or None
    """
    # Get the latest data point
    latest = df.iloc[-1]

    # Initialize signal strength counters
    long_signals = 0
    short_signals = 0

    # Initialize signal weights (higher weight = more important)
    long_weight = 0
    short_weight = 0

    # Check MACD crossover (prioritized)
    if 'macd_cross_up' in latest and latest['macd_cross_up']:
        long_signals += 1
        long_weight += 2  # Higher weight for MACD cross
    elif 'macd_cross_down' in latest and latest['macd_cross_down']:
        short_signals += 1
        short_weight += 2  # Higher weight for MACD cross

    # Check MACD divergence
    if 'macd_bullish_divergence' in latest and latest['macd_bullish_divergence']:
        long_signals += 1
        long_weight += 1.5
    elif 'macd_bearish_divergence' in latest and latest['macd_bearish_divergence']:
        short_signals += 1
        short_weight += 1.5

    # Check MACD zero line crossover
    if 'macd_zero_cross_up' in latest and latest['macd_zero_cross_up']:
        long_signals += 1
        long_weight += 1
    elif 'macd_zero_cross_down' in latest and latest['macd_zero_cross_down']:
        short_signals += 1
        short_weight += 1

    # Check RSI and candle pattern
    if latest['rsi'] < config.RSI_OVERSOLD and latest['is_green']:
        long_signals += 1
        long_weight += 1
    elif latest['rsi'] > config.RSI_OVERBOUGHT and latest['is_red']:
        short_signals += 1
        short_weight += 1

    # Check EMA crossover
    if latest['ema_cross_up']:
        long_signals += 1
        long_weight += 1
    elif latest['ema_cross_down']:
        short_signals += 1
        short_weight += 1

    # Check Bollinger Band breakout
    if latest['bb_breakout_up']:
        long_signals += 1
        long_weight += 1
    elif latest['bb_breakout_down']:
        short_signals += 1
        short_weight += 1

    # Check Smart Money Concept (SMC) market structure if available
    if use_smc and 'market_structure' in latest:
        if latest['market_structure'] in ['uptrend', 'bullish_reversal']:
            long_signals += 1
            long_weight += 1.5
        elif latest['market_structure'] in ['downtrend', 'bearish_reversal']:
            short_signals += 1
            short_weight += 1.5

    # Check for Break of Structure (BOS) if available
    if use_smc and 'bos_bullish' in latest and latest['bos_bullish']:
        long_signals += 1
        long_weight += 1.5
    elif use_smc and 'bos_bearish' in latest and latest['bos_bearish']:
        short_signals += 1
        short_weight += 1.5

    # Check for Fair Value Gaps (FVG) if available
    if use_smc and 'nearest_bullish_fvg' in latest and not pd.isna(latest['nearest_bullish_fvg']):
        # If price is near a bullish FVG, it's a potential support level
        fvg_idx = latest['nearest_bullish_fvg']
        if fvg_idx in df.index:
            fvg_bottom = df.loc[fvg_idx, 'fvg_bottom']
            # If price is close to the FVG bottom (potential support)
            if abs(latest['close'] - fvg_bottom) / latest['close'] < 0.01:  # Within 1%
                long_signals += 1
                long_weight += 1

    if use_smc and 'nearest_bearish_fvg' in latest and not pd.isna(latest['nearest_bearish_fvg']):
        # If price is near a bearish FVG, it's a potential resistance level
        fvg_idx = latest['nearest_bearish_fvg']
        if fvg_idx in df.index:
            fvg_top = df.loc[fvg_idx, 'fvg_top']
            # If price is close to the FVG top (potential resistance)
            if abs(latest['close'] - fvg_top) / latest['close'] < 0.01:  # Within 1%
                short_signals += 1
                short_weight += 1

    # Determine final signal based on signal strength and weights
    # MACD crossing is prioritized, so we require it for entry
    macd_cross_up = 'macd_cross_up' in latest and latest['macd_cross_up']
    macd_cross_down = 'macd_cross_down' in latest and latest['macd_cross_down']

    if macd_cross_up and long_signals >= 2 and long_weight > short_weight:
        return 'LONG'
    elif macd_cross_down and short_signals >= 2 and short_weight > long_weight:
        return 'SHORT'
    else:
        return None
