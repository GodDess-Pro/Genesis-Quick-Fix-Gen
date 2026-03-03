# QuickFix Generator - Pattern Matching Guide

## Overview

The QuickFix Generator uses advanced pattern matching to detect common coding errors across multiple programming languages. This guide explains how pattern matching works, including the important behavior that **quotes are not needed** when specifying patterns.

## Core Pattern Matching Behavior

### ✅ Correct Usage (No Quotes Needed)

```bash
# File watching patterns
python dashboard_server.py --watch-patterns *.html,*.css,*.js,*.py

# Batch operations
quickfix scan pattern *.js
quickfix scan pattern **/*.py
quickfix batch-fix src/**/*.html

# Configuration files
"watch_patterns": ["*.html", "*.css", "*.js", "*.py", "*.json"]
```

### ❌ Incorrect Usage (Don't Use Shell Quotes)

```bash
# Shell quotes prevent pattern expansion
quickfix scan pattern "*.js"      # This won't work as expected
quickfix batch-fix "src/**/*.py"  # Pattern won't expand properly
```

## Why No Quotes?

### Shell vs Application Pattern Handling

- **With Quotes**: Shell treats pattern as literal string
- **Without Quotes**: Shell expands pattern, application processes expanded files
- **Result**: QuickFix handles pattern expansion internally for better control

### Example Comparison

```bash
# Shell expansion (what we want to avoid)
ls *.js  # Shell expands to: ls file1.js file2.js file3.js

# Application pattern matching (what QuickFix does)
quickfix scan *.js  # QuickFix receives "*.js" and handles expansion
```

## Supported Pattern Types

### 1. Simple Wildcards

```bash
*.js           # All JavaScript files in current directory
*.html         # All HTML files in current directory
test*.py       # All Python files starting with "test"
*_spec.js      # All JavaScript spec files
```

### 2. Recursive Patterns

```bash
**/*.js        # All JavaScript files in all subdirectories
src/**/*.py    # All Python files under src directory
**/*test*      # All files containing "test" anywhere in tree
```

### 3. Multiple Extensions

```bash
*.{js,ts}      # JavaScript and TypeScript files
*.{html,htm}   # HTML files with either extension
*.{css,scss}   # CSS and SCSS files
```

### 4. Complex Patterns

```bash
src/**/*.{js,ts}           # JS/TS files under src
test/**/*{.test,.spec}.js  # Test files in test directory
**/*.min.{js,css}          # Minified assets
```

## Language-Specific Pattern Recognition

### HTML Patterns

```javascript
// Detected patterns (no quotes needed in config)
html_unclosed_tag: /<([^>]+)>(?!.*<\/\1>)/
html_missing_alt: /<img(?![^>]*alt=)/
html_deprecated_tag: /<(center|font|u)\b/
```

**Example Configuration**:

```json
{
  "html_patterns": {
    "enabled": true,
    "watch_patterns": ["*.html", "*.htm"],
    "confidence_threshold": 0.8
  }
}
```

### CSS Patterns

```javascript
// Detected patterns
css_missing_semicolon: /[^;{}]\s*$/
css_invalid_property: /[^:]+:\s*[^;{}]*[^;]\s*$/
css_duplicate_selector: /^(.+?)\s*{[\s\S]*?}\s*\1\s*{/
```

**Example Configuration**:

```json
{
  "css_patterns": {
    "enabled": true,
    "watch_patterns": ["*.css", "*.scss", "*.sass"],
    "confidence_threshold": 0.8
  }
}
```

### JavaScript Patterns

```javascript
// Detected patterns
js_missing_semicolon: /[^;{}]\s*$/
js_undefined_variable: /\b([a-zA-Z_$][a-zA-Z0-9_$]*)\s*(?![=:])/
js_console_log: /console\.log\(/
```

**Example Configuration**:

```json
{
  "javascript_patterns": {
    "enabled": true,
    "watch_patterns": ["*.js", "*.jsx", "*.mjs"],
    "confidence_threshold": 0.8
  }
}
```

### Python Patterns

```python
# Detected patterns
python_indentation_error: r'^[ \t]*\S'
python_missing_colon: r'(if|for|while|def|class|try|except|with)\s+[^:]+(?<!:)\s*$'
python_unused_import: r'^import\s+(\w+)(?!.*\1)'
```

**Example Configuration**:

