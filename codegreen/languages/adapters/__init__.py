"""
Built-in language adapters for CodeGreen

Each adapter provides both tree-sitter based analysis (when available)
and fallback regex-based analysis for maximum compatibility.
"""

from .python import PythonAdapter
from .c import CAdapter
from .cpp import CppAdapter  
from .java import JavaAdapter

__all__ = ['PythonAdapter', 'CAdapter', 'CppAdapter', 'JavaAdapter']