import tinkoff.invest as inv
from tinkoff.invest.async_services import AsyncServices

import pickle
import typing as tp
import yaml
import datetime
import asyncio
from pathlib import Path
from dateutil.relativedelta import relativedelta


###################################################################################
# Utility
###################################################################################


def quotation_to_float(quotation: inv.Quotation | inv.MoneyValue) -> float:
    return round(quotation.units + quotation.nano / 1e9, 9)


def get_token(filename: str = "keys.yaml") -> tuple[str, str]:
    with open(filename) as f:
        keys = yaml.safe_load(f)
    return keys["token"]

###################################################################################
# Load from cache
###################################################################################


async def load_from_cache(
    filename: str, function: tp.Callable[..., tp.Awaitable], force_update: bool
):
    """
    Loads function return value from cache
    """
    directory = Path("data/tinkoff")
    directory.mkdir(exist_ok=True)
    path = directory / (filename + ".pickle")
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


def get_shares(client: AsyncServices):
    async def function() -> inv.SharesResponse:
        return await client.instruments.shares()

    return function


def get_last_prices(client: AsyncServices, instruments: list[inv.Share | inv.Bond]):
    async def function() -> inv.GetLastPricesResponse:
        return (await client.market_data.get_last_prices(
            figi=[instrument.figi for instrument in instruments]
        )).last_prices

    return function


def get_bonds(client: AsyncServices):
    today = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)

    def is_good_bond(bond: inv.Bond) -> bool:
        if not bond.buy_available_flag or not bond.sell_available_flag or not bond.for_iis_flag or bond.otc_flag or bond.lot != 1:
            return False
        if bond.perpetual_flag or bond.floating_coupon_flag or bond.amortization_flag:
            return False
        if bond.currency != "rub" or bond.nominal.currency != "rub":
            return False
        if quotation_to_float(bond.nominal) != 1000:
            return False
        if not (bond.maturity_date <= today + relativedelta(years=20)):
            return False
        return True

    async def function() -> list[inv.Bond]:
        bonds = (await client.instruments.bonds(instrument_status=inv.InstrumentStatus.INSTRUMENT_STATUS_BASE)).instruments
        bonds = [bond for bond in bonds if is_good_bond(bond)]
        return bonds

    return function


def get_bonds_coupons(client: AsyncServices, bonds: list[inv.Bond]):
    async def function() -> list[list[inv.Coupon]]:
        min_time = datetime.datetime(year=1971, month=1, day=1, hour=0, minute=0, second=0)
        max_time = datetime.datetime(year=2200, month=1, day=1, hour=0, minute=0, second=0)
        tasks = [client.instruments.get_bond_coupons(figi=bond.figi, from_=min_time, to=max_time) for bond in bonds]
        responses: list[inv.GetBondCouponsResponse] = await asyncio.gather(*tasks)
        coupons = []
        for response in responses:
            coupons.append(response.events)
        return coupons

    return function

###################################################################################
# Get shares and bonds
###################################################################################


async def get_shares_info(force_update: bool) -> list[inv.Share]:
    async with inv.AsyncClient(token=get_token()) as client:
        return (await load_from_cache('shares', get_shares(client), force_update=force_update)).instruments


async def get_bonds_info(force_update: bool) -> tuple[list[inv.Bond], list[list[inv.Coupon]], list[inv.LastPrice]]:
    async with inv.AsyncClient(token=get_token()) as client:
        bonds: list[inv.Bond] = (await load_from_cache('bonds', get_bonds(client), force_update=force_update))
        bonds_coupons = (await load_from_cache('bonds_coupons', get_bonds_coupons(client, bonds), force_update=force_update))
        bonds_last_prices = (await load_from_cache('bonds_last_prices', get_last_prices(client, bonds), force_update=force_update))
    return bonds, bonds_coupons, bonds_last_prices


if __name__ == "__main__":
    asyncio.run(get_bonds_info(force_update=True))
