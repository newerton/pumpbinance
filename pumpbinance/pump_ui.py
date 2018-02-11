from Tkinter import Tk, DISABLED, NORMAL, Button, Spinbox, Label, StringVar, W, N, E, Entry, OptionMenu, END
import ttk
from tkFont import Font
from binance_api import binance_api
from helper_methods import btc_to_alt, readable_alt_balance, readable_btc_balance
from decimal import Decimal, InvalidOperation
from pumper import pumper, SELL_PROFIT, SELL_STOP_LOSS
from math import floor
from binance_api import BinanceAPIException, minimum_decimals_in_quantity
from threading import Thread
import logging
import time

# Object to log the bot's behaviour into a text file.
LOG_FILENAME = 'bot-'+str(time.time())+'.log'
logging.basicConfig(filename=LOG_FILENAME, level=logging.DEBUG)
        
#### User Interface ####
frame_title = "Binance P&D"
label_font_colour = "#ffffff"
background_colour = "#00471e"
default_relief = "raised"
minimum_trade = Decimal("0.002")
btc_to_use_increment = Decimal("0.001")
max_lines_in_console = 22 # There is a pattern that the lines should equal the height of the console.

class pump_ui(object):
    
    def __init__(self):
        master = Tk()
        master.style = ttk.Style()
        master.style.theme_use("default")
        master.config(bg=background_colour)
        master.resizable(0, 0) # Disable resizing the UI to prevent having to make widget placing dynamic
        master.winfo_toplevel().title(frame_title)
        master.iconbitmap("bitcoin.ico")
        
        # Create pumper assistant to store data on the current BTC and alt holdings.
        self.pumper = pumper()
        
        self.create_title(master)
        self.create_api_info(master,previous_row=0)
        self.create_auto_sell(master, previous_row=3)
        self.create_stop_loss(master, previous_row=4)
        self.create_order_type(master, previous_row=6)
        self.create_fee_type(master, previous_row=7)
        self.create_btc_balance_picker(master, previous_row=8)
        self.create_alt_ticker(master, previous_row=10)
        self.create_pump_and_sell_buttons(master, previous_row=11)
        self.create_current_profit(master, previous_row=12)
        
        self.create_output_box(master, rightmost_column=1)
        
        # Can hardcode API key and Secret
        #self.api_key_entry.delete(0,END)
        #self.api_key_entry.insert(0,"KEY")
        #self.api_key_entry.config(state=DISABLED)
        #self.api_secret_entry.delete(0, END)
        #self.api_secret_entry.insert(0, "SECRET")
        #self.api_secret_entry.config(state=DISABLED)
        
        # Display the UI, this can only be called once per program.
        # Nothing in the main Python script will be run after creating the UI because of this.
        master.mainloop()
        
    def create_title(self, master, previous_row=-1, previous_column=-1):
        empty = Label(master, text=frame_title)
        empty.grid(row=previous_row+1, column=previous_column+2, columnspan=1)
        empty.config(bg=background_colour, fg=label_font_colour)
        
    def create_api_info(self, master, previous_row=-1, previous_column=-1):
        api_key_lbl = Label(master, text="API Key:")
        api_key_lbl.grid(row=previous_row+1, column=previous_column+1, columnspan=1, sticky=E, padx=(3,0))
        api_key_lbl.config(bg=background_colour, fg=label_font_colour)
        
        self.api_key_entry = Entry(master, highlightthickness=0, bd=0, width=21, show="*")
        self.api_key_entry.config(borderwidth=2, relief=default_relief)
        self.api_key_entry.grid(row=previous_row+1, column=previous_column+2)
        
        api_secret_lbl = Label(master, text="API Secret:")
        api_secret_lbl.grid(row=previous_row+2, column=previous_column+1, columnspan=1, sticky=E, padx=(3,0))
        api_secret_lbl.config(bg=background_colour, fg=label_font_colour)
        
        self.api_secret_entry = Entry(master, highlightthickness=0, bd=0, width=21, show="*")
        self.api_secret_entry.config(borderwidth=2, relief=default_relief)
        self.api_secret_entry.grid(row=previous_row+2, column=previous_column+2)
        
        self.api_connect_btn = Button(master, text="Connect To Binance", command=self.on_connect_api)
        self.api_connect_btn.grid(row=previous_row+3, column=previous_column+2, columnspan=1, sticky=W+E, padx=10, pady=(0,3))
        self.api_connect_btn.config(highlightbackground=background_colour)
        
    def create_auto_sell(self, master, previous_row=-1, previous_column=-1):
        auto_sell_lbl = Label(master, text="Auto Sell (%):")
        auto_sell_lbl.grid(row=previous_row+1, column=previous_column+1, columnspan=1, sticky=E, padx=(3,0))
        auto_sell_lbl.config(bg=background_colour, fg=label_font_colour)
        
        self.auto_sell_spinbox = Spinbox(master, from_=1.0, to=300.0, increment=1.0, highlightbackground=background_colour)
        self.auto_sell_spinbox.config(borderwidth=2, relief=default_relief)
        self.auto_sell_spinbox.grid(row=previous_row+1, column=previous_column+2)
        self.auto_sell_spinbox.delete(0, "end")
        self.auto_sell_spinbox.insert(0, 50)
        
    def create_stop_loss(self, master, previous_row=-1, previous_column=-1):
        stop_loss_lbl = Label(master, text="Stop Loss (%):")
        stop_loss_lbl.grid(row=previous_row+1, column=previous_column+1, columnspan=1, sticky=E, padx=(3,0))
        stop_loss_lbl.config(bg=background_colour, fg=label_font_colour)
        
        self.stop_loss_spinbox = Spinbox(master, from_=-100.0, to=-10.0, increment=1.0, highlightbackground=background_colour)
        self.stop_loss_spinbox.config(borderwidth=2, relief=default_relief)
        self.stop_loss_spinbox.grid(row=previous_row+1, column=previous_column+2)
        self.stop_loss_spinbox.delete(0, "end")
        self.stop_loss_spinbox.insert(0, -10)
        
    def create_btc_balance_picker(self, master, previous_row=-1, previous_column=-1):
        self.btc_balance_str = StringVar()
        btc_balance_lbl = Label(master, textvar=self.btc_balance_str)
        btc_balance_lbl.grid(row=previous_row+1, column=previous_column+1, columnspan=2, sticky=W+E, padx=(3,0))
        btc_balance_lbl.config(bg=background_colour, fg=label_font_colour)
        self.set_available_btc_balance(Decimal(0))
        
        btc_to_use_label = Label(master, text="BTC to spend:", bg=background_colour, fg=label_font_colour)
        btc_to_use_label.grid(row=previous_row+2, column=previous_column+1, sticky=E, padx=(3,0))

        self.btc_to_use_spinbox = Spinbox(master, from_=minimum_trade, to=minimum_trade, increment=btc_to_use_increment, highlightbackground=background_colour)
        self.btc_to_use_spinbox.config(borderwidth=2, relief=default_relief)
        self.btc_to_use_spinbox.grid(row=previous_row+2, column=previous_column+2)
        
    def create_order_type(self, master, previous_row=-1, previous_column=-1):
        order_type_lbl = Label(master, text="Entry Type:")
        order_type_lbl.grid(row=previous_row+1, column=previous_column+1, sticky=E, padx=(3,0))
        order_type_lbl.config(bg=background_colour, fg=label_font_colour)
        
        self.is_entry_market = True
        def change_order_type(*args):
            self.is_entry_market = (self.order_type.get()=="Market Buy  \/")
        
        self.order_type = StringVar()
        self.order_type.trace("w", change_order_type) # Reduces how much work is done when the pump starts
        choices = {"Market Buy  \/", "Limit Buy     \/"}
        self.entry_type_option_menu = OptionMenu(master, self.order_type, *choices)
        self.entry_type_option_menu.grid(row=previous_row+1, column=previous_column+2, sticky=W+E, padx=8)
        self.entry_type_option_menu.config(highlightthickness=0)
        self.entry_type_option_menu.configure(indicatoron=0)
        self.order_type.set("Market Buy  \/")
        
    def create_fee_type(self, master, previous_row=-1, previous_column=-1):
        fee_type_lbl = Label(master, text="Fee Type:")
        fee_type_lbl.grid(row=previous_row+1, column=previous_column+1, sticky=E, padx=(3,0))
        fee_type_lbl.config(bg=background_colour, fg=label_font_colour)
        
        self.is_using_bnb = True
        def change_fee_type(*args):
            self.is_using_bnb = (self.order_type.get()=="Binance Coin (BNB) \/")
        
        self.fee_type = StringVar()
        self.fee_type.trace("w", change_fee_type) # Reduces how much work is done when the pump starts
        choices = {"Binance Coin (BNB) \/", "0.1% Of All Trades    \/"}
        self.fee_type_option_menu = OptionMenu(master, self.fee_type, *choices)
        self.fee_type_option_menu.grid(row=previous_row+1, column=previous_column+2, sticky=W+E, padx=8)
        self.fee_type_option_menu.config(highlightthickness=0)
        self.fee_type_option_menu.configure(indicatoron=0)
        self.fee_type.set("Binance Coin (BNB) \/")
        
    def create_pump_and_sell_buttons(self, master, previous_row=-1, previous_column=-1):
        # Manual sell button can only be activated after initiating a pump.
        self.manual_sell_btn = Button(master, text="Sell", state=DISABLED, command=self.on_manual_sell)
        self.manual_sell_btn.grid(row=previous_row+1, column=previous_column+1, sticky=W+E, padx=(3,0))
        self.manual_sell_btn.config(highlightbackground=background_colour)
        
        self.pump_btn = Button(master, text="Pump", command=self.on_pump)
        self.pump_btn.grid(row=previous_row+1, column=previous_column+2, sticky=W+E, padx=8)
        self.pump_btn.config(highlightbackground=background_colour, state=DISABLED)
        
    def create_alt_ticker(self, master, previous_row=-1, previous_column=-1):
        ticker_lbl = Label(master, text="Ticker To Pump:")
        ticker_lbl.grid(row=previous_row+1, column=previous_column+1, columnspan=1, sticky=E, padx=(3,0), pady=(0,8))
        ticker_lbl.config(bg=background_colour, fg=label_font_colour)
        
        self.ticker_entry = Entry(master, highlightthickness=0, bd=0, width=21)
        self.ticker_entry.config(borderwidth=2, relief=default_relief)
        self.ticker_entry.grid(row=previous_row+1, column=previous_column+2, pady=8)
        self.ticker_entry.bind('<Return>', self.on_pump_shortcut)
        
    def create_current_profit(self, master, previous_row=-1, previous_column=-1):
        self.current_profit_str = StringVar()
        current_profit_lbl = Label(master, textvar=self.current_profit_str)
        current_profit_lbl.grid(row=previous_row+1, column=previous_column+1, columnspan=2, sticky=W+E, padx=3, pady=(0,3))
        current_profit_lbl.config(bg=background_colour, fg=label_font_colour)
        self.current_profit_str.set("Current Profit: 0%")
        
    def create_output_box(self, master, rightmost_column):
        self.pump_output = StringVar()
        console_lbl = Label(master, textvar=self.pump_output, borderwidth=2, relief=default_relief, anchor=N)
        console_lbl.grid(row=0, column=rightmost_column+1, columnspan=1, rowspan=14, padx=(10,0), pady=0)
        console_lbl.config(width=50, height=22, bg="black", font=Font(family="Courier", size=9), fg="white")
        self.lines = 0
        
    def disable_pre_pump_options(self):
        # Change the buttons that can be clicked to prevent the user
        # from trying to pump multiple coins with one bot.
        self.manual_sell_btn.config(state=NORMAL)
        self.pump_btn.config(state=DISABLED)
        self.btc_to_use_spinbox.config(state=DISABLED)
        self.ticker_entry.config(state=DISABLED)
        self.auto_sell_spinbox.config(state=DISABLED)
        self.stop_loss_spinbox.config(state=DISABLED)
        self.api_key_entry.config(state=DISABLED) # Comment out if hardcoding key
        self.api_secret_entry.config(state=DISABLED) # Comment out if hardcoding secret
        self.api_connect_btn.config(state=DISABLED)
        self.entry_type_option_menu.config(state=DISABLED)
        self.fee_type_option_menu.config(state=DISABLED)
        
    def enable_pump_options(self):
        # Change the buttons that can be clicked to prevent the user
        # from trying to pump multiple coins with one bot.
        self.manual_sell_btn.config(state=DISABLED)
        self.pump_btn.config(state=NORMAL)
        self.btc_to_use_spinbox.config(state=NORMAL)
        self.ticker_entry.config(state=NORMAL)
        self.auto_sell_spinbox.config(state=NORMAL)
        self.stop_loss_spinbox.config(state=NORMAL)
        self.api_key_entry.config(state=NORMAL) # Comment out if hardcoding key
        self.api_secret_entry.config(state=NORMAL) # Comment out if hardcoding secret
        self.api_connect_btn.config(state=NORMAL)
        self.entry_type_option_menu.config(state=NORMAL)
        self.fee_type_option_menu.config(state=NORMAL)
        
    def set_available_btc_balance(self, btc_balance):
        self.pumper.btc_balance = btc_balance
        self.btc_balance_str.set("Available Balance: " + readable_btc_balance(btc_balance))
        
    def set_current_profit(self, current_profit):
        self.current_profit_str.set("Current Profit: "+'{0:.3f}'.format(round(current_profit*Decimal(100), 3))+"%")
        
    def write_to_console(self, line):
        self.lines += 1
        if self.lines > max_lines_in_console:
            i = self.pump_output.get().index('\n')
            self.pump_output.set(self.pump_output.get()[i+1:]+"\n"+line)
        elif self.lines == 1:
            self.pump_output.set(line)
        else:
            self.pump_output.set(self.pump_output.get()+"\n"+line)
        
    #### Button Behaviour ####
    def on_pump(self):
        try:
            api = self.api
            btc_to_use = Decimal(self.btc_to_use_spinbox.get())
        except InvalidOperation:
            # The BTC to spend box is empty.
            self.write_to_console("Stop!")
            self.write_to_console("BTC to spend cannot be empty.")
            return
        except AttributeError:
            # There is no API object.
            self.write_to_console("You need to connect to Binance before pumping.")
            return
            
        if btc_to_use >= minimum_trade:
            if btc_to_use <= self.pumper.btc_balance:
                target_profit_percentage = Decimal(float(self.auto_sell_spinbox.get())/100.0)
                
                # Validate auto-sell and stop loss
                if target_profit_percentage <= Decimal(0):
                    self.write_to_console("Auto sell has to be positive.")
                    return
                if Decimal(self.stop_loss_spinbox.get()) >= Decimal(0):
                    self.write_to_console("Stop loss has to be negative.")
                    return
                
                ticker = self.ticker_entry.get().upper()
                
                # Empty strings are False in Python
                if ticker:
                    full_ticker = api.full_ticker_for(ticker)
                    
                    try:
                        alt = self.api.get_ticker(symbol=full_ticker)
                    except BinanceAPIException, e:
                        logging.debug(str(e))
                        self.write_to_console("Invalid ticker.")
                        return
                    
                    alt_value = Decimal(alt["askPrice"])
                    
                    # Used in console output
                    decimal_points = minimum_decimals_in_quantity.get(full_ticker, 0)
                    self.pumper.decimal_points_in_alt = decimal_points
                    
                    self.pumper.set_up(btc_to_use, target_profit_percentage, alt_value, ticker)
                    if self.is_entry_market:
                        self.pumper.alt_holdings = api.market_buy(self.pumper.btc_to_use, full_ticker, self.is_using_bnb)
                        self.write_to_console("Bought "+readable_alt_balance(decimal_points, pumper=self.pumper)+" with "+readable_btc_balance(btc_to_use)+".")
                    else:
                        highest_bid = Decimal(alt["bidPrice"])
                        
                        if alt_value - highest_bid <= Decimal(0.00000001):
                            to_bid = highest_bid
                        else:
                            # Bid between the highest bid and the lowest ask for the best odds of being filled.
                            to_bid = (alt_value - highest_bid)/2 + highest_bid
                            to_bid = Decimal(floor(to_bid * Decimal(100000000.0))) / Decimal(100000000.0)
                        self.pumper.starting_alt_value = to_bid
                        
                        expected = api.limit_buy(btc_to_alt(btc_to_use, alt_value), pumper, full_ticker, to_bid, self.is_using_bnb)
                        self.write_to_console("Buying "+readable_alt_balance(decimal_points, alt_amount=expected, ticker=ticker)+" for "+readable_btc_balance(btc_to_use)+".")
                        self.write_to_console("This is a limit order, it may not get filled.")
                        
                    self.disable_pre_pump_options()
                    self.set_stop_loss()
                    self.start_monitoring_orderbook(full_ticker)
                else:
                    # The user is trying to trade with more than they actually have.
                    self.write_to_console("You did not enter a ticker.")
            else:
                # The user is trying to trade with more than they actually have.
                self.write_to_console("Stop!")
                self.write_to_console("You are trying to spend more BTC than you have.")
        else:
            # BTC is smaller than the minimum trade. Output an error.
            self.write_to_console("Stop!")
            self.write_to_console("The minimum trade is "+readable_btc_balance(minimum_trade)+".")
            
    def set_stop_loss(self):
        ''' Should be called before monitoring the ROI. '''
        self.pumper.stop_loss = Decimal(float(self.stop_loss_spinbox.get())/100.0)
            
    def start_monitoring_orderbook(self, full_ticker):
        def start():
            while self._monitor_orderbook:
                self.on_book(self.api.get_order_book(symbol=full_ticker))
        self._monitor_orderbook = True
        monitoring_thread = Thread(target=start)
        monitoring_thread.start()
        
    def stop_monitoring_orderbook(self):
        self._monitor_orderbook = False
            
    def on_book(self, book):
        '''
        A pump has started and the bot is listening to the exchange's asks to decide what to do.
        '''

        action = self.pumper.update_bids(book["bids"])

        if action == SELL_PROFIT:
            if not self.is_entry_market:
                # Cancel any open buy orders and sync the amount of alt that we have.
                btc_spent = self.cancel_pumper_limit_order_and_sync()
                self.write_to_console("Limit order was filled for "+readable_alt_balance(self.pumper.decimal_points_in_alt, pumper=self.pumper)+", spent "+readable_btc_balance(btc_spent)+".")
                
            # Wait until the order book can handle our sell order
            if self.pumper.can_sell():
                btc_received = self.api.market_sell(self.pumper, self.is_using_bnb)
                
                # Allow the user to start a new pump.
                self.stop_monitoring_orderbook()
                self.enable_pump_options()
                
                # Tell the user how much they made and sync their balance.
                self.write_to_console("Sold "+readable_alt_balance(self.pumper.decimal_points_in_alt, pumper=self.pumper)+" for "+readable_btc_balance(btc_received)+".")
                self.write_to_console("Profited "+readable_btc_balance(btc_received-self.pumper.btc_to_use)+".")
                self.on_connect_api()
                
        elif action == SELL_STOP_LOSS:
            if not self.is_entry_market:
                self.cancel_pumper_limit_order_and_sync()
            
            self.write_to_console("Stop loss reached.")
            
            if self.pumper.alt_holdings > Decimal(0):
                new_btc_balance = self.api.market_sell(self.pumper, self.is_using_bnb)
                self.write_to_console("Selling at market. Lost "+readable_btc_balance(self.pumper.btc_balance-new_btc_balance)+".")
                self.set_available_btc_balance(new_btc_balance)
            else:
                self.write_to_console("Limit order was not filled. No "+self.pumper.alt_ticker+" to sell.")
            
            self.write_to_console("Aborting pump bot.")
            
            # Allow the user to start a new pump.
            self.stop_monitoring_orderbook()
            self.enable_pump_options()
        
        # Update the UI with the current profit percentage.
        self.set_current_profit(self.pumper.current_profit_percentage)
            
    def on_pump_shortcut(self, event):
        if self.pump_btn['state'] == NORMAL:
            self.on_pump()
        
    def on_manual_sell(self):
        if not self.is_entry_market:
            self.cancel_pumper_limit_order_and_sync()
            
        # A limit order may have been placed but not filled
        if self.pumper.alt_holdings > Decimal(0):
            btc_received = self.api.market_sell(self.pumper, self.is_using_bnb)
            self.write_to_console("Manually sold "+readable_alt_balance(self.pumper.decimal_points_in_alt, pumper=self.pumper)+" for "+readable_btc_balance(btc_received)+".")
            net = btc_received-self.pumper.btc_to_use

            # Sync the BTC balance
            self.on_connect_api()
            if net > 0:
                self.write_to_console("Profited "+readable_btc_balance(net)+".")
            else:
                self.write_to_console("Lost "+readable_btc_balance(net)+".")
        else:
            self.write_to_console("You have no "+self.pumper.alt_ticker+" to sell.")
            self.write_to_console("Try a market order next time.")
            
        # Allow the user to start a new pump.
        self.stop_monitoring_orderbook()
        self.enable_pump_options()
        
    def on_connect_api(self):
        key = self.api_key_entry.get()
        secret = self.api_secret_entry.get()
        
        if key and secret:
            self.api = binance_api(key, secret)
            btc_balance = self.api.get_btc_balance()
            if btc_balance == None:
                self.write_to_console("Invalid API key or IP.")
            else:
                if btc_balance < minimum_trade:
                    self.btc_to_use_spinbox.config(to=minimum_trade)
                else:
                    self.btc_to_use_spinbox.config(to=btc_balance)
                self.set_available_btc_balance(btc_balance)

                self.pump_btn.config(state=NORMAL)
                self.write_to_console("Fetched BTC balance from Binance.")
                # Divide latency by two because Binance's API does not divide latency by 2.
                # See the API's get_average_latency method for details.
                self.write_to_console("Latency to Binance is "+str(int(round(self.api.latency_between_server_and_client/2.0)))+"ms.")
        else:
            self.write_to_console("Missing API info.")
            
    def cancel_pumper_limit_order_and_sync(self):
        '''
        :returns: BTC spent
        '''
        full_ticker = self.api.full_ticker_for(self.pumper.alt_ticker)
        order_info = self.api.get_order(origClientOrderId=self.pumper.limit_order_id, symbol=full_ticker)
        if order_info["status"] == "NEW" or order_info["status"] == "PARTIALLY_FILLED":
            self.api.cancel_order(origClientOrderId=self.pumper.limit_order_id, symbol=full_ticker)
        alt_bought = Decimal(order_info["executedQty"])
        self.pumper.alt_holdings = alt_bought
        return alt_bought * Decimal(order_info["price"])
    
if __name__ == "__main__":
    ui = pump_ui()
    