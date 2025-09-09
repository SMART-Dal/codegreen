/*
 * Complex Java Test for CodeGreen Instrumentation
 * Tests challenging constructs: generics, interfaces, streams, lambdas,
 * concurrency, reflection, annotations, nested classes
 */

import java.util.*;
import java.util.concurrent.*;
import java.util.stream.*;
import java.util.function.*;
import java.lang.reflect.*;
import java.lang.annotation.*;
import java.io.*;
import java.nio.file.*;
import java.time.*;
import java.math.*;

// Custom annotations for testing
@Retention(RetentionPolicy.RUNTIME)
@Target({ElementType.METHOD, ElementType.FIELD, ElementType.TYPE})
@interface ProcessingMetadata {
    String value() default "";
    int priority() default 0;
    boolean async() default false;
}

@Retention(RetentionPolicy.RUNTIME)
@Target(ElementType.METHOD)
@interface ComplexOperation {
    String description();
    int complexity() default 1;
}

// Complex generic interfaces
interface DataProcessor<T, R> {
    R process(T input) throws ProcessingException;
    
    default CompletableFuture<R> processAsync(T input) {
        return CompletableFuture.supplyAsync(() -> {
            try {
                return process(input);
            } catch (ProcessingException e) {
                throw new RuntimeException(e);
            }
        });
    }
}

interface BatchProcessor<T, R> extends DataProcessor<List<T>, List<R>> {
    @Override
    default List<R> process(List<T> input) throws ProcessingException {
        List<R> results = new ArrayList<>();
        
        // Complex nested processing
        for (int i = 0; i < input.size(); i++) {
            T item = input.get(i);
            
            try {
                // Nested validation loop
                int validationAttempts = 0;
                while (validationAttempts < 3) {
                    if (validate(item)) {
                        R result = processItem(item);
                        
                        // Complex post-processing
                        for (int j = 0; j < i % 3 + 1; j++) {
                            result = enhanceResult(result, j);
                            
                            // Early termination condition
                            if (isResultComplete(result)) {
                                break;
                            }
                        }
                        
                        results.add(result);
                        break;
                    }
                    validationAttempts++;
                }
                
                if (validationAttempts >= 3) {
                    results.add(getDefaultResult());
                }
                
            } catch (Exception e) {
                // Exception handling with retry logic
                R fallbackResult = handleProcessingError(item, e);
                if (fallbackResult != null) {
                    results.add(fallbackResult);
                }
            }
        }
        
        return results;
    }
    
    R processItem(T item) throws ProcessingException;
    R enhanceResult(R result, int enhancementLevel);
    R getDefaultResult();
    R handleProcessingError(T item, Exception error);
    boolean validate(T item);
    boolean isResultComplete(R result);
}

// Custom exception hierarchy
class ProcessingException extends Exception {
    private final int errorCode;
    private final String category;
    
    public ProcessingException(String message, int errorCode, String category) {
        super(message);
        this.errorCode = errorCode;
        this.category = category;
    }
    
    public ProcessingException(String message, Throwable cause, int errorCode, String category) {
        super(message, cause);
        this.errorCode = errorCode;
        this.category = category;
    }
    
    public int getErrorCode() { return errorCode; }
    public String getCategory() { return category; }
}

// Complex generic class with multiple type parameters
@ProcessingMetadata(value = "Advanced data container", priority = 1)
public class AdvancedContainer<T extends Comparable<T>, U extends Number, V> {
    private final Map<T, List<U>> primaryData;
    private final Map<String, V> metadata;
    private final ReentrantReadWriteLock lock;
    private final ExecutorService executorService;
    private volatile boolean isProcessing;
    
    // Nested generic class
    public static class ProcessingResult<R> {
        private final R result;
        private final long processingTime;
        private final Map<String, Object> statistics;
        private final List<String> warnings;
        
        private ProcessingResult(R result, long processingTime) {
            this.result = result;
            this.processingTime = processingTime;
            this.statistics = new ConcurrentHashMap<>();
            this.warnings = new CopyOnWriteArrayList<>();
        }
        
        public static <R> ProcessingResult<R> success(R result, long processingTime) {
            return new ProcessingResult<>(result, processingTime);
        }
        
