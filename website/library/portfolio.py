if __name__ == '__main__':
    # Add current working directory to Python path to test this file
    import sys
    import os
    sys.path.append(os.getcwd())

import numpy as np
import pandas as pd
import datetime
import typing as tp
from dataclasses import dataclass

import tinkoff.invest as inv
from research import load_data, ClosePricesStatistics
from research.library.markowitz import get_markowitz_w
from download_data import download_shares_info, download_bonds_info, quotation_to_float


###################################################################################
# Form risk values
###################################################################################

RISK_VALUES = [
    {'value': 'high', 'label': 'Готов на высокий риск для получения высокой доходности'},
    {'value': 'medium', 'label': 'Готов на средний риск для получения средней доходности'},
    {'value': 'low', 'label': 'Не готов терпеть риски, согласен на скромную доходность'}
]


###################################################################################
# tinkoff API sectors
###################################################################################

DEFAULT_SECTOR = 'другое'

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
    'other': DEFAULT_SECTOR
}


###################################################################################
# Portfolio containers
###################################################################################


class BondInfo:
    """
    Container to store bond information
    """
    RATE_LOWER_BOUND_PCT = -10
    RATE_UPPER_BOUND_PCT = 10000
    RATE_EPS_PCT = 0.001  # 0.001%

    TAX_RATE_PCT = 13

    def __init__(self, bond: inv.Bond, coupons: list[inv.Coupon], last_price: inv.LastPrice) -> None:
        # Extract (maturity date) and (acquired coupon interest)
        self.maturity_date = bond.maturity_date.date()
        self.aci_value = quotation_to_float(bond.aci_value)

        # Filter only futures coupons
        coupons = list(filter(lambda coupon: coupon.coupon_date >= datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc), coupons))
        # Extract coupon pays and dates from coupons
        self.coupon_pays = [quotation_to_float(coupon.pay_one_bond) for coupon in coupons]
        self.coupon_dates = [coupon.coupon_date.date() for coupon in coupons]

        # Extract nominal and price
        self.nominal = quotation_to_float(bond.nominal)
        self.price = quotation_to_float(last_price.price) * self.nominal / 100

        # Calculate ytm (real ytm is ytm with taxes)
        self.ytm_pct = self._get_ytm_pct(self._raw_present_value, self.price)
        self.real_ytm_pct = self._get_ytm_pct(self._real_present_value, self.price)

        # String for formatting rate
        self.real_ytm_pct_str = f'{self.real_ytm_pct:.1f}%'

        # Information about company's name, ticker and sector
        self.name = bond.name
        self.ticker = bond.ticker
        self.sector = bond.sector

    @staticmethod
    def _year_diff(date: datetime.date) -> float:
        """
        Return distance between date and now in years
        """
        days = (date - datetime.datetime.utcnow().date()).days
        assert days >= 0, days
        return days / 365

    @classmethod
    def _get_ytm_pct(cls, present_value_func: tp.Callable[[float], float], price: float):
        """
        Return yield to maturity
        Perform binary search to find [present_value(rate_pct) == cls.price]
        """
        # Start conditions
        lower = cls.RATE_LOWER_BOUND_PCT
        upper = cls.RATE_UPPER_BOUND_PCT

        # Binary search
        while upper - lower >= cls.RATE_EPS_PCT:
            middle = (lower + upper) / 2
            if present_value_func(middle) > float(price):
                lower = middle
            else:
                upper = middle

        # Return middle value
        return (lower + upper) / 2

    def _raw_present_value(self, rate_pct: float) -> float:
        """
        D(nominal) - aci + D(coupons)
        """
        value = self._discount(self.nominal, self.maturity_date, rate_pct) - self.aci_value
        for coupon_day, coupon_pay in zip(self.coupon_dates, self.coupon_pays):
            value += self._discount(coupon_pay, coupon_day, rate_pct)
        return value

    def _real_present_value(self, rate_pct: float) -> float:
        """
        D(nominal) - aci + (1 - tax) * D(coupons) - tax * D(max(0, nominal - price - aci))
        """
        tax_rate = self.TAX_RATE_PCT / 100
        value = -self.aci_value
        for coupon_day, coupon_pay in zip(self.coupon_dates, self.coupon_pays):
            value += (1 - tax_rate) * self._discount(coupon_pay, coupon_day, rate_pct)
        value += self._discount(self.nominal, self.maturity_date, rate_pct) - self._discount(tax_rate * max(0.0, float(self.nominal - self.price - self.aci_value)), self.maturity_date, rate_pct)
        return value

    @classmethod
    def _discount(cls, payment: float, date: datetime.date, rate_pct: float) -> float:
        discount_factor = 1 / (1 + rate_pct / 100)
        return payment * discount_factor ** cls._year_diff(date)


