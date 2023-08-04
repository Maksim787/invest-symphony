import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import time
from dataclasses import dataclass
from tqdm import tqdm

from download_data.moex import MOEX_CLOSE_DIRECTORY, MOEX_TICKERS_DIRECTORY


###################################################################################
# Config
###################################################################################

TRADING_DAYS_IN_YEAR = 252  # global constant
N_MIN_TRADING_YEARS = 8
# N_MIN_TRADING_YEARS = 9.5 # for debug
MIN_OBSERVATIONS = TRADING_DAYS_IN_YEAR * N_MIN_TRADING_YEARS  # number of observations per ticker

###################################################################################
# Load Data
###################################################################################


@dataclass
class ClosePricesStatistics:
    df_close: pd.DataFrame  # original close prices (with NaNs)
    tickers: list[str] = None  # tickers from df_close

    last_prices: pd.Series = None
    mean_returns: pd.Series = None  # mean returns
    std_returns: pd.Series = None  # returns std
    Sigma_cov: pd.DataFrame = None  # return's covariance matrix
    Sigma_corr: pd.DataFrame = None  # return's correlation matrix

    def __post_init__(self):
        """
        Calculate Sigma and mean_returns
        """
        # Calculate tickers
        self.tickers = list(self.df_close.columns)

        # Calculate last_prices
        self.last_prices = self.df_close.apply(lambda x: x.dropna().iloc[-1])

        # Calculate mean and std returns
        mean_returns = []
        std_returns = []
        for ticker in self.tickers:
            returns = self._normalize_returns(self.df_close[ticker])
            mean_returns.append(returns.mean())
            std_returns.append(returns.std())
        self.mean_returns = pd.Series(mean_returns, index=self.tickers)
        self.std_returns = pd.Series(std_returns, index=self.tickers)

        # Calculate Sigma_cov
        Sigma = pd.DataFrame(columns=self.tickers, index=self.tickers, dtype=float)
        for ticker_1 in (pbar := tqdm(self.tickers)):
            pbar.set_description(ticker_1)
            for ticker_2 in self.tickers:
                if self.tickers.index(ticker_2) <= self.tickers.index(ticker_1):
                    continue
                returns = self._normalize_returns(self.df_close[[ticker_1, ticker_2]])
                cov = returns.cov().loc[ticker_1, ticker_2]
                Sigma.loc[ticker_1, ticker_2] = cov
                Sigma.loc[ticker_2, ticker_1] = cov
        for ticker in self.tickers:
            Sigma.loc[ticker, ticker] = self._normalize_returns(self.df_close[ticker]).var()
        self.Sigma_cov = Sigma

        # Calculate Sigma_corr
        self.Sigma_corr = (1 / self.std_returns.values.reshape(-1, 1)) * Sigma * (1 / self.std_returns.values.reshape(1, -1))

        # Checks for correlation and covariance matrices
        assert np.allclose(np.sqrt(np.diag(self.Sigma_cov)), self.std_returns)
        assert np.allclose(np.diag(self.Sigma_corr), 1)
        assert np.allclose(self.Sigma_corr, self.Sigma_corr.T)
        assert np.allclose(self.Sigma_cov, self.Sigma_cov.T)

        # Remove outliers
        self._remove_outliers()

    def _remove_outliers(self):
        # TODO:
        # sharpe = self.mean_returns / self.std_returns
        # highest_ratio = sharpe.quantile(0.9)
        pass

    @staticmethod
    def _normalize_returns(prices: pd.Series | pd.DataFrame) -> pd.Series | pd.DataFrame:
        """
        Divide return by number of days and drop NaNs
        """
        # Compute returns without NaNs
        returns = prices.dropna().pct_change()

        # Normalize returns and drop first NaNs
        intervals = returns.index.to_series().diff().dt.days
        returns = returns.div(intervals, axis=0).dropna()
        assert len(returns) >= 1

        return returns


def load_data(verbose: bool = False, tickers_subset: list[str] | None = None) -> ClosePricesStatistics:
    """
    Return daily close prices for all assets
    """
    start_time = time.time()

    # Find all tickers presented
    tickers = sorted([file.name.removesuffix('.csv') for file in MOEX_CLOSE_DIRECTORY.iterdir()])
    assert tickers == sorted(pd.read_csv(MOEX_TICKERS_DIRECTORY / 'tickers.csv')['SECID'])
    print(f'Number of tickers in data: {len(tickers)}')
    if tickers_subset is not None:
        tickers = sorted(set(tickers) & set(tickers_subset))
        print(f'Number of tickers after taking subset: {len(tickers)} (subset size is {len(tickers_subset)})')

    # Load df by ticker
    df_by_ticker = {ticker: pd.read_csv(MOEX_CLOSE_DIRECTORY / f'{ticker}.csv', parse_dates=['TRADEDATE']) for ticker in tickers}
    columns = next(iter(df_by_ticker.values())).columns

    for ticker, df in df_by_ticker.items():
        # Checks
        assert df.isna().sum().sum() == df['CLOSE'].isna().sum()  # no NaNs except close prices
        assert np.all(columns == df.columns)  # the same columns
        assert len(df['TRADEDATE']) == len(df['TRADEDATE'].drop_duplicates())  # trade date does not have duplicates
        assert df['TRADEDATE'].is_monotonic_increasing  # trade date is monotonic
        assert np.all(df['BOARDID'] == 'TQBR')  # all tickers are in the TQBR section
        assert np.all((df['VALUE'] == 0) == (df['VOLUME'] == 0))
        # Drop NaNs and days without volume
        df = df.dropna()
        df = df[(df['VOLUME'] != 0)]
        # Set date index
        df = df.set_index('TRADEDATE')
        df.index.names = ['date']
        assert len(df) != 0
        # Update df
        df_by_ticker[ticker] = df

    # Get date range from data
    start_date = min(map(lambda df: df.index[0], df_by_ticker.values()))
    finish_date = max(map(lambda df: df.index[-1], df_by_ticker.values()))
    print(f'Data from {start_date.date()} to {finish_date.date()}')

    # Filter dfs
    df_by_ticker = {ticker: df for ticker, df in df_by_ticker.items() if len(df) >= MIN_OBSERVATIONS}
    print(f'Number of tickers after filtering by minimum number of observations: {len(df_by_ticker)}')

    # Filter
    df_by_ticker = {ticker: df for ticker, df in df_by_ticker.items() if (finish_date - df.index[-1]).days == 0}
    print(f'Number of tickers after filtering by final date: {len(df_by_ticker)}')

    # Plot number of observations for each ticker
    if verbose:
        sns.histplot([len(df) for df in df_by_ticker.values()])
        plt.axvline(MIN_OBSERVATIONS, label=f'Minimum number of observations: {MIN_OBSERVATIONS}', linestyle='--')
        plt.xlabel('Number of observations for ticker')
        plt.legend()
        plt.show()

    # Merge time series for all tickers
    df_prices = pd.concat([df['CLOSE'].rename(ticker) for ticker, df in df_by_ticker.items()], axis=1)
    print(f'df_prices.shape={df_prices.shape}')

    # Print number of observations and tickers per year
    for year, value in df_prices.index.year.value_counts().sort_index().items():
        print(f'{year} year: {value} observations ({df_prices[df_prices.index.year == year].notna().any().sum()}/{len(df_prices.columns)})')

    return_value = ClosePricesStatistics(df_prices)
    print(f'load_data: {time.time() - start_time:.1f} s')
    return return_value
