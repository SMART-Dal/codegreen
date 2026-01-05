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