#!/usr/bin/env python
"""
Simple Trading Simulation for $60 Account
"""

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

def calculate_position_size(price, account_balance, position_size_percent, leverage):
    """Calculate position size with minimum notional value check"""
    # Calculate position size based on percentage of account balance
    position_size_usdt = account_balance * (position_size_percent / 100)
    
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
        print(f"  WARNING: Notional value ({notional_value:.2f} USDT) is less than minimum required ({MIN_NOTIONAL_VALUE} USDT)")
        
        # Adjust quantity to meet minimum notional value
        min_quantity = MIN_NOTIONAL_VALUE / price
        
        # If the minimum quantity would exceed our available balance, we can't place the order
        min_quantity_value = min_quantity * price / leverage * (100 / margin_percentage)
        min_balance_needed = min_quantity_value * 100 / position_size_percent
        
        if min_balance_needed > account_balance:
            print(f"  ERROR: Insufficient balance ({account_balance:.2f} USDT) to meet minimum notional value.")
            print(f"         Need at least {min_balance_needed:.2f} USDT.")
            return 0, 0, False
            
        print(f"  Adjusting quantity from {quantity:.8f} to {min_quantity:.8f} to meet minimum notional value")
        quantity = min_quantity
        notional_value = MIN_NOTIONAL_VALUE
        adjusted = True
    
    return quantity, notional_value, adjusted

def main():
    """Run the simulation"""
    print(f"\n🤖 Simulating trading with ${ACCOUNT_BALANCE} account balance\n")
    
    # Print simulation parameters
    print("Simulation Parameters:")
    print(f"- Account Balance: ${ACCOUNT_BALANCE:.2f}")
    print(f"- Position Size Percent: {POSITION_SIZE_PERCENT:.1f}%")
    print(f"- Maximum Account Usage: {MAX_ACCOUNT_USAGE:.1f}%")
    print(f"- Leverage: {LEVERAGE}x")
    print(f"- Margin Percentage: {get_margin_percentage(LEVERAGE):.1f}%")
    print(f"- Minimum Notional Value: ${MIN_NOTIONAL_VALUE:.2f}")
    
    print("\nPosition Size Calculation Results:")
    
    valid_pairs = []
    
    for symbol, price in SAMPLE_PRICES.items():
        print(f"\n{symbol} (Price: ${price:.2f}):")
        
        quantity, notional_value, adjusted = calculate_position_size(
            price=price,
            account_balance=ACCOUNT_BALANCE,
            position_size_percent=POSITION_SIZE_PERCENT,
            leverage=LEVERAGE
        )
        
        if quantity > 0:
            print(f"  Quantity: {quantity:.8f}")
            print(f"  Notional Value: ${notional_value:.2f}")
            print(f"  Meets Minimum Notional: {'Yes' if notional_value >= MIN_NOTIONAL_VALUE else 'No'}")
            print(f"  Adjusted: {'Yes' if adjusted else 'No'}")
            valid_pairs.append(symbol)
        else:
            print(f"  Cannot trade {symbol} with current settings")
    
    # Count how many pairs meet minimum notional value
    total_pairs = len(SAMPLE_PRICES)
    
    print(f"\n{len(valid_pairs)} out of {total_pairs} pairs meet the minimum notional value requirement.")
    
    # Show recommendations
    print("\nRecommendations:")
    if len(valid_pairs) == 0:
        print("❌ No trading pairs meet the minimum notional value requirement with current settings.")
        print("   Consider increasing position size percentage, leverage, or account balance.")
    else:
        print(f"✅ You can trade {len(valid_pairs)} pairs with your ${ACCOUNT_BALANCE} account.")
        print(f"   Recommended pairs: {', '.join(valid_pairs)}")
    
    # Calculate maximum number of simultaneous positions
    max_positions = int(MAX_ACCOUNT_USAGE / POSITION_SIZE_PERCENT)
    print(f"\nWith {POSITION_SIZE_PERCENT:.1f}% position size and {MAX_ACCOUNT_USAGE:.1f}% max usage,")
    print(f"you can have up to {max_positions} simultaneous positions.")

if __name__ == "__main__":
    main()
