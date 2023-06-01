import asyncio
import aiohttp
import aiomoex
import shutil
import pandas as pd

from pathlib import Path


async def download_tickers(tickers_folder: Path = Path('data/tickers/'), force_download: bool = True) -> pd.DataFrame:
    file_path = tickers_folder / f'tickers.csv'
    if tickers_folder.exists() and not force_download:
        print(f'Use cache: tickers')
        return pd.read_csv(file_path)
    if tickers_folder.exists():
        shutil.rmtree(tickers_folder)
    tickers_folder.mkdir(parents=True, exist_ok=True)
    print('Download: tickers')
    async with aiohttp.ClientSession() as session:
        data = await aiomoex.get_board_securities(session)
        df = pd.DataFrame(data)
        df.to_csv(file_path, index=False)
    print('Success: tickers')
    return df


if __name__ == '__main__':
    asyncio.run(download_tickers())
