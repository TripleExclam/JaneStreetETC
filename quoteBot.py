#!/usr/bin/python
# ~~~~~==============   HOW TO RUN   ==============~~~~~
# 1) Configure things in CONFIGURATION section
# 2) Change permissions: chmod +x bot.py
# 3) Run in loop: while true; do ./bot.py; sleep 1; done

from __future__ import print_function

import math
import sys
import socket
import json
import VStock
from collections import defaultdict, deque

from typing import Dict, Set

from parser import *

# ~~~~~============== CONFIGURATION  ==============~~~~~
# replace REPLACEME with your team name!
from util import keydefaultdict

TEAM_NAME = "BUYHIGHSELLLOW"
# This variable dictates whether or not the bot is connecting to the prod
# or test exchange. Be careful with this switch!
TEST_MODE = False

# This setting changes which test exchange is connected to.
# 0 is prod-like
# 1 is slower
# 2 is empty
TEST_EXCHANGE_INDEX = 0 
PROD_EXCHANGE_HOSTNAME = "production"

PORT = 25000 + (TEST_EXCHANGE_INDEX if TEST_MODE else 0)
EXCHANGE_HOSTNAME = "test-exch-" + TEAM_NAME if TEST_MODE else PROD_EXCHANGE_HOSTNAME

# ~~~~~============== NETWORKING CODE ==============~~~~~
def connect():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((EXCHANGE_HOSTNAME, PORT))
    return s.makefile("rw", 1)

def write_to_exchange(exchange, obj):
    json.dump(obj, exchange)
    exchange.write("\n")

def read_from_exchange(exchange):
    return json.loads(exchange.readline())

##### DATA #######

SYMBOLS = ['BOND', 'VALBZ', 'VALE', 'GS', 'MS', 'WFC', 'XLF']

RISK_LIMITS = {
    'BOND': 100,
    'VALBZ': 10,
    'VALE': 10,
    'GS': 100,
    'MS': 100,
    'WFC': 100,
    'XLF': 100
}

positions: Dict[str, int] = defaultdict(int)
books: Dict[str, Book] = keydefaultdict(lambda sym: Book(sym, [], [], [], {}))
cur_orders: Set[int] = set()
basket = {"BOND": 3, "GS": 2, "MS": 3, "WFC": 2}
counter: int = 1
VPriceGS = VStock.VPrice(lookback=5, margin=0.01)
VPriceMS = VStock.VPrice(lookback=5, margin=0.01)
VPriceWFC = VStock.VPrice(lookback=5, margin=0.01)
VPriceVALE = VStock.VPrice(lookback=5, margin=0.01)
VPriceVALBZ = VStock.VPrice(lookback=5, margin=0.01)
pre_order_details = {}

trade_queue: deque = deque()
###### LOGIC #######

def force_cancel_order(exchange, order_id: int):
    write_to_exchange(exchange, {"type": "cancel", "order_id": order_id})


def pull_all_orders(exchange):
    for order_id in cur_orders:
        force_cancel_order(exchange, order_id)


def place_cancel(order_id: int):
    trade_queue.append({"type": "cancel", "order_id": order_id})


def place_order(symbol: str, price: int, size: int) -> int:
    global counter
    counter += 1
    direction = "BUY" if size > 0 else "SELL"

    order = {"type": "add", "order_id": counter, "symbol": symbol, "dir": direction,
                "price": price, "size": abs(size)}

    trade_queue.append(order)
    pre_order_details[counter] = order

    return counter


def place_convert(symbol: str, direction: str, size: int) -> int:
    global counter
    counter += 1
    assert (direction in ["BUY", "SELL"])

    msg = {"type": "convert", "order_id": counter, "symbol": symbol, "dir": direction, "size": size}

    trade_queue.append(msg)
    return counter


def on_book_update(exchange, symbol: str, book: Book):
    at_limit = abs(positions[symbol]) >= RISK_LIMITS[symbol]
    quote(book)

    if symbol == "BOND":
        hit_bond_bid = buy_bonds(book)
        if hit_bond_bid != -1:
            place_order(symbol, hit_bond_bid[0], hit_bond_bid[1])
        lift_bond_offer = sell_bonds(book)
        if lift_bond_offer != -1:
            place_order(symbol, lift_bond_offer[0], -lift_bond_offer[1])
        
    elif symbol == "VALBZ" and len(book.sell) != 0: # BUY VALBZ
        largest_sell = book.sell[0]
        if len(books["VALE"].buy) != 0:
            for item in books["VALE"].buy:
                quant = min(min(10 - positions["VALBZ"], largest_sell[1]), item[1]) 
                if quant * item[0] - 10 > quant * largest_sell[0]:
                    place_order("VALBZ", largest_sell[0], quant)
                    place_convert("VALE", "BUY", quant)
                    place_order("VALE", item[0], -quant)
    
    elif symbol == "VALE" and len(book.sell) != 0: # BUY VALBZ
        largest_sell = book.sell[0]
        if len(books["VALBZ"].buy) != 0:
            for item in books["VALBZ"].buy:
                quant = min(min(10 - positions["VALE"], largest_sell[1]), item[1])
                if quant * item[0] - 10 > quant * largest_sell[0]:
                    place_order("VALE", largest_sell[0], quant)
                    place_convert("VALE", "SELL", quant)
                    place_order("VALBZ", item[0], -quant)