        public R getResult() { return result; }
        public long getProcessingTime() { return processingTime; }
        public Map<String, Object> getStatistics() { return statistics; }
        public List<String> getWarnings() { return warnings; }
        
        public void addStatistic(String key, Object value) {
            statistics.put(key, value);
        }
        
        public void addWarning(String warning) {
            warnings.add(warning);
        }
    }
    
    // Constructor with complex initialization
    public AdvancedContainer() {
        this.primaryData = new ConcurrentHashMap<>();
        this.metadata = new ConcurrentHashMap<>();
        this.lock = new ReentrantReadWriteLock();
        this.executorService = Executors.newFixedThreadPool(4, r -> {
            Thread t = new Thread(r, "AdvancedContainer-Worker");
            t.setDaemon(true);
            return t;
        });
        this.isProcessing = false;
    }
    
    // Complex method with multiple generic constraints
    @ComplexOperation(description = "Process data with complex transformations", complexity = 5)
    public <W extends U> CompletableFuture<ProcessingResult<Map<T, Double>>> 
    processWithComplexTransformation(
            Map<T, List<W>> inputData,
            Function<W, Double> transformer,
            Predicate<T> keyFilter,
            BiFunction<T, Double, Double> aggregator) {
        
        return CompletableFuture.supplyAsync(() -> {
            long startTime = System.nanoTime();
            isProcessing = true;
            
            try {
                Map<T, Double> results = new ConcurrentHashMap<>();
                List<CompletableFuture<Void>> futures = new ArrayList<>();
                
                // Process each entry concurrently
                for (Map.Entry<T, List<W>> entry : inputData.entrySet()) {
                    T key = entry.getKey();
                    List<W> values = entry.getValue();
                    
                    if (!keyFilter.test(key)) {
                        continue;
                    }
                    
                    CompletableFuture<Void> future = CompletableFuture.runAsync(() -> {
                        try {
                            // Complex nested processing with multiple loops
                            double aggregatedValue = 0.0;
                            int processedCount = 0;
                            
                            for (int i = 0; i < values.size(); i++) {
                                W value = values.get(i);
                                
                                // Multi-stage transformation
                                Double transformed = transformer.apply(value);
                                
                                // Complex validation loop
                                int validationPasses = 0;
                                while (validationPasses < 3 && transformed != null) {
                                    if (transformed.isInfinite() || transformed.isNaN()) {
                                        transformed = value.doubleValue() * 0.5;
                                    } else if (transformed < 0) {
                                        // Handle negative values with iterative processing
                                        double temp = Math.abs(transformed);
                                        for (int j = 0; j < 5; j++) {
                                            temp = Math.sqrt(temp + 1);
                                            if (temp > 1.0) break;
                                        }
                                        transformed = temp;
                                    } else {
                                        break; // Valid transformation
                                    }
                                    validationPasses++;
                                }
                                
                                if (transformed != null) {
                                    // Apply aggregation function
                                    double aggregatedResult = aggregator.apply(key, transformed);
                                    
                                    // Complex accumulation logic
                                    synchronized (results) {
                                        aggregatedValue += aggregatedResult;
                                        processedCount++;
                                        
                                        // Intermediate results processing
                                        if (processedCount % 10 == 0) {
                                            double intermediate = aggregatedValue / processedCount;
                                            
                                            // Nested enhancement loop
                                            for (int k = 1; k <= 3; k++) {
                                                intermediate = Math.pow(intermediate, 1.0 + 0.1 * k);
                                                
                                                if (intermediate > 1000) {
                                                    intermediate = Math.log(intermediate);
                                                    break;
                                                }
                                            }
                                            
                                            aggregatedValue = intermediate * processedCount;
                                        }
                                    }
                                }
                            }
                            
                            // Final aggregation
                            if (processedCount > 0) {
                                double finalResult = aggregatedValue / processedCount;
                                results.put(key, finalResult);
                            }
                            
                        } catch (Exception e) {
                            System.err.println("Error processing key " + key + ": " + e.getMessage());
                        }
                    }, executorService);
                    
                    futures.add(future);
                }
                
                // Wait for all futures to complete
                CompletableFuture.allOf(futures.toArray(new CompletableFuture[0])).join();
                
                long endTime = System.nanoTime();
                ProcessingResult<Map<T, Double>> result = 
                    ProcessingResult.success(results, endTime - startTime);
                
                result.addStatistic("totalKeys", inputData.size());
                result.addStatistic("processedKeys", results.size());
                result.addStatistic("concurrentTasks", futures.size());
                
                return result;
                
            } finally {
                isProcessing = false;
            }
        }, executorService);
    }
    
