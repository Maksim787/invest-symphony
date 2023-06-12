from dataclasses import dataclass

from research.library.load import load_data
from research.library.markowitz import get_markowitz_w

RISK_VALUES = [
    {'value': 'high', 'label': 'готов на высокий риск для получения высокой доходности'},
    {'value': 'medium', 'label': 'готов на средний риск для получения средней доходности'},
    {'value': 'low', 'label': 'не готов терпеть риски, согласен на скромную доходность'}
]

df = None


@dataclass
class Stock:
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


@dataclass
class Portfolio:
    stocks: list[Stock]

    def __post_init__(self):
        portfolio_value = sum([stock.shares_price for stock in self.stocks])
        for stock in self.stocks:
            stock.ratio = stock.shares_price / portfolio_value
            stock.format_str()


def create_stock_only_portfolio(capital: float, risk: str):
    global df
    assert risk in ['high', 'medium', 'low']

    if df is None:
        df = load_data(verbose=False)

    mu_by_risk = {
        'high': 30.0,
        'medium': 20.0,
        'low': 10.0
    }

    w = get_markowitz_w(df, mu_year_pct=mu_by_risk[risk])
    prices = df.iloc[-1]
    stocks = []

    # Drop zero shares
    MINIMUM_CAPITAL_IN_STOCK = 300
    mask = ((capital * w / prices >= 1.0) & (capital * w >= MINIMUM_CAPITAL_IN_STOCK))
    w = w[mask]
    prices = prices[mask]
    w = w / w.sum()

    for name, w, price in zip(w.index, w, prices):
        n_shares = int(capital * w / price)
        if n_shares > 0:
            stocks.append(Stock(name=name, n_shares=int(capital * w / price), price=price))

    portfolio = Portfolio(stocks=stocks)
    return portfolio
