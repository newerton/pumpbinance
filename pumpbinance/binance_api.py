from decimal import Decimal
import hashlib
import hmac
import requests
import time
from urllib import urlencode
import warnings
from math import floor, fabs

post_binance_fee = Decimal(0.999)
API_URL = 'https://api.binance.com/api'
WEBSITE_URL = 'https://www.binance.com'
PUBLIC_API_VERSION = 'v1'
PRIVATE_API_VERSION = 'v3'
recvWindow = 20000 # Measured in milliseconds

minimum_decimals_in_quantity = {"ETHBTC": 3, "LTCBTC": 2, "BNBBTC": 0, "NEOBTC": 2, "GASBTC": 2, "BCCBTC": 3, "MCOBTC": 2,
                    "WTCBTC": 0, "QTUMBTC": 2, "OMGBTC": 2, "ZRXBTC": 0, "STRATBTC": 2, "SNGLSBTC": 0, "BQXBTC": 0,
                    "KNCBTC": 0, "FUNBTC": 0, "SNMBTC": 0, "LINKBTC": 0, "XVGBTC": 0, "CTRBTC": 0, "SALTBTC": 2,
                    "IOTABTC": 2, "MDABTC": 0, "MTLBTC": 0, "SUBBTC": 0, "EOSBTC": 0, "SNTBTC": 0, "ETCBTC": 2,
                    "MTHBTC": 0, "ENGBTC": 0, "DNTBTC": 0, "BNTBTC": 0, "ASTBTC": 0, "DASHBTC": 3, "ICNBTC": 0,
                    "OAXBTC": 0, "BTGBTC": 2, "EVXBTC": 0, "REQBTC": 0, "LRCBTC": 0, "VIBBTC": 0, "HSRBTC": 0,
                    "TRXBTC": 0, "POWRBTC": 0, "ARKBTC": 2, "YOYOBTC": 0, "XRPBTC": 0, "MODBTC": 0, "ENJBTC": 0,
                    "STORJBTC": 0, "VENBTC": 0, "KMDBTC": 0, "RCNBTC": 0, "NULSBTC": 0, "RDNBTC": 0, "XMRBTC": 3,
                    "DLTBTC": 3, "AMBBTC": 3, "BATBTC": 0, "ZECBTC": 3, "BCPTBTC": 0, "ARNBTC": 0, "GVTBTC": 2,
                    "CDTBTC": 0, "GXSBTC": 2, "POEBTC": 0, "QSPBTC": 0, "BTSBTC": 0, "XZCBTC": 2, "LSKBTC": 2,
                    "TNTBTC": 0,"FUELBTC": 0, "MANABTC": 0, "BCDBTC": 3, "DGDBTC": 3, "ADXBTC": 0, "ADABTC": 0,
                    "PPTBTC": 2, "CMTBTC": 0}

decimals_in_price = {"ETHBTC": 6, "BCCBTC": 6, "LTCBTC": 6, "NEOBTC": 6, "ETCBTC": 6, "DASHBTC": 6, "STRATBTC": 6,
                             "QTUMBTC": 6, "MCOBTC": 6, "BTGBTC": 6, "OMGBTC": 6, "ZECBTC": 6, "SALTBTC": 6, "XMRBTC": 6,
                             "ARKBTC": 7, "LSKBTC": 7, "MTLBTC": 6, "KMDBTC": 7, "HSRBTC": 6, "PPTBTC": 7, "GXSBTC": 7,
                             "BDCBTC": 6, "XZCBTC": 6, "DGDBTC": 6, "GASBTC": 6, "GVTBTC": 7, "MODBTC": 7}

