def workload():
    count = 0
    for i in range(1000): 
        for j in range(1000): count += 1

if __name__ == '__main__':
    workload()