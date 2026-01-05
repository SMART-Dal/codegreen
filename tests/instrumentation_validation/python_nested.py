def outer_function(text):
    text = text.upper()
    
    def inner_function():
        print(text)
        
    inner_function()
    
    def closure_maker(x):
        def closure(y):
            return x + y
        return closure
        
    add5 = closure_maker(5)
    print(add5(10))

def main():
    outer_function("hello")

if __name__ == "__main__":
    main()