class binance_api(object):
    
    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        
        self.session = self._init_session()
        self.get_average_latency() # Used to generate time stamps
        
    def get_average_latency(self):
        '''
        Based on the algorithm by Zachary Booth Simpson (2000)
        http://www.mine-control.com/zack/timesync/timesync.html
        
        Latency is measured in milliseconds.
        '''
        client_times = []
        server_times = []
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            
            self._get('time') # Exclude the first ping. It is abnormally long for some reason.
            
            i = 0
            while i < 5: # Arbitrary, but change averages below if this is changed
                client_times.append(round(time.time()*1000)) # seconds to milliseconds
                server_times.append(self._get('time')["serverTime"])
                i += 1
        
        # Logically, the latency should be divided by two  because the latency exists when the
        # data is being sent there AND back. However, the program sends commands more than 1000ms
        # ahead of Binance's server time when the latency is divided by zero so it is being removed.
        # Secondly, the latency should not be an absolute value in other applications since it doesn't
        # specify if the server or the client is ahead.
        average_server_time = sum(server_times) / 5.0
        average_client_time = sum(client_times) / 5.0
        time_dif = fabs(average_server_time - average_client_time)
        self.latency_between_server_and_client = int(time_dif)
        
    def full_ticker_for(self, alt):
        '''
        Pre: alt is a valid ticker for a coin. It is a String and entirely upper case.
        '''
        return alt + "BTC"
    
    def price_adjusted_for_decimals(self, price, ticker):
        decimals = decimals_in_price.get(ticker, 6)
        return Decimal(floor(price * Decimal(10**decimals))) / Decimal((10.0**decimals))
    
    def alt_amount_adjusted_for_decimals(self, alt_amount, ticker):
        decimals = minimum_decimals_in_quantity.get(ticker, 0)
        return Decimal(floor(alt_amount * Decimal(10**decimals))) / Decimal((10.0**decimals))
        
    def market_buy(self, btc_to_spend, ticker, use_bnb):
        '''
        :returns: The amount of the alt being received after paying fees.
        '''

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            
            alt_traded = Decimal(0)
            for ask in self.get_order_book(symbol=ticker)["asks"]:
                if btc_to_spend == 0:
                    alt_traded = self.alt_amount_adjusted_for_decimals(alt_traded, ticker)
                    self._order_market_buy(symbol=ticker, quantity=alt_traded)
                    if use_bnb:
                        return alt_traded
                    else:
                        return alt_traded * post_binance_fee
                
                price = Decimal(ask[0])
                quantity = Decimal(ask[1])
                
                btc_that_can_be_spent = price * quantity
                if btc_that_can_be_spent > btc_to_spend:
                    alt_to_buy = btc_to_spend / price
                    btc_to_spend = 0
                    alt_traded += alt_to_buy
                else:
                    btc_to_spend -= btc_that_can_be_spent
                    alt_traded += quantity
    
    def limit_buy(self, alt_amount, pumper, ticker, price, use_bnb):
        '''
        Pre: alt_amount is a Decimal
             ticker is in the form XXXBTC where XXX is the alt
             price is a Decimal
        Returns: The expected amount of the alt to receive after paying fees.
        '''
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            alt_amount = self.alt_amount_adjusted_for_decimals(alt_amount, ticker)
            price = self.price_adjusted_for_decimals(price, ticker)
            pumper.limit_order_id = self._order_limit_buy(symbol=ticker, quantity=alt_amount, price=price)["clientOrderId"]
        if use_bnb:
            return alt_amount
        else:
            return alt_amount * post_binance_fee
    
    def limit_sell(self, pumper, price):
        '''
        Pre: alt_amount is a Decimal
        '''
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ticker = self.full_ticker_for(pumper.alt_ticker)
            price = self.price_adjusted_for_decimals(price, ticker)
            pumper.limit_order_id = self._order_limit_sell(symbol=ticker, quantity=pumper.alt_holdings, price=price)["clientOrderId"]
    
    def market_sell(self, pumper, use_bnb):
        '''
        :returns: The amount of Bitcoin being received after paying fees.
        '''
        
        alt_amount = pumper.alt_holdings
        ticker = self.full_ticker_for(pumper.alt_ticker)
        
        # Place the market order first to make sure it is received soon.
        alt_amount = self.alt_amount_adjusted_for_decimals(alt_amount, ticker)
        self._order_market_sell(symbol=ticker, quantity=alt_amount)
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            
            btc_traded = Decimal(0)
            for bid in self.get_order_book(symbol=ticker)["bids"]:
                if alt_amount == 0:
                    if use_bnb:
                        return btc_traded
                    else:
                        return btc_traded * post_binance_fee
                
                price = Decimal(bid[0])
                quantity = Decimal(bid[1])
                
                if quantity > alt_amount:
                    btc_traded += alt_amount * price
                    alt_amount = 0
                else:
                    btc_traded += quantity * price
                    alt_amount -= quantity
    
    def get_timestamp(self):
        '''
        Accounts for the difference between the client and the server time.
        '''
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            client_time = int(round(time.time() * 1000))
            return client_time - self.latency_between_server_and_client
    
    def get_btc_balance(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for asset_balances in self._get('account', True, data={"timestamp":self.get_timestamp()})["balances"]:
                if asset_balances["asset"] == "BTC":
                    return Decimal(asset_balances["free"])

    def _init_session(self):

        session = requests.session()
        session.headers.update({'Accept': 'application/json',
                                'User-Agent': 'binance/python',
                                'X-MBX-APIKEY': self.api_key})
        return session

    def _create_api_uri(self, path, signed=True):
        v = PRIVATE_API_VERSION if signed else PUBLIC_API_VERSION
        return API_URL + '/' + v + '/' + path

    def _create_website_uri(self, path):
        return WEBSITE_URL + '/' + path

    def _generate_signature(self, data):

        query_string = urlencode(data)
        m = hmac.new(self.api_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256)
        return m.hexdigest()

    def _order_params(self, data):
        """Convert params to list with signature as last element
        :param data:
        :return:
        """
        has_signature = False
        params = []
        for key, value in data.items():
            if key == 'signature':
                has_signature = True
            else:
                params.append((key, value))
        if has_signature:
            params.append(('signature', data['signature']))
        return params

    def _request(self, method, uri, signed, force_params=False, **kwargs):

        data = kwargs.get('data', None)
        if data and isinstance(data, dict):
            kwargs['data'] = data
        if signed:
            # generate signature
            kwargs['data']['timestamp'] = self.get_timestamp()
            kwargs["data"]["recvWindow"] = recvWindow
            kwargs['data']['signature'] = self._generate_signature(kwargs['data'])

        if data and (method == 'get' or force_params):
            kwargs['params'] = self._order_params(kwargs['data'])
            del(kwargs['data'])

        response = getattr(self.session, method)(uri, verify=False, **kwargs)
        return self._handle_response(response)

    def _request_api(self, method, path, signed=False, **kwargs):
        uri = self._create_api_uri(path, signed)

        return self._request(method, uri, signed, **kwargs)

    def _request_website(self, method, path, signed=False, **kwargs):

        uri = self._create_website_uri(path)

        return self._request(method, uri, signed, **kwargs)

    def _handle_response(self, response):
        """Internal helper for handling API responses from the Binance server.
        Raises the appropriate exceptions when necessary; otherwise, returns the
        response.
        """
        if not str(response.status_code).startswith('2'):
            raise BinanceAPIException(response)
        try:
            return response.json()
        except ValueError:
            raise BinanceRequestException('Invalid Response: %s' % response.text)

    def _get(self, path, signed=False, **kwargs):
        return self._request_api('get', path, signed, **kwargs)

    def _post(self, path, signed=False, **kwargs):
        return self._request_api('post', path, signed, **kwargs)

    def _put(self, path, signed=False, **kwargs):
        return self._request_api('put', path, signed, **kwargs)

    def _delete(self, path, signed=False, **kwargs):
        return self._request_api('delete', path, signed, **kwargs)
    
    # Market Endpoints

    def get_ticker(self, **params):
        """24 hour price change statistics.
        https://www.binance.com/restapipub.html#24hr-ticker-price-change-statistics
        :param symbol: required
        :type symbol: str
        :returns: API response
        .. code-block:: python
            {
                "priceChange": "-94.99999800",
                "priceChangePercent": "-95.960",
                "weightedAvgPrice": "0.29628482",
                "prevClosePrice": "0.10002000",
                "lastPrice": "4.00000200",
                "bidPrice": "4.00000000",
                "askPrice": "4.00000200",
                "openPrice": "99.00000000",
                "highPrice": "100.00000000",
                "lowPrice": "0.10000000",
                "volume": "8913.30000000",
                "openTime": 1499783499040,
                "closeTime": 1499869899040,
                "fristId": 28385,   # First tradeId
                "lastId": 28460,    # Last tradeId
                "count": 76         # Trade count
            }
        :raises: BinanceResponseException, BinanceAPIException
        """
        return self._get('ticker/24hr', data=params)
    
    def get_order_book(self, **params):
        """Get the Order Book for the market
        https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#order-book
        :param symbol: required
        :type symbol: str
        :param limit:  Default 100; max 100
        :type limit: int
        :returns: API response
        .. code-block:: python
            {
                "lastUpdateId": 1027024,
                "bids": [
                    [
                        "4.00000000",     # PRICE
                        "431.00000000",   # QTY
                        []                # Can be ignored
                    ]
                ],
                "asks": [
                    [
                        "4.00000200",
                        "12.00000000",
                        []
                    ]
                ]
            }
        :raises: BinanceResponseException, BinanceAPIException
        """
        return self._get('depth', data=params)

    # Account Endpoints

    def create_order(self, **params):
        """Send in a new order
        https://www.binance.com/restapipub.html#new-order--signed
        :param symbol: required
        :type symbol: str
        :param side: required
        :type side: enum
        :param type: required
        :type type: enum
        :param timeInForce: required if limit order
        :type timeInForce: enum
        :param quantity: required
        :type quantity: decimal
        :param price: required
        :type price: decimal
        :param newClientOrderId: A unique id for the order. Automatically generated if not sent.
        :type newClientOrderId: str
        :param stopPrice: Used with stop orders
        :type stopPrice: decimal
        :param icebergQty: Used with iceberg orders
        :type icebergQty: decimal
        :returns: API response
        .. code-block:: python
            {
                "symbol":"LTCBTC",
                "orderId": 1,
                "clientOrderId": "myOrder1" # Will be newClientOrderId
                "transactTime": 1499827319559
            }
        :raises: BinanceResponseException, BinanceAPIException, BinanceOrderException, BinanceOrderMinAmountException, BinanceOrderMinPriceException, BinanceOrderMinTotalException, BinanceOrderUnknownSymbolException, BinanceOrderInactiveSymbolException
        """
        return self._post('order', True, data=params)

    def _order_limit(self, timeInForce="GTC", **params):
        """Send in a new limit order
        :param symbol: required
        :type symbol: str
        :param side: required
        :type side: enum
        :param quantity: required
        :type quantity: decimal
        :param price: required
        :type price: decimal
        :param timeInForce: default Good till cancelled
        :type timeInForce: enum
        :param newClientOrderId: A unique id for the order. Automatically generated if not sent.
        :type newClientOrderId: str
        :param stopPrice: Used with stop orders
        :type stopPrice: decimal
        :param icebergQty: Used with iceberg orders
        :type icebergQty: decimal
        :returns: API response
        .. code-block:: python
            {
                "symbol":"LTCBTC",
                "orderId": 1,
                "clientOrderId": "myOrder1" # Will be newClientOrderId
                "transactTime": 1499827319559
            }
        :raises: BinanceResponseException, BinanceAPIException, BinanceOrderException, BinanceOrderMinAmountException, BinanceOrderMinPriceException, BinanceOrderMinTotalException, BinanceOrderUnknownSymbolException, BinanceOrderInactiveSymbolException
        """
        params.update({
            'type': "LIMIT",
            'timeInForce': timeInForce
        })
        return self.create_order(**params)

    def _order_limit_buy(self, timeInForce="GTC", **params):
        """Send in a new limit buy order
        :param symbol: required
        :type symbol: str
        :param quantity: required
        :type quantity: decimal
        :param price: required
        :type price: decimal
        :param timeInForce: default Good till cancelled
        :type timeInForce: enum
        :param newClientOrderId: A unique id for the order. Automatically generated if not sent.
        :type newClientOrderId: str
        :param stopPrice: Used with stop orders
        :type stopPrice: decimal
        :param icebergQty: Used with iceberg orders
        :type icebergQty: decimal
        :returns: API response
        .. code-block:: python
            {
                "symbol":"LTCBTC",
                "orderId": 1,
                "clientOrderId": "myOrder1" # Will be newClientOrderId
                "transactTime": 1499827319559
            }
        :raises: BinanceResponseException, BinanceAPIException, BinanceOrderException, BinanceOrderMinAmountException, BinanceOrderMinPriceException, BinanceOrderMinTotalException, BinanceOrderUnknownSymbolException, BinanceOrderInactiveSymbolException
        """
        params.update({
            'side': "BUY",
        })
        return self._order_limit(timeInForce=timeInForce, **params)
    
    def _order_limit_sell(self, timeInForce="GTC", **params):
        """Send in a new limit buy order
        :param symbol: required
        :type symbol: str
        :param quantity: required
        :type quantity: decimal
        :param price: required
        :type price: decimal
        :param timeInForce: default Good till cancelled
        :type timeInForce: enum
        :param newClientOrderId: A unique id for the order. Automatically generated if not sent.
        :type newClientOrderId: str
        :param stopPrice: Used with stop orders
        :type stopPrice: decimal
        :param icebergQty: Used with iceberg orders
        :type icebergQty: decimal
        :returns: API response
        .. code-block:: python
            {
                "symbol":"LTCBTC",
                "orderId": 1,
                "clientOrderId": "myOrder1" # Will be newClientOrderId
                "transactTime": 1499827319559
            }
        :raises: BinanceResponseException, BinanceAPIException, BinanceOrderException, BinanceOrderMinAmountException, BinanceOrderMinPriceException, BinanceOrderMinTotalException, BinanceOrderUnknownSymbolException, BinanceOrderInactiveSymbolException
        """
        params.update({
            'side': "SELL",
        })
        return self._order_limit(timeInForce=timeInForce, **params)

    def _order_market(self, **params):
        """Send in a new market order
        :param symbol: required
        :type symbol: str
        :param side: required
        :type side: enum
        :param quantity: required
        :type quantity: decimal
        :param newClientOrderId: A unique id for the order. Automatically generated if not sent.
        :type newClientOrderId: str
        :returns: API response
        .. code-block:: python
            {
                "symbol":"LTCBTC",
                "orderId": 1,
                "clientOrderId": "myOrder1" # Will be newClientOrderId
                "transactTime": 1499827319559
            }
        :raises: BinanceResponseException, BinanceAPIException, BinanceOrderException, BinanceOrderMinAmountException, BinanceOrderMinPriceException, BinanceOrderMinTotalException, BinanceOrderUnknownSymbolException, BinanceOrderInactiveSymbolException
        """
        params.update({
            'type': "MARKET"
        })
        return self.create_order(**params)

    def _order_market_buy(self, **params):
        """Send in a new market buy order
        :param symbol: required
        :type symbol: str
        :param quantity: required
        :type quantity: decimal
        :param newClientOrderId: A unique id for the order. Automatically generated if not sent.
        :type newClientOrderId: str
        :returns: API response
        .. code-block:: python
            {
                "symbol":"LTCBTC",
                "orderId": 1,
                "clientOrderId": "myOrder1" # Will be newClientOrderId
                "transactTime": 1499827319559
            }
        :raises: BinanceResponseException, BinanceAPIException, BinanceOrderException, BinanceOrderMinAmountException, BinanceOrderMinPriceException, BinanceOrderMinTotalException, BinanceOrderUnknownSymbolException, BinanceOrderInactiveSymbolException
        """
        params.update({
            'side': "BUY"
        })
        return self._order_market(**params)

    def _order_market_sell(self, **params):
        """Send in a new market sell order
        :param symbol: required
        :type symbol: str
        :param quantity: required
        :type quantity: decimal
        :param newClientOrderId: A unique id for the order. Automatically generated if not sent.
        :type newClientOrderId: str
        :returns: API response
        .. code-block:: python
            {
                "symbol":"LTCBTC",
                "orderId": 1,
                "clientOrderId": "myOrder1" # Will be newClientOrderId
                "transactTime": 1499827319559
            }
        :raises: BinanceResponseException, BinanceAPIException, BinanceOrderException, BinanceOrderMinAmountException, BinanceOrderMinPriceException, BinanceOrderMinTotalException, BinanceOrderUnknownSymbolException, BinanceOrderInactiveSymbolException
        """
        params.update({
            'side': "SELL"
        })
        return self._order_market(**params)

    def get_order(self, **params):
        """Check an order's status. Either orderId or origClientOrderId must be sent.
        https://www.binance.com/restapipub.html#query-order-signed
        :param symbol: required
        :type symbol: str
        :param orderId: The unique order id
        :type orderId: int
        :param origClientOrderId: optional
        :type origClientOrderId: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int
        :returns: API response
        .. code-block:: python
            {
                "symbol": "LTCBTC",
                "orderId": 1,
                "clientOrderId": "myOrder1",
                "price": "0.1",
                "origQty": "1.0",
                "executedQty": "0.0",
                "status": "NEW",
                "timeInForce": "GTC",
                "type": "LIMIT",
                "side": "BUY",
                "stopPrice": "0.0",
                "icebergQty": "0.0",
                "time": 1499827319559
            }
        :raises: BinanceResponseException, BinanceAPIException
        """
        return self._get('order', True, data=params)

    def cancel_order(self, **params):
        """Cancel an active order. Either orderId or origClientOrderId must be sent.
        https://www.binance.com/restapipub.html#cancel-order-signed
        :param symbol: required
        :type symbol: str
        :param orderId: The unique order id
        :type orderId: int
        :param origClientOrderId: optional
        :type origClientOrderId: str
        :param newClientOrderId: Used to uniquely identify this cancel. Automatically generated by default.
        :type newClientOrderId: str
        :param recvWindow: the number of milliseconds the request is valid for
        :type recvWindow: int
        :returns: API response
        .. code-block:: python
            {
                "symbol": "LTCBTC",
                "origClientOrderId": "myOrder1",
                "orderId": 1,
                "clientOrderId": "cancelMyOrder1"
            }
        :raises: BinanceResponseException, BinanceAPIException
        """
        return self._delete('order', True, data=params)
    
    #  User Stream Endpoints

    def stream_get_listen_key(self):
        """Start a new user data stream and return the listen key
        https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#start-user-data-stream-user_stream
        :returns: API response
        .. code-block:: python
            {
                "listenKey": "pqia91ma19a5s61cv6a81va65sdf19v8a65a1a5s61cv6a81va65sdf19v8a65a1"
            }
        :raises: BinanceResponseException, BinanceAPIException
        """
        res = self._post('userDataStream', False, data={})
        return res['listenKey']

    def stream_keepalive(self, **params):
        """PING a user data stream to prevent a time out.
        https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#keepalive-user-data-stream-user_stream
        :returns: API response
        .. code-block:: python
            {}
        :raises: BinanceResponseException, BinanceAPIException
        """
        return self._put('userDataStream', False, data=params)

    def stream_close(self, **params):
        """Close out a user data stream.
        https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#close-user-data-stream-user_stream
        :returns: API response
        .. code-block:: python
            {}
        :raises: BinanceResponseException, BinanceAPIException
        """
        return self._delete('userDataStream', False, data=params)
    
class BinanceAPIException(Exception):
    
    LISTENKEY_NOT_EXIST = '-1125'
    
    def __init__(self, response):
        json_res = response.json()
        self.status_code = response.status_code
        self.response = response
        self.code = json_res['code']
        self.message = json_res['msg']
        self.request = getattr(response, 'request', None)

    def __str__(self):  # pragma: no cover
        return 'APIError(code=%s): %s' % (self.code, self.message)

class BinanceRequestException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return 'BinanceRequestException: %s' % self.message