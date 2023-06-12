import numpy as np
import pandas as pd


def is_sorted(values: np.ndarray | pd.Series) -> bool:
    return np.all(np.sort(values) == values)
