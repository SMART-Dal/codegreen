#!/usr/bin/env python3
"""
CodeGreen CLI - Energy Monitoring and Code Optimization Tool
"""

import sys
import os
import subprocess
from pathlib import Path

def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("CodeGreen - Energy Monitoring and Code Optimization Tool")
        print("Usage: codegreen <language> <source_file> [args...]")
        print("       codegreen --init-sensors")
        print("       codegreen --help")
        sys.exit(1)
    
    # Get the C++ binary path
    cpp_binary = Path(__file__).parent / "bin" / "codegreen"
    
    if not cpp_binary.exists():
        print("Error: CodeGreen C++ binary not found. Please run 'pip install -e .' first.")
        sys.exit(1)
    
    # Forward all arguments to the C++ binary
    try:
        result = subprocess.run([str(cpp_binary)] + sys.argv[1:], check=True)
        sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except FileNotFoundError:
        print("Error: CodeGreen C++ binary not found. Please install the tool properly.")
        sys.exit(1)

if __name__ == "__main__":
    main()
