#!/usr/bin/env python3
"""
Bridge script for C++ to call Python LanguageEngine for analysis.
"""
import sys
import os
import json
from pathlib import Path

# Add current directory to path to find modules
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir.parent))

try:
    from language_engine import LanguageEngine
except ImportError:
    # Try relative import if running from different context
    try:
        from src.instrumentation.language_engine import LanguageEngine
    except ImportError:
        print("Error: Could not import LanguageEngine")
        sys.exit(1)

def main():
    if len(sys.argv) < 2:
        print("Usage: bridge_analyze.py <source_file>")
        sys.exit(1)

    source_file = sys.argv[1]
    if not os.path.exists(source_file):
        print(f"Error: File not found: {source_file}")
        sys.exit(1)

    try:
        with open(source_file, 'r') as f:
            source_code = f.read()
            
        engine = LanguageEngine()
        result = engine.analyze_code(source_code, filename=source_file)
        
        if not result.success:
            print(f"Analysis failed: {result.error}")
            sys.exit(1)
            
        # Output checkpoints in a simple format for C++ adapter logging
        # or future JSON parsing
        print(f"Analysis complete: {len(result.instrumentation_points)} points found")
        for point in result.instrumentation_points:
            print(f"POINT|{point.id}|{point.type}|{point.name}|{point.line}|{point.column}")
            
    except Exception as e:
        print(f"Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
