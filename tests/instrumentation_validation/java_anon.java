interface Greeter {
    void greet();
}

public class java_anon {
    public static void main(String[] args) {
        Greeter g = new Greeter() {
            @Override
            public void greet() {
                System.out.println("Hello from anonymous class");
                helper();
            }
            
            private void helper() {
                System.out.println("Helper method");
            }
        };
        
        g.greet();
    }
}