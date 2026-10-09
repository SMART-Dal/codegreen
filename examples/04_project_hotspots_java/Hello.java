public class Hello {
    public static long slowSum(int n) {
        long acc = 0;
        for (int i = 0; i < n; i++) acc += (long) i * i;
        return acc;
    }
    public static int warm() {
        int s = 0;
        for (int i = 0; i < 1000; i++) s += i;
        return s;
    }
    public static void main(String[] args) {
        warm();
        System.out.println(slowSum(30_000_000));
    }
}
