import asyncio

N_PARALLEL_DOWNLOADS = 5
semaphore = asyncio.Semaphore(N_PARALLEL_DOWNLOADS)


async def limited_gather(*tasks):
    async with semaphore:
        return await asyncio.gather(*tasks)
