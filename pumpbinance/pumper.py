from decimal import Decimal

# Constants used when deciding what to do given the ROI.
SELL_PROFIT = True
SELL_STOP_LOSS = False

class pumper(object):
    
    btc_balance = Decimal(0)
    btc_to_use = Decimal(0)
    starting_alt_value = Decimal(0)
    target_profit_percentage = Decimal(0.5)
    current_profit_percentage = Decimal(0)
    alt_ticker = ""
    limit_order_id = ""
    stop_loss = Decimal(-0.25)
    decimal_points_in_alt = 0
    bid_threshold = Decimal(0)
    alt_holdings = Decimal(0) # Need to be set whenever a buy or sell order is made
    usable_sell_quantity = Decimal(0)
    
    def set_up(self, btc_to_use, target_profit_percentage, starting_alt_value, alt_ticker):
        assert isinstance(btc_to_use, Decimal)
        assert isinstance(target_profit_percentage, Decimal)
        assert isinstance(starting_alt_value, Decimal)
        self.btc_to_use = btc_to_use
        self.target_profit_percentage = target_profit_percentage
        self.current_profit_percentage = Decimal(0)
        self.starting_alt_value = starting_alt_value
        self.alt_ticker = alt_ticker
        
        # Rearranged version of profit_percentage = (highest_bid - starting_alt_value) / starting_alt_value
        self.bid_threshold = self.target_profit_percentage * self.starting_alt_value + self.starting_alt_value
        self.bid_threshold.quantize(Decimal('1E-8'))
        
    def update_current_profit_percentage(self, highest_bid):
        '''
        Pre: highest_bid is a Decimal
        '''

        self.current_profit_percentage = highest_bid / self.starting_alt_value - Decimal(1)

        if self.current_profit_percentage >= self.target_profit_percentage:
            return SELL_PROFIT
        elif self.current_profit_percentage <= self.stop_loss:
            return SELL_STOP_LOSS
        
    def is_bid_usable(self, bid):
        '''
        :param bid: required
        :type bid: Decimal
        :returns: If selling at the bid puts the pumper at or above its desired profit percentage.
        '''
        return bid >= self.bid_threshold
    
    def update_bids(self, bids):
        # Everything is calculated every time. It would be more efficient to use the web socket.
        highest_bid = Decimal(0)
        self.usable_sell_quantity = Decimal(0)
        for bid in bids:
            price = Decimal(bid[0])
            quantity = Decimal(bid[1])
            if highest_bid < price:
                highest_bid = price
            if self.is_bid_usable(price):
                self.usable_sell_quantity += quantity
            else:
                break
        return self.update_current_profit_percentage(highest_bid)
    
    def can_sell(self):
        return self.alt_holdings <= self.usable_sell_quantity