    // Complex stream processing method
    @ComplexOperation(description = "Stream-based complex analysis", complexity = 4)
    public Optional<Double> performComplexStreamAnalysis(Collection<T> keys) {
        lock.readLock().lock();
        try {
            return primaryData.entrySet().stream()
                .filter(entry -> keys.contains(entry.getKey()))
                .flatMap(entry -> {
                    // Complex nested stream processing
                    return entry.getValue().stream()
                        .filter(Objects::nonNull)
                        .map(Number::doubleValue)
                        .filter(value -> !Double.isNaN(value) && !Double.isInfinite(value))
                        .map(value -> {
                            // Complex transformation with multiple stages
                            double result = value;
                            
                            // Multi-stage processing
                            for (int stage = 1; stage <= 3; stage++) {
                                if (result > 0) {
                                    result = Math.pow(result, 1.0 / stage);
                                } else {
                                    result = Math.abs(result) + stage * 0.1;
                                }
                                
                                // Stage validation
                                if (result > 1000) {
                                    result = Math.log(result + 1);
                                } else if (result < 0.001) {
                                    result = 0.001;
                                }
                            }
                            
                            return result;
                        });
                })
                .collect(Collectors.groupingBy(
                    value -> value > 1.0 ? "high" : value > 0.5 ? "medium" : "low",
                    Collectors.summarizingDouble(Double::doubleValue)
                ))
                .entrySet().stream()
                .map(entry -> {
                    DoubleSummaryStatistics stats = entry.getValue();
                    String category = entry.getKey();
                    
                    // Complex metric calculation
                    double mean = stats.getAverage();
                    double variance = 0.0;
                    
                    // Calculate variance in a complex way (for testing nested structures)
                    for (Map.Entry<T, List<U>> dataEntry : primaryData.entrySet()) {
                        if (!keys.contains(dataEntry.getKey())) continue;
                        
                        for (U value : dataEntry.getValue()) {
                            if (value != null) {
                                double doubleValue = value.doubleValue();
                                String valueCategory = doubleValue > 1.0 ? "high" : 
                                                     doubleValue > 0.5 ? "medium" : "low";
                                
                                if (valueCategory.equals(category)) {
                                    double diff = doubleValue - mean;
                                    variance += diff * diff;
                                }
                            }
                        }
                    }
                    
                    variance /= stats.getCount();
                    double standardDeviation = Math.sqrt(variance);
                    
                    return mean + standardDeviation * 0.5; // Combined metric
                })
                .max(Double::compareTo);
                
        } finally {
            lock.readLock().unlock();
        }
    }
    
