def workload():
    x = 1.0
    for i in range(1000000): x = (x + i) / 2.0

if __name__ == '__main__':
    workload()