public class java_inner {
    private int x = 10;
    
    class Inner {
        void display() {
            System.out.println("Inner: " + x);
        }
    }
    
    static class StaticNested {
        void show() {
            System.out.println("Static Nested");
        }
    }
    
    public static void main(String[] args) {
        java_inner outer = new java_inner();
        java_inner.Inner inner = outer.new Inner();
        inner.display();
        
        java_inner.StaticNested staticNested = new java_inner.StaticNested();
        staticNested.show();
    }
}