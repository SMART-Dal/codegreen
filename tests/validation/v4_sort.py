def workload():
    import random
    data = [random.random() for _ in range(100000)]
    data.sort()

if __name__ == '__main__':
    workload()