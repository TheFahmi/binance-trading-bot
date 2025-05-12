#!/usr/bin/env python
"""
Close Losing Positions Script

This script checks for open positions with significant losses and closes them.
It can be run manually or scheduled to run periodically.
"""

import os
import sys
import logging
import argparse
from datetime import datetime

# Import from the trading bot codebase
import config
from binance_client import BinanceClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("close_positions.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def close_losing_positions(loss_threshold=50.0, symbol=None, dry_run=False):
    """
    Close positions that have losses exceeding the threshold

    Args:
        loss_threshold: Loss threshold in percentage (default: 50%)
        symbol: Specific symbol to check (default: all symbols)
        dry_run: If True, only show what would be done without actually closing positions

    Returns:
        Number of positions closed
    """
    client = BinanceClient()
    positions_closed = 0

    try:
        # Get all open positions
        positions = client.get_open_positions(symbol)
        logger.info(f"Found {len(positions)} open positions")

        if not positions:
            logger.info("No open positions found")
            return 0

        # Check each position for losses
        for position in positions:
            try:
                position_symbol = position.get('symbol', '')
                position_side = position.get('positionSide', 'BOTH')
                position_amt = float(position.get('positionAmt', 0))
                entry_price = float(position.get('entryPrice', 0))
                
                # Skip positions with zero amount
                if position_amt == 0:
                    continue
                
                # Get current price
                current_price = client.get_current_price(position_symbol)
                
                # Determine if LONG or SHORT based on position amount
                is_long = position_amt > 0
                
                # Calculate unrealized PnL percentage
                if is_long:
                    pnl_percent = ((current_price / entry_price) - 1) * 100 * float(position.get('leverage', 1))
                else:  # SHORT
                    pnl_percent = ((entry_price / current_price) - 1) * 100 * float(position.get('leverage', 1))
                
                # Check if loss exceeds threshold
                if pnl_percent <= -loss_threshold:
                    logger.warning(f"Position {position_symbol} {position_side} has loss of {pnl_percent:.2f}%, exceeding threshold of {loss_threshold:.2f}%")
                    
                    if dry_run:
                        logger.info(f"DRY RUN: Would close position {position_symbol} {position_side} with loss {pnl_percent:.2f}%")
                        positions_closed += 1
                        continue
                    
                    # Determine order parameters
                    side = 'SELL' if is_long else 'BUY'  # SELL to close LONG, BUY to close SHORT
                    quantity = abs(position_amt)
                    
                    # Place market order to close position
                    logger.info(f"Closing position {position_symbol} {position_side} with {side} order, quantity {quantity}")
                    
                    # Check if hedge mode is enabled
                    is_hedge_mode = client.get_position_mode()
                    
                    try:
                        if is_hedge_mode:
                            # In hedge mode, we need to specify positionSide
                            order = client.place_market_order(
                                side=side,
                                quantity=quantity,
                                position_side=position_side,
                                symbol=position_symbol
                            )
                        else:
                            # In one-way mode, we don't specify positionSide
                            order = client.place_market_order(
                                side=side,
                                quantity=quantity,
                                position_side='BOTH',  # This will be ignored in one-way mode
                                symbol=position_symbol
                            )
                        
                        logger.info(f"Successfully closed position: {order}")
                        positions_closed += 1
                        
                    except Exception as e:
                        logger.error(f"Error closing position {position_symbol} {position_side}: {str(e)}")
                
                else:
                    logger.info(f"Position {position_symbol} {position_side} has PnL {pnl_percent:.2f}%, below threshold of {loss_threshold:.2f}%")
            
            except Exception as e:
                logger.error(f"Error processing position {position.get('symbol', 'unknown')}: {str(e)}")
        
        return positions_closed
    
    except Exception as e:
        logger.error(f"Error in close_losing_positions: {str(e)}")
        return 0

def main():
    """
    Main function to run the script from command line
    """
    parser = argparse.ArgumentParser(description='Close losing positions exceeding a threshold')
    parser.add_argument('--threshold', type=float, default=50.0, help='Loss threshold in percentage (default: 50%%)')
    parser.add_argument('--symbol', type=str, default=None, help='Specific symbol to check (default: all symbols)')
    parser.add_argument('--dry-run', action='store_true', help='Only show what would be done without actually closing positions')
    
    args = parser.parse_args()
    
    print(f"\n🔍 Checking for positions with losses exceeding {args.threshold}%...")
    
    if args.dry_run:
        print("DRY RUN MODE: No positions will actually be closed")
    
    positions_closed = close_losing_positions(args.threshold, args.symbol, args.dry_run)
    
    if positions_closed > 0:
        print(f"\n✅ Closed {positions_closed} positions with losses exceeding {args.threshold}%")
    else:
        print(f"\n✅ No positions with losses exceeding {args.threshold}% found")

if __name__ == "__main__":
    main()
