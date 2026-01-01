/**
 * Sample JavaScript test file for CodeGreen VSCode Extension
 * Demonstrates energy hotspot detection in JavaScript code
 */

function fibonacci(n) {
    // Recursive Fibonacci - CPU intensive
    if (n <= 1) return n;
    return fibonacci(n - 1) + fibonacci(n - 2);
}

function matrixMultiply(a, b) {
    // Matrix multiplication - CPU and memory intensive
    const rows = a.length;
    const cols = b[0].length;
    const result = [];
    
    for (let i = 0; i < rows; i++) {
        result[i] = [];
        for (let j = 0; j < cols; j++) {
            result[i][j] = 0;
            for (let k = 0; k < a[0].length; k++) {
                result[i][j] += a[i][k] * b[k][j];
            }
        }
    }
    
    return result;
}

function cpuIntensiveLoop() {
    // CPU-intensive mathematical operations
    let total = 0;
    for (let i = 0; i < 1000000; i++) {
        total += Math.sqrt(i) * Math.sin(i) * Math.cos(i);
    }
    return total;
}

function memoryIntensiveOperation() {
    // Memory-intensive operation with large arrays
    const largeArray = [];
    for (let i = 0; i < 100000; i++) {
        largeArray.push(new Array(100).fill(Math.random()));
    }
    
    return largeArray.map(arr => arr.reduce((sum, val) => sum + val, 0));
}

function main() {
    console.log("Starting CodeGreen energy analysis test...");
    
    // Test various energy-intensive operations
    console.log("\n1. Testing Fibonacci...");
    const fibResult = fibonacci(30);
    console.log(`   Fibonacci(30) = ${fibResult}`);
    
    console.log("\n2. Testing Matrix Multiplication...");
    const matrixA = Array(50).fill(null).map(() => 
        Array(50).fill(null).map(() => Math.random())
    );
    const matrixB = Array(50).fill(null).map(() => 
        Array(50).fill(null).map(() => Math.random())
    );
    const matrixResult = matrixMultiply(matrixA, matrixB);
    console.log(`   Matrix result: ${matrixResult.length}x${matrixResult[0].length}`);
    
    console.log("\n3. Testing CPU-intensive loop...");
    const cpuResult = cpuIntensiveLoop();
    console.log(`   CPU loop result: ${cpuResult.toFixed(2)}`);
    
    console.log("\n4. Testing Memory-intensive operation...");
    const memResult = memoryIntensiveOperation();
    console.log(`   Memory operation result count: ${memResult.length}`);
    
    console.log("\n✅ All tests completed!");
}

if (require.main === module) {
    main();
}

module.exports = {
    fibonacci,
    matrixMultiply,
    cpuIntensiveLoop,
    memoryIntensiveOperation,
    main
};
