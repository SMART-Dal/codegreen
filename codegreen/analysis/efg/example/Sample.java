public class Sample {
    public static int hot(int n) {
        int total = 0;
        for (int i = 0; i < n; i++) {
            if (i % 2 == 0) { total += compute(i); }
            else { total -= 1; }
        }
        String s = new String("x");
        return total + s.length();
    }
    static int compute(int x) { return x * x; }
}
