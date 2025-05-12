#!/usr/bin/env python
"""
Close MOODENGUSDT Position Script

This script specifically closes the MOODENGUSDT position.
"""

import os
import sys
import logging
from datetime import datetime

# Import from the trading bot codebase
import config
from binance_client import BinanceClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("close_moodeng.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def close_moodeng_position():
    """
    Close the MOODENGUSDT position

    Returns:
        True if position was closed, False otherwise
    """
    client = BinanceClient()
    symbol = "MOODENGUSDT"

    try:
        # Get MOODENGUSDT position
        positions = client.get_open_positions(symbol)
        logger.info(f"Found {len(positions)} open positions for {symbol}")

        if not positions:
            logger.info(f"No open positions found for {symbol}")
            return False

        # Process each position (should be only one)
        for position in positions:
            try:
                position_side = position.get('positionSide', 'BOTH')
                position_amt = float(position.get('positionAmt', 0))
                entry_price = float(position.get('entryPrice', 0))
                
                # Skip positions with zero amount
                if position_amt == 0:
                    logger.info(f"Position {symbol} {position_side} has zero amount, skipping")
                    continue
                
                # Get current price
                current_price = client.get_current_price(symbol)
                
                # Determine if LONG or SHORT based on position amount
                is_long = position_amt > 0
                
                # Calculate unrealized PnL
                if is_long:
                    pnl_percent = ((current_price / entry_price) - 1) * 100 * float(position.get('leverage', 1))
                else:  # SHORT
                    pnl_percent = ((entry_price / current_price) - 1) * 100 * float(position.get('leverage', 1))
                
                logger.info(f"Position {symbol} {position_side} has PnL {pnl_percent:.2f}%")
                
                # Determine order parameters
                side = 'SELL' if is_long else 'BUY'  # SELL to close LONG, BUY to close SHORT
                quantity = abs(position_amt)
                
                # Place market order to close position
                logger.info(f"Closing position {symbol} {position_side} with {side} order, quantity {quantity}")
                
                # Check if hedge mode is enabled
                is_hedge_mode = client.get_position_mode()
                
                try:
                    if is_hedge_mode:
                        # In hedge mode, we need to specify positionSide
                        order = client.place_market_order(
                            side=side,
                            quantity=quantity,
                            position_side=position_side,
                            symbol=symbol
                        )
                    else:
                        # In one-way mode, we don't specify positionSide
                        order = client.place_market_order(
                            side=side,
                            quantity=quantity,
                            position_side='BOTH',  # This will be ignored in one-way mode
                            symbol=symbol
                        )
                    
                    logger.info(f"Successfully closed position: {order}")
                    return True
                    
                except Exception as e:
                    logger.error(f"Error closing position {symbol} {position_side}: {str(e)}")
                    return False
            
            except Exception as e:
                logger.error(f"Error processing position {symbol}: {str(e)}")
                return False
        
        return False
    
    except Exception as e:
        logger.error(f"Error in close_moodeng_position: {str(e)}")
        return False

def main():
    """
    Main function to run the script
    """
    print(f"\n🔍 Checking for MOODENGUSDT position...")
    
    result = close_moodeng_position()
    
    if result:
        print(f"\n✅ Successfully closed MOODENGUSDT position")
    else:
        print(f"\n❌ Failed to close MOODENGUSDT position or no position found")

if __name__ == "__main__":
    main()
