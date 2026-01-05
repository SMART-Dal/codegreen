import java.util.*;

// Complex Java: Collections and Streams
public class java_complex_07_collections {
    public static void main(String[] args) {
        List<Double> numbers = new ArrayList<>();
        Random rand = new Random();
        
        for (int i = 0; i < 20000; i++) {
            numbers.add(rand.nextDouble());
        }
        
        // Complex stream operation
        double sum = numbers.stream()
            .filter(n -> n > 0.5)
            .map(Math::sqrt)
            .reduce(0.0, Double::sum);
            
        System.out.println("Sum: " + sum);
    }
}