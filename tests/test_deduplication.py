#!/usr/bin/env python3
"""
Test script to verify deduplication logic works
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.instrumentation.language_engine import LanguageEngine

def test_deduplication():
    print("🧪 Testing deduplication logic...")
    
    # Enable debug logging
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    # Simple Python code that should produce duplicate function_exit points
    source_code = '''def hello():
    print("Hello from CodeGreen!")
    return 42
'''
    
    engine = LanguageEngine()
    result = engine.analyze_code(source_code, language='python', filename='test.py')
    
    print(f"Analysis success: {result.success}")
    print(f"Language: {result.language}")
    print(f"Analysis method: {result.metadata.get('analysis_method', 'unknown')}")
    print(f"Total instrumentation points: {len(result.instrumentation_points)}")
    
    # Group points by type
    by_type = {}
    for point in result.instrumentation_points:
        point_type = point.type
        if point_type not in by_type:
            by_type[point_type] = []
        by_type[point_type].append(point)
    
    print("\n📊 Instrumentation points by type:")
    for point_type, points in by_type.items():
        print(f"  {point_type}: {len(points)} points")
        for point in points:
            print(f"    - {point.id} ({point.name})")
    
    # Check for duplicates in function_exit
    function_exit_points = by_type.get('function_exit', [])
    if len(function_exit_points) > 1:
        print(f"\n❌ FAILURE: Found {len(function_exit_points)} function_exit points (should be 1 after deduplication)")
        return False
    elif len(function_exit_points) == 1:
        print(f"\n✅ SUCCESS: Found exactly 1 function_exit point (deduplication worked!)")
        return True
    else:
        print(f"\n⚠️  WARNING: No function_exit points found")
        return True

if __name__ == '__main__':
    success = test_deduplication()
    sys.exit(0 if success else 1)