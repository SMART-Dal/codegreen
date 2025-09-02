#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>

/**
 * Comprehensive C Sample for CodeGreen Testing
 * Tests various language constructs and checkpoint generation
 */

#define MAX_SIZE 100
#define PI 3.14159265359

// Structure to test struct checkpoint generation
typedef struct {
    double x, y;
    char name[50];
} Point;

// Function prototypes
int fibonacci_recursive(int n);
int fibonacci_iterative(int n);
double calculate_distance(Point p1, Point p2);
void process_array(double arr[], int size, double result[]);
void sort_array(int arr[], int size);
void print_point(Point p);

// Global variables to test global scope
int global_counter = 0;
double global_sum = 0.0;

int main() {
    printf("🚀 CodeGreen C Language Test\n");
    printf("=============================\n");
    
    // Test data processing
    double data[] = {1.0, 4.0, 9.0, 16.0, 25.0, -1.0, 36.0};
    int data_size = sizeof(data) / sizeof(data[0]);
    double processed_data[MAX_SIZE];
    
    printf("Input data: ");
    for (int i = 0; i < data_size; i++) {
        printf("%.1f ", data[i]);
    }
    printf("\n");
    
    // Process data
    clock_t start_time = clock();
    process_array(data, data_size, processed_data);
    clock_t end_time = clock();
    
    double processing_time = ((double)(end_time - start_time)) / CLOCKS_PER_SEC * 1000.0;
    
    printf("Processed results: ");
    for (int i = 0; i < data_size; i++) {
        if (data[i] > 0) {
            printf("%.2f ", processed_data[i]);
        }
    }
    printf("\n");
    printf("Processing time: %.2f milliseconds\n", processing_time);
    
    // Test Fibonacci functions
    printf("\n🧮 Testing Fibonacci functions:\n");
    for (int i = 0; i < 8; i++) {
        int fib_rec = fibonacci_recursive(i);
        int fib_iter = fibonacci_iterative(i);
        printf("F(%d) = %d (recursive), %d (iterative)\n", i, fib_rec, fib_iter);
    }
    
    // Test structure operations
    printf("\n📊 Testing structure operations:\n");
    Point p1 = {1.0, 2.0, "Point A"};
    Point p2 = {4.0, 6.0, "Point B"};
    
    print_point(p1);
    print_point(p2);
    
    double distance = calculate_distance(p1, p2);
    printf("Distance between points: %.2f\n", distance);
    
    // Test array operations
    printf("\n🔢 Testing array operations:\n");
    int numbers[] = {3, 1, 4, 1, 5, 9, 2, 6};
    int num_size = sizeof(numbers) / sizeof(numbers[0]);
    
    printf("Original array: ");
    for (int i = 0; i < num_size; i++) {
        printf("%d ", numbers[i]);
    }
    printf("\n");
    
    sort_array(numbers, num_size);
    
    printf("Sorted array: ");
    for (int i = 0; i < num_size; i++) {
        printf("%d ", numbers[i]);
    }
    printf("\n");
    
    // Test mathematical operations
    printf("\n🧮 Testing mathematical operations:\n");
    double angle = PI / 4.0;
    printf("sin(π/4) = %.4f\n", sin(angle));
    printf("cos(π/4) = %.4f\n", cos(angle));
    printf("tan(π/4) = %.4f\n", tan(angle));
    
    // Test global variable modifications
    global_counter++;
    global_sum += 42.0;
    printf("Global counter: %d, Global sum: %.1f\n", global_counter, global_sum);
    
    printf("\n✅ C language test completed successfully!\n");
    
    return 0;
}

int fibonacci_recursive(int n) {
    if (n <= 1) return n;
    return fibonacci_recursive(n - 1) + fibonacci_recursive(n - 2);
}

int fibonacci_iterative(int n) {
    if (n <= 1) return n;
    
    int a = 0, b = 1;
    for (int i = 2; i <= n; i++) {
        int temp = a + b;
        a = b;
        b = temp;
    }
    return b;
}

double calculate_distance(Point p1, Point p2) {
    double dx = p2.x - p1.x;
    double dy = p2.y - p1.y;
    return sqrt(dx * dx + dy * dy);
}

void process_array(double arr[], int size, double result[]) {
    for (int i = 0; i < size; i++) {
        if (arr[i] > 0) {
            result[i] = sqrt(arr[i]) * 2.0;
        } else {
            result[i] = 0.0;
        }
    }
}

void sort_array(int arr[], int size) {
    // Simple bubble sort
    for (int i = 0; i < size - 1; i++) {
        for (int j = 0; j < size - i - 1; j++) {
            if (arr[j] > arr[j + 1]) {
                int temp = arr[j];
                arr[j] = arr[j + 1];
                arr[j + 1] = temp;
            }
        }
    }
}

void print_point(Point p) {
    printf("Point %s: (%.1f, %.1f)\n", p.name, p.x, p.y);
}