```json
{
  "python_patterns": {
    "enabled": true,
    "watch_patterns": ["*.py", "*.pyw"],
    "confidence_threshold": 0.8
  }
}
```

## Configuration Examples

### Dashboard Configuration

```json
{
  "auto_apply_fixes": false,
  "backup_retention_days": 7,
  "max_temp_entries": 1000,
  "watch_patterns": ["*.html", "*.css", "*.js", "*.py", "*.json"],
  "refresh_interval": 30,
  "pattern_matching": {
    "case_sensitive": false,
    "follow_symlinks": true,
    "max_depth": 10,
    "exclude_patterns": ["node_modules/**", ".git/**", "*.min.*"]
  }
}
```

### Advanced Pattern Configuration

```json
{
  "pattern_recognition": {
    "html_patterns": {
      "enabled": true,
      "confidence_threshold": 0.8,
      "auto_apply_threshold": 0.9,
      "watch_patterns": ["*.html", "*.htm", "templates/**/*.html"],
      "exclude_patterns": ["**/dist/**", "**/build/**"]
    },
    "css_patterns": {
      "enabled": true,
      "confidence_threshold": 0.8,
      "auto_apply_threshold": 0.9,
      "watch_patterns": ["*.css", "*.scss", "*.sass", "styles/**/*"],
      "exclude_patterns": ["*.min.css", "**/vendor/**"]
    },
    "javascript_patterns": {
      "enabled": true,
      "confidence_threshold": 0.8,
      "auto_apply_threshold": 0.9,
      "watch_patterns": ["*.js", "*.jsx", "*.mjs", "src/**/*.js"],
      "exclude_patterns": ["*.min.js", "**/node_modules/**", "**/dist/**"]
    }
  }
}
```

## Best Practices

### 1. Pattern Specificity

```bash
# Good: Specific patterns
src/**/*.js          # Only JavaScript files in src
test/**/*.spec.js    # Only spec files in test directory

# Avoid: Overly broad patterns
**/*                 # Matches everything (too broad)
*                    # Only current directory (too narrow)
```

### 2. Performance Optimization

```bash
# Good: Exclude common directories
{
  "watch_patterns": ["src/**/*.js"],
  "exclude_patterns": ["node_modules/**", ".git/**", "dist/**"]
}

# Good: Limit depth for large projects
{
  "max_depth": 5,
  "follow_symlinks": false
}
```

### 3. Language-Specific Organization

```json
{
  "frontend": {
    "watch_patterns": ["src/**/*.{js,jsx,ts,tsx,html,css,scss}"]
  },
  "backend": {
    "watch_patterns": ["api/**/*.{js,py}", "server/**/*.{js,py}"]
  },
  "tests": {
    "watch_patterns": ["test/**/*.{js,py}", "**/*.{test,spec}.{js,py}"]
  }
}
```

## Command Line Usage

### File Watching

```bash
# Start file watcher with patterns (no quotes)
python core_generator.py --watch *.html,*.css,*.js

# Watch specific directories
python core_generator.py --watch src/**/*.py,test/**/*.py

# Watch with exclusions
python core_generator.py --watch **/*.js --exclude node_modules/**,dist/**
```

### Manual Scanning

```bash
# Scan current directory
python core_generator.py scan *.py

# Scan recursively
python core_generator.py scan **/*.{js,html,css}

# Scan with pattern
python core_generator.py scan --pattern html_unclosed_tag **/*.html
```

### Batch Operations

```bash
# Fix all JavaScript files
python core_generator.py fix *.js

# Fix specific pattern
python core_generator.py fix --pattern js_missing_semicolon src/**/*.js

# Preview fixes without applying
python core_generator.py fix --dry-run **/*.py
```

## API Usage

### Python API

```python
from core_generator import QuickFixGenerator

# Initialize with patterns (no quotes in code)
generator = QuickFixGenerator(
    workspace_path="/path/to/workspace",
    watch_patterns=["*.html", "*.css", "*.js", "*.py"],
    exclude_patterns=["node_modules/**", ".git/**"]
)

# Start watching
generator.start_file_watching()

# Manual scan
results = generator.scan_files(["src/**/*.js"])

# Apply fixes
generator.apply_fixes(pattern_id="js_missing_semicolon")
```

### REST API

