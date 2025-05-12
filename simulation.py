#!/usr/bin/env python
"""
Trading Simulation Script

This script runs a trading simulation with a $100 initial balance using historical data.
It leverages the backtesting functionality to simulate trading with a small account.
"""

import os
import sys
import logging
import argparse
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from tabulate import tabulate

# Import from the trading bot codebase
import config
from backtest import Backtester, run_backtest_for_symbol, run_backtest_for_multiple_symbols, compare_backtest_results
from binance_client import BinanceClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("simulation.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def run_simulation(symbol, start_date, end_date, initial_balance=100):
    """
    Run a trading simulation with a small account
    
    Args:
        symbol: Trading symbol (e.g., BTCUSDT)
        start_date: Start date for simulation (YYYY-MM-DD)
        end_date: End date for simulation (YYYY-MM-DD)
        initial_balance: Initial account balance in USDT (default: $100)
        
    Returns:
        BacktestResult object with simulation results
    """
    logger.info(f"Running simulation for {symbol} with ${initial_balance} initial balance")
    
    # Create backtester instance
    backtester = Backtester(symbol, start_date, end_date, initial_balance)
    
    # Run the backtest
    result = backtester.run_backtest()
    
    # Save and plot results
    output_dir = "simulation_results"
    os.makedirs(output_dir, exist_ok=True)
    
    # Create a timestamp for the filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    base_filename = f"{symbol}_{timestamp}"
    
    # Save results
    result_path = result.save_results(output_dir)
    plot_path = result.plot_results(output_dir)
    
    return result

def run_multi_symbol_simulation(symbols, start_date, end_date, initial_balance=100):
    """
    Run simulations on multiple symbols
    
    Args:
        symbols: List of trading symbols
        start_date: Start date for simulation (YYYY-MM-DD)
        end_date: End date for simulation (YYYY-MM-DD)
        initial_balance: Initial account balance in USDT (default: $100)
        
    Returns:
        Dictionary of symbol -> BacktestResult
    """
    logger.info(f"Running simulation for {len(symbols)} symbols with ${initial_balance} initial balance")
    
    results = {}
    
    for symbol in symbols:
        logger.info(f"Running simulation for {symbol}")
        result = run_simulation(symbol, start_date, end_date, initial_balance)
        results[symbol] = result
    
    # Compare results
    comparison = compare_backtest_results(results)
    
    # Save comparison to CSV
    output_dir = "simulation_results"
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    comparison.to_csv(f"{output_dir}/comparison_{timestamp}.csv", index=False)
    
    return results, comparison

def display_simulation_results(result):
    """
    Display simulation results in a user-friendly format
    
    Args:
        result: BacktestResult object
    """
    print("\n" + "="*50)
    print(f"SIMULATION RESULTS FOR {result.symbol}")
    print("="*50)
    
    # Basic metrics
    metrics = [
        ["Initial Balance", f"${result.initial_balance:.2f}"],
        ["Final Balance", f"${result.final_balance:.2f}"],
        ["Total Profit/Loss", f"${result.total_profit:.2f} ({result.total_profit_pct:.2f}%)"],
        ["Total Trades", result.total_trades],
        ["Winning Trades", result.winning_trades],
        ["Losing Trades", result.losing_trades],
        ["Win Rate", f"{result.win_rate*100:.2f}%"],
        ["Profit Factor", f"{result.profit_factor:.2f}"],
        ["Max Drawdown", f"${result.max_drawdown:.2f} ({result.max_drawdown_pct*100:.2f}%)"],
        ["Sharpe Ratio", f"{result.sharpe_ratio:.2f}"]
    ]
    
    print(tabulate(metrics, tablefmt="simple"))
    
    # Trade summary
    if result.trades:
        print("\nTRADE SUMMARY:")
        
        # Convert trades to DataFrame for easier display
        trades_df = pd.DataFrame(result.trades)
        
        # Format the DataFrame for display
        trades_df['entry_time'] = pd.to_datetime(trades_df['entry_time'])
        trades_df['exit_time'] = pd.to_datetime(trades_df['exit_time'])
        
        # Format columns for display
        display_df = trades_df.copy()
        display_df['entry_time'] = display_df['entry_time'].dt.strftime('%Y-%m-%d %H:%M')
        display_df['exit_time'] = display_df['exit_time'].dt.strftime('%Y-%m-%d %H:%M')
        display_df['pnl'] = display_df['pnl'].map('${:.2f}'.format)
        display_df['pnl_pct'] = display_df['pnl_pct'].map('{:.2f}%'.format)
        
        # Select columns to display
        display_cols = ['entry_time', 'side', 'entry_price', 'exit_time', 'exit_price', 'pnl', 'pnl_pct']
        
        # Display the last 10 trades
        print(tabulate(display_df[display_cols].tail(10), headers='keys', tablefmt='simple', showindex=False))
        
        if len(trades_df) > 10:
            print(f"\n(Showing last 10 of {len(trades_df)} trades)")
    
    print("\nSimulation results saved to 'simulation_results' directory")

def display_comparison_results(comparison):
    """
    Display comparison results for multiple symbols
    
    Args:
        comparison: DataFrame with comparison metrics
    """
    print("\n" + "="*50)
    print("SYMBOL COMPARISON RESULTS")
    print("="*50)
    
    # Format the DataFrame for display
    display_df = comparison.copy()
    display_df['win_rate'] = display_df['win_rate'].map('{:.2f}'.format)
    display_df['profit_factor'] = display_df['profit_factor'].map('{:.2f}'.format)
    display_df['total_profit'] = display_df['total_profit'].map('${:.2f}'.format)
    display_df['total_profit_pct'] = display_df['total_profit_pct'].map('{:.2f}%'.format)
    display_df['max_drawdown_pct'] = display_df['max_drawdown_pct'].map('{:.2f}%'.format)
    display_df['sharpe_ratio'] = display_df['sharpe_ratio'].map('{:.2f}'.format)
    
    print(tabulate(display_df, headers='keys', tablefmt='simple', showindex=False))
    print("\nComparison results saved to 'simulation_results' directory")

def main():
    """
    Main function to run the simulation from command line
    """
    parser = argparse.ArgumentParser(description='Run trading simulation with $100 initial balance')
    parser.add_argument('--symbol', type=str, default=config.SYMBOL, help='Trading symbol')
    parser.add_argument('--start', type=str, default=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'), 
                        help='Start date (YYYY-MM-DD), defaults to 30 days ago')
    parser.add_argument('--end', type=str, default=None, help='End date (YYYY-MM-DD), defaults to today')
    parser.add_argument('--balance', type=float, default=100, help='Initial balance in USDT')
    parser.add_argument('--multi', action='store_true', help='Run simulation for multiple symbols')
    parser.add_argument('--min-volume', type=float, default=config.MIN_VOLUME_USDT, 
                        help='Minimum 24h volume in USDT for symbol selection')
    parser.add_argument('--limit', type=int, default=5, help='Maximum number of symbols to test in multi mode')
    
    args = parser.parse_args()
    
    print(f"\n🤖 Starting trading simulation with ${args.balance} initial balance")
    
    if args.multi:
        # Get high volume pairs
        client = BinanceClient()
        symbols = client.get_high_volume_pairs(args.min_volume, args.limit)
        
        if not symbols:
            logger.error("Failed to get high volume pairs")
            return
        
        print(f"Running simulation for {len(symbols)} symbols: {', '.join(symbols)}")
        
        # Run simulations
        results, comparison = run_multi_symbol_simulation(symbols, args.start, args.end, args.balance)
        
        # Display comparison results
        display_comparison_results(comparison)
        
        # Display detailed results for the best performing symbol
        best_symbol = comparison.iloc[0]['symbol']
        print(f"\nDetailed results for best performing symbol ({best_symbol}):")
        display_simulation_results(results[best_symbol])
        
    else:
        # Run simulation for single symbol
        print(f"Running simulation for {args.symbol} from {args.start} to {args.end or 'today'}")
        
        result = run_simulation(args.symbol, args.start, args.end, args.balance)
        
        # Display results
        display_simulation_results(result)

if __name__ == "__main__":
    main()
