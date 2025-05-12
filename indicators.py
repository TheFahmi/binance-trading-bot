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

    # Add more sensitive signals - approaching bands
    df['bb_approaching_upper'] = (df['close'] > df['bb_middle']) & (df['close'] > df['close'].shift(1)) & (df['close'] < df['bb_upper']) & (df['bb_upper'] - df['close'] < df['bb_std'] * 0.5)
    df['bb_approaching_lower'] = (df['close'] < df['bb_middle']) & (df['close'] < df['close'].shift(1)) & (df['close'] > df['bb_lower']) & (df['close'] - df['bb_lower'] < df['bb_std'] * 0.5)

    # Add squeeze detection (when bands are narrow)
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
    df['bb_squeeze'] = df['bb_width'] < df['bb_width'].rolling(window=20).mean() * 0.8

    # Add bounce signals (price bouncing off the bands)
    df['bb_bounce_up'] = (df['low'] <= df['bb_lower']) & (df['close'] > df['bb_lower']) & (df['close'] > df['open'])
    df['bb_bounce_down'] = (df['high'] >= df['bb_upper']) & (df['close'] < df['bb_upper']) & (df['close'] < df['open'])

    # Add mean reversion signals
    df['bb_mean_reversion_up'] = (df['close'].shift(1) < df['bb_lower'].shift(1)) & (df['close'] > df['bb_lower'])
    df['bb_mean_reversion_down'] = (df['close'].shift(1) > df['bb_upper'].shift(1)) & (df['close'] < df['bb_upper'])

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
    # Make conditions much more flexible to generate more trading signals

    # Check for MACD signals (high priority)
    macd_cross_up = 'macd_cross_up' in latest and latest['macd_cross_up']
    macd_cross_down = 'macd_cross_down' in latest and latest['macd_cross_down']
    macd_zero_cross_up = 'macd_zero_cross_up' in latest and latest['macd_zero_cross_up']
    macd_zero_cross_down = 'macd_zero_cross_down' in latest and latest['macd_zero_cross_down']

    # Check for RSI signals
    rsi_oversold = 'rsi' in latest and latest['rsi'] < config.RSI_OVERSOLD + 5  # Add 5 to make it less strict
    rsi_overbought = 'rsi' in latest and latest['rsi'] > config.RSI_OVERBOUGHT - 5  # Subtract 5 to make it less strict

    # Check for Bollinger Band signals
    bb_breakout_up = 'bb_breakout_up' in latest and latest['bb_breakout_up']
    bb_breakout_down = 'bb_breakout_down' in latest and latest['bb_breakout_down']
    bb_approaching_upper = 'bb_approaching_upper' in latest and latest['bb_approaching_upper']
    bb_approaching_lower = 'bb_approaching_lower' in latest and latest['bb_approaching_lower']
    bb_bounce_up = 'bb_bounce_up' in latest and latest['bb_bounce_up']
    bb_bounce_down = 'bb_bounce_down' in latest and latest['bb_bounce_down']
    bb_mean_reversion_up = 'bb_mean_reversion_up' in latest and latest['bb_mean_reversion_up']
    bb_mean_reversion_down = 'bb_mean_reversion_down' in latest and latest['bb_mean_reversion_down']
    bb_squeeze = 'bb_squeeze' in latest and latest['bb_squeeze']

    # Check for EMA signals
    ema_cross_up = 'ema_cross_up' in latest and latest['ema_cross_up']
    ema_cross_down = 'ema_cross_down' in latest and latest['ema_cross_down']

    # Check for candle patterns
    green_candle = 'is_green' in latest and latest['is_green']
    red_candle = 'is_red' in latest and latest['is_red']

    # Define more flexible entry conditions

    # LONG signals (any of these conditions can trigger a LONG entry)
    long_conditions = [
        # MACD conditions
        macd_cross_up,
        macd_zero_cross_up,

        # RSI conditions with candle confirmation
        rsi_oversold and green_candle,

        # Bollinger Band conditions
        bb_breakout_up and green_candle,
        bb_bounce_up,
        bb_mean_reversion_up,
        bb_approaching_lower and green_candle,
        bb_squeeze and green_candle and (latest['close'] > latest['open']),

        # EMA conditions
        ema_cross_up,

        # Combined conditions
        rsi_oversold and ema_cross_up,
        rsi_oversold and macd_zero_cross_up,
        bb_bounce_up and rsi_oversold,
        bb_mean_reversion_up and macd_zero_cross_up,

        # Weight-based condition
        long_signals >= 1 and long_weight > short_weight and green_candle
    ]

    # SHORT signals (any of these conditions can trigger a SHORT entry)
    short_conditions = [
        # MACD conditions
        macd_cross_down,
        macd_zero_cross_down,

        # RSI conditions with candle confirmation
        rsi_overbought and red_candle,

        # Bollinger Band conditions
        bb_breakout_down and red_candle,
        bb_bounce_down,
        bb_mean_reversion_down,
        bb_approaching_upper and red_candle,
        bb_squeeze and red_candle and (latest['close'] < latest['open']),

        # EMA conditions
        ema_cross_down,

        # Combined conditions
        rsi_overbought and ema_cross_down,
        rsi_overbought and macd_zero_cross_down,
        bb_bounce_down and rsi_overbought,
        bb_mean_reversion_down and macd_zero_cross_down,

        # Weight-based condition
        short_signals >= 1 and short_weight > long_weight and red_candle
    ]

    # Return signal based on conditions
    if any(long_conditions):
        return 'LONG'
    elif any(short_conditions):
        return 'SHORT'
    else:
        return None
