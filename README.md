# invest-symphony

## Setup

1. Put a read-only Tinkoff API token into `keys.yaml`
Example:

```
token: t.a-lot-of-letters
```
2. Install dependencies: `pip install -r requirements.txt`

## Scripts

Launch IMOEX portfolio construction (capital_rub is the capital in RUB):

```
python scripts/get_shares.py --capital_rub 100000
```

It does the following:
1. Load shares from https://smart-lab.ru/q/index_stocks/IMOEX/ and map them to tinkoff tickers (mapping is manually hard-coded, so it should be changed when index constituents change)
2. Substitute shares with preference shares where possible
3. Take shares while their weight in portfolio is less than weight in IMOEX
4. Allocate the rest of the capital greedily to minimize the difference between the ratio in portfolio and the ratio in index.
5. The results will be in `results/` folder in csv format:
a. ticker
b. tinkoff_name
c. lot_size — lot size (number of shares in 1 lot)
d. price — price of 1 share (not 1 lot)
e. real_price — price of 1 lot (lot_size * price)
f. n_lots_to_buy — number of lots to buy
d. imoex_weight,% — weight in IMOEX
e. real_weight,% — weight in portfolio (the closer to imoex_weight,%, the better)
f. real_value,RUB — value in RUB in portfolio (price * n_lots_to_buy * lot_size)

## Download data

To initially download all data run script:

```bash
python download_all.py
```

To download particular data use functions from `download_data`:

1. `download_shares_close_prices` - download close prices for all shares in the TQBR section of MOEX
2. `download_bonds_info` - download bonds info from Tinkoff API (aci, nominal, coupons, sector, ...)
3. `download_shares_info` - download shares info from Tinkoff API (sector, ...)

## Research

`research/library` - functions for constructing portfolio

```python
from research.library.load import load_data
from research.library.markowitz

df_close_prices = load_data()  # load and filter close prices for shares
w = get_markowitz_w(df_close_prices, mu_year_pct=0.0)  # construct portfolio
```

## Website

Run website:

Locally:

```bash
python main.py --debug
```

On server:

```bash
python main.py --download_every_day --download_on_start
```

Flags (you can ignore them if the data is already downloaded):

- `download_every_day`: to run job to download data every day
- `download_every`: to run job to download data on start

### website/main.py

`get_job_to_run_once_a_day()` - create job to run once a day. This job downloads financial data and then loads it into RAM using `load_data_to_ram()`

### website/views.py

`home_get()` - render form

`home_post()` - retrieve form answers and provide with the portfolio

### website/{templates, static}/

- `templates` - html code
- `static` - css code (styles)

### website/library/portfolio.py

`create_portfolio()` - use `research/library` to construct portfolio from answers

`load_data_to_ram()` - load data to RAM (for higher efficiency)
