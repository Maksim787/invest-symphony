import numpy as np
from dataclasses import dataclass

from research.library.load import load_data
from research.library.markowitz import get_markowitz_w

RISK_VALUES = [
    {'value': 'high', 'label': 'Готов на высокий риск для получения высокой доходности'},
    {'value': 'medium', 'label': 'Готов на средний риск для получения средней доходности'},
    {'value': 'low', 'label': 'Не готов терпеть риски, согласен на скромную доходность'}
]

df = None


def update_df():
    global df
    df = load_data(verbose=False)


@dataclass
class Stock:
    MINIMUM_CAPITAL_IN_STOCK = 300

    name: str
    n_shares: int
    price: float

    shares_price: float = None
    ratio: float = None

    def __post_init__(self):
        self.shares_price = self.n_shares * self.price

    def format_str(self):
        self.price = f'{self.price} руб.'
        self.shares_price = f'{self.shares_price:.2f} руб.'
        self.ratio = f'{self.ratio:.1%}'

    @classmethod
    def _get_lot_size(cls, price: float):
        for lot_size in [1, 5, 10, 100, 1000, 10000, 10000]:
            if lot_size * price >= cls.MINIMUM_CAPITAL_IN_STOCK:
                return lot_size
        return 10000


@dataclass
class Portfolio:
    stocks: list[Stock]

    def __post_init__(self):
        portfolio_value = sum([stock.shares_price for stock in self.stocks])
        for stock in self.stocks:
            stock.ratio = stock.shares_price / portfolio_value
            stock.format_str()


def create_stock_only_portfolio(capital: float, risk: str, max_instruments: int | None):
    assert risk in ['high', 'medium', 'low']

    mu_by_risk = {
        'high': 30.0,
        'medium': 20.0,
        'low': 10.0
    }

    w = get_markowitz_w(df, mu_year_pct=mu_by_risk[risk])
    prices = df.iloc[-1]
    stocks = []

    # Drop zero shares
    w = w / w.sum()

    stocks = []
    names = list(w.index)
    weights = w.tolist()
    prices = prices.tolist()

    while True:
        n_taken = 0
        stocks = []
        for name, w, price in zip(names, weights, prices):
            lot_size = Stock._get_lot_size(price)
            n_shares = int(capital * w / price) // lot_size * lot_size
            if n_shares > 0:
                stocks.append(Stock(name=name, n_shares=n_shares, price=price))
                n_taken += 1
        if n_taken == len(names) and len(names) <= max_instruments:
            break
        remove_ind = np.argmin(weights)
        names.pop(remove_ind)
        weights.pop(remove_ind)
        prices.pop(remove_ind)
        weights = (np.array(weights) / np.sum(weights)).tolist()

    portfolio = Portfolio(stocks=stocks)
    return portfolio
