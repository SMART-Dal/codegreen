"""
Integration layer for CodeGreen Language System

Provides unified interface for code analysis and instrumentation with
extensible multi-language architecture.
"""

import logging
from typing import List, Optional, Dict, Any
from pathlib import Path

from .manager import get_plugin_manager
from .registry import get_language_adapter, get_adapter_for_file
from .base import CodeCheckpoint, InstrumentationPoint

logger = logging.getLogger(__name__)


class LanguageService:
    """
    High-level service for language operations in CodeGreen.
    
    Provides a unified interface for the plugin-based language system.
    """
    
    def __init__(self):
        self.plugin_manager = get_plugin_manager()
        self._v1_fallback_enabled = True
        
    def get_supported_languages(self) -> List[str]:
        """Get list of all supported language identifiers"""
        return self.plugin_manager.registry.list_supported_languages()
    
    def get_supported_extensions(self) -> List[str]:
        """Get list of all supported file extensions"""
        return self.plugin_manager.registry.list_supported_extensions()
    
    def is_language_supported(self, language_id: str) -> bool:
        """Check if a language is supported"""
        return self.plugin_manager.registry.is_supported(language_id)
    
    def is_file_supported(self, filename: str) -> bool:
        """Check if a file type is supported based on extension"""
        adapter = get_adapter_for_file(filename)
        return adapter is not None
    
    def analyze_source_code(
        self, 
        source_code: str, 
        language_id: str = None, 
        filename: str = None
    ) -> Dict[str, Any]:
        """
        Analyze source code and generate instrumentation points.
        
        Args:
            source_code: Source code to analyze
            language_id: Explicit language identifier  
            filename: Filename for extension-based language detection
            
        Returns:
            Dictionary containing analysis results
        """
        # Determine language
        adapter = None
        detected_language = None
        
        if language_id:
            adapter = get_language_adapter(language_id)
            detected_language = language_id
        elif filename:
            adapter = get_adapter_for_file(filename)
            if adapter:
                detected_language = adapter.language_id
        
        if not adapter:
            return {
                'success': False,
                'error': f'No adapter available for language: {language_id or "unknown"}',
                'language': detected_language,
                'checkpoints': [],
                'instrumentation_points': [],
                'analysis_suggestions': []
            }
        
        try:
            # Generate instrumentation points
            instrumentation_points = adapter._generate_instrumentation_points_treesitter(source_code) \
                if adapter.parser else adapter._generate_instrumentation_points_fallback(source_code)
            
            # Convert to legacy checkpoints for backward compatibility
            checkpoints = [CodeCheckpoint.from_instrumentation_point(point) for point in instrumentation_points]
            
            # Get optimization suggestions
            suggestions = adapter.analyze_code(source_code)
            
            return {
                'success': True,
                'language': detected_language,
                'parser_available': adapter.parser is not None,
                'instrumentation_points': len(instrumentation_points),
                'checkpoints': checkpoints,
                'analysis_suggestions': suggestions,
                'metadata': {
                    'adapter_class': adapter.__class__.__name__,
                    'query_based': adapter.parser is not None,
                    'fallback_mode': adapter.parser is None
                }
            }
            
        except Exception as e:
            logger.error(f"Error analyzing {detected_language} code: {e}")
            return {
                'success': False,
                'error': str(e),
                'language': detected_language,
                'checkpoints': [],
                'instrumentation_points': [],
                'analysis_suggestions': []
            }
    
    def instrument_source_code(
        self, 
        source_code: str, 
        language_id: str = None, 
        filename: str = None
    ) -> Dict[str, Any]:
        """
        Instrument source code with energy measurement calls.
        
        Args:
            source_code: Source code to instrument
            language_id: Explicit language identifier
            filename: Filename for extension-based language detection
            
        Returns:
            Dictionary containing instrumented code and metadata
        """
        analysis_result = self.analyze_source_code(source_code, language_id, filename)
        
        if not analysis_result['success']:
            return analysis_result
        
        adapter = get_language_adapter(analysis_result['language']) or get_adapter_for_file(filename)
        if not adapter:
            return {
                'success': False,
                'error': 'Adapter not available for instrumentation',
                'instrumented_code': source_code
            }
        
        try:
            instrumented_code = adapter.instrument_code(source_code, analysis_result['checkpoints'])
            
            return {
                'success': True,
                'language': analysis_result['language'],
                'instrumented_code': instrumented_code,
                'checkpoints_added': len(analysis_result['checkpoints']),
                'original_lines': len(source_code.split('\n')),
                'instrumented_lines': len(instrumented_code.split('\n')),
                'metadata': analysis_result['metadata']
            }
            
        except Exception as e:
            logger.error(f"Error instrumenting {analysis_result['language']} code: {e}")
            return {
                'success': False,
                'error': str(e),
                'instrumented_code': source_code
            }
    
    def get_language_info(self, language_id: str) -> Dict[str, Any]:
        """Get detailed information about a supported language"""
        adapter = get_language_adapter(language_id)
        if not adapter:
            return {
                'supported': False,
                'language_id': language_id
            }
        
        return {
            'supported': True,
            'language_id': adapter.language_id,
            'file_extensions': adapter.get_file_extensions(),
            'adapter_class': adapter.__class__.__name__,
            'parser_available': adapter.parser is not None,
            'queries_available': len(adapter._queries) if hasattr(adapter, '_queries') else 0,
            'query_names': list(adapter._queries.keys()) if hasattr(adapter, '_queries') else [],
            'features': {
                'tree_sitter_analysis': adapter.parser is not None,
                'fallback_analysis': True,
                'code_instrumentation': True,
                'optimization_analysis': True
            }
        }
    
    def batch_analyze_files(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        Analyze multiple files in batch.
        
        Args:
            file_paths: List of file paths to analyze
            
        Returns:
            Dictionary with results for each file
        """
        results = {}
        summary = {
            'total_files': len(file_paths),
            'successful': 0,
            'failed': 0,
            'unsupported': 0,
            'languages_detected': set()
        }
        
        for file_path in file_paths:
            path = Path(file_path)
            
            if not path.exists():
                results[file_path] = {
                    'success': False,
                    'error': 'File not found'
                }
                summary['failed'] += 1
                continue
            
            if not self.is_file_supported(path.name):
                results[file_path] = {
                    'success': False,
                    'error': 'Unsupported file type'
                }
                summary['unsupported'] += 1
                continue
            
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    source_code = f.read()
                
                result = self.analyze_source_code(source_code, filename=path.name)
                results[file_path] = result
                
                if result['success']:
                    summary['successful'] += 1
                    summary['languages_detected'].add(result['language'])
                else:
                    summary['failed'] += 1
                    
            except Exception as e:
                results[file_path] = {
                    'success': False,
                    'error': f'Error reading file: {str(e)}'
                }
                summary['failed'] += 1
        
        return {
            'results': results,
            'summary': {
                **summary,
                'languages_detected': list(summary['languages_detected'])
            }
        }


# Global service instance
_language_service = None


def get_language_service() -> LanguageService:
    """Get global language service instance"""
    global _language_service
    if _language_service is None:
        _language_service = LanguageService()
    return _language_service


# Convenience functions for backward compatibility
def analyze_code(source_code: str, language: str) -> List[CodeCheckpoint]:
    """
    Legacy function for backward compatibility with existing CLI.
    
    Args:
        source_code: Source code to analyze
        language: Language identifier
        
    Returns:
        List of legacy CodeCheckpoint objects
    """
    service = get_language_service()
    result = service.analyze_source_code(source_code, language_id=language)
    return result.get('checkpoints', [])


def instrument_code(source_code: str, checkpoints: List[CodeCheckpoint], language: str) -> str:
    """
    Legacy function for backward compatibility with existing CLI.
    
    Args:
        source_code: Source code to instrument
        checkpoints: List of checkpoints to add
        language: Language identifier
        
    Returns:
        Instrumented source code
    """
    service = get_language_service()
    adapter = get_language_adapter(language)
    
    if adapter:
        return adapter.instrument_code(source_code, checkpoints)
    else:
        logger.warning(f"No adapter found for language {language}, returning original code")
        return source_code