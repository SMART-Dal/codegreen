def workload():
    s1 = set(range(50000))
    s2 = set(range(25000, 75000))
    _ = s1 | s2

if __name__ == '__main__':
    workload()