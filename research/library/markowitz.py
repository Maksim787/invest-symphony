import pandas as pd
import numpy as np
import typing as tp
from enum import Enum, auto
from scipy.optimize import minimize

from .load import TRADING_DAYS_IN_YEAR


def get_markowitz_w(df: pd.DataFrame, mu_year_pct: float) -> pd.Series:
    # convert mu to ratio return in 1 day
    mu = mu_year_pct / 100 / TRADING_DAYS_IN_YEAR

    returns = df.pct_change().dropna()
    Sigma = returns.cov()
    returns = returns.mean(axis=0)

    n_assets = len(returns)

    bounds = [(0, 1)] * n_assets
    w0 = [1 / n_assets] * n_assets
    constraints = [{'type': 'eq', 'fun': lambda w:  w.sum() - 1},
                   {'type': 'eq', 'fun': lambda w: w @ returns - mu}]

    def objective(w): return w.reshape(1, -1) @ Sigma @ w.reshape(-1, 1)
    result = minimize(objective, w0, bounds=bounds, constraints=constraints)

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
    return pd.Series(w, index=df.columns)
