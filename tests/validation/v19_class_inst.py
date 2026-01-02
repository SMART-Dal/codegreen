def workload():
    class A: pass
    for _ in range(100000): _ = A()

if __name__ == '__main__':
    workload()