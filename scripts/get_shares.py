import sys
sys.path.append('d:/Projects/invest-symphony/')  # noqa

import pandas as pd
import numpy as np
import asyncio
import tinkoff.invest as inv
import requests
import argparse
from pathlib import Path
from functools import partial

from download_data import download_shares_info, download_shares_close_prices
from research import load_data, ClosePricesStatistics

IMOEX_DATA_DIRECTORY = Path("data/imoex")
IMOEX_DATA_DIRECTORY.mkdir(exist_ok=True, parents=True)

RESULTS_DIRECTORY = Path('results/')
RESULTS_DIRECTORY.mkdir(exist_ok=True, parents=True)

IMOEX_FILE = IMOEX_DATA_DIRECTORY / 'imoex.csv'

NAME_TO_TICKER_MAP = {
    'ЛУКОЙЛ': 'LKOH',
    'ГАЗПРОМ ао': 'GAZP',
    'Сбербанк': 'SBER',
    'ГМКНорНик': 'GMKN',
    'Магнит ао': 'MGNT',
    'Татнфт 3ао': 'TATN',
    'Новатэк ао': 'NVTK',
    'Сургнфгз': 'SNGS',
    'Полюс': 'PLZL',
    'Сургнфгз-п': 'SNGSP',
    'Роснефть': 'ROSN',
    'ПИК ао': 'PIKK',
    'Сбербанк-п': 'SBERP',
    'СевСт-ао': 'CHMF',
    'НЛМК ао': 'NLMK',
    'ИнтерРАОао': 'IRAO',
    'АЛРОСА ао': 'ALRS',
    'Yandex clA': 'YNDX',
    'РУСАЛ ао': 'RUAL',
    'ММК': 'MAGN',
    'МТС-ао': 'MTSS',
    'ВТБ ао': 'VTBR',
    'ФосАгро ао': 'PHOR',
    'Ростел -ао': 'RTKM',
    'OZON-адр': 'OZON',
    'Татнфт 3ап': 'TATNP',
    'TCS-гдр': 'TCSG',
    'AGRO-гдр': 'AGRO',
    'Аэрофлот': 'AFLT',
    'Россети': 'FEES',
    'Система ао': 'AFKS',
    'Транснф ап': 'TRNFP',
    'FIVE-гдр': 'FIVE',
    'VK-гдр': 'VKCO',
    'МКБ ао': 'CBOM',
    'ЭН+ГРУП ао': 'ENPG',
    'МосБиржа': 'MOEX',
    'Сегежа': 'SGZH',
    'Polymetal': 'POLY',
    'GLTR-гдр': 'GLTR',
    'РусГидро': 'HYDR',
    'FIXP-гдр': 'FIXP',
}

assert len(NAME_TO_TICKER_MAP) == len(set(NAME_TO_TICKER_MAP.values()))


def download_imoex_components(force_update: bool):
    if not force_update and IMOEX_FILE.exists():
        print('Load IMOEX from cache')
        return pd.read_csv(IMOEX_FILE).set_index('ticker')
    url = 'https://smart-lab.ru/q/index_stocks/IMOEX/'
    response = requests.get(url)
    response.raise_for_status()
    tables = pd.read_html(response.content, encoding='utf-8')
    assert len(tables) == 1
    table = tables[0]
    table = table[['Название', 'Вес', 'Цена,  посл']].rename(columns={'Название': 'imoex_name', 'Вес': 'imoex_weight', 'Цена,  посл': 'imoex_price'})
    table['imoex_weight'] = table['imoex_weight'].str.rstrip('%').astype(float) / 100
    print(f'Names: {table["imoex_name"].tolist()}')
    table['ticker'] = table['imoex_name'].map(NAME_TO_TICKER_MAP)
    assert table.isna().sum().sum() == 0, table.loc[table.isna().any(axis=1)]
    table.to_csv(IMOEX_FILE, index=False)
    return table.set_index('ticker')


def merge_ordinary_and_preference_shares(imoex: pd.DataFrame, share_by_ticker: dict[str, inv.Share]) -> pd.DataFrame:
    imoex = imoex.copy()

    tickers = imoex.index.to_list()
    ordinary_to_preference = {}
    for ticker in tickers:
        preference_ticker = f'{ticker}P'
        if preference_ticker in tickers or preference_ticker in share_by_ticker:
            ordinary_to_preference[ticker] = preference_ticker
    print()
    for ordinary_ticker, preference_ticker in ordinary_to_preference.items():
        if ordinary_ticker in tickers and preference_ticker in tickers:
            ordinary_weight = imoex.loc[ordinary_ticker, 'imoex_weight']
            preference_weight = imoex.loc[preference_ticker, 'imoex_weight']
            imoex = imoex.drop(index=[ordinary_ticker])
        else:
            ordinary_weight = imoex.loc[ordinary_ticker, 'imoex_weight']
            assert preference_ticker not in imoex.index
            preference_weight = 0.0
        imoex.loc[preference_ticker, 'imoex_weight'] = ordinary_weight + preference_weight
        print(f'Ordinary share {ordinary_ticker}:\t{ordinary_weight}')
        print(f'Preference share {preference_ticker}:\t{preference_weight}')
        print(f'Combined share {preference_ticker}: \t{imoex.loc[preference_ticker, "imoex_weight"]}')
        print()
    return imoex


