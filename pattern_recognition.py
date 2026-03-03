#!/usr/bin/env python3
"""
QuickFix Pattern Recognition System
=====================================

Advanced error pattern recognition and classification system for multiple programming languages.
Identifies common coding errors, syntax issues, and provides intelligent categorization.

Author: WorkspaceSentinel QuickFix System
Date: November 17, 2025
"""

import re
import json
import hashlib
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import difflib

class ErrorSeverity(Enum):
    CRITICAL = "critical"      # Breaks functionality
    HIGH = "high"             # Major issues
    MEDIUM = "medium"         # Standard problems
    LOW = "low"               # Minor issues
    STYLE = "style"           # Code style/formatting

class ErrorCategory(Enum):
    SYNTAX = "syntax"
    LOGIC = "logic"
    STYLE = "style"
    PERFORMANCE = "performance"
    SECURITY = "security"
    ACCESSIBILITY = "accessibility"
    COMPATIBILITY = "compatibility"
    DUPLICATION = "duplication"

@dataclass
class ErrorPattern:
    """Represents a detected error pattern"""
    pattern_id: str
    language: str
    category: ErrorCategory
    severity: ErrorSeverity
    pattern_regex: str
    description: str
    explanation: str
    common_causes: List[str]
    solutions: List[Dict[str, Any]]
    confidence: float = 0.0
    line_number: int = 0
    column_number: int = 0
    context: str = ""

