def workload():
    d = {i: i for i in range(100000)}
    for i in range(100000): _ = d[i]

if __name__ == '__main__':
    workload()