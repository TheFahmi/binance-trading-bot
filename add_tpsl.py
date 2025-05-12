#!/usr/bin/env python
"""
Script to add Take Profit (TP) and Stop Loss (SL) orders to existing open positions.
"""

import logging
import sys
from binance_client import BinanceClient
from position_manager import PositionManager
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("tpsl.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def add_tpsl_to_positions():
    """
    Add TP/SL orders to all open positions
    """
    client = BinanceClient()
    position_manager = PositionManager(client)
    
    # Get all open positions
    positions = client.get_open_positions()
    
    if not positions:
        logger.info("No open positions found.")
        return
    
    logger.info(f"Found {len(positions)} open positions.")
    
    # Get all open orders
    open_orders = client.get_open_orders()
    
    # Process each position
    for position in positions:
        symbol = position['symbol']
        position_side = position['positionSide']
        position_amt = float(position['positionAmt'])
        entry_price = float(position['entryPrice'])
        
        # Skip positions with zero amount
        if position_amt == 0:
            continue
        
        # Determine actual position side (LONG or SHORT)
        actual_side = 'LONG' if position_amt > 0 else 'SHORT'
        
        # If positionSide is BOTH, use the actual side
        if position_side == 'BOTH':
            position_side = actual_side
        
        # Check if TP/SL orders already exist for this position
        has_tp = False
        has_sl = False
        
        for order in open_orders:
            if order['symbol'] == symbol and order['positionSide'] == position_side:
                if order['type'] == 'TAKE_PROFIT_MARKET':
                    has_tp = True
                elif order['type'] == 'STOP_MARKET':
                    has_sl = True
        
        # Calculate TP and SL prices
        tp_price = position_manager.calculate_take_profit_price(entry_price, position_side)
        sl_price = position_manager.calculate_stop_loss_price(entry_price, position_side)
        
        # Determine order side for TP and SL
        if position_side == 'LONG':
            tp_side = 'SELL'
            sl_side = 'SELL'
        else:  # SHORT
            tp_side = 'BUY'
            sl_side = 'BUY'
        
        # Place TP order if it doesn't exist
        if not has_tp:
            try:
                tp_order = client.place_take_profit_order(
                    side=tp_side,
                    quantity=abs(position_amt),
                    stop_price=tp_price,
                    position_side=position_side,
                    symbol=symbol
                )
                logger.info(f"Placed TP order for {symbol} {position_side}: {tp_order}")
            except Exception as e:
                logger.error(f"Failed to place TP order for {symbol} {position_side}: {str(e)}")
        else:
            logger.info(f"TP order already exists for {symbol} {position_side}")
        
        # Place SL order if it doesn't exist
        if not has_sl:
            try:
                sl_order = client.place_stop_loss_order(
                    side=sl_side,
                    quantity=abs(position_amt),
                    stop_price=sl_price,
                    position_side=position_side,
                    symbol=symbol
                )
                logger.info(f"Placed SL order for {symbol} {position_side}: {sl_order}")
            except Exception as e:
                logger.error(f"Failed to place SL order for {symbol} {position_side}: {str(e)}")
        else:
            logger.info(f"SL order already exists for {symbol} {position_side}")

if __name__ == "__main__":
    try:
        add_tpsl_to_positions()
        logger.info("TP/SL addition completed.")
    except Exception as e:
        logger.error(f"Error adding TP/SL: {str(e)}")
        sys.exit(1)
