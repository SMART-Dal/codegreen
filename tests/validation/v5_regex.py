def workload():
    import re
    text = 'abc ' * 100000
    re.findall(r'(abc)', text)

if __name__ == '__main__':
    workload()