#!/usr/bin/env python3
"""
Setup script for CodeGreen publishing preparation.
"""

import os
import sys
import subprocess
from pathlib import Path

def create_cli_wrapper():
    """Create a proper CLI wrapper for the hybrid tool."""
    cli_content = '''#!/usr/bin/env python3
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
'''
    
    with open("codegreen_cli.py", "w") as f:
        f.write(cli_content)
    
    print("✅ Created CLI wrapper: codegreen_cli.py")

def update_pyproject():
    """Update pyproject.toml for better packaging."""
    pyproject_updates = '''
# Add to [project.scripts]
[project.scripts]
codegreen = "codegreen_cli:main"

# Add to dependencies
dependencies = [
    "typer>=0.17.0",
    "rich>=12.0.0", 
    "pydantic>=1.10.0",
    "psutil>=5.9.0",
    "packaging>=21.0",
    "markdown-it-py<4.0.0,>=3.0.0",
    "tree-sitter>=0.20.0",
    "tree-sitter-language-pack>=0.1.0"
]

# Add build requirements
[build-system]
requires = [
    "setuptools>=64", 
    "wheel", 
    "cmake-build-extension>=0.6.0", 
    "pybind11>=3.0.0",
    "tree-sitter>=0.20.0"
]
'''
    
    print("✅ Update pyproject.toml with the following:")
    print(pyproject_updates)

def create_install_script():
    """Create installation script."""
    install_script = '''#!/bin/bash
# CodeGreen Installation Script

set -e

echo "🚀 Installing CodeGreen..."

# Check Python version
python3 --version || { echo "❌ Python 3.8+ required"; exit 1; }

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip3 install -r requirements.txt

# Build C++ components
echo "🔨 Building C++ components..."
mkdir -p build
cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)

# Install Python package
echo "📦 Installing Python package..."
cd ..
pip3 install -e .

echo "✅ CodeGreen installed successfully!"
echo "Usage: codegreen python3 script.py"
'''
    
    with open("install.sh", "w") as f:
        f.write(install_script)
    
    os.chmod("install.sh", 0o755)
    print("✅ Created installation script: install.sh")

def create_dockerfile():
    """Create Dockerfile for easy deployment."""
    dockerfile_content = '''FROM ubuntu:22.04

# Install dependencies
RUN apt-get update && apt-get install -y \\
    python3 python3-pip python3-dev \\
    build-essential cmake \\
    libjsoncpp-dev libcurl4-openssl-dev libsqlite3-dev \\
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy source code
COPY . .

# Install Python dependencies
RUN pip3 install -r requirements.txt

# Build C++ components
RUN mkdir build && cd build && \\
    cmake .. -DCMAKE_BUILD_TYPE=Release && \\
    make -j$(nproc)

# Install Python package
RUN pip3 install -e .

# Set entry point
ENTRYPOINT ["codegreen"]
'''
    
    with open("Dockerfile", "w") as f:
        f.write(dockerfile_content)
    
    print("✅ Created Dockerfile for containerized deployment")

def main():
    """Main setup function."""
    print("🔧 Setting up CodeGreen for publishing...")
    
    create_cli_wrapper()
    update_pyproject()
    create_install_script()
    create_dockerfile()
    
    print("\n🎉 Setup complete! Next steps:")
    print("1. Update pyproject.toml with the suggested changes")
    print("2. Test installation: ./install.sh")
    print("3. Test CLI: codegreen --help")
    print("4. Create GitHub release")
    print("5. Publish to PyPI: python -m build && twine upload dist/*")

if __name__ == "__main__":
    main()
