import time
import asyncio

def outer_function(x):
    """Testing nested functions."""
    def inner_function(y):
        return y * 2
    
    result = inner_function(x)
    if result > 10:
        return result
    return 0

class BaseClass:
    def base_method(self):
        print("Base method")

class DerivedClass(BaseClass):
    @staticmethod
    def static_method():
        return "static"

    @classmethod
    def class_method(cls):
        return "class"

    def base_method(self):
        """Overriding method."""
        super().base_method()
        return "Derived"

def exception_handling():
    try:
        print("In try")
        if time.time() > 0:
            return "success"
    except Exception as e:
        print(f"Error: {e}")
        return "error"
    finally:
        print("Finally")

def complex_conditionals(a, b):
    if a > 0:
        if b > 0:
            return "both positive"
        elif b < 0:
            return "a positive, b negative"
        else:
            return "a positive, b zero"
    elif a < 0:
        return "a negative"
    else:
        return "a zero"

async def async_with_context():
    async with asyncio.Lock() as lock:
        await asyncio.sleep(0.01)
        return "locked result"

def loop_with_control(items):
    for item in items:
        if item == "skip":
            continue
        if item == "stop":
            break
        print(item)
    return "done"

lambda_func = lambda x: x + 1

def list_comp_test(n):
    return [i * 2 for i in range(n) if i % 2 == 0]