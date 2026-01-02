/*
 * Complex C Test for CodeGreen Instrumentation
 * Tests challenging constructs: nested functions, function pointers, 
 * complex control flow, macros, structures, memory management
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <math.h>
#include <assert.h>
#include <stdarg.h>
#include <setjmp.h>

#define MAX_BUFFER_SIZE 1024
#define MIN(a, b) ((a) < (b) ? (a) : (b))
#define MAX(a, b) ((a) > (b) ? (a) : (b))

// Complex macro with multiple statements
#define COMPLEX_OPERATION(x, y, result) do { \
    int temp1 = (x) * 2; \
    int temp2 = (y) * 3; \
    for (int i = 0; i < 5; i++) { \
        temp1 += i; \
        if (temp1 > 100) break; \
    } \
    (result) = temp1 + temp2; \
} while(0)

// Forward declarations
typedef struct DataNode DataNode;
typedef struct ProcessorContext ProcessorContext;
typedef int (*comparison_func_t)(const void*, const void*);
typedef double (*calculation_func_t)(double, double);

// Complex nested structures
typedef struct {
    double real;
    double imaginary;
} Complex;

typedef struct DataNode {
    int id;
    double value;
    char name[64];
    struct DataNode* left;
    struct DataNode* right;
    struct DataNode* parent;
    void* metadata;
} DataNode;

typedef struct {
    DataNode** nodes;
    size_t capacity;
    size_t count;
    comparison_func_t compare;
} DynamicArray;

typedef struct ProcessorContext {
    DynamicArray* data_array;
    Complex* complex_numbers;
    size_t complex_count;
    calculation_func_t* operations;
    size_t operation_count;
    FILE* log_file;
    jmp_buf error_context;
    int error_code;
} ProcessorContext;

// Global variables for testing
static ProcessorContext* global_context = NULL;
static long long fibonacci_cache[100] = {0};
static int cache_initialized = 0;

// Complex function pointer array
static calculation_func_t math_operations[] = {
    sin, cos, tan, log, exp, sqrt, NULL
};

// Function prototypes
int compare_nodes_by_value(const void* a, const void* b);
int compare_nodes_by_id(const void* a, const void* b);
double add_operation(double a, double b);
double multiply_operation(double a, double b);
double power_operation(double a, double b);

// Complex recursive function with memoization
long long fibonacci_recursive(int n) {
    if (!cache_initialized) {
        memset(fibonacci_cache, -1, sizeof(fibonacci_cache));
        fibonacci_cache[0] = 0;
        fibonacci_cache[1] = 1;
        cache_initialized = 1;
    }
    
    if (n < 0) return -1;
    if (n >= 100) return -1;  // Prevent overflow
    
    if (fibonacci_cache[n] != -1) {
        return fibonacci_cache[n];
    }
    
    // Complex recursive case with nested calls
    if (n <= 1) {
        fibonacci_cache[n] = n;
    } else {
        long long fib_n_minus_1 = fibonacci_recursive(n - 1);
        long long fib_n_minus_2 = fibonacci_recursive(n - 2);
        
        // Additional complexity: check for potential overflow
        if (fib_n_minus_1 > 0 && fib_n_minus_2 > 0 && 
            fib_n_minus_1 > LLONG_MAX - fib_n_minus_2) {
            return -1;  // Overflow detected
        }
        
        fibonacci_cache[n] = fib_n_minus_1 + fib_n_minus_2;
    }
    
    return fibonacci_cache[n];
}

// Function with complex nested loops and goto statements
int complex_matrix_operation(double** matrix, int rows, int cols, double* result) {
    if (!matrix || !result || rows <= 0 || cols <= 0) {
        goto error_invalid_params;
    }
    
    double sum = 0.0;
    int processed_elements = 0;
    
    // Triple nested loop with complex conditions
    for (int i = 0; i < rows; i++) {
        for (int j = 0; j < cols; j++) {
            for (int k = 0; k < MIN(i + 1, j + 1); k++) {
                double current_value = matrix[i][j];
                
                // Complex conditional logic
                if (current_value < 0) {
                    // Handle negative values with nested while loop
                    double abs_val = -current_value;
                    int iterations = 0;
                    
                    while (abs_val > 1.0 && iterations < 10) {
                        abs_val = sqrt(abs_val);
                        iterations++;
                        
                        if (abs_val < 0.01) {
                            goto skip_element;
                        }
                        
                        // Nested for loop inside while
                        for (int m = 0; m < 3; m++) {
                            abs_val *= 1.1;
                            if (abs_val > 100) {
                                goto skip_element;
                            }
                        }
                    }
                    current_value = -abs_val;
                } else if (current_value == 0) {
                    goto skip_element;
                } else {
                    // Positive values get different processing
                    double log_val = log(current_value);
                    if (isnan(log_val) || isinf(log_val)) {
                        goto skip_element;
                    }
                    current_value = log_val;
                }
                
                sum += current_value * (k + 1);
                processed_elements++;
                continue;
                
skip_element:
                printf("Skipping element at [%d][%d], k=%d\n", i, j, k);
                continue;
            }
        }
    }
    
    if (processed_elements == 0) {
        goto error_no_elements;
    }
    
    *result = sum / processed_elements;
    return processed_elements;

error_invalid_params:
    fprintf(stderr, "Invalid parameters to complex_matrix_operation\n");
    return -1;

error_no_elements:
    fprintf(stderr, "No valid elements processed\n");
    return -2;
}

// Variadic function with complex logic
double variadic_calculator(const char* operation, int count, ...) {
    if (!operation || count <= 0) return 0.0;
    
    va_list args;
    va_start(args, count);
    
    double result = 0.0;
    double values[count];
    
    // Extract all values first
    for (int i = 0; i < count; i++) {
        values[i] = va_arg(args, double);
    }
    va_end(args);
    
    // Complex switch with nested operations
    if (strcmp(operation, "sum") == 0) {
        for (int i = 0; i < count; i++) {
            result += values[i];
        }
    } else if (strcmp(operation, "product") == 0) {
        result = 1.0;
        for (int i = 0; i < count; i++) {
            result *= values[i];
            if (result == 0.0) break;  // Short circuit on zero
        }
    } else if (strcmp(operation, "complex_mean") == 0) {
        // Complex mean calculation with outlier removal
        double sum = 0.0;
        int valid_count = 0;
        
        // First pass: calculate basic mean
        for (int i = 0; i < count; i++) {
            sum += values[i];
        }
        double basic_mean = sum / count;
        
        // Second pass: remove outliers (> 2 standard deviations)
        double variance_sum = 0.0;
        for (int i = 0; i < count; i++) {
            double diff = values[i] - basic_mean;
            variance_sum += diff * diff;
        }
        double std_dev = sqrt(variance_sum / count);
        
        // Third pass: calculate mean without outliers
        sum = 0.0;
        valid_count = 0;
        for (int i = 0; i < count; i++) {
            double diff = fabs(values[i] - basic_mean);
            if (diff <= 2.0 * std_dev) {
                sum += values[i];
                valid_count++;
            }
        }
        
        result = valid_count > 0 ? sum / valid_count : basic_mean;
    } else {
        // Unknown operation - use function pointers
        for (int op_idx = 0; math_operations[op_idx] != NULL; op_idx++) {
            double temp_result = 0.0;
            for (int i = 0; i < count; i++) {
                temp_result += math_operations[op_idx](values[i]);
            }
            result += temp_result / count;
        }
    }
    
    return result;
}

// Binary tree operations with complex recursion
DataNode* create_node(int id, double value, const char* name) {
    DataNode* node = malloc(sizeof(DataNode));
    if (!node) return NULL;
    
    node->id = id;
    node->value = value;
    strncpy(node->name, name ? name : "", sizeof(node->name) - 1);
    node->name[sizeof(node->name) - 1] = '\0';
    node->left = node->right = node->parent = NULL;
    node->metadata = NULL;
    
    return node;
}

int insert_node_recursive(DataNode** root, DataNode* new_node, comparison_func_t compare) {
    if (!root || !new_node || !compare) return 0;
    
    if (*root == NULL) {
        *root = new_node;
        return 1;
    }
    
    int cmp_result = compare(new_node, *root);
    
    if (cmp_result < 0) {
        // Insert in left subtree
        if ((*root)->left == NULL) {
            (*root)->left = new_node;
            new_node->parent = *root;
            return 1;
        } else {
            return insert_node_recursive(&((*root)->left), new_node, compare);
        }
    } else if (cmp_result > 0) {
        // Insert in right subtree
        if ((*root)->right == NULL) {
            (*root)->right = new_node;
            new_node->parent = *root;
            return 1;
        } else {
            return insert_node_recursive(&((*root)->right), new_node, compare);
        }
    } else {
        // Duplicate node - update value and free new_node
        (*root)->value = new_node->value;
        free(new_node);
        return 1;
    }
}

void traverse_and_process(DataNode* root, void (*processor)(DataNode*, void*), void* context) {
    if (!root || !processor) return;
    
    // Complex traversal with multiple recursive calls
    if (root->left) {
        traverse_and_process(root->left, processor, context);
    }
    
    // Process current node with error checking
    processor(root, context);
    
    // Handle right subtree with tail recursion optimization attempt
    while (root->right && !root->right->left) {
        root = root->right;
        processor(root, context);
    }
    
    if (root->right && root->right->left) {
        traverse_and_process(root->right, processor, context);
    }
}

// Memory pool allocator for testing complex memory management
typedef struct MemoryBlock {
    size_t size;
    int is_free;
    struct MemoryBlock* next;
    char data[];
} MemoryBlock;

typedef struct {
    MemoryBlock* first_block;
    size_t total_size;
    size_t used_size;
} MemoryPool;

MemoryPool* create_memory_pool(size_t initial_size) {
    MemoryPool* pool = malloc(sizeof(MemoryPool));
    if (!pool) return NULL;
    
    // Allocate initial block
    MemoryBlock* first_block = malloc(sizeof(MemoryBlock) + initial_size);
    if (!first_block) {
        free(pool);
        return NULL;
    }
    
    first_block->size = initial_size;
    first_block->is_free = 1;
    first_block->next = NULL;
    
    pool->first_block = first_block;
    pool->total_size = initial_size;
    pool->used_size = 0;
    
    return pool;
}

void* pool_alloc(MemoryPool* pool, size_t size) {
    if (!pool || size == 0) return NULL;
    
    MemoryBlock* current = pool->first_block;
    MemoryBlock* best_fit = NULL;
    size_t best_fit_size = SIZE_MAX;
    
    // Find best fit block
    while (current) {
        if (current->is_free && current->size >= size) {
            if (current->size < best_fit_size) {
                best_fit = current;
                best_fit_size = current->size;
                
                // Perfect fit - use immediately
                if (current->size == size) {
                    break;
                }
            }
        }
        current = current->next;
    }
    
    if (!best_fit) {
        // No suitable block found - expand pool
        size_t new_block_size = MAX(size, 1024);
        MemoryBlock* new_block = malloc(sizeof(MemoryBlock) + new_block_size);
        if (!new_block) return NULL;
        
        new_block->size = new_block_size;
        new_block->is_free = 1;
        new_block->next = pool->first_block;
        pool->first_block = new_block;
        pool->total_size += new_block_size;
        best_fit = new_block;
        best_fit_size = new_block_size;
    }
    
    // Split block if necessary
    if (best_fit_size > size + sizeof(MemoryBlock) + 16) {
        MemoryBlock* new_block = (MemoryBlock*)(best_fit->data + size);
        new_block->size = best_fit_size - size - sizeof(MemoryBlock);
        new_block->is_free = 1;
        new_block->next = best_fit->next;
        
        best_fit->size = size;
        best_fit->next = new_block;
    }
    
    best_fit->is_free = 0;
    pool->used_size += best_fit->size;
    
    return best_fit->data;
}

void pool_free(MemoryPool* pool, void* ptr) {
    if (!pool || !ptr) return;
    
    // Find the block containing this pointer
    MemoryBlock* current = pool->first_block;
    while (current) {
        if (current->data == ptr) {
            if (!current->is_free) {
                current->is_free = 1;
                pool->used_size -= current->size;
                
                // Coalesce with next block if possible
                if (current->next && current->next->is_free) {
                    MemoryBlock* next_block = current->next;
                    current->size += next_block->size + sizeof(MemoryBlock);
                    current->next = next_block->next;
                }
            }
            return;
        }
        current = current->next;
    }
}

// Complex main function with error handling and multiple test cases
int main(int argc, char* argv[]) {
    printf("🧪 Starting Complex C CodeGreen Test\n");
    printf("===================================\n");
    
    int exit_code = 0;
    MemoryPool* test_pool = NULL;
    DataNode* tree_root = NULL;
    double** test_matrix = NULL;
    
    // Set up error handling
    jmp_buf main_error_context;
    if (setjmp(main_error_context) != 0) {
        printf("Fatal error occurred, cleaning up...\n");
        exit_code = 1;
        goto cleanup;
    }
    
    // Test 1: Fibonacci with various inputs
    printf("\n📊 Testing Fibonacci sequence:\n");
    for (int i = 0; i < 15; i++) {
        long long fib_result = fibonacci_recursive(i);
        printf("F(%d) = %lld\n", i, fib_result);
        
        // Test negative and boundary cases
        if (i == 5) {
            printf("F(-1) = %lld (should be -1)\n", fibonacci_recursive(-1));
            printf("F(100) = %lld (should be -1)\n", fibonacci_recursive(100));
        }
    }
    
    // Test 2: Matrix operations
    printf("\n🔢 Testing matrix operations:\n");
    int matrix_rows = 4, matrix_cols = 4;
    test_matrix = malloc(matrix_rows * sizeof(double*));
    if (!test_matrix) {
        longjmp(main_error_context, 1);
    }
    
    for (int i = 0; i < matrix_rows; i++) {
        test_matrix[i] = malloc(matrix_cols * sizeof(double));
        if (!test_matrix[i]) {
            longjmp(main_error_context, 1);
        }
        
        // Fill with test data including negative and zero values
        for (int j = 0; j < matrix_cols; j++) {
            test_matrix[i][j] = (double)(i * matrix_cols + j) - 8.0;  // -8 to 7 range
        }
    }
    
    double matrix_result;
    int elements_processed = complex_matrix_operation(test_matrix, matrix_rows, matrix_cols, &matrix_result);
    printf("Matrix operation processed %d elements, result: %.4f\n", elements_processed, matrix_result);
    
    // Test 3: Variadic function
    printf("\n🧮 Testing variadic calculator:\n");
    double calc_result;
    
    calc_result = variadic_calculator("sum", 5, 1.0, 2.0, 3.0, 4.0, 5.0);
    printf("Sum of 1,2,3,4,5 = %.2f\n", calc_result);
    
    calc_result = variadic_calculator("product", 4, 2.0, 3.0, 4.0, 0.5);
    printf("Product of 2,3,4,0.5 = %.2f\n", calc_result);
    
    calc_result = variadic_calculator("complex_mean", 8, 1.0, 2.0, 3.0, 4.0, 5.0, 100.0, 6.0, 7.0);
    printf("Complex mean (with outlier 100) = %.2f\n", calc_result);
    
    // Test 4: Binary tree operations
    printf("\n🌳 Testing binary tree operations:\n");
    
    // Create and insert nodes
    for (int i = 0; i < 10; i++) {
        char node_name[32];
        snprintf(node_name, sizeof(node_name), "Node_%d", i);
        
        DataNode* new_node = create_node(i, (double)i * 1.5, node_name);
        if (new_node) {
            if (!insert_node_recursive(&tree_root, new_node, compare_nodes_by_id)) {
                printf("Failed to insert node %d\n", i);
                free(new_node);
            }
        }
    }
    
    printf("Binary tree created with nodes 0-9\n");
    
    // Test 5: Memory pool
    printf("\n💾 Testing memory pool:\n");
    test_pool = create_memory_pool(2048);
    if (!test_pool) {
        printf("Failed to create memory pool\n");
        longjmp(main_error_context, 1);
    }
    
    // Allocate various sized blocks
    void* ptrs[10];
    size_t sizes[] = {64, 128, 256, 32, 512, 16, 1024, 8, 256, 128};
    
    for (int i = 0; i < 10; i++) {
        ptrs[i] = pool_alloc(test_pool, sizes[i]);
        if (ptrs[i]) {
            printf("Allocated %zu bytes at %p\n", sizes[i], ptrs[i]);
            // Write some data to test the allocation
            memset(ptrs[i], i + 1, sizes[i]);
        } else {
            printf("Failed to allocate %zu bytes\n", sizes[i]);
        }
    }
    
    // Free some blocks
    for (int i = 0; i < 10; i += 2) {
        if (ptrs[i]) {
            pool_free(test_pool, ptrs[i]);
            printf("Freed block at %p\n", ptrs[i]);
        }
    }
    
    printf("Memory pool test completed. Used: %zu / %zu bytes\n", 
           test_pool->used_size, test_pool->total_size);
    
    // Test 6: Complex macro usage
    printf("\n🔧 Testing complex macros:\n");
    for (int x = 1; x <= 5; x++) {
        for (int y = 1; y <= 3; y++) {
            int macro_result;
            COMPLEX_OPERATION(x, y, macro_result);
            printf("COMPLEX_OPERATION(%d, %d) = %d\n", x, y, macro_result);
        }
    }
    
    printf("\n✅ All tests completed successfully!\n");
    exit_code = 0;

cleanup:
    // Cleanup allocated memory
    if (test_matrix) {
        for (int i = 0; i < matrix_rows; i++) {
            free(test_matrix[i]);
        }
        free(test_matrix);
    }
    
    // Free binary tree (simple cleanup - not full traversal for brevity)
    while (tree_root) {
        DataNode* temp = tree_root;
        tree_root = tree_root->right;  // Simplified cleanup
        free(temp);
    }
    
    // Free memory pool
    if (test_pool) {
        MemoryBlock* current = test_pool->first_block;
        while (current) {
            MemoryBlock* next = current->next;
            free(current);
            current = next;
        }
        free(test_pool);
    }
    
    printf("\n🧹 Cleanup completed. Exit code: %d\n", exit_code);
    return exit_code;
}

// Comparison functions for sorting
int compare_nodes_by_value(const void* a, const void* b) {
    const DataNode* node_a = (const DataNode*)a;
    const DataNode* node_b = (const DataNode*)b;
    
    if (node_a->value < node_b->value) return -1;
    if (node_a->value > node_b->value) return 1;
    return 0;
}

int compare_nodes_by_id(const void* a, const void* b) {
    const DataNode* node_a = (const DataNode*)a;
    const DataNode* node_b = (const DataNode*)b;
    
    return node_a->id - node_b->id;
}

// Mathematical operations for function pointers
double add_operation(double a, double b) {
    return a + b;
}

double multiply_operation(double a, double b) {
    return a * b;
}

double power_operation(double a, double b) {
    return pow(a, b);
}