    // Method with complex exception handling and nested try-catch
    @ComplexOperation(description = "Complex batch processing with error recovery", complexity = 3)
    public List<ProcessingResult<String>> processBatchWithErrorRecovery(
            List<T> keys, Function<T, String> processor) {
        
        List<ProcessingResult<String>> results = new ArrayList<>();
        
        for (int i = 0; i < keys.size(); i++) {
            T key = keys.get(i);
            long startTime = System.nanoTime();
            
            try {
                // Primary processing attempt
                try {
                    String result = processor.apply(key);
                    
                    // Validation with nested loops
                    boolean isValid = true;
                    for (int j = 0; j < result.length(); j++) {
                        char c = result.charAt(j);
                        
                        // Complex character validation
                        int validationChecks = 0;
                        while (validationChecks < 3) {
                            if (Character.isLetterOrDigit(c) || Character.isWhitespace(c)) {
                                break;
                            }
                            
                            // Try to fix the character
                            if (Character.isUpperCase(c)) {
                                c = Character.toLowerCase(c);
                            } else if (Character.isLowerCase(c)) {
                                c = Character.toUpperCase(c);
                            } else {
                                c = '_';
                            }
                            
                            validationChecks++;
                        }
                        
                        if (validationChecks >= 3) {
                            isValid = false;
                            break;
                        }
                    }
                    
                    if (!isValid) {
                        throw new ProcessingException("Invalid result format", 1001, "VALIDATION");
                    }
                    
                    long endTime = System.nanoTime();
                    ProcessingResult<String> successResult = 
                        ProcessingResult.success(result, endTime - startTime);
                    successResult.addStatistic("attempts", 1);
                    results.add(successResult);
                    
                } catch (ProcessingException pe) {
                    // Handle specific processing exceptions with retry logic
                    int maxRetries = 3;
                    String retryResult = null;
                    
                    for (int retry = 0; retry < maxRetries; retry++) {
                        try {
                            // Modified processing for retry
                            String baseResult = key.toString();
                            StringBuilder retryBuilder = new StringBuilder();
                            
                            // Complex retry processing
                            for (int pos = 0; pos < baseResult.length(); pos++) {
                                char c = baseResult.charAt(pos);
                                
                                // Transform character based on retry attempt
                                switch (retry) {
                                    case 0:
                                        retryBuilder.append(Character.toLowerCase(c));
                                        break;
                                    case 1:
                                        retryBuilder.append(Character.toUpperCase(c));
                                        break;
                                    case 2:
                                        if (Character.isLetterOrDigit(c)) {
                                            retryBuilder.append(c);
                                        } else {
                                            retryBuilder.append('_');
                                        }
                                        break;
                                }
                            }
                            
                            retryResult = retryBuilder.toString();
                            break; // Success, exit retry loop
                            
                        } catch (Exception retryException) {
                            if (retry == maxRetries - 1) {
                                // Last retry failed, use default value
                                retryResult = "DEFAULT_" + i;
                            }
                        }
                    }
                    
                    long endTime = System.nanoTime();
                    ProcessingResult<String> retrySuccessResult = 
                        ProcessingResult.success(retryResult, endTime - startTime);
                    retrySuccessResult.addStatistic("attempts", maxRetries + 1);
                    retrySuccessResult.addWarning("Original processing failed: " + pe.getMessage());
                    results.add(retrySuccessResult);
                    
                } catch (RuntimeException re) {
                    // Handle runtime exceptions
                    try {
                        // Attempt emergency processing
                        String emergencyResult = "EMERGENCY_" + key.toString().hashCode();
                        
                        // Validate emergency result
                        if (emergencyResult.length() > 0) {
                            long endTime = System.nanoTime();
                            ProcessingResult<String> emergencySuccessResult = 
                                ProcessingResult.success(emergencyResult, endTime - startTime);
                            emergencySuccessResult.addStatistic("attempts", 1);
                            emergencySuccessResult.addWarning("Emergency processing used: " + re.getMessage());
                            results.add(emergencySuccessResult);
                        } else {
                            throw new ProcessingException("Emergency processing failed", 2001, "EMERGENCY");
                        }
                        
                    } catch (ProcessingException emergencyPe) {
                        // Final fallback
                        long endTime = System.nanoTime();
                        ProcessingResult<String> fallbackResult = 
                            ProcessingResult.success("FALLBACK", endTime - startTime);
                        fallbackResult.addStatistic("attempts", 1);
                        fallbackResult.addWarning("All processing attempts failed");
                        results.add(fallbackResult);
                    }
                }
                
            } catch (Exception e) {
                // Top-level exception handler
                long endTime = System.nanoTime();
                ProcessingResult<String> errorResult = 
                    ProcessingResult.success("ERROR", endTime - startTime);
                errorResult.addWarning("Unexpected error: " + e.getMessage());
                results.add(errorResult);
            }
        }
        
        return results;
    }
    
