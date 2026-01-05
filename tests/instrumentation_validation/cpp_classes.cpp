#include <iostream>

class Outer {
private:
    int x;
    
    class Inner {
    public:
        void print() {
            std::cout << "Inner class" << std::endl;
        }
    };
    
public:
    Outer() : x(0) {}
    
    void run() {
        Inner i;
        i.print();
    }
    
    friend class FriendClass;
};

class FriendClass {
public:
    void access(Outer& o) {
        o.x = 10;
    }
};

int main() {
    Outer o;
    o.run();
    FriendClass f;
    f.access(o);
    return 0;
}