def allocate_portfolio(imoex: pd.DataFrame, capital_rub: float) -> pd.Series:
    imoex = imoex.copy()
    portfolio = (capital_rub * imoex['imoex_weight'] / imoex['real_price']).apply(np.floor).astype(int)

    while True:
        portfolio_value = (portfolio * imoex['real_price']).sum()
        # Current weights
        curr_weights = portfolio * imoex['real_price'] / capital_rub
        # New weights after adding one stock
        new_weights = curr_weights + imoex['real_price'] / capital_rub
        assert np.all(new_weights >= imoex['imoex_weight'])
        # Do not exceed capital
        possible_mask = (portfolio_value + imoex['real_price']) <= capital_rub
        # Take stock with closest weight to IMOEX weight
        best_stock_ticker = (new_weights - imoex['imoex_weight'] + (~possible_mask) * 100).idxmin()
        if not possible_mask[best_stock_ticker]:
            break
        portfolio[best_stock_ticker] += 1
    return portfolio


def format_portfolio(imoex: pd.DataFrame, portfolio: pd.Series, capital_rub: float):
    result = pd.DataFrame(index=imoex.index)
    result['tinkoff_name'] = imoex['tinkoff_name']
    result['lot_size'] = imoex['lot']
    result['price'] = imoex['imoex_price']
    result['real_price'] = result['lot_size'] * result['price']
    result['n_lots_to_buy'] = imoex['lot'] * portfolio
    result['imoex_weight,%'] = (imoex['imoex_weight'] * 100).apply(partial(np.round, decimals=10))

    real_value = result['price'] * result['n_lots_to_buy']
    portfolio_value = real_value.sum()
    print(f'Portfolio value: {portfolio_value} RUB')
    result['real_weight,%'] = real_value / portfolio_value * 100
    result['real_value,RUB'] = real_value
    result.loc['Cash', 'real_value,RUB'] = capital_rub - portfolio_value
    result = result.sort_values(by='real_weight,%')
    result.to_csv(RESULTS_DIRECTORY / 'portfolio_imoex.csv')
    print(result)


def main(force_update: bool):
    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--capital_rub', required=True, type=float)
    args = parser.parse_args()
    capital_rub = args.capital_rub
    assert capital_rub >= 0

    # Load IMOEX
    imoex = download_imoex_components(force_update=force_update)

    # Load shares from tinkoff
    tinkoff_shares = asyncio.run(download_shares_info(force_update=force_update))
    share_by_ticker = {share.ticker: share for share in tinkoff_shares}

    # Load close prices
    asyncio.run(download_shares_close_prices(force_update=force_update))

    # Merge ordinary and preference shares
    imoex = merge_ordinary_and_preference_shares(imoex, share_by_ticker)

    # Load close prices from MOEX
    last_prices_by_ticker = load_data(tickers_subset=imoex.index.tolist(), with_statistics=False).last_prices.to_dict()

    # Check close prices from MOEX
    for ticker, moex_price in last_prices_by_ticker.items():
        imoex_price = imoex.loc[ticker, 'imoex_price']
        if np.isnan(imoex_price):
            print(f'{ticker}: set price = {moex_price}')
            imoex.loc[ticker, 'imoex_price'] = moex_price
        else:
            assert np.isclose(imoex_price, moex_price, rtol=0.05), f'{ticker}. IMOEX price: {imoex_price}. MOEX price: {moex_price}'
    print()

    # Calculate lots and tinkoff name
    imoex['lot'] = [share_by_ticker[ticker].lot for ticker in imoex.index]
    imoex['tinkoff_name'] = [share_by_ticker[ticker].name for ticker in imoex.index]
    imoex['real_price'] = imoex['lot'] * imoex['imoex_price']

    # Allocate portfolio
    portfolio = allocate_portfolio(imoex, capital_rub=capital_rub)
    format_portfolio(imoex, portfolio, capital_rub=capital_rub)

if __name__ == '__main__':
    main(force_update=True)