class PatternRecognition:
    """Main pattern recognition engine"""
    
    def __init__(self):
        self.patterns = self._initialize_patterns()
        self.custom_patterns = {}
        self.learning_data = {}
        
    def _initialize_patterns(self) -> Dict[str, List[ErrorPattern]]:
        """Initialize default error patterns for different languages"""
        patterns = {
            'html': self._get_html_patterns(),
            'css': self._get_css_patterns(),
            'javascript': self._get_javascript_patterns(),
            'python': self._get_python_patterns(),
            'json': self._get_json_patterns(),
            'markdown': self._get_markdown_patterns()
        }
        return patterns
    
    def _get_html_patterns(self) -> List[ErrorPattern]:
        """HTML-specific error patterns"""
        return [
            ErrorPattern(
                pattern_id="html_unclosed_tag",
                language="html",
                category=ErrorCategory.SYNTAX,
                severity=ErrorSeverity.HIGH,
                pattern_regex=r'<(\w+)(?:[^>]*)>(?!.*</\1>)',
                description="Unclosed HTML tag",
                explanation="HTML tags must be properly closed to maintain document structure",
                common_causes=["Forgotten closing tag", "Nested tag conflicts", "Copy-paste errors"],
                solutions=[
                    {
                        "description": "Add missing closing tag",
                        "template": "</{tag}>",
                        "success_rate": 0.95,
                        "auto_applicable": True
                    },
                    {
                        "description": "Convert to self-closing tag if appropriate",
                        "template": "<{tag} />",
                        "success_rate": 0.8,
                        "auto_applicable": False
                    }
                ]
            ),
            ErrorPattern(
                pattern_id="html_duplicate_id",
                language="html",
                category=ErrorCategory.SYNTAX,
                severity=ErrorSeverity.MEDIUM,
                pattern_regex=r'id=["\']([^"\']+)["\'].*id=["\'](\1)["\']',
                description="Duplicate ID attributes",
                explanation="HTML IDs must be unique within a document",
                common_causes=["Copy-paste without updating IDs", "Template duplication"],
                solutions=[
                    {
                        "description": "Make IDs unique by adding suffix",
                        "template": "id=\"{original_id}_{suffix}\"",
                        "success_rate": 0.9,
                        "auto_applicable": True
                    }
                ]
            ),
            ErrorPattern(
                pattern_id="html_missing_alt",
                language="html",
                category=ErrorCategory.ACCESSIBILITY,
                severity=ErrorSeverity.MEDIUM,
                pattern_regex=r'<img(?![^>]*alt=)[^>]*>',
                description="Missing alt attribute on image",
                explanation="Images should have alt attributes for accessibility",
                common_causes=["Accessibility oversight", "Quick prototyping"],
                solutions=[
                    {
                        "description": "Add descriptive alt attribute",
                        "template": "alt=\"{description}\"",
                        "success_rate": 0.85,
                        "auto_applicable": False
                    }
                ]
            )
        ]
    
    def _get_css_patterns(self) -> List[ErrorPattern]:
        """CSS-specific error patterns"""
        return [
            ErrorPattern(
                pattern_id="css_duplicate_property",
                language="css",
                category=ErrorCategory.DUPLICATION,
                severity=ErrorSeverity.LOW,
                pattern_regex=r'(\w+):\s*[^;]+;.*\1:\s*[^;]+;',
                description="Duplicate CSS property",
                explanation="Same CSS property declared multiple times in one rule",
                common_causes=["Copy-paste errors", "Incremental development"],
                solutions=[
                    {
                        "description": "Keep the last declaration",
                        "template": "/* Remove duplicate: {property} */",
                        "success_rate": 0.9,
                        "auto_applicable": True
                    }
                ]
            ),
            ErrorPattern(
                pattern_id="css_vendor_prefix_missing",
                language="css",
                category=ErrorCategory.COMPATIBILITY,
                severity=ErrorSeverity.MEDIUM,
                pattern_regex=r'(?<!-webkit-)(?<!-moz-)(?<!-ms-)(backdrop-filter|transform|transition|animation):',
                description="Missing vendor prefixes",
                explanation="Modern CSS properties need vendor prefixes for browser compatibility",
                common_causes=["Forgetting browser support", "Rapid development"],
                solutions=[
                    {
                        "description": "Add webkit prefix for Safari support",
                        "template": "-webkit-{property}: {value};\n{property}: {value};",
                        "success_rate": 0.95,
                        "auto_applicable": True
                    }
                ]
            ),
            ErrorPattern(
                pattern_id="css_unused_selector",
                language="css",
                category=ErrorCategory.PERFORMANCE,
                severity=ErrorSeverity.LOW,
                pattern_regex=r'\.[\w-]+\s*{[^}]*}',
                description="Potentially unused CSS selector",
                explanation="CSS rules that may not be used in the HTML",
                common_causes=["Refactoring without cleanup", "Over-specific selectors"],
                solutions=[
                    {
                        "description": "Review and remove if unused",
                        "template": "/* TODO: Verify if {selector} is used */",
                        "success_rate": 0.7,
                        "auto_applicable": False
                    }
                ]
            )
        ]
    
    def _get_javascript_patterns(self) -> List[ErrorPattern]:
        """JavaScript-specific error patterns"""
        return [
            ErrorPattern(
                pattern_id="js_var_instead_const",
                language="javascript",
                category=ErrorCategory.STYLE,
                severity=ErrorSeverity.LOW,
                pattern_regex=r'\bvar\s+(\w+)\s*=\s*[^;]+;(?![^{]*\1\s*=)',
                description="Use const/let instead of var",
                explanation="Modern JavaScript prefers const/let over var for block scoping",
                common_causes=["Old JavaScript habits", "Legacy code"],
                solutions=[
                    {
                        "description": "Replace var with const",
                        "template": "const {variable} = {value};",
                        "success_rate": 0.9,
                        "auto_applicable": True
                    },
                    {
                        "description": "Replace var with let if reassigned",
                        "template": "let {variable} = {value};",
                        "success_rate": 0.85,
                        "auto_applicable": False
                    }
                ]
            ),
            ErrorPattern(
                pattern_id="js_missing_semicolon",
                language="javascript",
                category=ErrorCategory.STYLE,
                severity=ErrorSeverity.LOW,
                pattern_regex=r'[^;\s]\n\s*[^/\s]',
                description="Missing semicolon",
                explanation="JavaScript statements should end with semicolons",
                common_causes=["Automatic semicolon insertion reliance", "Inconsistent style"],
                solutions=[
                    {
                        "description": "Add missing semicolon",
                        "template": "{statement};",
                        "success_rate": 0.95,
                        "auto_applicable": True
                    }
                ]
            ),
            ErrorPattern(
                pattern_id="js_console_log",
                language="javascript",
                category=ErrorCategory.STYLE,
                severity=ErrorSeverity.LOW,
                pattern_regex=r'console\.log\([^)]*\)',
                description="Console.log statement found",
                explanation="Debug console.log statements should be removed from production",
                common_causes=["Debugging leftovers", "Development artifacts"],
                solutions=[
                    {
                        "description": "Remove console.log statement",
                        "template": "// Debug: {original_statement}",
                        "success_rate": 0.8,
                        "auto_applicable": False
                    }
                ]
            )
        ]
    
    def _get_python_patterns(self) -> List[ErrorPattern]:
        """Python-specific error patterns"""
        return [
            ErrorPattern(
                pattern_id="py_unused_import",
                language="python",
                category=ErrorCategory.PERFORMANCE,
                severity=ErrorSeverity.LOW,
                pattern_regex=r'^import\s+(\w+)(?!\s*#.*used)',
                description="Potentially unused import",
                explanation="Unused imports increase startup time and clutter code",
                common_causes=["Refactoring without cleanup", "Copy-paste imports"],
                solutions=[
                    {
                        "description": "Remove unused import",
                        "template": "# Removed unused import: {import_name}",
                        "success_rate": 0.85,
                        "auto_applicable": False
                    }
                ]
            ),
            ErrorPattern(
                pattern_id="py_long_line",
                language="python",
                category=ErrorCategory.STYLE,
                severity=ErrorSeverity.LOW,
                pattern_regex=r'^.{80,}$',
                description="Line too long (PEP 8)",
                explanation="Python PEP 8 recommends lines under 79 characters",
                common_causes=["Long string literals", "Complex expressions"],
                solutions=[
                    {
                        "description": "Break into multiple lines",
                        "template": "# TODO: Break long line",
                        "success_rate": 0.7,
                        "auto_applicable": False
                    }
                ]
            )
        ]
    
    def _get_json_patterns(self) -> List[ErrorPattern]:
        """JSON-specific error patterns"""
        return [
            ErrorPattern(
                pattern_id="json_trailing_comma",
                language="json",
                category=ErrorCategory.SYNTAX,
                severity=ErrorSeverity.HIGH,
                pattern_regex=r',\s*[}\]]',
                description="Trailing comma in JSON",
                explanation="JSON does not allow trailing commas",
                common_causes=["JavaScript habits", "Copy-paste from JS objects"],
                solutions=[
                    {
                        "description": "Remove trailing comma",
                        "template": "{without_comma}",
                        "success_rate": 0.98,
                        "auto_applicable": True
                    }
                ]
            )
        ]
    
    def _get_markdown_patterns(self) -> List[ErrorPattern]:
        """Markdown-specific error patterns"""
        return [
            ErrorPattern(
                pattern_id="md_missing_alt_text",
                language="markdown",
                category=ErrorCategory.ACCESSIBILITY,
                severity=ErrorSeverity.MEDIUM,
                pattern_regex=r'!\[\]\([^)]+\)',
                description="Missing alt text in markdown image",
                explanation="Images should have descriptive alt text",
                common_causes=["Quick documentation", "Accessibility oversight"],
                solutions=[
                    {
                        "description": "Add descriptive alt text",
                        "template": "![{description}]({url})",
                        "success_rate": 0.85,
                        "auto_applicable": False
                    }
                ]
            )
        ]
    
    def analyze_file(self, content: str, language: str, filename: str = "") -> List[ErrorPattern]:
        """Analyze file content for error patterns"""
        detected_errors = []
        
        if language not in self.patterns:
            return detected_errors
        
        lines = content.split('\n')
        
        for pattern in self.patterns[language]:
            matches = re.finditer(pattern.pattern_regex, content, re.MULTILINE | re.IGNORECASE)
            
            for match in matches:
                # Calculate line and column numbers
                line_num = content[:match.start()].count('\n') + 1
                col_num = match.start() - content.rfind('\n', 0, match.start())
                
                # Create error instance
                error = ErrorPattern(
                    pattern_id=pattern.pattern_id,
                    language=pattern.language,
                    category=pattern.category,
                    severity=pattern.severity,
                    pattern_regex=pattern.pattern_regex,
                    description=pattern.description,
                    explanation=pattern.explanation,
                    common_causes=pattern.common_causes,
                    solutions=pattern.solutions,
                    confidence=self._calculate_confidence(pattern, match.group(), content),
                    line_number=line_num,
                    column_number=col_num,
                    context=self._get_context(lines, line_num)
                )
                
                detected_errors.append(error)
        
        return detected_errors
    
    def _calculate_confidence(self, pattern: ErrorPattern, match: str, content: str) -> float:
        """Calculate confidence score for detected pattern"""
        base_confidence = 0.7
        
        # Adjust based on pattern complexity
        if len(pattern.pattern_regex) > 50:
            base_confidence += 0.1
        
        # Adjust based on context
        if pattern.category == ErrorCategory.SYNTAX:
            base_confidence += 0.2
        elif pattern.category == ErrorCategory.STYLE:
            base_confidence -= 0.1
        
        # Adjust based on learning data
        pattern_key = f"{pattern.language}_{pattern.pattern_id}"
        if pattern_key in self.learning_data:
            historical_accuracy = self.learning_data[pattern_key].get('accuracy', 0.5)
            base_confidence = (base_confidence + historical_accuracy) / 2
        
        return min(1.0, max(0.0, base_confidence))
    
    def _get_context(self, lines: List[str], line_num: int, context_size: int = 2) -> str:
        """Get surrounding context for error location"""
        start = max(0, line_num - context_size - 1)
        end = min(len(lines), line_num + context_size)
        
        context_lines = []
        for i in range(start, end):
            marker = ">>> " if i == line_num - 1 else "    "
            context_lines.append(f"{marker}{i+1}: {lines[i]}")
        
        return '\n'.join(context_lines)
    
    def add_custom_pattern(self, pattern: ErrorPattern):
        """Add custom user-defined pattern"""
        if pattern.language not in self.custom_patterns:
            self.custom_patterns[pattern.language] = []
        self.custom_patterns[pattern.language].append(pattern)
    
    def learn_from_feedback(self, pattern_id: str, language: str, was_correct: bool, solution_applied: str = ""):
        """Learn from user feedback to improve accuracy"""
        pattern_key = f"{language}_{pattern_id}"
        
        if pattern_key not in self.learning_data:
            self.learning_data[pattern_key] = {
                'total_detections': 0,
                'correct_detections': 0,
                'accuracy': 0.5,
                'solutions_feedback': {}
            }
        
        data = self.learning_data[pattern_key]
        data['total_detections'] += 1
        
        if was_correct:
            data['correct_detections'] += 1
        
        data['accuracy'] = data['correct_detections'] / data['total_detections']
        
        # Track solution effectiveness
        if solution_applied and was_correct:
            if solution_applied not in data['solutions_feedback']:
                data['solutions_feedback'][solution_applied] = {'used': 0, 'successful': 0}
            data['solutions_feedback'][solution_applied]['used'] += 1
            data['solutions_feedback'][solution_applied]['successful'] += 1
    
    def get_pattern_statistics(self) -> Dict[str, Any]:
        """Get statistics about pattern detection accuracy"""
        stats = {
            'total_patterns': sum(len(patterns) for patterns in self.patterns.values()),
            'custom_patterns': sum(len(patterns) for patterns in self.custom_patterns.values()),
            'languages_supported': list(self.patterns.keys()),
            'learning_data': self.learning_data
        }
        return stats
    
    def export_patterns(self, filename: str):
        """Export patterns to JSON file"""
        export_data = {
            'patterns': {
                lang: [asdict(pattern) for pattern in patterns]
                for lang, patterns in self.patterns.items()
            },
            'custom_patterns': {
                lang: [asdict(pattern) for pattern in patterns]
                for lang, patterns in self.custom_patterns.items()
            },
            'learning_data': self.learning_data
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, default=str)
    
    def import_patterns(self, filename: str):
        """Import patterns from JSON file"""
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Import custom patterns
        if 'custom_patterns' in data:
            for lang, patterns in data['custom_patterns'].items():
                self.custom_patterns[lang] = [
                    ErrorPattern(**pattern) for pattern in patterns
                ]
        
        # Import learning data
        if 'learning_data' in data:
            self.learning_data.update(data['learning_data'])
    
    def get_files_by_pattern(self, workspace_path, pattern):
        """Get files matching a pattern"""
        import fnmatch
        from pathlib import Path
        matches = []
        try:
            for file_path in Path(workspace_path).rglob('*'):
                if file_path.is_file():
                    if fnmatch.fnmatch(file_path.name, pattern) or fnmatch.fnmatch(str(file_path), pattern):
                        matches.append(str(file_path))
        except Exception as e:
            print(f"Error matching pattern {pattern}: {e}")
        return matches

