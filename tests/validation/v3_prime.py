def workload():
    primes = []
    for num in range(2, 5000):
        if all(num % i != 0 for i in range(2, int(num**0.5) + 1)): primes.append(num)

if __name__ == '__main__':
    workload()