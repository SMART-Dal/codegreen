def workload():
    size = 100
    res = [[0]*size for _ in range(size)]
    for i in range(size): 
        for j in range(size):
            for k in range(size): res[i][j] += i*k

if __name__ == '__main__':
    workload()