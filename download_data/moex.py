import asyncio
import aiohttp
import aiomoex
import pandas as pd
import typing as tp
from pathlib import Path

from .utility import limited_gather

###################################################################################
# Config
###################################################################################

MOEX_DATA_DIRECTORY = Path("data/moex")
MOEX_CLOSE_DIRECTORY = MOEX_DATA_DIRECTORY / "close"
MOEX_TICKERS_DIRECTORY = MOEX_DATA_DIRECTORY / "tickers"

MOEX_CLOSE_DIRECTORY.mkdir(exist_ok=True, parents=True)
MOEX_TICKERS_DIRECTORY.mkdir(exist_ok=True)

###################################################################################
# Load from cache
###################################################################################


async def _load_from_cache(folder: Path, filename: str, function: tp.Callable[..., tp.Awaitable], force_update: bool) -> pd.DataFrame:
    """
    Loads function return value from cache
    """
    path = folder / f"{filename}.csv"
    if path.exists() and not force_update:
        print(f"Load {path} from cache")
        return pd.read_csv(path)
    print(f"Create {path}")
    result = await function()
    assert isinstance(result, pd.DataFrame)
    result.to_csv(path, index=False)
    return result

###################################################################################
# Download functions
###################################################################################


def _download_tickers(session: aiohttp.ClientSession) -> tp.Awaitable:
    """
    Download tickers on the TQBR board
    """
    async def function():
        print("Download tickers")
        df = pd.DataFrame(await aiomoex.get_board_securities(session))
        print("Success: tickers")
        return df

    return function


def _download_ticker_close_prices(session: aiohttp.ClientSession, ticker: str) -> tp.Callable:
    async def function() -> pd.DataFrame:
        print(f"Download: {ticker}")
        df = pd.DataFrame(await aiomoex.get_board_history(session, ticker))
        assert len(df) > 0
        print(f"Success: {ticker}: {len(df)} observations")
        return df

    return function


async def download_shares_close_prices(force_update: bool):
    # Remove old data
    if force_update:
        for file in MOEX_CLOSE_DIRECTORY.iterdir():
            file.unlink()
    async with aiohttp.ClientSession() as session:
        # Download tickers
        tickers_df = await _load_from_cache(MOEX_TICKERS_DIRECTORY, 'tickers', _download_tickers(session), force_update=force_update)
        tickers = list(tickers_df["SECID"])
        # Download close prices for each ticker
        print(f"Found tickers: {len(tickers)}: {tickers}")
        tasks = []
        for ticker in tickers:
            tasks.append(_load_from_cache(MOEX_CLOSE_DIRECTORY, ticker, _download_ticker_close_prices(session, ticker), force_update=force_update))
        await limited_gather(*tasks)
    print('Successfully downloaded close prices data')


if __name__ == "__main__":
    asyncio.run(download_shares_close_prices(force_update=True))
