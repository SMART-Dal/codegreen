import asyncio
import time

# Complex Python: Async/Await simulation
async def worker(id, delay):
    start = time.time()
    # CPU work simulation
    count = 0
    for i in range(20000):
        count += i
    return count

async def main():
    tasks = []
    print("Starting tasks...")
    for i in range(5):
        tasks.append(worker(i, 0.1))
    
    results = await asyncio.gather(*tasks)
    print(f"Total results: {sum(results)}")

if __name__ == "__main__":
    asyncio.run(main())