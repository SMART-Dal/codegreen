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