#!/usr/bin/python
# ~~~~~==============   HOW TO RUN   ==============~~~~~
# 1) Configure things in CONFIGURATION section
# 2) Change permissions: chmod +x bot.py
# 3) Run in loop: while true; do ./bot.py; sleep 1; done

from __future__ import print_function

import time
import sys
import socket
import json
import VStock
from enum import Enum
from collections import defaultdict, deque

from typing import Dict, Set

from parser import *

# ~~~~~============== CONFIGURATION  ==============~~~~~
# replace REPLACEME with your team name!
from util import keydefaultdict

TEAM_NAME = "BUYHIGHSELLLOW"
# This variable dictates whether or not the bot is connecting to the prod
# or test exchange. Be careful with this switch!
TEST_MODE = True

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
books: Dict[str, Book] = keydefaultdict(lambda sym: Book(sym, [], [], []))
cur_orders: Set[int] = set()
basket = {"BOND": 3, "GS": 2, "MS": 3, "WFC": 2}
counter: int = 1
VPrice = VStock.VPrice(lookback=5, margin=0.01)

trade_queue: deque = deque()
###### LOGIC #######

def cancel_order(exchange, order_id: int):
    write_to_exchange(exchange, {"type": "cancel", "order_id": order_id})

def pull_all_orders(exchange):
    for order_id in cur_orders:
        cancel_order(exchange, order_id)

def place_order(exchange, symbol: str, price: int, size: int):
    global counter
    counter += 1
    direction = "BUY" if size > 0 else "SELL"

    order = {"type": "add", "order_id": counter, "symbol": symbol, "dir": direction,
                "price": price, "size": abs(size)}
    print("PERSONAL ORDER", order)
    trade_queue.append(order)

def on_book_update(exchange, symbol: str, book: Book):
    at_limit = abs(positions[symbol]) >= RISK_LIMITS[symbol]

    if symbol == "BONDA":
        hit_bond_bid = buy_bonds(book)
        if hit_bond_bid != -1:
            place_order(exchange, symbol, hit_bond_bid[0], hit_bond_bid[1])
        lift_bond_offer = sell_bonds(book)
        if lift_bond_offer != -1:
            place_order(exchange, symbol, lift_bond_offer[0], -lift_bond_offer[1])
        
    elif symbol == "VALBZ" or symbol == "VALE":
        VPrice.addOrders(book.sell + book.buy)
        validBuy = VPrice.buySignal(book.sell)
        validSell = VPrice.sellSignal(book.buy)
        if validBuy != -1:
            place_order(exchange, symbol, validBuy[0], validBuy[1])
        if validSell != -1:
            place_order(exchange, symbol, validSell[0], -validSell[1])
    # do trades?

def on_our_order_traded(exchange, order_id: int, symbol: str, dir: str, price: int, size: int):
    multiply = (1 if dir == "BUY" else -1)
    positions[symbol] += (size * multiply)
    pass 

def etf_strat(book):
    # check sell price of ETF
    order = book.sell[0]
    order_price = order[0]

    position = positions["XLF"]
    position_multiple_10 = round(position/10) * 10

    n = 3
    total_buy = 0
    for symbol in basket:
        buy_price = books[symbol].buy[0][0]
        buy_volume = books[symbol].buy[0][1]
        total_buy += buy_price * basket[symbol]

    if order_price - 100 > total_buy:
        pass

def quote(exchange, book):
    symbol = book.symbol
    bid = book.buy[0]
    sell = book.sell[0]
    if symbol == "BOND":
        if bid[0] < 999:
            place_order(exchange, symbol, bid[0]+1, 1)
        if sell[0] > 1001:
            place_order(exchange, symbol, sell[0]-1, -1)

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
    start = time.time()
    write_to_exchange(exchange, {"type": "hello", "team": TEAM_NAME.upper()})
    hello_from_exchange = read_from_exchange(exchange)

    if hello_from_exchange["type"] != "hello":
        # error!
        print("error")
        print(hello_from_exchange)

    # initial positions
    for pos in hello_from_exchange["symbols"]:
        positions[pos["symbol"]] = pos["position"]

    # A common mistake people make is to call write_to_exchange() > 1
    # time for every read_from_exchange() response.
    # Since many write messages generate marketdata, this will cause an
    # exponential explosion in pending messages. Please, don't do that!

    print("The exchange replied:", hello_from_exchange, file=sys.stderr)

    while True:
        if time.time() - start > 30:
            start = time.time()
            print(positions)
        message = read_from_exchange(exchange)
        msg_type = message["type"]

        if msg_type == "error":
            print("ERROR:")
            print(message["error"])
            break

        if msg_type == "book":
            books[message["symbol"]].update_book(message["buy"], message["sell"])
            on_book_update(exchange, message["symbol"], books[message["symbol"]])

        if msg_type == "out":
            cur_orders.remove(int(message["order_id"]))
            pass

        if msg_type == "ack":
            print(message)
            cur_orders.add(int(message["order_id"]))

        if msg_type == "reject":
            print("ERROR: Order rejected")
            print(message)

        if msg_type == "fill":
            print(message)
            on_our_order_traded(exchange,
                                message["order_id"], message["symbol"], message["dir"], message["price"], message["size"])

        if msg_type == "close":
            print("The round has ended")
            break

        if len(trade_queue) > 0:
            next_trade = trade_queue.popleft()
            # TODO: check if trade is still valid
            write_to_exchange(exchange, next_trade)

if __name__ == "__main__":
    exchange = connect()
    try:
        main(exchange)
    except KeyboardInterrupt:
        pull_all_orders(exchange)
        sys.exit()

