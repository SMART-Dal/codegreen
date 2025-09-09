"""
CodeGreen Language Support System

This module provides extensible, plugin-based language support using tree-sitter
for precise code analysis and instrumentation point detection.

Key Features:
- Dynamic parser loading via tree-sitter-languages
- Query-based instrumentation point detection  
- Graceful fallback to regex-based analysis
- Plugin architecture for easy language addition
"""

from .registry import LanguageRegistry, get_language_adapter
from .base import LanguageAdapter, InstrumentationPoint, CodeCheckpoint
from .manager import LanguagePluginManager
from .integration import get_language_service

__all__ = [
    'LanguageRegistry',
    'LanguageAdapter', 
    'InstrumentationPoint',
    'CodeCheckpoint',
    'LanguagePluginManager',
    'get_language_adapter',
    'get_language_service'
]