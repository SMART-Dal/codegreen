def workload():
    import json
    data = {'a': [i for i in range(10000)]}
    s = json.dumps(data)
    json.loads(s)

if __name__ == '__main__':
    workload()