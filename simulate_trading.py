#!/usr/bin/env python
"""
Trading Simulation Script for $60 Account

This script simulates how the trading bot would calculate position sizes
and notional values with a $60 account balance.
"""

import os
import sys
import logging
import pandas as pd
from tabulate import tabulate

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Simulation parameters
ACCOUNT_BALANCE = 60.0  # $60 account balance
POSITION_SIZE_PERCENT = 20.0  # 20% of account balance per position
MAX_ACCOUNT_USAGE = 60.0  # Maximum 60% of account balance for all positions
LEVERAGE = 20  # 20x leverage
MIN_NOTIONAL_VALUE = 5.0  # Minimum 5 USDT notional value required by Binance

# Sample cryptocurrency prices (approximate values)
SAMPLE_PRICES = {
    'BTCUSDT': 65000.0,
    'ETHUSDT': 3500.0,
    'SOLUSDT': 150.0,
    'BNBUSDT': 600.0,
    'ADAUSDT': 0.45,
    'DOGEUSDT': 0.15,
    'XRPUSDT': 0.55,
    'AVAXUSDT': 35.0,
    'DOTUSDT': 7.0,
    'MATICUSDT': 0.8,
}

def get_margin_percentage(leverage):
    """Calculate margin percentage based on leverage"""
    if leverage <= 25:
        return 5.0
    elif leverage <= 50:
        return 4.0
    elif leverage <= 75:
        return 3.0
    elif leverage <= 100:
        return 2.0
    else:
        return 1.0

def calculate_position_size(price, account_balance, position_size_percent, leverage, current_usage_percent=0):
    """
    Calculate position size with minimum notional value check
    
    Args:
        price: Current market price
        account_balance: Account balance in USDT
        position_size_percent: Percentage of account balance to use for position
        leverage: Leverage to use
        current_usage_percent: Current account usage percentage
        
    Returns:
        Dictionary with position details
    """
    # Calculate available balance percentage
    available_percent = max(0, MAX_ACCOUNT_USAGE - current_usage_percent)
    
    # If we've reached the maximum account usage, return 0
    if available_percent <= 0:
        logger.warning(f"Maximum account usage reached ({MAX_ACCOUNT_USAGE}%). Cannot open new positions.")
        return {
            'quantity': 0,
            'notional_value': 0,
            'effective_position_size': 0,
            'margin_amount': 0,
            'position_size_usdt': 0,
            'max_position_percent': 0,
            'meets_min_notional': False,
            'adjusted': False
        }
    
    # Calculate maximum position size based on available balance percentage
    max_position_percent = min(position_size_percent, available_percent)
    
    # Calculate position size based on percentage of account balance
    position_size_usdt = account_balance * (max_position_percent / 100)
    
    # Calculate margin amount based on margin percentage
    margin_percentage = get_margin_percentage(leverage)
    margin_amount = position_size_usdt * (margin_percentage / 100)
    
    # Calculate effective position size with leverage
    effective_position_size = margin_amount * leverage
    
    # Calculate quantity
    quantity = effective_position_size / price
    
    # Check if notional value meets minimum requirement
    notional_value = quantity * price
    adjusted = False
    
    if notional_value < MIN_NOTIONAL_VALUE:
        logger.warning(f"Calculated notional value ({notional_value:.2f} USDT) is less than minimum required ({MIN_NOTIONAL_VALUE} USDT)")
        
        # Adjust quantity to meet minimum notional value
        min_quantity = MIN_NOTIONAL_VALUE / price
        
        # If the minimum quantity would exceed our available balance, we can't place the order
        min_quantity_value = min_quantity * price / leverage * (100 / margin_percentage)
        min_balance_needed = min_quantity_value * 100 / max_position_percent
        
        if min_balance_needed > account_balance:
            logger.warning(f"Insufficient balance ({account_balance:.2f} USDT) to meet minimum notional value. Need at least {min_balance_needed:.2f} USDT.")
            return {
                'quantity': 0,
                'notional_value': 0,
                'effective_position_size': 0,
                'margin_amount': 0,
                'position_size_usdt': 0,
                'max_position_percent': 0,
                'meets_min_notional': False,
                'adjusted': False
            }
            
        logger.info(f"Adjusting quantity from {quantity} to {min_quantity} to meet minimum notional value")
        quantity = min_quantity
        notional_value = MIN_NOTIONAL_VALUE
        adjusted = True
    
    return {
        'quantity': quantity,
        'notional_value': notional_value,
        'effective_position_size': effective_position_size,
        'margin_amount': margin_amount,
        'position_size_usdt': position_size_usdt,
        'max_position_percent': max_position_percent,
        'meets_min_notional': notional_value >= MIN_NOTIONAL_VALUE,
        'adjusted': adjusted
    }