    // Complex concurrent processing method
    @ComplexOperation(description = "Concurrent processing with complex synchronization", complexity = 5)
    @ProcessingMetadata(async = true, priority = 2)
    public CompletableFuture<Map<String, Object>> performConcurrentAnalysis(int threadCount) {
        return CompletableFuture.supplyAsync(() -> {
            Map<String, Object> analysisResults = new ConcurrentHashMap<>();
            CountDownLatch latch = new CountDownLatch(threadCount);
            CyclicBarrier barrier = new CyclicBarrier(threadCount);
            AtomicInteger processedItems = new AtomicInteger(0);
            
            // Create worker tasks
            List<Future<Map<String, Object>>> futures = new ArrayList<>();
            
            for (int threadId = 0; threadId < threadCount; threadId++) {
                final int currentThreadId = threadId;
                
                Future<Map<String, Object>> future = executorService.submit(() -> {
                    Map<String, Object> threadResults = new HashMap<>();
                    
                    try {
                        // Complex initialization phase
                        Random random = new Random(System.nanoTime() + currentThreadId);
                        List<T> threadKeys = new ArrayList<>();
                        
                        // Prepare thread-specific data
                        lock.readLock().lock();
                        try {
                            int startIndex = currentThreadId * (primaryData.size() / threadCount);
                            int endIndex = Math.min(startIndex + (primaryData.size() / threadCount), 
                                                  primaryData.size());
                            
                            threadKeys.addAll(primaryData.keySet().stream()
                                .skip(startIndex)
                                .limit(endIndex - startIndex)
                                .collect(Collectors.toList()));
                                
                        } finally {
                            lock.readLock().unlock();
                        }
                        
                        // Wait for all threads to be ready
                        barrier.await();
                        
                        // Complex processing phase
                        for (T key : threadKeys) {
                            try {
                                // Multi-stage processing with nested loops
                                Map<String, Double> keyAnalysis = new HashMap<>();
                                
                                lock.readLock().lock();
                                try {
                                    List<U> values = primaryData.get(key);
                                    if (values != null && !values.isEmpty()) {
                                        
                                        // Stage 1: Basic statistics
                                        double sum = 0.0;
                                        double sumSquares = 0.0;
                                        int validCount = 0;
                                        
                                        for (U value : values) {
                                            if (value != null) {
                                                double doubleVal = value.doubleValue();
                                                if (!Double.isNaN(doubleVal) && !Double.isInfinite(doubleVal)) {
                                                    sum += doubleVal;
                                                    sumSquares += doubleVal * doubleVal;
                                                    validCount++;
                                                }
                                            }
                                        }
                                        
                                        if (validCount > 0) {
                                            double mean = sum / validCount;
                                            double variance = (sumSquares / validCount) - (mean * mean);
                                            
                                            keyAnalysis.put("mean", mean);
                                            keyAnalysis.put("variance", variance);
                                            keyAnalysis.put("count", (double) validCount);
                                        }
                                        
                                        // Stage 2: Complex pattern analysis
                                        for (int analysisPass = 1; analysisPass <= 3; analysisPass++) {
                                            double patternScore = 0.0;
                                            
                                            for (int i = 0; i < values.size(); i++) {
                                                U currentValue = values.get(i);
                                                if (currentValue == null) continue;
                                                
                                                // Look ahead analysis
                                                for (int j = i + 1; j < Math.min(i + analysisPass + 1, values.size()); j++) {
                                                    U nextValue = values.get(j);
                                                    if (nextValue != null) {
                                                        double diff = Math.abs(nextValue.doubleValue() - 
                                                                             currentValue.doubleValue());
                                                        
                                                        // Pattern scoring with nested conditions
                                                        if (diff < 0.1) {
                                                            patternScore += 1.0;
                                                        } else if (diff < 1.0) {
                                                            patternScore += 0.5;
                                                            
                                                            // Additional analysis for medium differences
                                                            for (int k = j + 1; k < Math.min(j + 3, values.size()); k++) {
                                                                U futureValue = values.get(k);
                                                                if (futureValue != null) {
                                                                    double futureDiff = Math.abs(futureValue.doubleValue() - 
                                                                                                nextValue.doubleValue());
                                                                    if (Math.abs(futureDiff - diff) < 0.05) {
                                                                        patternScore += 0.2; // Consistency bonus
                                                                    }
                                                                }
                                                            }
                                                        } else {
                                                            patternScore -= 0.1; // Penalty for large differences
                                                        }
                                                    }
                                                }
                                            }
                                            
                                            keyAnalysis.put("pattern_" + analysisPass, patternScore);
                                        }
                                    }
                                } finally {
                                    lock.readLock().unlock();
                                }
                                
                                // Stage 3: Cross-reference analysis
                                if (!keyAnalysis.isEmpty()) {
                                    double crossRefScore = 0.0;
                                    
                                    // Compare with other keys (complex nested comparison)
                                    for (T otherKey : threadKeys) {
                                        if (!otherKey.equals(key)) {
                                            try {
                                                int comparison = key.compareTo(otherKey);
                                                if (comparison != 0) {
                                                    // Complex comparison logic
                                                    double similarity = 1.0 / (1.0 + Math.abs(comparison));
                                                    crossRefScore += similarity * 0.1;
                                                    
                                                    if (crossRefScore > 5.0) break; // Limit computation
                                                }
                                            } catch (ClassCastException e) {
                                                // Handle comparison failures
                                                crossRefScore += 0.01;
                                            }
                                        }
                                    }
                                    
                                    keyAnalysis.put("cross_ref", crossRefScore);
                                }
                                
                                threadResults.put("key_" + key.toString(), keyAnalysis);
                                processedItems.incrementAndGet();
                                
                            } catch (Exception e) {
                                threadResults.put("error_" + key.toString(), e.getMessage());
                            }
                        }
                        
                        // Thread completion statistics
                        threadResults.put("thread_id", currentThreadId);
                        threadResults.put("processed_count", threadKeys.size());
                        threadResults.put("completion_time", System.nanoTime());
                        
                    } catch (Exception e) {
                        threadResults.put("thread_error", e.getMessage());
                    } finally {
                        latch.countDown();
                    }
                    
                    return threadResults;
                });
                
                futures.add(future);
            }
            
            // Wait for all threads to complete
            try {
                latch.await(30, TimeUnit.SECONDS);
                
                // Collect results from all threads
                for (int i = 0; i < futures.size(); i++) {
                    try {
                        Future<Map<String, Object>> future = futures.get(i);
                        if (future.isDone()) {
                            Map<String, Object> threadResult = future.get();
                            analysisResults.putAll(threadResult);
                        } else {
                            analysisResults.put("thread_" + i + "_timeout", true);
                        }
                    } catch (Exception e) {
                        analysisResults.put("thread_" + i + "_error", e.getMessage());
                    }
                }
                
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                analysisResults.put("interrupted", true);
            }
            
            // Final analysis aggregation
            analysisResults.put("total_processed", processedItems.get());
            analysisResults.put("analysis_timestamp", System.currentTimeMillis());
            
            return analysisResults;
        });
    }
    
