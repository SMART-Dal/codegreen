#!/usr/bin/env python3
"""
Bridge script for C++ to call Python LanguageEngine for instrumentation.
"""
import sys
import os
from pathlib import Path

# Add current directory to path to find modules
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir.parent))

try:
    from language_engine import LanguageEngine
except ImportError:
    try:
        from src.instrumentation.language_engine import LanguageEngine
    except ImportError:
        print("Error: Could not import LanguageEngine")
        sys.exit(1)

def main():
    if len(sys.argv) < 2:
        print("Usage: bridge_instrument.py <source_file>")
        sys.exit(1)

    source_file = sys.argv[1]
    if not os.path.exists(source_file):
        print(f"Error: File not found: {source_file}")
        sys.exit(1)

    try:
        with open(source_file, 'r') as f:
            source_code = f.read()
            
        engine = LanguageEngine()
        # First analyze to get points
        result = engine.analyze_code(source_code, filename=source_file)
        
        if not result.success:
            # If analysis failed, just output original code (fail safe)
            print(source_code)
            sys.exit(0)
            
        # Then instrument
        instrumented_code = engine.instrument_code(
            source_code, 
            result.instrumentation_points, 
            result.language
        )
        
        # Output instrumented code to stdout
        print(instrumented_code)
            
    except Exception as e:
        # Fallback to original code
        try:
            with open(source_file, 'r') as f:
                print(f.read())
        except:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()
