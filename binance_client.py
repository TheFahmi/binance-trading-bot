import time
import hmac
import hashlib
import requests
import json
from urllib.parse import urlencode
import pandas as pd
import config

class BinanceClient:
    def __init__(self, api_key=None, api_secret=None, symbol=None):
        self.api_key = api_key or config.API_KEY
        self.api_secret = api_secret or config.API_SECRET
        self.base_url = config.BASE_URL
        self.symbol = symbol or config.SYMBOL

        # Get exchange info to have precision data
        self.exchange_info = self._get_exchange_info()
        self.symbol_info = {}

        # Extract precision info for the symbol
        for symbol_data in self.exchange_info['symbols']:
            if symbol_data['symbol'] == self.symbol:
                self.symbol_info = symbol_data
                break

    def get_high_volume_pairs(self, min_volume=None, limit=20):
        """
        Get trading pairs with high 24h volume

        Args:
            min_volume: Minimum 24h volume in USDT (default from config)
            limit: Maximum number of pairs to return

        Returns:
            List of high volume trading pairs
        """
        min_volume = min_volume or config.MIN_VOLUME_USDT

        # Get 24h ticker statistics
        tickers = self._send_request('GET', '/fapi/v1/ticker/24hr')

        # Filter for USDT pairs and sort by volume
        usdt_pairs = [ticker for ticker in tickers if ticker['symbol'].endswith('USDT')]

        # Convert volume to float for sorting
        for pair in usdt_pairs:
            pair['quoteVolume'] = float(pair['quoteVolume'])

        # Sort by quote volume (USDT volume) in descending order
        usdt_pairs.sort(key=lambda x: x['quoteVolume'], reverse=True)

        # Filter by minimum volume
        high_volume_pairs = [pair for pair in usdt_pairs if pair['quoteVolume'] >= min_volume]

        # Limit the number of pairs
        high_volume_pairs = high_volume_pairs[:limit]

        # Log the selected pairs
        symbols = [pair['symbol'] for pair in high_volume_pairs]
        volumes = [f"{pair['quoteVolume']:,.0f} USDT" for pair in high_volume_pairs]

        for i, (symbol, volume) in enumerate(zip(symbols, volumes)):
            print(f"{i+1}. {symbol}: {volume}")

        return symbols

    def update_symbol(self, symbol):
        """
        Update the current symbol and its precision info

        Args:
            symbol: New symbol to use
        """
        self.symbol = symbol

        # Update symbol info
        for symbol_data in self.exchange_info['symbols']:
            if symbol_data['symbol'] == symbol:
                self.symbol_info = symbol_data
                break

    def set_position_mode(self, hedge_mode=None):
        """
        Set position mode (hedge or one-way)

        Args:
            hedge_mode: True for hedge mode, False for one-way mode (default from config)

        Returns:
            Response from API
        """
        hedge_mode = hedge_mode if hedge_mode is not None else config.HEDGE_MODE

        params = {
            'dualSidePosition': 'true' if hedge_mode else 'false'
        }

        try:
            return self._send_request('POST', '/fapi/v1/positionSide/dual', params, signed=True, recv_window=60000)
        except Exception as e:
            import logging
            # If the mode is already set, ignore the error
            if "No need to change position side" in str(e):
                logging.info(f"Position mode already set to {'hedge' if hedge_mode else 'one-way'}")
                return {"msg": "No need to change position side"}
            else:
                logging.error(f"Failed to set position mode: {str(e)}")
                raise

    def get_position_mode(self):
        """
        Get current position mode (hedge or one-way)

        Returns:
            True if hedge mode is enabled, False otherwise
        """
        try:
            response = self._send_request('GET', '/fapi/v1/positionSide/dual', signed=True, recv_window=60000)
            return response.get('dualSidePosition', False)
        except Exception as e:
            import logging
            logging.error(f"Failed to get position mode: {str(e)}")
            # Default to config value if we can't get the current mode
            return config.HEDGE_MODE

    def _get_timestamp(self):
        return int(time.time() * 1000)

    def _generate_signature(self, query_string):
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def _send_request(self, method, endpoint, params=None, signed=False, recv_window=None):
        url = f"{self.base_url}{endpoint}"
        headers = {'X-MBX-APIKEY': self.api_key}

        if params is None:
            params = {}

        if signed:
            params['timestamp'] = self._get_timestamp()
            # Add recvWindow parameter for signed requests
            params['recvWindow'] = recv_window or config.RECV_WINDOW
            query_string = urlencode(params)
            params['signature'] = self._generate_signature(query_string)

        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params
        )

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"API request failed: {response.text}")

    def _get_exchange_info(self):
        return self._send_request('GET', '/fapi/v1/exchangeInfo')

    def get_price_precision(self):
        """Get the price precision for the configured symbol"""
        return self.symbol_info.get('pricePrecision', 2)

    def get_quantity_precision(self):
        """Get the quantity precision for the configured symbol"""
        return self.symbol_info.get('quantityPrecision', 3)

    def get_klines(self, symbol=None, interval=None, limit=None):
        """Get candlestick data"""
        params = {
            'symbol': symbol or config.SYMBOL,
            'interval': interval or config.KLINE_INTERVAL,
            'limit': limit or config.KLINE_LIMIT
        }

        klines = self._send_request('GET', '/fapi/v1/klines', params)

        # Convert to DataFrame
        df = pd.DataFrame(klines, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])

        # Convert types
        df['open'] = pd.to_numeric(df['open'])
        df['high'] = pd.to_numeric(df['high'])
        df['low'] = pd.to_numeric(df['low'])
        df['close'] = pd.to_numeric(df['close'])
        df['volume'] = pd.to_numeric(df['volume'])

        return df

    def get_current_price(self, symbol=None):
        """Get current price for a symbol"""
        params = {'symbol': symbol or config.SYMBOL}
        ticker = self._send_request('GET', '/fapi/v1/ticker/price', params)
        return float(ticker['price'])

    def get_account_info(self):
        """Get account information"""
        return self._send_request('GET', '/fapi/v2/account', signed=True, recv_window=60000)

    def get_open_positions(self, symbol=None):
        """
        Get open positions for a symbol

        Args:
            symbol: Trading symbol (optional)

        Returns:
            List of open positions
        """
        account_info = self.get_account_info()
        positions = account_info['positions']

        if symbol:
            positions = [p for p in positions if p['symbol'] == symbol]

        # Filter out positions with zero amount
        positions = [p for p in positions if float(p['positionAmt']) != 0]

        return positions

    def get_position_pnl(self, symbol=None, position_side=None):
        """
        Get unrealized PnL for a specific position

        Args:
            symbol: Trading symbol (optional)
            position_side: 'LONG' or 'SHORT' (optional)

        Returns:
            Dictionary with PnL information
        """
        symbol = symbol or self.symbol
        positions = self.get_open_positions(symbol)

        if position_side:
            positions = [p for p in positions if p['positionSide'] == position_side]

        if not positions:
            return {
                'symbol': symbol,
                'position_side': position_side,
                'entry_price': 0,
                'mark_price': 0,
                'position_amt': 0,
                'unrealized_pnl': 0,
                'unrealized_pnl_percent': 0,
                'leverage': 0,
                'margin_type': 'NONE'
            }

        # Get current price
        current_price = self.get_current_price(symbol)

        # Calculate PnL for each position
        pnl_info = []
        for position in positions:
            entry_price = float(position['entryPrice'])
            position_amt = float(position['positionAmt'])
            leverage = int(position['leverage'])
            margin_type = position['marginType']
            position_side = position['positionSide']

            # Calculate unrealized PnL
            if position_side == 'LONG':
                unrealized_pnl = (current_price - entry_price) * abs(position_amt)
                unrealized_pnl_percent = ((current_price / entry_price) - 1) * 100 * leverage
            else:  # SHORT
                unrealized_pnl = (entry_price - current_price) * abs(position_amt)
                unrealized_pnl_percent = ((entry_price / current_price) - 1) * 100 * leverage

            pnl_info.append({
                'symbol': symbol,
                'position_side': position_side,
                'entry_price': entry_price,
                'mark_price': current_price,
                'position_amt': position_amt,
                'unrealized_pnl': unrealized_pnl,
                'unrealized_pnl_percent': unrealized_pnl_percent,
                'leverage': leverage,
                'margin_type': margin_type
            })

        # If position_side was specified, return the first matching position
        if position_side and pnl_info:
            return pnl_info[0]

        # Otherwise, return all positions
        return pnl_info

    def get_combined_position_pnl(self, symbol=None):
        """
        Get combined PnL for both LONG and SHORT positions on the same symbol

        Args:
            symbol: Trading symbol (optional)

        Returns:
            Dictionary with combined PnL information
        """
        symbol = symbol or self.symbol
        long_pnl = self.get_position_pnl(symbol, 'LONG')
        short_pnl = self.get_position_pnl(symbol, 'SHORT')

        # If we have both positions
        if isinstance(long_pnl, dict) and isinstance(short_pnl, dict) and long_pnl['position_amt'] != 0 and short_pnl['position_amt'] != 0:
            # Calculate combined PnL
            combined_unrealized_pnl = long_pnl['unrealized_pnl'] + short_pnl['unrealized_pnl']

            # Calculate weighted average entry prices
            long_value = abs(long_pnl['position_amt'] * long_pnl['entry_price'])
            short_value = abs(short_pnl['position_amt'] * short_pnl['entry_price'])
            total_value = long_value + short_value

            # Calculate combined PnL percentage
            if total_value > 0:
                combined_unrealized_pnl_percent = (combined_unrealized_pnl / total_value) * 100
            else:
                combined_unrealized_pnl_percent = 0

            return {
                'symbol': symbol,
                'long_position': long_pnl,
                'short_position': short_pnl,
                'combined_unrealized_pnl': combined_unrealized_pnl,
                'combined_unrealized_pnl_percent': combined_unrealized_pnl_percent,
                'is_hedged': True
            }

        # If we only have one position
        elif isinstance(long_pnl, dict) and long_pnl['position_amt'] != 0:
            return {
                'symbol': symbol,
                'long_position': long_pnl,
                'short_position': None,
                'combined_unrealized_pnl': long_pnl['unrealized_pnl'],
                'combined_unrealized_pnl_percent': long_pnl['unrealized_pnl_percent'],
                'is_hedged': False
            }
        elif isinstance(short_pnl, dict) and short_pnl['position_amt'] != 0:
            return {
                'symbol': symbol,
                'long_position': None,
                'short_position': short_pnl,
                'combined_unrealized_pnl': short_pnl['unrealized_pnl'],
                'combined_unrealized_pnl_percent': short_pnl['unrealized_pnl_percent'],
                'is_hedged': False
            }

        # If we have no positions
        else:
            return {
                'symbol': symbol,
                'long_position': None,
                'short_position': None,
                'combined_unrealized_pnl': 0,
                'combined_unrealized_pnl_percent': 0,
                'is_hedged': False
            }

    def get_leverage_brackets(self, symbol=None):
        """
        Get leverage brackets for a symbol

        Args:
            symbol: Trading symbol (default from config)

        Returns:
            List of leverage brackets with notionalCap, notionalFloor, and maintMarginRatio
        """
        symbol = symbol or self.symbol
        params = {'symbol': symbol}

        try:
            # Get leverage brackets
            brackets = self._send_request('GET', '/fapi/v1/leverageBracket', params, signed=True, recv_window=60000)

            # If response is a list, find the matching symbol
            if isinstance(brackets, list):
                for item in brackets:
                    if item.get('symbol') == symbol:
                        return item.get('brackets', [])

            # If response is a dict with direct brackets
            elif isinstance(brackets, dict) and 'brackets' in brackets:
                return brackets['brackets']

            # If response is a dict with symbol as key
            elif isinstance(brackets, dict) and symbol in brackets:
                return brackets[symbol].get('brackets', [])

            return []

        except Exception as e:
            import logging
            logging.error(f"Error getting leverage brackets for {symbol}: {str(e)}")
            return []

    def get_max_leverage(self, symbol=None):
        """
        Get maximum allowed leverage for a symbol

        Args:
            symbol: Trading symbol (default from config)

        Returns:
            Maximum allowed leverage (default: 20 if can't determine)
        """
        symbol = symbol or self.symbol
        brackets = self.get_leverage_brackets(symbol)

        if brackets:
            # The first bracket has the highest leverage
            return int(brackets[0].get('initialLeverage', 20))

        # Default to 20x if we can't determine
        return 20

    def set_leverage(self, leverage, symbol=None):
        """
        Set leverage for a symbol, with fallback to maximum allowed leverage

        Args:
            leverage: Desired leverage
            symbol: Trading symbol (default from config)

        Returns:
            Response from API
        """
        symbol = symbol or self.symbol

        # Get maximum allowed leverage
        max_leverage = self.get_max_leverage(symbol)

        # If requested leverage is higher than maximum, use maximum
        if leverage > max_leverage:
            import logging
            logging.warning(f"Requested leverage {leverage}x exceeds maximum allowed {max_leverage}x for {symbol}. Using {max_leverage}x instead.")
            leverage = max_leverage

        params = {
            'symbol': symbol,
            'leverage': leverage
        }

        try:
            return self._send_request('POST', '/fapi/v1/leverage', params, signed=True, recv_window=60000)
        except Exception as e:
            import logging
            error_msg = f"Failed to set leverage for {symbol}: {str(e)}"
            logging.error(error_msg)

            # If we get an invalid leverage error, try with a lower leverage
            if "is not valid" in str(e) and leverage > 1:
                new_leverage = max(1, leverage // 2)  # Try with half the leverage, minimum 1x
                logging.info(f"Retrying with lower leverage {new_leverage}x for {symbol}")
                return self.set_leverage(new_leverage, symbol)

            # Re-raise the exception if we can't handle it
            raise

    def place_market_order(self, side, quantity, position_side, symbol=None):
        """Place a market order"""
        params = {
            'symbol': symbol or config.SYMBOL,
            'side': side,  # 'BUY' or 'SELL'
            'type': 'MARKET',
            'quantity': quantity,
            'positionSide': position_side,  # 'LONG' or 'SHORT'
        }

        return self._send_request('POST', '/fapi/v1/order', params, signed=True, recv_window=60000)

    def place_take_profit_order(self, side, quantity, stop_price, position_side, symbol=None):
        """Place a take profit market order"""
        params = {
            'symbol': symbol or config.SYMBOL,
            'side': side,  # 'BUY' or 'SELL'
            'type': 'TAKE_PROFIT_MARKET',
            'quantity': quantity,
            'stopPrice': stop_price,
            'positionSide': position_side,  # 'LONG' or 'SHORT'
            'timeInForce': 'GTC',
            'workingType': 'MARK_PRICE',
            'priceProtect': 'TRUE'
        }

        return self._send_request('POST', '/fapi/v1/order', params, signed=True, recv_window=60000)

    def place_stop_loss_order(self, side, quantity, stop_price, position_side, symbol=None):
        """Place a stop market order"""
        params = {
            'symbol': symbol or config.SYMBOL,
            'side': side,  # 'BUY' or 'SELL'
            'type': 'STOP_MARKET',
            'quantity': quantity,
            'stopPrice': stop_price,
            'positionSide': position_side,  # 'LONG' or 'SHORT'
            'timeInForce': 'GTC',
            'workingType': 'MARK_PRICE',
            'priceProtect': 'TRUE'
        }

        return self._send_request('POST', '/fapi/v1/order', params, signed=True, recv_window=60000)

    def round_price(self, price):
        """Round price according to symbol precision"""
        precision = self.get_price_precision()
        return round(price, precision)

    def round_quantity(self, quantity):
        """Round quantity according to symbol precision"""
        precision = self.get_quantity_precision()
        return round(quantity, precision)

    def get_income_history(self, income_type=None, start_time=None, end_time=None, limit=1000):
        """
        Get income history (realized PnL, funding fees, etc.)

        Args:
            income_type: Optional filter by income type (REALIZED_PNL, FUNDING_FEE, etc.)
            start_time: Start time in milliseconds
            end_time: End time in milliseconds
            limit: Maximum number of records to return

        Returns:
            List of income records
        """
        params = {'limit': limit}

        if income_type:
            params['incomeType'] = income_type

        if start_time:
            params['startTime'] = start_time

        if end_time:
            params['endTime'] = end_time

        # Use a larger recvWindow for income history requests (60 seconds)
        return self._send_request('GET', '/fapi/v1/income', params, signed=True, recv_window=60000)

    def get_daily_pnl(self, start_of_day=None):
        """
        Calculate daily PnL from income history

        Args:
            start_of_day: Start timestamp of the day in milliseconds

        Returns:
            Dictionary with PnL summary
        """
        from datetime import datetime, timezone

        try:
            # If start_of_day not provided, use the start of the current day (UTC)
            if not start_of_day:
                now = datetime.now(timezone.utc)
                start_of_day = int(datetime(now.year, now.month, now.day, tzinfo=timezone.utc).timestamp() * 1000)

            # Get current time in milliseconds
            current_time = int(time.time() * 1000)

            # Initialize PnL summary with default values
            pnl_summary = {
                'total_pnl': 0.0,
                'realized_pnl': 0.0,
                'funding_fee': 0.0,
                'commission': 0.0,
                'other': 0.0,
                'trades_count': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'pnl_percentage': 0
            }

            # Get account information first to have balance data even if income history fails
            account_info = self.get_account_info()
            total_wallet_balance = float(account_info['totalWalletBalance'])

            # Try to get income history with a large recvWindow
            try:
                # Get income history for the day
                income_history = self.get_income_history(start_time=start_of_day, end_time=current_time)

                # Process income records
                for record in income_history:
                    amount = float(record['income'])
                    income_type = record['incomeType']

                    # Add to total PnL
                    pnl_summary['total_pnl'] += amount

                    # Categorize by income type
                    if income_type == 'REALIZED_PNL':
                        pnl_summary['realized_pnl'] += amount
                        pnl_summary['trades_count'] += 1

                        if amount > 0:
                            pnl_summary['winning_trades'] += 1
                        elif amount < 0:
                            pnl_summary['losing_trades'] += 1

                    elif income_type == 'FUNDING_FEE':
                        pnl_summary['funding_fee'] += amount

                    elif income_type == 'COMMISSION':
                        pnl_summary['commission'] += amount

                    else:
                        pnl_summary['other'] += amount

                # Calculate win rate if there were any trades
                if pnl_summary['trades_count'] > 0:
                    pnl_summary['win_rate'] = (pnl_summary['winning_trades'] / pnl_summary['trades_count']) * 100

            except Exception as e:
                import logging
                logging.warning(f"Failed to get income history: {str(e)}. Using default PnL values.")

            # Calculate PnL percentage based on account balance
            if total_wallet_balance > 0:
                pnl_summary['pnl_percentage'] = (pnl_summary['total_pnl'] / total_wallet_balance) * 100

            return pnl_summary

        except Exception as e:
            import logging
            logging.error(f"Error in get_daily_pnl: {str(e)}")

            # Return default PnL summary if everything fails
            return {
                'total_pnl': 0.0,
                'realized_pnl': 0.0,
                'funding_fee': 0.0,
                'commission': 0.0,
                'other': 0.0,
                'trades_count': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'pnl_percentage': 0
            }
