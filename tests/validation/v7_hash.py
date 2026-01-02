def workload():
    import hashlib
    for _ in range(50000): hashlib.sha256(b'hello').hexdigest()

if __name__ == '__main__':
    workload()