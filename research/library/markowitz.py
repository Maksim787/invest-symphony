import pandas as pd
import numpy as np
import cvxpy as cp
import time

from .load import TRADING_DAYS_IN_YEAR, ClosePricesStatistics


def _year_return_pct_to_day_return(year_return: float) -> float:
    """
    Convert year return in % to daily return in ratio
    """
    return year_return / TRADING_DAYS_IN_YEAR / 100


def get_markowitz_w(stat: ClosePricesStatistics, bond_year_return_pct: float, bond_year_return_std_pct: float, bond_share_corr: float, mu_year_pct: float) -> pd.Series:
    """
    Get markowitz portfolio optimization result
    Use assets from stat
    Add bond asset to portfolio
    """
    start_time = time.time()
    assert bond_year_return_pct >= 0

    # Convert mu to ratio return in 1 day
    mu = _year_return_pct_to_day_return(mu_year_pct)
    bond_day_return_mean = _year_return_pct_to_day_return(bond_year_return_pct)
    bond_day_return_std = bond_year_return_std_pct / 100 / np.sqrt(TRADING_DAYS_IN_YEAR)

    # Get required statistics
    n_assets = len(stat.tickers) + 1

    corr_col = (bond_share_corr * bond_day_return_std * stat.std_returns.values).reshape(-1, 1)
    Sigma = np.block([[np.full((1, 1), bond_day_return_std ** 2), corr_col.T], [corr_col, stat.Sigma_cov.values]])
    returns = np.append(bond_day_return_mean, stat.mean_returns.values)

    # Define optimized variable
    w = cp.Variable(n_assets)

    # Define objective (w.T @ Sigma @ w -> min)
    objective = cp.Minimize((1/2) * cp.quad_form(w, Sigma))

    # Define constraints (0 <= w_i <= 1, sum(w_i) = 1, returns @ w = mu)
    constraints = [w >= 0, w <= 1, w @ np.ones(n_assets) == 1, returns @ w == mu]

    # Define problem
    problem = cp.Problem(objective, constraints)

    # Solve problem
    problem.solve()
    assert problem.status == cp.OPTIMAL, f'{problem.status}: {n_assets=}, {bond_year_return_pct=}, {bond_year_return_std_pct=}, {bond_share_corr=}, {mu_year_pct=}'

    # Convert to pd.Series
    solution = pd.Series(w.value, index=['bond'] + stat.tickers)

    # Remove values below 0
    solution[solution < 0] = 0

    # Do sanity checks
    assert np.isclose(solution.sum(), 1)
    assert np.all((0 <= solution) & (solution <= 1))
    assert np.isclose(solution @ returns, mu)

    print(f'Optimization time: {time.time() - start_time:.2f} s. n_assets={n_assets}')

    return solution
