#!/usr/bin/env python3
"""
Bridge script for C++ to Python instrumentation system - Analysis phase
Called by PythonBridgeAdapter to analyze code and generate checkpoints
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
            print("ERROR: Usage: bridge_analyze.py <source_file>", file=sys.stderr)
            sys.exit(1)
        
        source_file = sys.argv[1]
        
        try:
            # Read source code
            with open(source_file, 'r') as f:
                source_code = f.read()
            
            # Initialize language engine
            engine = LanguageEngine()
            
            # Analyze the code
            analysis_result = engine.analyze_code(source_code, 'python')
            
            if analysis_result.success:
                print(f"ANALYSIS_SUCCESS: Found {len(analysis_result.instrumentation_points)} instrumentation points")
                
                # Output each instrumentation point
                for i, point in enumerate(analysis_result.instrumentation_points):
                    print(f"CHECKPOINT_{i}: {point.type}:{point.name}:{point.line}:{point.column}")
                    
            else:
                error_msg = analysis_result.error if analysis_result.error else "Unknown analysis error"
                print(f"ANALYSIS_ERROR: {error_msg}", file=sys.stderr)
                sys.exit(1)
                
        except FileNotFoundError:
            print(f"ERROR: Source file not found: {source_file}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: Analysis failed: {str(e)}", file=sys.stderr)
            sys.exit(1)

    if __name__ == "__main__":
        main()
        
except ImportError as e:
    print(f"ERROR: Failed to import instrumentation modules: {e}", file=sys.stderr)
    print("Make sure the instrumentation system is properly installed", file=sys.stderr)
    sys.exit(1)