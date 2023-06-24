import pandas as pd
import numpy as np
import typing as tp
from enum import Enum, auto
from scipy.optimize import minimize

from .load import TRADING_DAYS_IN_YEAR


def get_markowitz_w(df_price: pd.DataFrame, mu_year_pct: float) -> pd.Series:
    # convert mu to ratio return in 1 day
    mu = (1 + mu_year_pct / 100) ** (1 / TRADING_DAYS_IN_YEAR) - 1

    day_returns = df_price.pct_change().dropna()
    day_distance = pd.to_timedelta((df_price.index[1:] - df_price.index[:-1]).total_seconds(), unit='s')
    day_returns['day_distance'] = day_distance
    days = day_returns['day_distance'].dt.days
    day_returns = day_returns.drop(columns=['day_distance'])
    for ticker in df_price.columns:
        if ticker == 'bond':
            day_returns[ticker] = df_price[ticker][0]
        else:
            day_returns[ticker] /= days

    Sigma = day_returns.cov()
    returns = day_returns.mean(axis=0)

    n_assets = len(returns)

    bounds = [(0, 1)] * n_assets
    assert Sigma.columns[-1] == 'bond'
    w0 = [1 / (2 * (n_assets - 1))] * (n_assets - 1) + [1/2]
    constraints = [{'type': 'eq', 'fun': lambda w:  w.sum() - 1},
                   {'type': 'eq', 'fun': lambda w: w @ returns - mu}]

    def objective(w): return w @ Sigma @ w
    def jac(w): return 2 * Sigma @ w
    result = minimize(objective, w0, bounds=bounds, constraints=constraints, jac=jac)

    try:
        assert result.success
        w = result.x
    except AssertionError:
        print(f'Fail to optimize (no success): {returns=}')
        w = np.array(w0)
    try:
        assert np.isclose(w.sum(), 1)
    except AssertionError:
        print(f'Fail to optimize (sum of weights is not 1): {returns=}; {w=}; {w.sum()=}; {w @ returns=}')
        w = np.array(w0)
    assert np.isclose(w.sum(), 1)
    assert np.all(w >= 0)
    return pd.Series(w, index=df_price.columns)
