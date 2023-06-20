import argparse
import asyncio
from pathlib import Path
from website import create_app
from apscheduler.schedulers.background import BackgroundScheduler

from download_data.download_tickers import download_tickers
from download_data.download_day_close_or_candles import download_day_close_or_candles, TimeSeriesConfig, TimeSeriesType
from website.library.stock_only_portfolio import update_df


scheduler = BackgroundScheduler()
app = create_app()


def job_to_run_once_a_day():
    print('Run job')

    # Download data
    Path('data').mkdir(exist_ok=True)
    asyncio.run(download_tickers(force_download=not app.debug))
    asyncio.run(download_day_close_or_candles(
        time_series_folder=Path('data/day_close/'),
        time_series_config=TimeSeriesConfig(TimeSeriesType.CLOSE),
        force_download=not app.debug
    ))

    # Load data to RAM
    update_df()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()
    app.debug = args.debug
    scheduler.add_job(job_to_run_once_a_day, 'interval', days=1)

    scheduler.start()
    job_to_run_once_a_day()
    app.run(debug=args.debug, port=80, host='0.0.0.0')
