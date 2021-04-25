class VPrice:
    def __init__(self, lookback=5, margin=0.01):
        self.LOOKBACK = lookback
        self.MARGIN = margin
        self.history = []
        self.price = -1

    def addOrders(self, orders):
        if len(orders) >= self.LOOKBACK:
            self.history = orders[-self.LOOKBACK:]
        else:
            self.history = self.history[-(self.LOOKBACK - len(orders)):] + orders
        self.price = self.getPrice(self.history)

    def getPrice(self, orders):
        if len(orders) == 0:
            return -1
        return sum([order[0] * order[1] for order in orders]) \
               / sum([order[1] for order in orders])
    
    def getMargin(self, signal):
        return self.price * (1 - self.MARGIN) if signal == "BUY" else self.price * (1 + self.MARGIN)
    
    def buySignal(self, order):
        if len(order) == 0 or self.price == -1:
            return -1
        order = order[0]
        fair = self.price
        if order[0] < fair * (1 - self.MARGIN):
            return order
        return -1

    def sellSignal(self, order):
        if len(order) == 0 or self.price == -1:
            return -1
        order = order[0]
        fair = self.price
        if order[0] > fair * (1 + self.MARGIN):
            return order
        return -1