    // Add data method for testing
    public void addData(T key, U value) {
        lock.writeLock().lock();
        try {
            primaryData.computeIfAbsent(key, k -> new ArrayList<>()).add(value);
        } finally {
            lock.writeLock().unlock();
        }
    }
    
    // Cleanup method
    public void shutdown() {
        executorService.shutdown();
        try {
            if (!executorService.awaitTermination(5, TimeUnit.SECONDS)) {
                executorService.shutdownNow();
            }
        } catch (InterruptedException e) {
            executorService.shutdownNow();
            Thread.currentThread().interrupt();
        }
    }
}

// Complex main class with comprehensive testing
public class ComplexJavaTest {
    
    // Nested static class for additional complexity
    public static class ReflectionTestHelper {
        @ProcessingMetadata(value = "Test reflection processing", priority = 3)
        public static void performReflectionAnalysis(Class<?> targetClass) {
            System.out.println("\n🔍 Performing reflection analysis on: " + targetClass.getSimpleName());
            
            // Analyze methods with complex nested loops
            Method[] methods = targetClass.getDeclaredMethods();
            Map<String, Integer> annotationCounts = new HashMap<>();
            
            for (Method method : methods) {
                Annotation[] annotations = method.getAnnotations();
                
                for (Annotation annotation : annotations) {
                    String annotationType = annotation.annotationType().getSimpleName();
                    annotationCounts.merge(annotationType, 1, Integer::sum);
                    
                    // Complex annotation analysis
                    if (annotation instanceof ComplexOperation) {
                        ComplexOperation complexOp = (ComplexOperation) annotation;
                        System.out.println("  Complex method: " + method.getName() + 
                                         " (complexity: " + complexOp.complexity() + ")");
                        
                        // Analyze method parameters with nested loops
                        Parameter[] parameters = method.getParameters();
                        for (int i = 0; i < parameters.length; i++) {
                            Parameter param = parameters[i];
                            Type paramType = param.getParameterizedType();
                            
                            // Deep type analysis
                            if (paramType instanceof ParameterizedType) {
                                ParameterizedType pType = (ParameterizedType) paramType;
                                Type[] typeArgs = pType.getActualTypeArguments();
                                
                                for (int j = 0; j < typeArgs.length; j++) {
                                    System.out.println("    Param " + i + " type arg " + j + ": " + typeArgs[j]);
                                    
                                    // Nested analysis of type arguments
                                    if (typeArgs[j] instanceof ParameterizedType) {
                                        ParameterizedType nestedType = (ParameterizedType) typeArgs[j];
                                        Type[] nestedArgs = nestedType.getActualTypeArguments();
                                        
                                        for (Type nestedArg : nestedArgs) {
                                            System.out.println("      Nested type: " + nestedArg);
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            
            System.out.println("  Annotation summary: " + annotationCounts);
        }
    }
    
    public static void main(String[] args) {
        System.out.println("🧪 Starting Complex Java CodeGreen Test");
        System.out.println("=======================================");
        
        try {
            // Test 1: Generic container operations
            System.out.println("\n📦 Testing generic container operations:");
            
            AdvancedContainer<String, Integer, String> container = new AdvancedContainer<>();
            
            // Populate with test data using complex loops
            String[] testKeys = {"alpha", "beta", "gamma", "delta", "epsilon"};
            Random random = new Random(12345);
            
            for (String key : testKeys) {
                int valueCount = 5 + random.nextInt(10);
                
                for (int i = 0; i < valueCount; i++) {
                    Integer value = random.nextInt(1000) - 500; // -500 to 499
                    container.addData(key, value);
                }
            }
            
            // Test complex transformation
            Map<String, List<Integer>> testData = new HashMap<>();
            for (String key : testKeys) {
                List<Integer> values = new ArrayList<>();
                for (int i = 0; i < 8; i++) {
                    values.add(random.nextInt(200) - 100);
                }
                testData.put(key, values);
            }
            
            CompletableFuture<AdvancedContainer.ProcessingResult<Map<String, Double>>> transformFuture = 
                container.processWithComplexTransformation(
                    testData,
                    x -> x.doubleValue() * 1.5 + Math.sin(x.doubleValue()),
                    key -> key.length() > 4,
                    (key, value) -> value + key.length() * 0.1
                );
            
            AdvancedContainer.ProcessingResult<Map<String, Double>> transformResult = 
                transformFuture.get(10, TimeUnit.SECONDS);
            
            System.out.println("Transformation completed in " + 
                             transformResult.getProcessingTime() / 1_000_000 + " ms");
            System.out.println("Results: " + transformResult.getResult().size() + " keys processed");
            System.out.println("Statistics: " + transformResult.getStatistics());
            
            // Test 2: Stream analysis
            System.out.println("\n🌊 Testing stream analysis:");
            
            Optional<Double> streamResult = container.performComplexStreamAnalysis(
                Arrays.asList(testKeys).subList(0, 3)
            );
            
            if (streamResult.isPresent()) {
                System.out.println("Stream analysis result: " + streamResult.get());
            } else {
                System.out.println("Stream analysis returned no result");
            }
            
            // Test 3: Error recovery processing
            System.out.println("\n🔄 Testing error recovery processing:");
            
            List<String> errorTestKeys = Arrays.asList("test1", "test2", null, "test4", "");
            
            List<AdvancedContainer.ProcessingResult<String>> errorResults = 
                container.processBatchWithErrorRecovery(errorTestKeys, key -> {
                    if (key == null) {
                        throw new RuntimeException("Null key provided");
                    }
                    if (key.isEmpty()) {
                        throw new ProcessingException("Empty key not allowed", 1001, "VALIDATION");
                    }
                    return "PROCESSED_" + key.toUpperCase();
                });
            
            System.out.println("Error recovery test completed with " + errorResults.size() + " results:");
            for (int i = 0; i < errorResults.size(); i++) {
                AdvancedContainer.ProcessingResult<String> result = errorResults.get(i);
                System.out.println("  Result " + i + ": " + result.getResult() + 
                                 " (time: " + result.getProcessingTime() / 1_000_000 + " ms)");
                if (!result.getWarnings().isEmpty()) {
                    System.out.println("    Warnings: " + result.getWarnings());
                }
            }
            
            // Test 4: Concurrent analysis
            System.out.println("\n⚡ Testing concurrent analysis:");
            
            CompletableFuture<Map<String, Object>> concurrentFuture = 
                container.performConcurrentAnalysis(4);
            
            Map<String, Object> concurrentResults = concurrentFuture.get(30, TimeUnit.SECONDS);
            
            System.out.println("Concurrent analysis completed:");
            System.out.println("  Total processed: " + concurrentResults.get("total_processed"));
            System.out.println("  Result keys: " + concurrentResults.keySet().size());
            
            // Count different result types
            long keyResults = concurrentResults.keySet().stream()
                .filter(key -> key.startsWith("key_"))
                .count();
            long errorResults = concurrentResults.keySet().stream()
                .filter(key -> key.startsWith("error_"))
                .count();
            
            System.out.println("  Successful analyses: " + keyResults);
            System.out.println("  Errors: " + errorResults);
            
            // Test 5: Reflection analysis
            System.out.println("\n🔍 Testing reflection capabilities:");
            
            ReflectionTestHelper.performReflectionAnalysis(AdvancedContainer.class);
            ReflectionTestHelper.performReflectionAnalysis(ComplexJavaTest.class);
            
            // Test 6: Complex nested loop structures
            System.out.println("\n🔄 Testing complex nested loop structures:");
            
            int[][][] threeDimensionalArray = new int[5][4][3];
            int totalSum = 0;
            int processedElements = 0;
            
            // Initialize with complex pattern
            for (int i = 0; i < threeDimensionalArray.length; i++) {
                for (int j = 0; j < threeDimensionalArray[i].length; j++) {
                    for (int k = 0; k < threeDimensionalArray[i][j].length; k++) {
                        threeDimensionalArray[i][j][k] = i * 100 + j * 10 + k;
                    }
                }
            }
            
            // Complex processing with nested loops and conditions
            for (int x = 0; x < threeDimensionalArray.length; x++) {
                for (int y = 0; y < threeDimensionalArray[x].length; y++) {
                    for (int z = 0; z < threeDimensionalArray[x][y].length; z++) {
                        int currentValue = threeDimensionalArray[x][y][z];
                        
                        // Complex nested processing
                        if (currentValue % 2 == 0) {
                            // Even values: multiple processing stages
                            int processedValue = currentValue;
                            
                            for (int stage = 1; stage <= 3; stage++) {
                                processedValue = processedValue / stage + stage;
                                
                                // Inner validation loop
                                int validationAttempts = 0;
                                while (validationAttempts < stage && processedValue > 0) {
                                    if (processedValue % (stage + 1) == 0) {
                                        processedValue *= 2;
                                    } else {
                                        processedValue += stage;
                                    }
                                    validationAttempts++;
                                }
                                
                                // Early termination condition
                                if (processedValue > 1000) {
                                    processedValue = processedValue % 100;
                                    break;
                                }
                            }
                            
                            totalSum += processedValue;
                            processedElements++;
                            
                        } else {
                            // Odd values: different processing path
                            int iterations = 0;
                            int tempValue = currentValue;
                            
                            do {
                                tempValue = tempValue * 3 + 1;
                                if (tempValue % 2 == 0) {
                                    tempValue /= 2;
                                }
                                iterations++;
                                
                                // Complex nested condition
                                if (iterations % 5 == 0) {
                                    for (int bonus = 1; bonus <= iterations % 3 + 1; bonus++) {
                                        tempValue += bonus * x * y * z;
                                        
                                        if (tempValue > 10000) {
                                            tempValue %= 1000;
                                            break;
                                        }
                                    }
                                }
                                
                            } while (tempValue != 1 && iterations < 50);
                            
                            totalSum += iterations;
                            processedElements++;
                        }
                    }
                }
            }
            
            System.out.println("Nested loop processing completed:");
            System.out.println("  Total elements processed: " + processedElements);
            System.out.println("  Final sum: " + totalSum);
            System.out.println("  Average value: " + (totalSum / (double) processedElements));
            
            // Cleanup
            container.shutdown();
            
            System.out.println("\n✅ All Java tests completed successfully!");
            
        } catch (Exception e) {
            System.err.println("\n❌ Test failed with exception: " + e.getMessage());
            e.printStackTrace();
            System.exit(1);
        }
    }
}