import asyncio

N_PARALLEL_DOWNLOADS = 5
semaphore = asyncio.Semaphore(N_PARALLEL_DOWNLOADS)


async def limited_gather(*tasks) -> list:
    async def _wrapper(coro):
        async with semaphore:
            return await coro

    return await asyncio.gather(*(_wrapper(task) for task in tasks))
