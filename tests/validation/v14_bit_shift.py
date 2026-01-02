def workload():
    n = 1
    for i in range(1000000): n = (n << 1) ^ i

if __name__ == '__main__':
    workload()