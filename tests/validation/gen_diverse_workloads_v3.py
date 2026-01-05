
import os
from pathlib import Path

path = Path("tests/validation")
os.makedirs(path, exist_ok=True)

# ---------------------------------------------------------
# C Workloads
# ---------------------------------------------------------

def generate_c_recursion():
    content = """
#include <stdio.h>
#include <stdlib.h>

// Complex recursion: Ackermann function
// Tests function entry/exit overhead and deep stack
long ackermann(long m, long n) {
    if (m == 0) return n + 1;
    if (n == 0) return ackermann(m - 1, 1);
    return ackermann(m - 1, ackermann(m, n - 1));
}

int main() {
    long m = 3, n = 8;
    printf("Computing Ackermann(%ld, %ld)...\\n", m, n);
    long result = ackermann(m, n);
    printf("Result: %ld\\n", result);
    return 0;
}
"""
    with open(path / "c_complex_01_recursion.c", "w") as f: f.write(content.strip())

def generate_c_io():
    content = """
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Complex IO: File processing simulation
// Tests loop instrumentation and IO waits
void process_file() {
    FILE *fp = fopen("temp_test.dat", "w+");
    if (!fp) return;
    
    // Write data
    for (int i = 0; i < 10000; i++) {
        fprintf(fp, "Line %d: data data data\\n", i);
    }
    
    rewind(fp);
    
    // Read and process
    char buffer[100];
    long sum = 0;
    while (fgets(buffer, sizeof(buffer), fp)) {
        sum += strlen(buffer);
    }
    
    printf("Total length: %ld\\n", sum);
    fclose(fp);
    remove("temp_test.dat");
}

int main() {
    process_file();
    return 0;
}
"""
    with open(path / "c_complex_02_io.c", "w") as f: f.write(content.strip())

def generate_c_memory():
    content = """
#include <stdio.h>
#include <stdlib.h>

// Complex Memory: Linked List operations
typedef struct Node {
    int data;
    struct Node* next;
} Node;

Node* create_node(int data) {
    Node* newNode = (Node*)malloc(sizeof(Node));
    newNode->data = data;
    newNode->next = NULL;
    return newNode;
}

void process_list() {
    Node* head = NULL;
    // Build list
    for (int i = 0; i < 20000; i++) {
        Node* n = create_node(i);
        n->next = head;
        head = n;
    }
    
    // Traverse
    long sum = 0;
    Node* curr = head;
    while (curr) {
        sum += curr->data;
        curr = curr->next;
    }
    
    // Cleanup
    while (head) {
        Node* temp = head;
        head = head->next;
        free(temp);
    }
    printf("Sum: %ld\\n", sum);
}

int main() {
    process_list();
    return 0;
}
"""
    with open(path / "c_complex_03_memory.c", "w") as f: f.write(content.strip())

def generate_c_math():
    content = """
#include <stdio.h>
#include <stdlib.h>
#include <math.h>

// Complex Math: Monte Carlo Pi estimation
// Tests loop density and FPU usage
void compute_pi() {
    long iterations = 1000000;
    long inside = 0;
    
    for (long i = 0; i < iterations; i++) {
        double x = (double)rand() / RAND_MAX;
        double y = (double)rand() / RAND_MAX;
        if (x*x + y*y <= 1.0) inside++;
    }
    
    double pi = 4.0 * inside / iterations;
    printf("Pi approx: %f\\n", pi);
}

int main() {
    compute_pi();
    return 0;
}
"""
    with open(path / "c_complex_04_math.c", "w") as f: f.write(content.strip())

# ---------------------------------------------------------
# C++ Workloads
# ---------------------------------------------------------

def generate_cpp_oop():
    content = """
#include <iostream>
#include <vector>
#include <memory>
#include <cmath>

// Complex OOP: Polymorphism and Virtual Methods
class Shape {
public:
    virtual double area() const = 0;
    virtual ~Shape() = default;
};

class Circle : public Shape {
    double r;
public:
    Circle(double radius) : r(radius) {}
    double area() const override { return 3.14159 * r * r; }
};

class Square : public Shape {
    double s;
public:
    Square(double side) : s(side) {}
    double area() const override { return s * s; }
};

int main() {
    std::vector<std::unique_ptr<Shape>> shapes;
    for (int i = 0; i < 10000; i++) {
        if (i % 2 == 0) shapes.push_back(std::make_unique<Circle>(i * 0.1));
        else shapes.push_back(std::make_unique<Square>(i * 0.1));
    }
    
    double totalArea = 0;
    for (const auto& shape : shapes) {
        totalArea += shape->area();
    }
    
    std::cout << "Total Area: " << totalArea << std::endl;
    return 0;
}
"""
    with open(path / "cpp_complex_05_oop.cpp", "w") as f: f.write(content.strip())

