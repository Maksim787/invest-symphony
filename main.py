# Uncomment these lines to run on server to install dependencies
# print('Rewrite requirements.txt')
# with open('requirements.txt') as f:
#     lines = f.readlines()
#     lines = [line for line in lines if 'pywin' not in line]
# with open('requirements.txt', 'w') as f:
#     f.writelines(lines)

# import time; time.sleep(5)
# import os; os.system('pip install -r requirements.txt')
# print('Requirements are successfully installed')
# time.sleep(5)
# print('Start main.py')

from apscheduler.schedulers.background import BackgroundScheduler
from website import create_app
import asyncio
import argparse
import typing as tp

from website.library import load_data_to_ram
from download_all import download_all


# Define scheduler and app
scheduler = BackgroundScheduler()
app = create_app()


def get_job_to_run_once_a_day(download_data: bool) -> tp.Callable:
    """
    download_data: whether to download the data
    """
    def job():
        print('Run job')
        # Download data
        if download_data:
            asyncio.run(download_all(force_update=True))
        # Load data to RAM
        asyncio.run(load_data_to_ram())

    return job


def main():
    # Define arguments: debug and download
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--download_every_day', action='store_true', help='Download data every day')
    parser.add_argument('--download_on_start', action='store_true', help='Download data on start')

    # Parse arguments and set debug mode for app
    args = parser.parse_args()
    app.debug = args.debug

    # Run scheduler for every day job
    scheduler.add_job(get_job_to_run_once_a_day(download_data=args.download_every_day), 'interval', days=1)
    scheduler.start()

    # Run job on start
    get_job_to_run_once_a_day(download_data=args.download_on_start)()

    # Run app
    print('Run app')
    app.run(debug=args.debug, port=80, host='0.0.0.0')


if __name__ == '__main__':
    main()
