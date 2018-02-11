from decimal import Decimal

def btc_to_alt(btc_amount, alt_value):
    '''
    Pre: btc_amount and alt_value are both Decimals
    '''
    return Decimal(round(btc_amount / alt_value, 4))

def readable_btc_balance(decimal_amount):
    return '{0:.8f}'.format(decimal_amount)+"BTC"

def readable_alt_balance(decimal_points, alt_amount=None, ticker="", pumper=None):
    if pumper != None:
        alt_amount = pumper.alt_holdings
        ticker = pumper.alt_ticker
    
    if decimal_points == 0:
        return str(int(alt_amount))+ticker
    elif decimal_points == 1:
        return '{0:.1f}'.format(alt_amount)+ticker
    elif decimal_points == 2:
        return '{0:.2f}'.format(alt_amount)+ticker
    elif decimal_points == 3:
        return '{0:.3f}'.format(alt_amount)+ticker
    else:
        return '{0:.4f}'.format(alt_amount)+ticker
    