#!/usr/bin/env python3
"""
Test instrumentation for all supported languages to verify deduplication works
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.instrumentation.language_engine import LanguageEngine

def test_language(language, source_code, filename):
    print(f"\n🧪 Testing {language} instrumentation...")
    
    engine = LanguageEngine()
    result = engine.analyze_code(source_code, language=language, filename=filename)
    
    print(f"✓ Analysis success: {result.success}")
    print(f"✓ Language: {result.language}")
    print(f"✓ Analysis method: {result.metadata.get('analysis_method', 'unknown')}")
    print(f"✓ Total instrumentation points: {len(result.instrumentation_points)}")
    
    if not result.success:
        print(f"❌ Error: {result.error}")
        return False
    
    # Group points by type
    by_type = {}
    for point in result.instrumentation_points:
        point_type = point.type
        if point_type not in by_type:
            by_type[point_type] = []
        by_type[point_type].append(point)
    
    print("📊 Instrumentation points by type:")
    has_duplicates = False
    for point_type, points in by_type.items():
        print(f"  {point_type}: {len(points)} points")
        
        # Check for function_exit duplicates
        if point_type == 'function_exit' and len(points) > 1:
            print(f"    ⚠️  Multiple function_exit points detected:")
            for point in points:
                print(f"      - {point.id} ({point.name})")
            has_duplicates = True
        else:
            for point in points:
                print(f"    - {point.id} ({point.name})")
    
    if has_duplicates:
        print(f"❌ {language} has function_exit duplicates")
        return False
    else:
        print(f"✅ {language} instrumentation looks clean!")
        return True

def main():
    test_cases = [
        ('python', '''def hello():
    print("Hello from Python!")
    return 42
''', 'test.py'),
        
        ('c', '''#include <stdio.h>

int hello() {
    printf("Hello from C!\\n");
    return 42;
}
''', 'test.c'),
        
        ('cpp', '''#include <iostream>

int hello() {
    std::cout << "Hello from C++!" << std::endl;
    return 42;
}
''', 'test.cpp'),
        
        ('java', '''public class Test {
    public static int hello() {
        System.out.println("Hello from Java!");
        return 42;
    }
}
''', 'Test.java'),
        
        ('javascript', '''function hello() {
    console.log("Hello from JavaScript!");
    return 42;
}
''', 'test.js')
    ]
    
    print("🚀 Testing instrumentation for all supported languages...")
    print("=" * 60)
    
    success_count = 0
    total_count = len(test_cases)
    
    for language, source_code, filename in test_cases:
        success = test_language(language, source_code, filename)
        if success:
            success_count += 1
        print("-" * 40)
    
    print(f"\n📊 Final Results: {success_count}/{total_count} languages passed")
    
    if success_count == total_count:
        print("🎉 ALL LANGUAGES PASSED! Deduplication is working correctly across all languages.")
        return True
    else:
        print(f"❌ {total_count - success_count} languages failed. Check the output above for details.")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)