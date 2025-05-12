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

def check_entry_signal(df):
    """
    Check for entry signals based on multiple indicators:
    - RSI and candle patterns
    - EMA crossovers
    - Bollinger Band breakouts

    Args:
        df: DataFrame with OHLC and indicator data

    Returns:
        Signal: 'LONG', 'SHORT', or None
    """
    # Get the latest data point
    latest = df.iloc[-1]

    # Initialize signal strength counters
    long_signals = 0
    short_signals = 0

    # Check RSI and candle pattern
    if latest['rsi'] < config.RSI_OVERSOLD and latest['is_green']:
        long_signals += 1
    elif latest['rsi'] > config.RSI_OVERBOUGHT and latest['is_red']:
        short_signals += 1

    # Check EMA crossover
    if latest['ema_cross_up']:
        long_signals += 1
    elif latest['ema_cross_down']:
        short_signals += 1

    # Check Bollinger Band breakout
    if latest['bb_breakout_up']:
        long_signals += 1
    elif latest['bb_breakout_down']:
        short_signals += 1

    # Determine final signal based on signal strength
    if long_signals >= 2:  # At least 2 indicators suggest LONG
        return 'LONG'
    elif short_signals >= 2:  # At least 2 indicators suggest SHORT
        return 'SHORT'
    else:
        return None