def detect_language(filename: str, content: str) -> str:
    """Detect programming language from filename and content"""
    extension_map = {
        '.html': 'html',
        '.htm': 'html',
        '.css': 'css',
        '.js': 'javascript',
        '.ts': 'javascript',
        '.py': 'python',
        '.json': 'json',
        '.md': 'markdown',
        '.txt': 'text'
    }
    
    # Check file extension
    for ext, lang in extension_map.items():
        if filename.lower().endswith(ext):
            return lang
    
    # Analyze content for language hints
    if content.strip().startswith('<!DOCTYPE') or '<html' in content:
        return 'html'
    elif content.strip().startswith('{') and content.strip().endswith('}'):
        return 'json'
    elif 'def ' in content and 'import ' in content:
        return 'python'
    elif 'function' in content and ('var ' in content or 'let ' in content):
        return 'javascript'
    
    return 'text'

if __name__ == "__main__":
    # Example usage
    recognizer = PatternRecognition()
    
    # Test HTML content
    html_content = """
    <div>
        <img src="test.jpg">
        <p id="test">Hello</p>
        <p id="test">World</p>
    </div>
    """
    
    errors = recognizer.analyze_file(html_content, 'html', 'test.html')
    
    print(f"Found {len(errors)} potential issues:")
    for error in errors:
        print(f"- {error.description} (Line {error.line_number})")
        print(f"  Severity: {error.severity.value}")
        print(f"  Confidence: {error.confidence:.2f}")
        print(f"  Solutions: {len(error.solutions)} available")
        print()