```bash
# Start dashboard server
curl -X POST http://localhost:5000/api/scan-workspace \
  -d '{"patterns": ["*.html", "*.css", "*.js"]}'

# Get pattern statistics
curl http://localhost:5000/api/patterns

# Apply specific fix
curl -X POST http://localhost:5000/api/apply-fix \
  -d '{"solution_id": "js_semicolon_fix_1", "file_path": "src/app.js"}'
```

## Troubleshooting

### Common Issues

#### 1. Pattern Not Matching

```bash
# Problem: No files found
quickfix scan *.js

# Solution: Check current directory
ls *.js  # Verify files exist

# Solution: Use recursive pattern
quickfix scan **/*.js
```

#### 2. Too Many Files Matched

```bash
# Problem: Pattern too broad
quickfix scan **/*

# Solution: Be more specific
quickfix scan src/**/*.{js,py}

# Solution: Add exclusions
quickfix scan **/*.js --exclude node_modules/**,dist/**
```

#### 3. Permission Errors

```bash
# Problem: Cannot access files
quickfix scan **/*.py

# Solution: Check permissions
ls -la /path/to/files

# Solution: Run with appropriate permissions
sudo quickfix scan **/*.py  # Unix/Linux
```

### Debug Mode

```bash
# Enable verbose logging
python core_generator.py --verbose scan *.js

# Show pattern expansion
python core_generator.py --debug-patterns **/*.py

# Test pattern matching
python core_generator.py test-pattern "src/**/*.js"
```

## Advanced Features

### Pattern Validation

```python
def validate_pattern(pattern: str) -> bool:
    """Validate pattern syntax before use"""
    try:
        # Test pattern compilation
        regex_pattern = pattern_to_regex(pattern)
        return True
    except Exception:
        return False

# Usage
if validate_pattern("src/**/*.js"):
    generator.add_watch_pattern("src/**/*.js")
```

### Custom Pattern Types

```python
# Define custom patterns
custom_patterns = {
    "react_components": "src/components/**/*.{jsx,tsx}",
    "api_routes": "api/**/*.{js,py}",
    "test_files": "**/*.{test,spec}.{js,py,ts}",
    "config_files": "**/*.{json,yaml,yml,toml}"
}

# Apply custom patterns
for name, pattern in custom_patterns.items():
    generator.add_watch_pattern(pattern, category=name)
```

### Performance Monitoring

```python
# Monitor pattern matching performance
stats = generator.get_pattern_stats()
print(f"Patterns processed: {stats['total_patterns']}")
print(f"Files matched: {stats['files_matched']}")
print(f"Average match time: {stats['avg_match_time']}ms")
```

## Integration Examples

### VS Code Integration

```json
// .vscode/settings.json
{
  "quickfix.watchPatterns": ["src/**/*.{js,ts,jsx,tsx}"],
  "quickfix.excludePatterns": ["node_modules/**", "dist/**"],
  "quickfix.autoApplyFixes": false,
  "quickfix.confidenceThreshold": 0.8
}
```

### Git Hooks Integration

```bash
#!/bin/bash
# pre-commit hook

# Scan staged files
staged_files=$(git diff --cached --name-only --diff-filter=ACM)

# Apply QuickFix to staged files
python quickfix.py scan $staged_files --auto-fix

# Add fixed files back to staging
git add $staged_files
```

### CI/CD Integration

```yaml
# GitHub Actions
- name: QuickFix Analysis
  run: |
    python quickfix.py scan src/**/*.{js,py} --report=junit
    python quickfix.py scan test/**/*.{js,py} --report=junit
```

## Summary

### Key Points to Remember

1. **No Quotes Needed**: Pattern matching works without shell quotes
2. **Application Handles Expansion**: QuickFix processes patterns internally
3. **Multiple Pattern Types**: Simple wildcards, recursive, multiple extensions
4. **Language-Specific**: Each language has optimized pattern recognition
5. **Performance Optimized**: Exclude common directories, limit depth
6. **Configurable**: Extensive configuration options available
7. **Debug Support**: Verbose logging and pattern testing available

### Quick Reference

```bash
# Basic patterns (no quotes)
*.js *.py *.html *.css

# Recursive patterns
**/*.js src/**/*.py

# Multiple extensions
*.{js,ts,jsx,tsx}

# Complex patterns
src/**/*.{js,py} test/**/*{.test,.spec}.js
```

This pattern matching system provides powerful, flexible file detection while maintaining optimal performance and user-friendly syntax.
