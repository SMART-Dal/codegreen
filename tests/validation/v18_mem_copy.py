def workload():
    data = bytearray(10*1024*1024)
    for _ in range(50): _ = data[:]

if __name__ == '__main__':
    workload()