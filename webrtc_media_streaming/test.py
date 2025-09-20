import asyncio

async def worker(name, delay):
    await asyncio.sleep(delay)
    print(f"[{name}] finished after {delay}s")

async def main():
    # 启动两个后台任务，但不等待它们
    asyncio.create_task(worker("A", 2))
    asyncio.create_task(worker("B", 3))

    print("Main is doing other things...")
    await asyncio.sleep(1)
    print("Main finished quickly!")

asyncio.run(main())
