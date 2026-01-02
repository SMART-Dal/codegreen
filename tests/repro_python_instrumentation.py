
import time
import asyncio

def simple_function():
    """A simple docstring."""
    print("Simple function body")
    time.sleep(0.1)

def function_with_args(a, b):
    # A comment before body
    result = a + b
    return result

async def async_worker():
    """Async function docstring."""
    await asyncio.sleep(0.1)
    return "done"

class MyClass:
    def __init__(self):
        self.value = 0

    def method_one(self):
        self.value += 1
        if self.value > 5:
            return True
        print("Continuing...")
        return False

def complex_control_flow(x):
    if x > 0:
        for i in range(x):
            if i == 5:
                return "Early return in loop"
    else:
        return "Early return else"
    
    # Implicit return at end
    print("End of function")

def empty_function():
    pass

@property
def decorated_function():
    return "decorated"
