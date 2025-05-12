import argparse
import logging
import sys
from datetime import datetime
from tabulate import tabulate

from binance_client import BinanceClient
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def format_timestamp(timestamp):
    """Format timestamp to human-readable date/time"""
    return datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')

def check_open_positions(client, symbol=None):
    """
    Check open positions
    
    Args:
        client: BinanceClient instance
        symbol: Optional symbol to filter positions
    """
    try:
        positions = client.get_open_positions(symbol)
        
        if not positions:
            print("No open positions found.")
            return
        
        # Prepare data for tabulate
        table_data = []
        for pos in positions:
            symbol = pos['symbol']
            position_side = pos.get('positionSide', 'BOTH')
            entry_price = float(pos['entryPrice'])
            position_amt = float(pos['positionAmt'])
            leverage = int(pos.get('leverage', 1))
            unrealized_pnl = float(pos.get('unrealizedProfit', 0))
            margin_type = pos.get('marginType', 'cross')
            
            # Calculate position value
            position_value = abs(position_amt) * entry_price
            
            # Calculate unrealized PnL percentage
            if position_value > 0:
                current_price = client.get_current_price(symbol)
                if position_side == 'LONG' or position_side == 'BOTH':
                    pnl_percent = ((current_price / entry_price) - 1) * 100 * leverage
                else:  # SHORT
                    pnl_percent = ((entry_price / current_price) - 1) * 100 * leverage
            else:
                pnl_percent = 0
            
            table_data.append([
                symbol,
                position_side,
                f"{position_amt:.6f}",
                f"{entry_price:.6f}",
                f"{position_value:.2f} USDT",
                f"{leverage}x",
                f"{unrealized_pnl:.2f} USDT",
                f"{pnl_percent:.2f}%",
                margin_type
            ])
        
        # Print table
        headers = ["Symbol", "Side", "Amount", "Entry Price", "Value", "Leverage", "Unrealized PnL", "PnL %", "Margin Type"]
        print("\nOpen Positions:")
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        
    except Exception as e:
        logger.error(f"Error checking open positions: {str(e)}")

def check_recent_trades(client, symbol=None, limit=20):
    """
    Check recent trades
    
    Args:
        client: BinanceClient instance
        symbol: Optional symbol to filter trades
        limit: Maximum number of trades to show
    """
    try:
        trades = client.get_recent_trades(symbol, limit)
        
        if not trades:
            print("No recent trades found.")
            return
        
        # Prepare data for tabulate
        table_data = []
        for trade in trades:
            symbol = trade['symbol']
            side = trade['side']
            position_side = trade.get('positionSide', 'BOTH')
            price = float(trade['price'])
            qty = float(trade['qty'])
            realized_pnl = float(trade.get('realizedPnl', 0))
            commission = float(trade['commission'])
            commission_asset = trade['commissionAsset']
            time = format_timestamp(trade['time'])
            
            table_data.append([
                symbol,
                side,
                position_side,
                f"{price:.6f}",
                f"{qty:.6f}",
                f"{price * qty:.2f} USDT",
                f"{realized_pnl:.2f} USDT",
                f"{commission:.6f} {commission_asset}",
                time
            ])
        
        # Print table
        headers = ["Symbol", "Side", "Position Side", "Price", "Quantity", "Value", "Realized PnL", "Commission", "Time"]
        print("\nRecent Trades:")
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        
    except Exception as e:
        logger.error(f"Error checking recent trades: {str(e)}")

def check_account_balance(client):
    """
    Check account balance
    
    Args:
        client: BinanceClient instance
    """
    try:
        account_info = client.get_account_info()
        
        # Get total wallet balance
        total_balance = float(account_info['totalWalletBalance'])
        total_unrealized_profit = float(account_info['totalUnrealizedProfit'])
        available_balance = float(account_info['availableBalance'])
        
        # Print account summary
        print("\nAccount Balance:")
        print(f"Total Balance: {total_balance:.2f} USDT")
        print(f"Unrealized Profit: {total_unrealized_profit:.2f} USDT")
        print(f"Available Balance: {available_balance:.2f} USDT")
        
        # Get assets with non-zero balance
        assets = []
        for asset in account_info['assets']:
            wallet_balance = float(asset['walletBalance'])
            if wallet_balance > 0:
                assets.append([
                    asset['asset'],
                    f"{wallet_balance:.6f}",
                    f"{float(asset['unrealizedProfit']):.6f}",
                    f"{float(asset['marginBalance']):.6f}",
                    asset['marginAvailable'] == 'true'
                ])
        
        if assets:
            # Print assets table
            headers = ["Asset", "Wallet Balance", "Unrealized Profit", "Margin Balance", "Margin Available"]
            print("\nAssets:")
            print(tabulate(assets, headers=headers, tablefmt="grid"))
        
    except Exception as e:
        logger.error(f"Error checking account balance: {str(e)}")

def check_open_orders(client, symbol=None):
    """
    Check open orders
    
    Args:
        client: BinanceClient instance
        symbol: Optional symbol to filter orders
    """
    try:
        orders = client.get_open_orders(symbol)
        
        if not orders:
            print("No open orders found.")
            return
        
        # Prepare data for tabulate
        table_data = []
        for order in orders:
            symbol = order['symbol']
            order_id = order['orderId']
            side = order['side']
            position_side = order.get('positionSide', 'BOTH')
            type = order['type']
            price = float(order.get('price', 0))
            stop_price = float(order.get('stopPrice', 0))
            orig_qty = float(order['origQty'])
            time = format_timestamp(order['time'])
            
            table_data.append([
                symbol,
                order_id,
                side,
                position_side,
                type,
                f"{price:.6f}" if price > 0 else "Market",
                f"{stop_price:.6f}" if stop_price > 0 else "N/A",
                f"{orig_qty:.6f}",
                time
            ])
        
        # Print table
        headers = ["Symbol", "Order ID", "Side", "Position Side", "Type", "Price", "Stop Price", "Quantity", "Time"]
        print("\nOpen Orders:")
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        
    except Exception as e:
        logger.error(f"Error checking open orders: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Check Binance Futures positions and trades')
    parser.add_argument('--positions', action='store_true', help='Check open positions')
    parser.add_argument('--trades', action='store_true', help='Check recent trades')
    parser.add_argument('--orders', action='store_true', help='Check open orders')
    parser.add_argument('--balance', action='store_true', help='Check account balance')
    parser.add_argument('--symbol', type=str, help='Filter by symbol (e.g., BTCUSDT)')
    parser.add_argument('--limit', type=int, default=20, help='Limit number of trades to show')
    parser.add_argument('--all', action='store_true', help='Show all information')
    
    args = parser.parse_args()
    
    # If no arguments provided, show help
    if len(sys.argv) == 1:
        parser.print_help()
        return
    
    # Create Binance client
    client = BinanceClient()
    
    # Check account balance
    if args.balance or args.all:
        check_account_balance(client)
    
    # Check open positions
    if args.positions or args.all:
        check_open_positions(client, args.symbol)
    
    # Check open orders
    if args.orders or args.all:
        check_open_orders(client, args.symbol)
    
    # Check recent trades
    if args.trades or args.all:
        check_recent_trades(client, args.symbol, args.limit)

if __name__ == "__main__":
    main()
