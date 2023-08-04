import tinkoff.invest as inv
from tinkoff.invest.async_services import AsyncServices
from tinkoff.invest.exceptions import AioRequestError
import pickle
import typing as tp
import yaml
import datetime
import asyncio
import time
from collections import deque
from pathlib import Path
from dateutil.relativedelta import relativedelta

from .utility import limited_gather

###################################################################################
# Config
###################################################################################

TOKEN_FILE = Path("keys.yaml")
TINKOFF_DATA_DIRECTORY = Path("data/tinkoff")

assert TOKEN_FILE.exists()
TINKOFF_DATA_DIRECTORY.mkdir(exist_ok=True, parents=True)


###################################################################################
# Utility
###################################################################################


def quotation_to_float(quotation: inv.Quotation | inv.MoneyValue) -> float:
    """
    Convert Tinkoff API quantity to float
    """
    return round(quotation.units + quotation.nano / 1e9, 9)


def _get_token(filename: str = TOKEN_FILE) -> str:
    """
    Read token to access Tinkoff API
    """
    with open(filename) as f:
        keys = yaml.safe_load(f)
    return keys["token"]


class RateLimiter:
    PERIOD_SECONDS = 60
    N_REQUESTS_PER_PERIOD = 60

    requests_queue = deque()
    n_waiting_tasks = 0
    last_message_time = time.time() - 5

    @classmethod
    async def wait(cls):
        # Wait on rate limit
        cls.clear_queue()
        while len(cls.requests_queue) == cls.N_REQUESTS_PER_PERIOD:
            last_request_time = cls.requests_queue[0]
            sleep_time = cls.PERIOD_SECONDS - (time.time() - last_request_time)
            if time.time() - cls.last_message_time >= 5:
                cls.last_message_time = time.time()
                print(f'RateLimiter: {cls.n_waiting_tasks} pending tasks. Sleep for this task: {sleep_time} s')
            cls.n_waiting_tasks += 1
            await asyncio.sleep(sleep_time)
            cls.n_waiting_tasks -= 1
            cls.clear_queue()
        # Create new request
        cls.requests_queue.append(time.time())

    @classmethod
    def clear_queue(cls):
        # Clear old requests
        now = time.time()
        while cls.requests_queue and now - cls.requests_queue[0] > cls.PERIOD_SECONDS:
            cls.requests_queue.popleft()

###################################################################################
# Load from cache
###################################################################################


async def _load_from_cache(filename: str, function: tp.Callable[..., tp.Awaitable], force_update: bool):
    """
    Loads function return value from cache
    """
    path = TINKOFF_DATA_DIRECTORY / f"{filename}.pickle"
    if path.exists() and not force_update:
        print(f"Load {filename} from cache")
        with open(path, "rb") as f:
            return pickle.load(f)
    print(f"Create {filename}")
    result = await function()
    with open(path, "wb") as f:
        pickle.dump(result, f)
    return result


###################################################################################
# Requests
###################################################################################

def _download_shares(client: AsyncServices) -> tp.Awaitable:
    async def function() -> inv.SharesResponse:
        return await client.instruments.shares()

    return function


def _download_last_prices(client: AsyncServices, instruments: list[inv.Share | inv.Bond]) -> tp.Awaitable:
    """
    Download recent price for each instrument
    """
    async def function() -> inv.GetLastPricesResponse:
        await RateLimiter.wait()
        return (await client.market_data.get_last_prices(
            figi=[instrument.figi for instrument in instruments]
        )).last_prices

    return function


def _download_bonds_general_info(client: AsyncServices) -> tp.Awaitable:
    """
    Download bonds general information
    Filter only standard bonds
    """
    today = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)

    def is_good_bond(bond: inv.Bond) -> bool:
        if not bond.buy_available_flag or not bond.sell_available_flag or not bond.for_iis_flag or bond.otc_flag or bond.lot != 1 or bond.for_qual_investor_flag:
            return False
        if bond.perpetual_flag or bond.floating_coupon_flag or bond.amortization_flag:
            return False
        if bond.currency != "rub" or bond.nominal.currency != "rub":
            return False
        if quotation_to_float(bond.nominal) != 1000:
            return False
        if bond.maturity_date > today + relativedelta(years=20):
            return False
        return True

    async def function() -> list[inv.Bond]:
        await RateLimiter.wait()
        bonds = (await client.instruments.bonds(instrument_status=inv.InstrumentStatus.INSTRUMENT_STATUS_BASE)).instruments
        bonds = [bond for bond in bonds if is_good_bond(bond)]
        return bonds

    return function


def _download_bonds_coupons(client: AsyncServices, bonds: list[inv.Bond]) -> tp.Awaitable:
    """
    Download coupons for each bond
    """
    async def function() -> list[list[inv.Coupon]]:
        min_time = datetime.datetime(year=1971, month=1, day=1, hour=0, minute=0, second=0)
        max_time = datetime.datetime(year=2200, month=1, day=1, hour=0, minute=0, second=0)

        async def task(figi: str) -> inv.GetBondCouponsResponse:
            while True:
                try:
                    await RateLimiter.wait()
                    return await client.instruments.get_bond_coupons(figi=figi, from_=min_time, to=max_time)
                except AioRequestError as ex:
                    print(f'AioRequestError for bond: {figi}: {ex}')

        tasks = [task(bond.figi) for bond in bonds]
        print(f'Download coupons for {len(tasks)} bonds')
        responses: list[inv.GetBondCouponsResponse] = await limited_gather(*tasks)
        coupons = [response.events for response in responses]
        return coupons

    return function

###################################################################################
# Get bonds
###################################################################################


async def download_shares_info(force_update: bool = True) -> list[inv.Share]:
    async with inv.AsyncClient(token=_get_token()) as client:
        return (await _load_from_cache('shares', _download_shares(client), force_update=force_update)).instruments


async def download_bonds_info(force_update: bool = True) -> tuple[list[inv.Bond], list[list[inv.Coupon]], list[inv.LastPrice]]:
    async with inv.AsyncClient(token=_get_token()) as client:
        bonds: list[inv.Bond] = (await _load_from_cache("bonds", _download_bonds_general_info(client), force_update=force_update))
        bonds_coupons = (await _load_from_cache("bonds_coupons", _download_bonds_coupons(client, bonds), force_update=force_update))
        bonds_last_prices = (await _load_from_cache("bonds_last_prices", _download_last_prices(client, bonds), force_update=force_update))
    print('Successfully downloaded bonds info data')
    return bonds, bonds_coupons, bonds_last_prices


if __name__ == "__main__":
    asyncio.run(download_shares_info())
    asyncio.run(download_bonds_info())
