import numpy as np
import pandas as pd
import datetime
from dataclasses import dataclass

import tinkoff.invest as inv
from research.library.load import load_data, TRADING_DAYS_IN_YEAR
from research.library.markowitz import get_markowitz_w
from download_data.download_tinkoff import get_shares_info, get_bonds_info, quotation_to_float

RISK_VALUES = [
    {'value': 'high', 'label': 'Готов на высокий риск для получения высокой доходности'},
    {'value': 'medium', 'label': 'Готов на средний риск для получения средней доходности'},
    {'value': 'low', 'label': 'Не готов терпеть риски, согласен на скромную доходность'}
]


class BondInfo:
    def __init__(self, bond: inv.Bond, coupons: list[inv.Coupon], last_price: inv.LastPrice) -> None:
        # cash flow
        self.maturity_date = bond.maturity_date
        self.aci_value = quotation_to_float(bond.aci_value)
        coupons = list(filter(lambda coupon: coupon.coupon_date >= datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc), coupons))
        self.coupon_pays = [quotation_to_float(coupon.pay_one_bond) for coupon in coupons]
        self.coupon_dates = [coupon.coupon_date.date() for coupon in coupons]

        # price
        self.nominal = quotation_to_float(bond.nominal)
        self.price = quotation_to_float(last_price.price) * self.nominal / 100

        # rate
        self.rate = self._get_rate(self._raw_present_value)
        self.real_rate = self._get_rate(self._real_present_value)
        self.real_rate_str = f'{self.real_rate:.1f}%'

        # general info
        self.name = bond.name
        self.ticker = bond.ticker
        self.sector = bond.sector

    def _year_diff(self, date: datetime.date) -> float:
        days = (date - datetime.datetime.utcnow().date()).days
        assert days >= 0, days
        return days / 365

    def _get_rate(self, present_value):
        left = -10.0
        right = 1e4
        eps = 1e-3
        while right - left >= eps:
            middle = (left + right) / 2
            if present_value(middle) > float(self.price):
                left = middle
            else:
                right = middle

        return left

    def _raw_present_value(self, r) -> float:
        discount = 1 + r / 100
        value = 0.0
        value += float(self.nominal) / discount ** self._year_diff(self.maturity_date.date())
        value -= float(self.aci_value)
        for coupon_day, coupon_pay in zip(self.coupon_dates, self.coupon_pays):
            value += float(coupon_pay) / discount ** self._year_diff(coupon_day)
        return value

    def _real_present_value(self, r) -> float:
        tax = 0.13
        discount = 1 + r / 100
        value = 0.0
        value -= float(self.aci_value)
        for coupon_day, coupon_pay in zip(self.coupon_dates, self.coupon_pays):
            value += (1 - tax) * float(coupon_pay) / discount ** self._year_diff(coupon_day)
        value += float(self.nominal) / discount ** self._year_diff(self.maturity_date.date())
        value -= tax * max(0.0, float(self.nominal - self.price - self.aci_value)) / discount ** self._year_diff(self.maturity_date.date())
        return value


class Information:
    df: pd.DataFrame = None
    share_by_ticker: dict[str, inv.Share]
    bonds: list[BondInfo]


async def update_information():
    # get daily stock info
    Information.df = load_data(verbose=False).drop(columns=['MTLR', 'MTLRP', 'UTAR'])

    # get shares info
    shares = await get_shares_info(force_update=False)
    Information.share_by_ticker = {share.ticker: share for share in shares}

    # get bonds info
    bonds, bonds_coupons, bonds_last_prices = await get_bonds_info(force_update=False)
    Information.bonds = [BondInfo(bond, coupons, last_price) for bond, coupons, last_price in zip(bonds, bonds_coupons, bonds_last_prices)]
    Information.bonds.sort(key=lambda bond: bond.real_rate, reverse=True)


SECTOR_TRANSLATION = {
    'consumer': 'потребительский',
    'energy': 'энергия',
    'financial': 'финансы',
    'government': 'государственный',
    'health_care': 'здравоохранение',
    'industrials': 'промышленность',
    'materials': 'сырье',
    'real_estate': 'недвижимость',
    'telecom': 'телекоммуникации',
    'utilities': 'коммунальные услуги',
    'it': 'IT',
    'other': 'другое'
}


@dataclass
class Bond:
    number: int
    info: BondInfo

    price: float = None
    total_price: float = None
    sector: str = None
    ratio: float = None

    def __post_init__(self):
        self.price = self.info.price + self.info.aci_value
        self.total_price = self.price * self.number
        self.sector = SECTOR_TRANSLATION.get(self.info.sector)
        if self.sector is None:
            print(self.info.sector)
            self.sector = 'другое'

    def format_str(self):
        self.price = f'{self.price:.2f} руб.'
        self.total_price = f'{self.total_price:.2f} руб.'
        self.ratio = f'{self.ratio:.1%}'