@dataclass
class Bond:
    number: int
    info: BondInfo

    price: float = None
    invested_capital: float = None
    sector: str = None
    ratio: float = None  # is filled inside the Portfolio class

    price_str: str = None
    ratio_str: str = None

    def __post_init__(self):
        self.price = self.info.price + self.info.aci_value
        self.invested_capital = self.price * self.number
        self.sector = SECTOR_TRANSLATION.get(self.info.sector)
        if self.sector is None:
            print(self.info.sector)
            self.sector = 'другое'

    def fill_str_fields(self):
        self.price_str = f'{self.price:.2f} руб.'
        self.ratio_str = f'{self.ratio:.1%}'


@dataclass
class Stock:
    # init params
    number: int
    info: inv.Share

    # post init params
    price: float = None
    invested_capital: float = None
    sector: str = None
    ratio: float = None  # is filled inside the Portfolio class

    # format params
    price_str: str = None
    invested_capital_str: str = None
    ratio_str: str = None

    def __post_init__(self):
        assert self.number % self.info.lot == 0
        self.price = DataRAM.stat.last_prices[self.info.ticker]
        self.invested_capital = self.number * self.price
        self.sector = SECTOR_TRANSLATION.get(self.info.sector)
        if self.sector is None:
            print(f'ERROR: unknown sector: {self.info.sector}')
            self.sector = DEFAULT_SECTOR

    def fill_str_fields(self):
        """
        Fill fields for displaying on website
        """
        self.price_str = f'{self.price} руб.'
        self.invested_capital_str = f'{self.invested_capital:.2f} руб.'
        self.ratio_str = f'{self.ratio:.1%}'


@dataclass
class Portfolio:
    total_capital: float
    stocks: list[Stock]
    bonds: list[Bond]

    # post init params
    money: float = None

    # format params
    stocks_ratio_str: str = None
    bonds_ratio_str: str = None

    def __post_init__(self):
        # Calculate total stocks, bonds and portfolio value
        stocks_value = sum([stock.invested_capital for stock in self.stocks])
        bonds_value = sum([bond.invested_capital for bond in self.bonds])
        portfolio_value = stocks_value + bonds_value

        # Calculate the amount of remaining money
        self.money = portfolio_value - self.total_capital

        # Format stocks and bonds ratios
        self.stocks_ratio_str = f'{stocks_value / self.total_capital:.1%}'
        self.bonds_ratio_str = f'{bonds_value / self.total_capital:.1%}'

        # Format stocks and bonds ratios
        for stock in self.stocks:
            stock.ratio = stock.invested_capital / stocks_value
            stock.fill_str_fields()
        for bond in self.bonds:
            bond.ratio = bond.invested_capital / bonds_value
            bond.fill_str_fields()


###################################################################################
# Data container for storing it in RAM
###################################################################################

class DataRAM:
    stat: ClosePricesStatistics = None  # shares statistics to do markowitz optimization
    share_by_ticker: dict[str, inv.Share] = None  # shares info
    bonds: list[BondInfo] = None  # bonds info sorted by real_ytm


async def load_data_to_ram():
    # Load shares info
    shares = await download_shares_info(force_update=False)
    DataRAM.share_by_ticker = {share.ticker: share for share in shares}

    # Load close prices
    DataRAM.stat = load_data(verbose=False, tickers_subset=list(DataRAM.share_by_ticker.keys()))

    # Load bonds info
    bonds, bonds_coupons, bonds_last_prices = await download_bonds_info(force_update=False)
    DataRAM.bonds = [BondInfo(bond, coupons, last_price) for bond, coupons, last_price in zip(bonds, bonds_coupons, bonds_last_prices) if bond.maturity_date >= datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)]
    DataRAM.bonds.sort(key=lambda bond: bond.real_ytm_pct, reverse=True)


###################################################################################
# Portfolio construction
###################################################################################