def simulate_trading():
    """Simulate trading with a $60 account balance"""
    print(f"\n🤖 Simulating trading with ${ACCOUNT_BALANCE} account balance\n")
    
    # Print simulation parameters
    print("Simulation Parameters:")
    params = [
        ["Account Balance", f"${ACCOUNT_BALANCE:.2f}"],
        ["Position Size Percent", f"{POSITION_SIZE_PERCENT:.1f}%"],
        ["Maximum Account Usage", f"{MAX_ACCOUNT_USAGE:.1f}%"],
        ["Leverage", f"{LEVERAGE}x"],
        ["Margin Percentage", f"{get_margin_percentage(LEVERAGE):.1f}%"],
        ["Minimum Notional Value", f"${MIN_NOTIONAL_VALUE:.2f}"]
    ]
    print(tabulate(params, tablefmt="simple"))
    
    # Calculate position sizes for each cryptocurrency
    results = []
    
    for symbol, price in SAMPLE_PRICES.items():
        position = calculate_position_size(
            price=price,
            account_balance=ACCOUNT_BALANCE,
            position_size_percent=POSITION_SIZE_PERCENT,
            leverage=LEVERAGE
        )
        
        results.append({
            'symbol': symbol,
            'price': price,
            'quantity': position['quantity'],
            'notional_value': position['notional_value'],
            'effective_position_size': position['effective_position_size'],
            'margin_amount': position['margin_amount'],
            'position_size_usdt': position['position_size_usdt'],
            'max_position_percent': position['max_position_percent'],
            'meets_min_notional': position['meets_min_notional'],
            'adjusted': position['adjusted']
        })
    
    # Convert to DataFrame for easier display
    df = pd.DataFrame(results)
    
    # Sort by whether they meet minimum notional value, then by symbol
    df = df.sort_values(by=['meets_min_notional', 'symbol'], ascending=[False, True])
    
    # Display results
    print("\nPosition Size Calculation Results:")
    
    # Format for display
    display_df = df.copy()
    display_df['price'] = display_df['price'].map('${:.2f}'.format)
    display_df['quantity'] = display_df['quantity'].map('{:.8f}'.format)
    display_df['notional_value'] = display_df['notional_value'].map('${:.2f}'.format)
    display_df['effective_position_size'] = display_df['effective_position_size'].map('${:.2f}'.format)
    display_df['margin_amount'] = display_df['margin_amount'].map('${:.2f}'.format)
    display_df['position_size_usdt'] = display_df['position_size_usdt'].map('${:.2f}'.format)
    display_df['max_position_percent'] = display_df['max_position_percent'].map('{:.1f}%'.format)
    display_df['meets_min_notional'] = display_df['meets_min_notional'].map(lambda x: '✅' if x else '❌')
    display_df['adjusted'] = display_df['adjusted'].map(lambda x: '✅' if x else '❌')
    
    # Select columns to display
    display_cols = ['symbol', 'price', 'quantity', 'notional_value', 'meets_min_notional', 'adjusted']
    print(tabulate(display_df[display_cols], headers='keys', tablefmt='simple', showindex=False))
    
    # Count how many pairs meet minimum notional value
    valid_pairs = df[df['meets_min_notional']].shape[0]
    total_pairs = df.shape[0]
    
    print(f"\n{valid_pairs} out of {total_pairs} pairs meet the minimum notional value requirement.")
    
    # Show detailed information for valid pairs
    if valid_pairs > 0:
        print("\nDetailed Information for Valid Pairs:")
        valid_df = display_df[display_df['meets_min_notional'] == '✅']
        detail_cols = ['symbol', 'price', 'quantity', 'notional_value', 'effective_position_size', 
                       'margin_amount', 'position_size_usdt', 'max_position_percent', 'adjusted']
        print(tabulate(valid_df[detail_cols], headers='keys', tablefmt='simple', showindex=False))
    
    # Show recommendations
    print("\nRecommendations:")
    if valid_pairs == 0:
        print("❌ No trading pairs meet the minimum notional value requirement with current settings.")
        print("   Consider increasing position size percentage, leverage, or account balance.")
    else:
        print(f"✅ You can trade {valid_pairs} pairs with your ${ACCOUNT_BALANCE} account.")
        print(f"   Recommended pairs: {', '.join(df[df['meets_min_notional']]['symbol'].tolist())}")
    
    # Calculate maximum number of simultaneous positions
    max_positions = int(MAX_ACCOUNT_USAGE / POSITION_SIZE_PERCENT)
    print(f"\nWith {POSITION_SIZE_PERCENT:.1f}% position size and {MAX_ACCOUNT_USAGE:.1f}% max usage,")
    print(f"you can have up to {max_positions} simultaneous positions.")

if __name__ == "__main__":
    simulate_trading()
