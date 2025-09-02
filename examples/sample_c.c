/*
 * Sample C program for CodeGreen energy measurement testing.
 * Demonstrates various C constructs that should generate energy checkpoints.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

// Function to calculate factorial recursively (energy-intensive)
int factorial_recursive(int n) {
    if (n <= 1) {
        return 1;
    }
    return n * factorial_recursive(n - 1);
}

// Function to calculate factorial iteratively (more efficient)
int factorial_iterative(int n) {
    int result = 1;
    for (int i = 2; i <= n; ++i) {
        result *= i;
    }
    return result;
}

// Function with nested loops (energy-intensive)
void matrix_multiply() {
    const int SIZE = 100;
    int a[SIZE][SIZE], b[SIZE][SIZE], c[SIZE][SIZE];
    
    // Initialize matrices
    for (int i = 0; i < SIZE; ++i) {
        for (int j = 0; j < SIZE; ++j) {
            a[i][j] = i + j;
            b[i][j] = i - j;
            c[i][j] = 0;
        }
    }
    
    // Matrix multiplication
    for (int i = 0; i < SIZE; ++i) {
        for (int j = 0; j < SIZE; ++j) {
            for (int k = 0; k < SIZE; ++k) {
                c[i][j] += a[i][k] * b[k][j];
            }
        }
    }
    
    printf("Matrix multiplication completed (result[0][0] = %d)\n", c[0][0]);
}

// Function with memory allocation
void memory_intensive_task() {
    const int NUM_ALLOCATIONS = 1000;
    char* pointers[NUM_ALLOCATIONS];
    
    // Allocate memory in a loop
    for (int i = 0; i < NUM_ALLOCATIONS; ++i) {
        pointers[i] = malloc(1024); // 1KB each
        if (pointers[i]) {
            memset(pointers[i], i % 256, 1024);
        }
    }
    
    // Use the memory
    int sum = 0;
    for (int i = 0; i < NUM_ALLOCATIONS; ++i) {
        if (pointers[i]) {
            for (int j = 0; j < 1024; ++j) {
                sum += pointers[i][j];
            }
        }
    }
    
    // Free memory
    for (int i = 0; i < NUM_ALLOCATIONS; ++i) {
        free(pointers[i]);
    }
    
    printf("Memory intensive task completed (sum = %d)\n", sum);
}

// Function with I/O operations
void io_intensive_task() {
    const char* filename = "/tmp/codegreen_test.txt";
    FILE* file;
    
    // Write operation
    file = fopen(filename, "w");
    if (file) {
        for (int i = 0; i < 1000; ++i) {
            fprintf(file, "Line %d: Energy measurement test data\n", i);
        }
        fclose(file);
    }
    
    // Read operation
    file = fopen(filename, "r");
    if (file) {
        char buffer[256];
        int line_count = 0;
        while (fgets(buffer, sizeof(buffer), file)) {
            line_count++;
        }
        fclose(file);
        printf("I/O intensive task completed (%d lines processed)\n", line_count);
    }
    
    // Cleanup
    unlink(filename);
}

// Main function demonstrating various patterns
int main() {
    printf("CodeGreen C Energy Measurement Demo\n");
    printf("===================================\n");
    
    // Function calls with different computational complexity
    printf("Calculating factorials...\n");
    int fact_rec = factorial_recursive(10);
    int fact_iter = factorial_iterative(10);
    
    printf("Factorial(10) - Recursive: %d\n", fact_rec);
    printf("Factorial(10) - Iterative: %d\n", fact_iter);
    
    // Nested loops (matrix operations)
    printf("Performing matrix multiplication...\n");
    matrix_multiply();
    
    // Memory allocation patterns
    printf("Running memory intensive task...\n");
    memory_intensive_task();
    
    // I/O operations
    printf("Running I/O intensive task...\n");
    io_intensive_task();
    
    // Control flow with switch
    int choice = 2;
    switch (choice) {
        case 1:
            printf("Choice 1 selected\n");
            break;
        case 2:
            printf("Choice 2 selected\n");
            break;
        default:
            printf("Default choice\n");
            break;
    }
    
    // Loop with string operations
    char* large_string = malloc(10000);
    if (large_string) {
        for (int i = 0; i < 100; ++i) {
            strcat(large_string, "test ");
        }
        printf("String operations completed (length: %zu)\n", strlen(large_string));
        free(large_string);
    }
    
    printf("Demo complete!\n");
    return 0;
}