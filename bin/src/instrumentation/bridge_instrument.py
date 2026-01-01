#!/usr/bin/env python3
"""
Bridge script for C++ to Python instrumentation system - Instrumentation phase
Called by PythonBridgeAdapter to instrument code with energy measurement checkpoints
"""

import sys
import os
from pathlib import Path

# Add instrumentation directory to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from language_engine import LanguageEngine
    
    def main():
        if len(sys.argv) != 2:
            print("ERROR: Usage: bridge_instrument.py <source_file>", file=sys.stderr)
            sys.exit(1)
        
        source_file = sys.argv[1]
        
        try:
            # Read source code
            with open(source_file, 'r') as f:
                source_code = f.read()
            
            # Initialize language engine
            engine = LanguageEngine()
            
            # Instrument the code (analyze first, then instrument)
            analysis_result = engine.analyze_code(source_code, 'python')
            if analysis_result.success:
                instrumented_code = engine.instrument_code(source_code, analysis_result.instrumentation_points, 'python')
                # Output the instrumented code (engine.instrument_code returns string, not result object)
                print(instrumented_code)
            else:
                error_msg = analysis_result.error if analysis_result.error else "Unknown analysis error"
                print(f"ERROR: Analysis failed: {error_msg}", file=sys.stderr)
                print(source_code)  # Output original code as fallback
                sys.exit(1)
                
        except FileNotFoundError:
            print(f"ERROR: Source file not found: {source_file}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: Instrumentation failed: {str(e)}", file=sys.stderr)
            # Output original code as fallback
            try:
                with open(source_file, 'r') as f:
                    print(f.read())
            except:
                pass
            sys.exit(1)

    if __name__ == "__main__":
        main()
        
except ImportError as e:
    print(f"ERROR: Failed to import instrumentation modules: {e}", file=sys.stderr)
    print("Make sure the instrumentation system is properly installed", file=sys.stderr)
    sys.exit(1)