def quote(book):
    symbol = book.symbol
    if len(book.buy) == 0 or len(book.sell) == 0 or len(book.last_trades) == 0:
        return
    bid = book.buy
    sell = book.sell
    last_trades = book.last_trades
    margin = 0.001

    if symbol == "BOND":
        quote_margin = 1
        fair_val = 1000
    elif symbol == "GS":
        VPriceGS.addOrders(last_trades)
        fair_val = VPriceGS.price * (1 - margin * positions[symbol] / RISK_LIMITS[symbol])
        quote_margin = margin * fair_val
    elif symbol == "MS":
        VPriceMS.addOrders(last_trades)
        fair_val = VPriceMS.price * (1 - margin * positions[symbol] / RISK_LIMITS[symbol])
        quote_margin = margin * fair_val
    elif symbol == "WFC":
        VPriceWFC.addOrders(last_trades)
        fair_val = VPriceWFC.price * (1 - margin * positions[symbol] / RISK_LIMITS[symbol])
        quote_margin = margin * fair_val
    elif symbol == "XXX":
        VPriceVALE.addOrders(last_trades)
        fair_val = VPriceVALE.price * (1 - margin * positions[symbol] / RISK_LIMITS[symbol])
        quote_margin = margin * fair_val
    else:
        return
    our_orders = book.our_resting_orders
    our_bid = -1
    our_ask = -1
    for order_id, order in our_orders.items():
        if order[0] == "BUY":
            our_bid = order[1]
            bid_id = order_id
        elif order[0] == "SELL":
            our_ask = order[1]
            ask_id = order_id

    if bid[0][0] < math.floor(fair_val - quote_margin) and bid[0][0] != our_bid:
        if our_bid != -1:
            place_cancel(bid_id)
        print("QUOTING")
        place_order(symbol, bid[0][0] + 1, 1)
    if sell[0][0] > math.ceil(fair_val + quote_margin) and sell[0][0] != our_ask:
        if our_ask != -1:
            place_cancel(ask_id)
        print("QUOTING")
        place_order(symbol, sell[0][0] - 1, -1)

def on_our_order_traded(exchange, order_id: int, symbol: str, dir: str, price: int, size: int):
    multiply = (1 if dir == "BUY" else -1)
    positions[symbol] += (size * multiply)
    pass 


def etf_strat(book):
    # check sell price of ETF
    order = book.sell[0]
    order_price = order[0]

    position = positions["XLF"]
    multiples_10 = round(position/10)

    n = multiples_10 #TODO
    total_buy = 0
    for symbol in basket:
        buy_price = books[symbol].buy[0][0]
        total_buy += buy_price * basket[symbol]

    if order_price - 100 > total_buy:
        place_convert("XLF", )
        # convert ETF positions["XLF"]


def buy_bonds(book):
    if len(book.sell) == 0:
        return -1
    order = book.sell[0]
    if order[0] < 1000:
        return order
    return -1


def sell_bonds(book):
    if len(book.buy) == 0:
        return -1
    order = book.buy[0]
    if order[0] > 1000:
        return order
    return -1


def adr_strat(book):
    pass

# ~~~~~============== MAIN LOOP ==============~~~~~

def main(exchange):
    write_to_exchange(exchange, {"type": "hello", "team": TEAM_NAME.upper()})
    hello_from_exchange = read_from_exchange(exchange)

    if hello_from_exchange["type"] != "hello":
        # error!
        print("error")
        print(hello_from_exchange)

    # initial positions
    for pos in hello_from_exchange["symbols"]:
        positions[pos["symbol"]] = pos["position"]

    print("CUR POSITIONS")
    print(positions)

    while True:
        message = read_from_exchange(exchange)
        msg_type = message["type"]

        if msg_type == "error":
            print("ERROR:")
            print(message["error"])
            break

        if msg_type == "book":
            books[message["symbol"]].update_book(message["buy"], message["sell"])
            on_book_update(exchange, message["symbol"], books[message["symbol"]])

        if msg_type == "trade":
            books[message["symbol"]].add_trade((message["price"], message["size"]))

        if msg_type == "out":
            print(message)
            cur_orders.remove(int(message["order_id"]))
            if message["order_id"] in pre_order_details.keys():
                details = pre_order_details[message["order_id"]]
                # remove from the book
                books[details["symbol"]].remove_resting_order(message["order_id"])
                pre_order_details.pop(message["order_id"])


        if msg_type == "ack":
            print(message)
            cur_orders.add(int(message["order_id"]))
            if message["order_id"] in pre_order_details.keys():
                details = pre_order_details[message["order_id"]]
                # add to the book
                books[details["symbol"]].add_resting_order(
                    message["order_id"], details["dir"], details["price"], details["size"])

        if msg_type == "reject":
            print("ERROR: Order rejected")
            print(message)

        if msg_type == "fill":
            print(message)
            if message["order_id"] in books[message["symbol"]].our_resting_orders.keys():
                books[message["symbol"]].update_resting_order(message["order_id"], message["size"])

            on_our_order_traded(exchange,
                                message["order_id"], message["symbol"], message["dir"], message["price"], message["size"])

        if msg_type == "close":
            print("The round has ended")
            break

        if len(trade_queue) > 0:
            next_trade = trade_queue.popleft()
            print(next_trade)
            # TODO: check if trade is still valid? IDK hows
            write_to_exchange(exchange, next_trade)

if __name__ == "__main__":
    exchange = connect()
    try:
        main(exchange)
    except KeyboardInterrupt:
        pull_all_orders(exchange)
        sys.exit()

