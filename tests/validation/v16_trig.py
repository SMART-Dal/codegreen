def workload():
    import math
    for i in range(500000): _ = math.sin(i) + math.cos(i)

if __name__ == '__main__':
    workload()