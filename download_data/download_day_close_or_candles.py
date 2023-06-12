import asyncio
import aiohttp
import aiomoex
import pandas as pd
import shutil
from enum import Enum, auto
from pathlib import Path
from dataclasses import dataclass

from .download_tickers import download_tickers


class TimeSeriesType(Enum):
    CLOSE = auto()
    CANDLES = auto()


@dataclass
class TimeSeriesConfig:
    type: TimeSeriesType
    # number of minutes: 1, 10, 60
    # number of hours: 24
    # number of days: 7, 31
    # number of months: 4
    candle_interval: int | None = None

    def __post_init__(self):
        assert self.type == TimeSeriesType.CLOSE or self.candle_interval is not None


async def download_by_ticker_task(
        session: aiohttp.ClientSession,
        time_series_folder: Path,
        time_series_config: TimeSeriesConfig,
        security: str
) -> pd.DataFrame:
    file_path = time_series_folder / f'{security}.csv'
    print(f'Download: {security}')
    if time_series_config.type == TimeSeriesType.CLOSE:
        data = await aiomoex.get_board_history(session, security)
    else:
        data = await aiomoex.get_board_candles(session, security, interval=time_series_config.candle_interval)
    day_close_by_security = pd.DataFrame(data)
    if len(day_close_by_security) == 0:
        print(f'Warning: {security} has zero observations, do not save it')
    else:
        day_close_by_security.to_csv(file_path, index=False)
    print(f'Success: {security}: {len(day_close_by_security)} observations')
    return day_close_by_security


async def download_day_close_or_candles(time_series_folder: Path, time_series_config: TimeSeriesConfig, tickers_folder: Path = Path('data/tickers/'), force_download: bool = True):
    if time_series_folder.exists() and not force_download:
        print(f'Use cache: {time_series_folder}')
        return
    if time_series_folder.exists():
        shutil.rmtree(time_series_folder)
    time_series_folder.mkdir(parents=True, exist_ok=True)
    async with aiohttp.ClientSession() as session:
        all_securities_df = await download_tickers(tickers_folder, force_download=force_download)
        securities = list(all_securities_df['SECID'])
        print(f'Found tickers: {len(securities)}: {securities}')
        await asyncio.gather(
            *[download_by_ticker_task(session, time_series_folder, time_series_config, security) for security in securities]
        )


if __name__ == '__main__':
    asyncio.run(download_day_close_or_candles(
        time_series_folder=Path('data/day_close/'),
        time_series_config=TimeSeriesConfig(TimeSeriesType.CLOSE)
    ))

    asyncio.run(download_day_close_or_candles(
        time_series_folder=Path('data/day_candles/'),
        time_series_config=TimeSeriesConfig(TimeSeriesType.CANDLES, candle_interval=24)
    ))