def generate_cpp_stl():
    content = """
#include <iostream>
#include <map>
#include <string>
#include <algorithm>

// Complex STL: Map and string operations
void process_data() {
    std::map<int, std::string> data;
    
    // Insert
    for (int i = 0; i < 10000; i++) {
        data[i] = "Value_" + std::to_string(i);
    }
    
    // Find and modify
    long total_chars = 0;
    for (int i = 0; i < 10000; i++) {
        if (data.find(i) != data.end()) {
            total_chars += data[i].length();
        }
    }
    
    std::cout << "Total chars: " << total_chars << std::endl;
}

int main() {
    process_data();
    return 0;
}
"""
    with open(path / "cpp_complex_06_stl.cpp", "w") as f: f.write(content.strip())

# ---------------------------------------------------------
# Java Workloads
# ---------------------------------------------------------

def generate_java_collections():
    content = """
import java.util.*;

// Complex Java: Collections and Streams
public class java_complex_07_collections {
    public static void main(String[] args) {
        List<Double> numbers = new ArrayList<>();
        Random rand = new Random();
        
        for (int i = 0; i < 20000; i++) {
            numbers.add(rand.nextDouble());
        }
        
        // Complex stream operation
        double sum = numbers.stream()
            .filter(n -> n > 0.5)
            .map(Math::sqrt)
            .reduce(0.0, Double::sum);
            
        System.out.println("Sum: " + sum);
    }
}
"""
    with open(path / "java_complex_07_collections.java", "w") as f: f.write(content.strip())

def generate_java_exception():
    content = """
import java.util.*;

// Complex Java: Exception Handling logic
public class java_complex_08_exception {
    static double riskyOperation(int i) throws Exception {
        if (i % 100 == 0) throw new Exception("Error");
        return 100.0 / (i % 100);
    }

    public static void main(String[] args) {
        int success = 0;
        int failures = 0;
        
        for (int i = 1; i < 10000; i++) {
            try {
                riskyOperation(i);
                success++;
            } catch (Exception e) {
                failures++;
            } finally {
                // Ensure checkpointing handles finally blocks
                if (i % 10000 == 0) System.out.print(".");
            }
        }
        System.out.println("\\nSuccess: " + success + ", Failures: " + failures);
    }
}
"""
    with open(path / "java_complex_08_exception.java", "w") as f: f.write(content.strip())

# ---------------------------------------------------------
# Python Workloads
# ---------------------------------------------------------

def generate_python_data_science():
    content = """
import math
import random

# Complex Python: Data Simulation
class DataSimulator:
    def __init__(self, size):
        self.data = [random.random() for _ in range(size)]
    
    def normalize(self):
        # List comprehension and math
        mean = sum(self.data) / len(self.data)
        variance = sum((x - mean) ** 2 for x in self.data) / len(self.data)
        std_dev = math.sqrt(variance)
        
        self.data = [(x - mean) / std_dev for x in self.data]
        return std_dev

def main():
    sim = DataSimulator(20000)
    std_dev = sim.normalize()
    print(f"Std Dev: {std_dev:.4f}")

if __name__ == "__main__":
    main()
"""
    with open(path / "python_complex_09_data.py", "w") as f: f.write(content.strip())

def generate_python_async():
    content = """
import asyncio
import time

# Complex Python: Async/Await simulation
async def worker(id, delay):
    start = time.time()
    # CPU work simulation
    count = 0
    for i in range(20000):
        count += i
    return count

async def main():
    tasks = []
    print("Starting tasks...")
    for i in range(5):
        tasks.append(worker(i, 0.1))
    
    results = await asyncio.gather(*tasks)
    print(f"Total results: {sum(results)}")

if __name__ == "__main__":
    asyncio.run(main())
"""
    with open(path / "python_complex_10_async.py", "w") as f: f.write(content.strip())

if __name__ == "__main__":
    generate_c_recursion()
    generate_c_io()
    generate_c_memory()
    generate_c_math()
    generate_cpp_oop()
    generate_cpp_stl()
    generate_java_collections()
    generate_java_exception()
    generate_python_data_science()
    generate_python_async()
    print("Generated 10 diverse validation workloads.")
