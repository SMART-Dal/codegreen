def workload():
    def gen():
        for i in range(1000000): yield i
    sum(gen())

if __name__ == '__main__':
    workload()