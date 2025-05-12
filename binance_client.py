import time
import hmac
import hashlib
import requests
from urllib.parse import urlencode
import pandas as pd
import config
from datetime import datetime, timedelta

class BinanceClient:
    def __init__(self, api_key=None, api_secret=None, symbol=None):
        self.api_key = api_key or config.API_KEY
        self.api_secret = api_secret or config.API_SECRET
        self.base_url = config.BASE_URL
        self.symbol = symbol or config.SYMBOL
        self.fallback_urls = config.FALLBACK_BASE_URLS.copy()
        self.current_url_index = 0  # Track which URL we're currently using

        # Initialize logging
        import logging
        self.logger = logging.getLogger(__name__)

        # Initialize cache
        self.cache = {}  # Dictionary to store cached data

        # Get exchange info to have precision data
        try:
            self.exchange_info = self._get_exchange_info()
            self.symbol_info = {}

            # Extract precision info for the symbol
            for symbol_data in self.exchange_info['symbols']:
                if symbol_data['symbol'] == self.symbol:
                    self.symbol_info = symbol_data
                    break
        except Exception as e:
            self.logger.error(f"Error initializing Binance client: {str(e)}")
            self.exchange_info = {'symbols': []}
            self.symbol_info = {}

    # Cache high volume pairs for 30 minutes to reduce API calls
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

        # Check if we have cached data
        cache_key = f"high_volume_pairs_{min_volume}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            self.logger.debug("Using cached high volume pairs data")
            return cached_data

        # Get 24h ticker statistics
        tickers = self._send_request('GET', '/fapi/v1/ticker/24hr')

        # Filter for USDT pairs and sort by volume
        usdt_pairs = [ticker for ticker in tickers if ticker['symbol'].endswith('USDT')]

        # Convert volume to float for sorting
        for pair in usdt_pairs:
            pair['quoteVolume'] = float(pair['quoteVolume'])

        # Store in cache for 30 minutes
        self._store_in_cache(cache_key, usdt_pairs, 30 * 60)  # 30 minutes in seconds

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
        # Use the logger instance instead of importing logging
        hedge_mode = hedge_mode if hedge_mode is not None else config.HEDGE_MODE

        params = {
            'dualSidePosition': 'true' if hedge_mode else 'false'
        }

        try:
            # First check if we need to change the position mode
            current_mode = self.get_position_mode()
            if current_mode == hedge_mode:
                self.logger.info(f"Position mode already set to {'hedge' if hedge_mode else 'one-way'}")
                return {"msg": "No need to change position side"}

            # If we need to change, make the API call
            return self._send_request('POST', '/fapi/v1/positionSide/dual', params, signed=True, recv_window=60000)
        except Exception as e:
            # If the mode is already set, ignore the error
            if "No need to change position side" in str(e):
                self.logger.info(f"Position mode already set to {'hedge' if hedge_mode else 'one-way'}")
                return {"msg": "No need to change position side"}
            else:
                error_msg = f"Failed to set position mode: {str(e)}"
                self.logger.error(error_msg)
                # Add a small delay before raising the exception
                time.sleep(1)  # Using the time module imported at the top of the file
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
            error_msg = f"Failed to get position mode: {str(e)}"
            self.logger.error(error_msg)
            # Add a small delay before returning the default value
            time.sleep(1)  # Using the time module imported at the top of the file
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

    def _store_in_cache(self, key, data, ttl_seconds):
        """
        Store data in cache with expiration time

        Args:
            key: Cache key
            data: Data to cache
            ttl_seconds: Time to live in seconds
        """
        expiry_time = datetime.now() + timedelta(seconds=ttl_seconds)
        self.cache[key] = {
            'data': data,
            'expiry': expiry_time
        }

    def _get_from_cache(self, key):
        """
        Get data from cache if it exists and is not expired

        Args:
            key: Cache key

        Returns:
            Cached data or None if not found or expired
        """
        if key in self.cache:
            cache_entry = self.cache[key]
            if datetime.now() < cache_entry['expiry']:
                return cache_entry['data']
            else:
                # Remove expired entry
                del self.cache[key]
        return None

    def _switch_endpoint(self):
        """
        Switch to the next available API endpoint

        Returns:
            bool: True if switched successfully, False if no more endpoints available
        """
        if not self.fallback_urls:
            self.logger.error("No more fallback URLs available")
            return False

        # Get the next fallback URL
        self.base_url = self.fallback_urls.pop(0)
        self.current_url_index += 1
        self.logger.warning(f"Switching to fallback endpoint: {self.base_url}")
        return True

    def _send_request(self, method, endpoint, params=None, signed=False, recv_window=None, retry_count=None):
        if params is None:
            params = {}

        # Use retry count from config if not specified
        if retry_count is None:
            retry_count = config.API_RETRY_COUNT

        if signed:
            params['timestamp'] = self._get_timestamp()
            # Add recvWindow parameter for signed requests
            params['recvWindow'] = recv_window or config.RECV_WINDOW
            query_string = urlencode(params)
            params['signature'] = self._generate_signature(query_string)

        # Set timeouts from config
        connect_timeout = config.API_CONNECT_TIMEOUT
        read_timeout = config.API_TIMEOUT

        # Try with current endpoint and fallbacks if needed
        max_endpoint_attempts = 1 + len(self.fallback_urls)

        for endpoint_attempt in range(max_endpoint_attempts):
            url = f"{self.base_url}{endpoint}"
            headers = {'X-MBX-APIKEY': self.api_key}

            # Implement retry logic with exponential backoff
            for attempt in range(retry_count):
                try:
                    self.logger.debug(f"Sending request to {url}")

                    # Set up proxies if configured
                    proxies = None
                    if config.USE_PROXY and config.PROXY_URL:
                        proxies = {
                            'http': config.PROXY_URL,
                            'https': config.PROXY_URL
                        }
                        self.logger.debug(f"Using proxy: {config.PROXY_URL}")

                    response = requests.request(
                        method=method,
                        url=url,
                        headers=headers,
                        params=params,
                        timeout=(connect_timeout, read_timeout),  # (connect timeout, read timeout)
                        proxies=proxies
                    )

                    if response.status_code == 200:
                        return response.json()
                    elif response.status_code == 429:  # Rate limit exceeded
                        # Get retry-after header if available
                        retry_after = response.headers.get('Retry-After')
                        if retry_after:
                            wait_time = int(retry_after)
                        else:
                            # Calculate wait time with exponential backoff
                            wait_time = (2 ** attempt) + 5  # Increased base wait time

                        self.logger.warning(f"Rate limit exceeded. Waiting {wait_time} seconds before retry.")
                        time.sleep(wait_time)
                        continue
                    elif response.status_code >= 500:  # Server error
                        wait_time = (2 ** attempt) + 1
                        self.logger.warning(f"Server error (status {response.status_code}). Waiting {wait_time} seconds before retry.")
                        time.sleep(wait_time)
                        continue
                    else:
                        # For other errors, log the full response and raise a detailed exception
                        error_msg = f"API request failed: Status {response.status_code}, Response: {response.text}"
                        self.logger.error(error_msg)

                        # Check if we have a JSON response with error details
                        try:
                            error_json = response.json()
                            if 'code' in error_json and 'msg' in error_json:
                                error_msg = f"API error {error_json['code']}: {error_json['msg']}"
                        except:
                            # If we can't parse JSON, use the text response
                            pass

                        # If this is not the last attempt, retry
                        if attempt < retry_count - 1:
                            wait_time = (2 ** attempt) + 2
                            self.logger.warning(f"Request failed. Retrying in {wait_time} seconds... (Attempt {attempt+1}/{retry_count})")
                            time.sleep(wait_time)
                            continue

                        # If this is the last attempt but we have more endpoints, break to try next endpoint
                        if endpoint_attempt < max_endpoint_attempts - 1 and self._switch_endpoint():
                            self.logger.info(f"Trying with fallback endpoint: {self.base_url}")
                            break

                        # Otherwise, raise the exception
                        raise Exception(error_msg)
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                    if attempt < retry_count - 1:
                        wait_time = (2 ** attempt) + 1
                        self.logger.warning(f"Connection error: {str(e)}. Retrying in {wait_time} seconds... (Attempt {attempt+1}/{retry_count})")
                        time.sleep(wait_time)
                        continue
                    else:
                        self.logger.error(f"Failed to connect after {retry_count} attempts: {str(e)}")
                        # Try switching to a fallback endpoint
                        if endpoint_attempt < max_endpoint_attempts - 1 and self._switch_endpoint():
                            self.logger.info(f"Trying with fallback endpoint: {self.base_url}")
                            break  # Break the retry loop to try with new endpoint
                        else:
                            raise Exception(f"All API endpoints failed: {str(e)}")

            # If we completed all retries without success but have more endpoints, continue to next endpoint
            continue

        # If we get here, all endpoints and retries failed
        raise Exception(f"API request failed after trying all endpoints")

    def _get_exchange_info(self):
        return self._send_request('GET', '/fapi/v1/exchangeInfo')

    def get_price_precision(self):
        """Get the price precision for the configured symbol"""
        return self.symbol_info.get('pricePrecision', 2)

    def get_quantity_precision(self):
        """Get the quantity precision for the configured symbol"""
        return self.symbol_info.get('quantityPrecision', 3)

    def get_klines(self, symbol=None, interval=None, limit=None, max_retries=3):
        """
        Get candlestick data with enhanced error handling and fallbacks

        Args:
            symbol: Trading symbol (default from config)
            interval: Kline interval (default from config)
            limit: Number of klines to get (default from config)
            max_retries: Maximum number of retries for fallback methods

        Returns:
            DataFrame with candlestick data
        """
        symbol = symbol or config.SYMBOL
        interval = interval or config.KLINE_INTERVAL
        limit = limit or config.KLINE_LIMIT

        # Check cache first (cache for 30 seconds for 1m candles, longer for higher timeframes)
        cache_ttl = 30  # Default 30 seconds
        if interval.endswith('m'):
            # For minute candles, cache for interval length in seconds
            try:
                minutes = int(interval[:-1])
                cache_ttl = minutes * 60
            except ValueError:
                cache_ttl = 30
        elif interval.endswith('h'):
            # For hour candles, cache for interval length in seconds
            try:
                hours = int(interval[:-1])
                cache_ttl = hours * 3600
            except ValueError:
                cache_ttl = 300
        elif interval.endswith('d'):
            # For day candles, cache for 1 hour
            cache_ttl = 3600

        cache_key = f"klines_{symbol}_{interval}_{limit}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data is not None:
            self.logger.debug(f"Using cached klines data for {symbol} {interval}")
            return cached_data

        # Main method: Try to get klines directly
        try:
            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': limit
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

            # Store in cache
            self._store_in_cache(cache_key, df, cache_ttl)

            return df

        except Exception as e:
            self.logger.warning(f"Error getting klines for {symbol} {interval}: {str(e)}")

            # Fallback 1: Try with a smaller limit
            if limit > 100 and max_retries > 0:
                self.logger.info(f"Trying with smaller limit (100) for {symbol} {interval}")
                try:
                    return self.get_klines(symbol, interval, 100, max_retries - 1)
                except Exception as e2:
                    self.logger.warning(f"Fallback 1 failed: {str(e2)}")

            # Fallback 2: Try with a different interval
            if max_retries > 0:
                fallback_interval = None
                if interval == '1m':
                    fallback_interval = '3m'
                elif interval == '3m':
                    fallback_interval = '5m'
                elif interval == '5m':
                    fallback_interval = '15m'
                elif interval == '15m':
                    fallback_interval = '30m'
                elif interval == '30m':
                    fallback_interval = '1h'
                elif interval == '1h':
                    fallback_interval = '2h'
                elif interval == '2h':
                    fallback_interval = '4h'
                elif interval == '4h':
                    fallback_interval = '6h'
                elif interval == '6h':
                    fallback_interval = '8h'
                elif interval == '8h':
                    fallback_interval = '12h'
                elif interval == '12h':
                    fallback_interval = '1d'

                if fallback_interval:
                    self.logger.info(f"Trying with fallback interval {fallback_interval} for {symbol}")
                    try:
                        return self.get_klines(symbol, fallback_interval, limit, max_retries - 1)
                    except Exception as e3:
                        self.logger.warning(f"Fallback 2 failed: {str(e3)}")

            # Fallback 3: Return empty DataFrame with correct structure
            self.logger.error(f"All fallbacks failed for {symbol} {interval}. Returning empty DataFrame.")

            # Create an empty DataFrame with the correct structure
            empty_df = pd.DataFrame(columns=[
                'open_time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])

            # Convert types for the empty DataFrame
            for col in ['open', 'high', 'low', 'close', 'volume']:
                empty_df[col] = pd.to_numeric(empty_df[col])

            # Add a warning row
            warning_row = {
                'open_time': int(time.time() * 1000),
                'open': 0, 'high': 0, 'low': 0, 'close': 0, 'volume': 0,
                'close_time': int(time.time() * 1000) + 60000,
                'quote_asset_volume': 0, 'number_of_trades': 0,
                'taker_buy_base_asset_volume': 0, 'taker_buy_quote_asset_volume': 0, 'ignore': 0
            }
            empty_df = pd.concat([empty_df, pd.DataFrame([warning_row])], ignore_index=True)

            # Raise the original exception
            raise Exception(f"Failed to get klines for {symbol} {interval}: {str(e)}")

    def get_current_price(self, symbol=None):
        """Get current price for a symbol"""
        symbol = symbol or config.SYMBOL

        # Check cache first (cache for 5 seconds)
        cache_key = f"price_{symbol}"
        cached_price = self._get_from_cache(cache_key)
        if cached_price is not None:
            self.logger.debug(f"Using cached price for {symbol}")
            return cached_price

        params = {'symbol': symbol}
        ticker = self._send_request('GET', '/fapi/v1/ticker/price', params)
        price = float(ticker['price'])

        # Store in cache for 5 seconds
        self._store_in_cache(cache_key, price, 5)

        return price

    def get_account_info(self):
        """Get account information"""
        # Check cache first (cache for 10 seconds)
        cache_key = "account_info"
        cached_data = self._get_from_cache(cache_key)
        if cached_data is not None:
            self.logger.debug("Using cached account info")
            return cached_data

        account_info = self._send_request('GET', '/fapi/v2/account', signed=True, recv_window=60000)

        # Store in cache for 10 seconds
        self._store_in_cache(cache_key, account_info, 10)

        return account_info

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
            error_msg = f"Error getting leverage brackets for {symbol}: {str(e)}"
            self.logger.error(error_msg)
            # Return empty list without delay
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
            self.logger.warning(f"Requested leverage {leverage}x exceeds maximum allowed {max_leverage}x for {symbol}. Using {max_leverage}x instead.")
            leverage = max_leverage

        params = {
            'symbol': symbol,
            'leverage': leverage
        }

        try:
            return self._send_request('POST', '/fapi/v1/leverage', params, signed=True, recv_window=60000)
        except Exception as e:
            error_msg = f"Failed to set leverage for {symbol}: {str(e)}"
            self.logger.error(error_msg)

            # If we get an invalid leverage error, try with a lower leverage
            if "is not valid" in str(e) and leverage > 1:
                new_leverage = max(1, leverage // 2)  # Try with half the leverage, minimum 1x
                self.logger.info(f"Retrying with lower leverage {new_leverage}x for {symbol}")
                # No delay needed
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

    def place_limit_order(self, side, quantity, price, position_side, symbol=None):
        """
        Place a limit order

        Args:
            side: 'BUY' or 'SELL'
            quantity: Order quantity
            price: Limit price
            position_side: 'LONG' or 'SHORT'
            symbol: Trading symbol (default from config)

        Returns:
            Response from API
        """
        params = {
            'symbol': symbol or config.SYMBOL,
            'side': side,
            'type': 'LIMIT',
            'quantity': quantity,
            'price': price,
            'positionSide': position_side,
            'timeInForce': 'GTC'
        }

        return self._send_request('POST', '/fapi/v1/order', params, signed=True, recv_window=60000)

    def place_stop_limit_order(self, side, quantity, stop_price, limit_price, position_side, symbol=None):
        """
        Place a stop-limit order

        Args:
            side: 'BUY' or 'SELL'
            quantity: Order quantity
            stop_price: Trigger price
            limit_price: Limit price
            position_side: 'LONG' or 'SHORT'
            symbol: Trading symbol (default from config)

        Returns:
            Response from API
        """
        params = {
            'symbol': symbol or config.SYMBOL,
            'side': side,
            'type': 'STOP',
            'quantity': quantity,
            'price': limit_price,
            'stopPrice': stop_price,
            'positionSide': position_side,
            'timeInForce': 'GTC',
            'workingType': 'MARK_PRICE'
        }

        return self._send_request('POST', '/fapi/v1/order', params, signed=True, recv_window=60000)

    def cancel_order(self, order_id, symbol=None):
        """
        Cancel an order

        Args:
            order_id: Order ID to cancel
            symbol: Trading symbol (default from config)

        Returns:
            Response from API
        """
        params = {
            'symbol': symbol or config.SYMBOL,
            'orderId': order_id
        }

        return self._send_request('DELETE', '/fapi/v1/order', params, signed=True, recv_window=60000)

    def get_open_orders(self, symbol=None):
        """
        Get all open orders for a symbol

        Args:
            symbol: Trading symbol (default from config)

        Returns:
            List of open orders
        """
        params = {}
        if symbol:
            params['symbol'] = symbol

        return self._send_request('GET', '/fapi/v1/openOrders', params, signed=True, recv_window=60000)

    def get_order(self, order_id, symbol=None):
        """
        Get order details

        Args:
            order_id: Order ID
            symbol: Trading symbol (default from config)

        Returns:
            Order details
        """
        params = {
            'symbol': symbol or config.SYMBOL,
            'orderId': order_id
        }

        return self._send_request('GET', '/fapi/v1/order', params, signed=True, recv_window=60000)

    def get_recent_trades(self, symbol=None, limit=100):
        """
        Get recent trades for a symbol

        Args:
            symbol: Trading symbol (default from config)
            limit: Maximum number of trades to return

        Returns:
            List of recent trades
        """
        params = {
            'symbol': symbol or config.SYMBOL,
            'limit': limit
        }

        return self._send_request('GET', '/fapi/v1/userTrades', params, signed=True, recv_window=60000)

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
                self.logger.warning(f"Failed to get income history: {str(e)}. Using default PnL values.")

            # Calculate PnL percentage based on account balance
            if total_wallet_balance > 0:
                pnl_summary['pnl_percentage'] = (pnl_summary['total_pnl'] / total_wallet_balance) * 100

            return pnl_summary

        except Exception as e:
            self.logger.error(f"Error in get_daily_pnl: {str(e)}")

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