def _create_stocks_portfolio(total_capital: float, w: pd.Series, max_stocks: int | float) -> list[Stock]:
    """
    Create stocks portfolio from results of markowitz optimization
    Include top max_stocks into portfolio
    Important: total_capital is capital in both stocks and bonds (remove w['bond'] weight to obtain stocks capital)
    """
    assert w.index[0] == 'bond'

    w = w.iloc[1:].values
    w_sum = w.sum()
    prices = DataRAM.stat.last_prices.values
    tickers = np.array(DataRAM.stat.tickers)
    lot_size = pd.Series([DataRAM.share_by_ticker[ticker].lot for ticker in tickers], index=tickers)

    # Remove stocks from (w, prices, lot_size) until all stocks are taken into portfolio
    while True:
        # Calculate number of lots to buy
        lots = total_capital * w / prices / lot_size
        # Floor number of lots
        numbers = np.floor(lots) * lot_size
        # Check that all stocks are taken
        n_taken = (numbers > 0).sum()
        if n_taken == len(numbers) and len(w) <= max_stocks:
            break
        # Drop stock with the minimum number of lots
        drop_ind = np.argmin(lots)
        w = np.delete(w, drop_ind)
        prices = np.delete(prices, drop_ind)
        tickers = np.delete(tickers, drop_ind)
        lot_size = np.delete(lot_size, drop_ind)
        # Normalize weights
        w = w / w.sum() * w_sum

    # Construct Stocks
    stocks = [Stock(number=int(number), info=DataRAM.share_by_ticker[ticker]) for number, ticker in zip(numbers, tickers)]
    # Sort by sector
    return sorted(stocks, key=lambda stock: stock.sector)


def _create_bonds_portfolio(capital_in_bonds: float, max_bonds: int | float, lower_rate_pct: float, upper_rate_pct: float) -> list[Bond]:
    """
    Create bonds portfolio from bonds with real YTM in [lower_rate_pct, upper_rate_pct]
    """
    # Filter bonds with YTM in [lower_rate_pct, upper_rate_pct]
    bonds = [bond for bond in DataRAM.bonds if lower_rate_pct <= bond.real_ytm_pct <= upper_rate_pct]
    if max_bonds < len(bonds):
        bonds = bonds[:max_bonds]

    # How many bonds of each type to take
    n_bonds_taken = [0] * len(bonds)
    added_bond = True  # flag whether new bond was added to portfolio
    while added_bond:
        added_bond = False
        for i, bond in enumerate(bonds):
            dirty_price = bond.price + bond.aci_value
            if capital_in_bonds >= dirty_price:
                n_bonds_taken[i] += 1
                capital_in_bonds -= dirty_price
                added_bond = True

    bonds = [Bond(number=number, info=bond) for number, bond in zip(n_bonds_taken, bonds) if number > 0]
    bonds.sort(key=lambda bond: bond.sector)
    return bonds


def create_portfolio(total_capital: float, risk: str, max_instruments: int | None):
    # Check parameters
    assert risk in ['high', 'medium', 'low'], 'Incorrect risk value'
    if max_instruments is None:
        max_stocks = float('+inf')
        max_bonds = float('+inf')
    else:
        max_stocks = max_instruments // 2
        max_bonds = max_instruments - max_stocks

    # markowitz optimization parameters
    MU_PCT_BY_RISK = {
        'high': 30.0,
        'medium': 15.0,
        'low': 7.5
    }
    BOND_RATE_BOUNDS_BY_RISK = {
        'high': [11, 15],
        'medium': [9, 11],
        'low': [8, 9]
    }
    BOND_MEAN_RATE_BY_RISK = {
        'high': 13,
        'medium': 10,
        'low': 8.5
    }
    BOND_STD_BY_RISK = {
        'high': 2.0,
        'medium': 1.0,
        'low': 0.5
    }
    BOND_SHARE_CORR = 0.1
    w = get_markowitz_w(DataRAM.stat, bond_year_return_pct=BOND_MEAN_RATE_BY_RISK[risk], bond_year_return_std_pct=BOND_STD_BY_RISK[risk], bond_share_corr=BOND_SHARE_CORR, mu_year_pct=MU_PCT_BY_RISK[risk])

    # Create stocks portfolio from weights
    stocks = _create_stocks_portfolio(total_capital, w, max_stocks)

    # Create bonds portfolio
    capital_in_bonds = total_capital - sum([stock.invested_capital for stock in stocks])
    lower_rate, upper_rate = BOND_RATE_BOUNDS_BY_RISK[risk]
    bonds = _create_bonds_portfolio(capital_in_bonds, max_bonds, lower_rate, upper_rate)

    portfolio = Portfolio(total_capital=total_capital, stocks=stocks, bonds=bonds)
    return portfolio


def _test_portfolio():
    """
    Function to test portfolio construction
    """

    # Load data to RAM
    import asyncio
    asyncio.run(load_data_to_ram())

    CAPITAL = 5e6
    RISK_VALUE = 'medium'
    portfolio = create_portfolio(total_capital=CAPITAL, risk=RISK_VALUE, max_instruments=5)
    print(portfolio)


if __name__ == '__main__':
    _test_portfolio()
