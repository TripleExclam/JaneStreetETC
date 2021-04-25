from dataclasses import dataclass
from typing import List, Tuple, Dict


@dataclass
class Book:
    symbol: str
    buy: List[List[int]] # [[price, volume]]
    sell: List[List[int]] # [[price, volume]]
    last_trades: List[Tuple[int, int]] # [(price, volume)]
    our_resting_orders: Dict[int, List] # order_id -> [direction, price, volume]

    def update_book(self, buy: List[List[int]], sell: List[List[int]]):
        self.buy = buy
        self.sell = sell

    def add_trade(self, price: Tuple[int, int]):
        self.last_trades.append(price)

    def add_resting_order(self, order_id, direction, price, volume):
        self.our_resting_orders[order_id] = [direction, price, volume]

    def remove_resting_order(self, order_id: int):
        self.our_resting_orders.pop(order_id)

    def update_resting_order(self, order_id, size):
        self.our_resting_orders[order_id][2] -= size

    def update_resting_order(self, order_id, size):
        self.our_resting_orders[order_id][2] -= size
