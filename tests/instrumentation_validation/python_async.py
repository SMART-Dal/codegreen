import asyncio

async def async_task(name, delay):
    print(f"Task {name} starting")
    await asyncio.sleep(delay)
    print(f"Task {name} finished")
    return len(name)

async def main():
    task1 = asyncio.create_task(async_task("A", 0.1))
    task2 = asyncio.create_task(async_task("B", 0.2))
    
    await task1
    await task2
    print("All tasks done")

if __name__ == "__main__":
    asyncio.run(main())