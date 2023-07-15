import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import datetime
from pathlib import Path

from .utils import is_sorted
from download_data.moex import MOEX_CLOSE_DIRECTORY

N_TARGET_TICKERS = 31
REMOVE_TICKERS = ['IRAO']
# N_TARGET_STOCKS = 5
# REMOVE_TICKERS = ['HYDR']

MIN_OBSERVATIONS_PER_YEAR = 240
TEST_RATIO = 0.3
TRADING_DAYS_IN_YEAR = 252


def load_data(day_close_folder: Path = MOEX_CLOSE_DIRECTORY, n_target_tickers: int = N_TARGET_TICKERS, remove_tickers: list[str] = REMOVE_TICKERS, min_observations_per_year: int = MIN_OBSERVATIONS_PER_YEAR, verbose: bool = True) -> pd.DataFrame:
    # load data
    if not day_close_folder.exists():
        day_close_folder = Path(f'../') / MOEX_CLOSE_DIRECTORY
    assert day_close_folder.exists()
    tickers_original = sorted([file.removesuffix('.csv') for file in os.listdir(day_close_folder)])
    print(f'Original number of tickers: {len(tickers_original)}')

    dfs_original = {ticker: pd.read_csv(day_close_folder / f'{ticker}.csv', parse_dates=['TRADEDATE']).dropna() for ticker in tickers_original}
    assert len(dfs_original) == len(tickers_original)
    for df in dfs_original.values():
        assert np.all(next(iter(dfs_original.values())).columns == df.columns)
        assert len(df['TRADEDATE']) == len(df['TRADEDATE'].drop_duplicates())
        assert is_sorted(df['TRADEDATE'])
        assert np.all(df['BOARDID'] == 'TQBR')

    # filter tickers
    dfs = _filter_dfs(dfs_original, n_target_tickers, remove_tickers)

    if verbose:
        start_date = max(map(lambda df: df.iloc[0]['TRADEDATE'], dfs.values()))
        finish_date = min(map(lambda df: df.iloc[-1]['TRADEDATE'], dfs.values()))
        print(f'From {start_date.strftime("%Y-%m-%d")} to {finish_date.strftime("%Y-%m-%d")}')
        sns.histplot([df.shape[0] for df in dfs.values()])
        plt.xlabel('n_observations')
        plt.show()

    # merge in one dataframe
    df_price = _merge_dfs(dfs, date_column='TRADEDATE', price_column='CLOSE').dropna()
    assert len(df_price.columns) == len(dfs)
    print(f'DataFrame size after merge: {len(df_price)}')

    if verbose:
        plt.title('Before removing some years')
        _plot_observations_by_year(df_price)

    n_observations_by_years = df_price.index.year.value_counts()
    n_observations_by_years = n_observations_by_years[n_observations_by_years >= min_observations_per_year]
    df_price = df_price[df_price.index.year.isin(n_observations_by_years.index)]

    if verbose:
        plt.title('After removing some years')
        _plot_observations_by_year(df_price)

    print(f'DataFrame size after removing some years: {len(df_price)}')
    print()
    for ind, value in df_price.index.year.value_counts().sort_index().items():
        print(f'{ind} year: {value} observations')
    print()
    return df_price


def _is_earlier(df: pd.DataFrame, date: datetime.date) -> bool:
    return df.iloc[0]['TRADEDATE'] <= pd.to_datetime(date)


def _filter_dfs(dfs: dict[str, pd.DataFrame], n_target_stocks: int, remove_tickers: list[str]) -> dict[str, pd.DataFrame]:
    # search for common starting date for n_target_stocks
    day = datetime.timedelta(days=1)
    left = datetime.date(1990, 1, 1)
    right = datetime.date.today()
    filtered_tickers = list(dfs.keys())
    # (left, right]
    while left + day != right:
        middle = left + (right - left) // 2
        is_good = [_is_earlier(dfs[ticker], middle) for ticker in filtered_tickers]
        if sum(is_good) >= n_target_stocks:
            filtered_tickers = [ticker for i, ticker in enumerate(filtered_tickers) if is_good[i]]
            right = middle
        else:
            left = middle

    # drop remove_tickers
    assert len(filtered_tickers) >= n_target_stocks
    if len(filtered_tickers) > n_target_stocks:
        assert sum([_is_earlier(dfs[ticker], left) for ticker in filtered_tickers]) < n_target_stocks
        assert sum([_is_earlier(dfs[ticker], right) for ticker in filtered_tickers]) >= n_target_stocks
        assert remove_tickers
    print(f'Drop tickers: {[ticker for ticker in filtered_tickers if ticker in remove_tickers]}')
    print(f'Start date = {right.strftime("%Y-%m-%d")}')

    filtered_tickers = [ticker for ticker in filtered_tickers if ticker not in remove_tickers]
    assert len(filtered_tickers) == n_target_stocks - len(remove_tickers)
    filtered_dfs = {ticker: dfs[ticker].copy() for ticker in filtered_tickers}
    tickers = list(filtered_dfs.keys())
    print(f'Filtered number of tickers: {len(filtered_dfs)}')
    print(f'Stocks: {tickers}')
    return filtered_dfs


def _merge_dfs(dfs: dict[str, pd.DataFrame], date_column, price_column: str) -> pd.DataFrame:
    # TODO: do not drop observations where there are NaNs
    result_df = None
    for ticker, df in dfs.items():
        df = df.copy().set_index(date_column)
        if result_df is None:
            result_df = df[[price_column]]
            result_df.columns = [ticker]
        else:
            result_df = result_df.join(df[[price_column]].rename(columns={'CLOSE': ticker}))
    return result_df


def _plot_observations_by_year(df_price):
    n_observations_by_years = df_price.index.year.value_counts().sort_index()
    ax = sns.barplot(y=n_observations_by_years, x=n_observations_by_years.index)
    ax.bar_label(ax.containers[0])
    plt.ylabel('n_observations')
    plt.xlabel('year')
    plt.show()
