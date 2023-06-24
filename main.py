import argparse
import asyncio
from pathlib import Path
from website import create_app
from apscheduler.schedulers.background import BackgroundScheduler

from download_data.download_tickers import download_tickers
from download_data.download_day_close_or_candles import download_day_close_or_candles, TimeSeriesConfig, TimeSeriesType
from download_data.download_tinkoff import get_shares_info, get_bonds_info
from website.library.portfolio import update_information


scheduler = BackgroundScheduler()
app = create_app()


def job_to_run_once_a_day():
    print('Run job')

    if download:
        Path('data').mkdir(exist_ok=True)
        asyncio.run(download_tickers(force_download=True))
        asyncio.run(download_day_close_or_candles(
            time_series_folder=Path('data/day_close/'),
            time_series_config=TimeSeriesConfig(TimeSeriesType.CLOSE),
            force_download=True
        ))
        asyncio.run(get_shares_info(force_update=True))
        asyncio.run(get_bonds_info(force_update=True))

    # Load data to RAM
    asyncio.run(update_information())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--download', action='store_true', help='Enable debug mode')
    args = parser.parse_args()
    download = args.download
    app.debug = args.debug
    scheduler.add_job(job_to_run_once_a_day, 'interval', days=1)

    scheduler.start()
    job_to_run_once_a_day()
    app.run(debug=args.debug, port=80, host='0.0.0.0')
