import time

def timer_decorator(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"{func.__name__} took {end-start}s")
        return result
    return wrapper

@timer_decorator
def heavy_computation(n):
    total = 0
    for i in range(n):
        total += i
    return total

def main():
    heavy_computation(10000)

if __name__ == "__main__":
    main()