
import os
path = "tests/validation"
os.makedirs(path, exist_ok=True)
scripts = [
    ("v1_fib.py", "def workload():\n    def fib(n):\n        if n < 2: return n\n        return fib(n-1) + fib(n-2)\n    fib(30)"),
    ("v2_mat_mul.py", "def workload():\n    size = 100\n    res = [[0]*size for _ in range(size)]\n    for i in range(size): \n        for j in range(size):\n            for k in range(size): res[i][j] += i*k"),
    ("v3_prime.py", "def workload():\n    primes = []\n    for num in range(2, 5000):\n        if all(num % i != 0 for i in range(2, int(num**0.5) + 1)): primes.append(num)"),
    ("v4_sort.py", "def workload():\n    import random\n    data = [random.random() for _ in range(100000)]\n    data.sort()"),
    ("v5_regex.py", "def workload():\n    import re\n    text = 'abc ' * 100000\n    re.findall(r'(abc)', text)"),
    ("v6_json.py", "def workload():\n    import json\n    data = {'a': [i for i in range(10000)]}\n    s = json.dumps(data)\n    json.loads(s)"),
    ("v7_hash.py", "def workload():\n    import hashlib\n    for _ in range(50000): hashlib.sha256(b'hello').hexdigest()"),
    ("v8_list_comp.py", "def workload():\n    [i**2 for i in range(1000000)]"),
    ("v9_float_ops.py", "def workload():\n    x = 1.0\n    for i in range(1000000): x = (x + i) / 2.0"),
    ("v10_dict_lookup.py", "def workload():\n    d = {i: i for i in range(100000)}\n    for i in range(100000): _ = d[i]"),
    ("v11_generator.py", "def workload():\n    def gen():\n        for i in range(1000000): yield i\n    sum(gen())"),
    ("v12_heavy_io.py", "def workload():\n    import time\n    for _ in range(10): time.sleep(0.05)"),
    ("v13_string_concat.py", "def workload():\n    s = ''\n    for i in range(50000): s += str(i)"),
    ("v14_bit_shift.py", "def workload():\n    n = 1\n    for i in range(1000000): n = (n << 1) ^ i"),
    ("v15_set_ops.py", "def workload():\n    s1 = set(range(50000))\n    s2 = set(range(25000, 75000))\n    _ = s1 | s2"),
    ("v16_trig.py", "def workload():\n    import math\n    for i in range(500000): _ = math.sin(i) + math.cos(i)"),
    ("v17_nested_loop.py", "def workload():\n    count = 0\n    for i in range(1000): \n        for j in range(1000): count += 1"),
    ("v18_mem_copy.py", "def workload():\n    data = bytearray(10*1024*1024)\n    for _ in range(50): _ = data[:]"),
    ("v19_class_inst.py", "def workload():\n    class A: pass\n    for _ in range(100000): _ = A()"),
    ("v20_large_sum.py", "def workload():\n    data = list(range(1000000))\n    sum(data)"),
    ("v21_fib.c", "#include <stdio.h>\nint main() {\n    long long x = 0;\n    for (int i = 0; i < 500000000; i++) {\n        x += (i % 2 == 0 ? 1 : -1);\n    }\n    printf(\"%lld\\n\", x);\n    return 0;\n}"),
    ("v22_mat_mul.c", "#include <stdio.h>\n#include <stdlib.h>\nint main() {\n    int size = 200;\n    double *res = calloc(size * size, sizeof(double));\n    for (int i = 0; i < size; i++) {\n        for (int j = 0; j < size; j++) {\n            for (int k = 0; k < size; k++) {\n                res[i * size + j] += i * k;\n            }\n        }\n    }\n    free(res);\n    return 0;\n}"),
    ("v23_fib.cpp", "#include <iostream>\nint main() {\n    long long x = 0;\n    for (int i = 0; i < 500000000; i++) {\n        x += (i % 2 == 0 ? 1 : -1);\n    }\n    std::cout << x << std::endl;\n    return 0;\n}"),
    ("v24_prime.java", "public class v24_prime {\n    public static void main(String[] args) {\n        java.util.List<Integer> primes = new java.util.ArrayList<>();\n        for (int num = 2; num < 50000; num++) {\n            boolean isPrime = true;\n            for (int i = 2; i <= Math.sqrt(num); i++) {\n                if (num % i == 0) {\n                    isPrime = false;\n                    break;\n                }\n            }\n            if (isPrime) primes.add(num);\n        }\n        System.out.println(primes.size());\n    }\n}")
]

for name, content in scripts:
    with open(os.path.join(path, name), "w") as f:
        if name.endswith(".py"):
            f.write(content + "\n\nif __name__ == '__main__':\n    workload()")
        else:
            f.write(content)
