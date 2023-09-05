import asyncio

from download_data import download_shares_close_prices, download_bonds_info, download_shares_info


async def download_all(force_update: bool):
    await download_shares_info(force_update=force_update)
    # await download_bonds_info(force_update=force_update)
    await download_shares_close_prices(force_update=force_update)
    print('Successfully downloaded all data')


if __name__ == '__main__':
    asyncio.run(download_all(force_update=True))