@dataclass
class Stock:
    number: int
    info: inv.Share

    price: float = None
    total_price: float = None
    sector: str = None
    ratio: float = None

    def __post_init__(self):
        self.number = self.number // self.info.lot * self.info.lot
        self.price = Information.df.iloc[-1][self.info.ticker]
        self.total_price = self.number * self.price
        self.sector = SECTOR_TRANSLATION.get(self.info.sector)
        if self.sector is None:
            print(self.info.sector)
            self.sector = 'другое'

    def format_str(self):
        self.price = f'{self.price} руб.'
        self.total_price = f'{self.total_price:.2f} руб.'
        self.ratio = f'{self.ratio:.1%}'


@dataclass
class Portfolio:
    stocks: list[Stock]
    bonds: list[Bond]
    stocks_ratio: float = None
    bonds_ratio: float = None

    def __post_init__(self):
        stocks_value = sum([stock.total_price for stock in self.stocks])
        bonds_value = sum([bond.total_price for bond in self.bonds])
        portfolio_value = stocks_value + bonds_value
        self.stocks_ratio = f'{stocks_value / portfolio_value:.1%}'
        self.bonds_ratio = f'{bonds_value / portfolio_value:.1%}'
        for stock in self.stocks:
            stock.ratio = stock.total_price / stocks_value
            stock.format_str()
        for bond in self.bonds:
            bond.ratio = bond.total_price / bonds_value
            bond.format_str()


def create_portfolio(capital: float, risk: str, max_instruments: int | None):
    assert risk in ['high', 'medium', 'low']
    if max_instruments is None:
        max_stocks = float('+inf')
        max_bonds = float('+inf')
    else:
        max_stocks = max_instruments // 2
        max_bonds = max_instruments - max_stocks

    mu_by_risk = {
        'high': 18.0,
        'medium': 16.0,
        'low': 7.5
    }
    bond_real_rate_by_risk = {
        'high': [11, 15],
        'medium': [9, 11],
        'low': [8, 9]
    }

    df = Information.df.copy()
    # add bonds to daily stock info
    df['bond'] = (1 + 7 / 100) ** (1 / TRADING_DAYS_IN_YEAR) - 1

    w = get_markowitz_w(df, mu_year_pct=mu_by_risk[risk])
    prices = df.iloc[-1]
    stocks = []

    # Drop zero shares
    w = w / w.sum()

    stocks = []
    names = list(w.index)
    weights = w.tolist()
    prices = prices.tolist()

    # Filter stocks by lot size and max_stocks
    while len(names) > 1:
        n_taken = 0
        stocks = []
        for name, w, price in zip(names, weights, prices):
            if name != 'bond':
                stock = Stock(number=int(capital * w / price), info=Information.share_by_ticker[name])
                if stock.number > 0:
                    stocks.append(stock)
                    n_taken += 1
        if n_taken == len(names) - 1 and len(names) - 1 <= max_stocks:
            break
        tmp = np.array(weights)
        tmp[np.array(names) == 'bond'] = 1.0
        remove_ind = np.argmin(tmp)
        names.pop(remove_ind)
        weights.pop(remove_ind)
        prices.pop(remove_ind)
        weights = (np.array(weights) / np.sum(weights)).tolist()
    stocks.sort(key=lambda stock: stock.sector)

    # Get bonds
    assert 'bond' in names

    lower_rate, upper_rate = bond_real_rate_by_risk[risk]
    bonds = [bond for bond in Information.bonds if lower_rate <= bond.real_rate <= upper_rate]
    capital_in_bonds = capital - sum([stock.total_price for stock in stocks])
    n_bonds = min(max_bonds, int(capital_in_bonds / 1000))
    if n_bonds < len(bonds):
        bonds = bonds[:n_bonds]

    n_bonds = [0] * len(bonds)
    while capital_in_bonds > 0:
        for i, bond in enumerate(bonds):
            capital_in_bonds -= bond.price + bond.aci_value
            if capital_in_bonds < 0:
                break
            n_bonds[i] += 1
    bonds = [Bond(n_bonds, info=bond) for n_bonds, bond in zip(n_bonds, bonds) if n_bonds > 0]
    bonds.sort(key=lambda bond: bond.sector)

    portfolio = Portfolio(stocks=stocks, bonds=bonds)
    return portfolio
