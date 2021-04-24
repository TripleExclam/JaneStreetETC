#!/usr/bin/python
# ~~~~~==============   HOW TO RUN   ==============~~~~~
# 1) Configure things in CONFIGURATION section
# 2) Change permissions: chmod +x bot.py
# 3) Run in loop: while true; do ./bot.py; sleep 1; done

from __future__ import print_function

import sys
import socket
import json
from parser import *

# ~~~~~============== CONFIGURATION  ==============~~~~~
# replace REPLACEME with your team name!
team_name = "BUYHIGHSELLLOW"
# This variable dictates whether or not the bot is connecting to the prod
# or test exchange. Be careful with this switch!
test_mode = False

# This setting changes which test exchange is connected to.
# 0 is prod-like
# 1 is slower
# 2 is empty
test_exchange_index = 0
prod_exchange_hostname = "production"

port = 25000 + (test_exchange_index if test_mode else 0)
exchange_hostname = "test-exch-" + team_name if test_mode else prod_exchange_hostname

# ~~~~~============== NETWORKING CODE ==============~~~~~
def connect():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((exchange_hostname, port))
    return s.makefile("rw", 1)


def write_to_exchange(exchange, obj):
    json.dump(obj, exchange)
    exchange.write("\n")


def read_from_exchange(exchange):
    return json.loads(exchange.readline())


# ~~~~~============== MAIN LOOP ==============~~~~~

def buy_bonds(book):
    for order in book["BOND"][-1]["sell"]:
        if order[0] < 1000:
            return order
    return -1

def sell_bonds(book):
    for order in book["BOND"][-1]["buy"]:
        if order[0] > 1000:
            return order
    return -1

def main():
    exchange = connect()
    write_to_exchange(exchange, {"type": "hello", "team": team_name.upper()})
    hello_from_exchange = read_from_exchange(exchange)
    # A common mistake people make is to call write_to_exchange() > 1
    # time for every read_from_exchange() response.
    # Since many write messages generate marketdata, this will cause an
    # exponential explosion in pending messages. Please, don't do that!
    print("The exchange replied:", hello_from_exchange, file=sys.stderr)
    counter = 0
    check_bonds = -1
    sell = -1
    books = {"BOND" : []}
    while True:
        counter += 1
        message = read_from_exchange(exchange)
        
        if message["type"] == "book":
            if message["symbol"] == "BOND":
                books["BOND"].append(message)
                check_bonds = buy_bonds(books)
                sell = sell_bonds(books)

        if check_bonds != -1:
            buy_order = {"type": "add", "order_id": counter * 5, "symbol": "BOND", "dir": "BUY", "price": check_bonds[0], "size": check_bonds[1]}
            write_to_exchange(exchange, buy_order)
            check_bonds = -1
            print("BOUGHT")

        if sell != -1:
            sell_order = {"type": "add", "order_id": counter * 3, "symbol": "BOND", "dir": "SELL", "price": sell[0], "size": sell[1]}
            write_to_exchange(exchange, sell_order) 
            sell = -1
            print("SOLD")

        if message["type"] == "close":
            print("The round has ended")

if __name__ == "__main__":
    main()
