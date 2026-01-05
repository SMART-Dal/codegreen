#include <stdio.h>
#include <stdlib.h>

// Complex Memory: Linked List operations
typedef struct Node {
    int data;
    struct Node* next;
} Node;

Node* create_node(int data) {
    Node* newNode = (Node*)malloc(sizeof(Node));
    newNode->data = data;
    newNode->next = NULL;
    return newNode;
}

void process_list() {
    Node* head = NULL;
    // Build list
    for (int i = 0; i < 20000; i++) {
        Node* n = create_node(i);
        n->next = head;
        head = n;
    }
    
    // Traverse
    long sum = 0;
    Node* curr = head;
    while (curr) {
        sum += curr->data;
        curr = curr->next;
    }
    
    // Cleanup
    while (head) {
        Node* temp = head;
        head = head->next;
        free(temp);
    }
    printf("Sum: %ld\n", sum);
}

int main() {
    process_list();
    return 0;
}