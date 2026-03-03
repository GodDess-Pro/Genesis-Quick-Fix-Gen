"""
QuickFix Auto Solution Generator
Automatically detects, logs, and fixes common coding errors across multiple languages.
"""

import os
import json
import re
import time
import hashlib
import shutil
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
import logging


class QuickFixGenerator:
    """Main class for the Quick Fix Auto Solution Generator system."""
    
    def __init__(self, workspace_root: str = None):
        self.workspace_root = workspace_root or str(Path(__file__).parent.parent)
        self.quick_fix_root = str(Path(__file__).parent)
        self.logs_dir = os.path.join(self.quick_fix_root, "logs")
        self.templates_dir = os.path.join(self.quick_fix_root, "templates")
        self.backups_dir = os.path.join(self.quick_fix_root, "backups")
        
        # Configuration
        self.config = self.load_config()
        self.temp_log_cleanup_days = self.config.get("temp_log_cleanup_days", 7)
        self.solution_confidence_threshold = self.config.get("solution_confidence_threshold", 0.7)
        
        # Language mappings
        self.language_extensions = {
            '.html': 'HTML',
            '.htm': 'HTML',
            '.css': 'CSS',
            '.js': 'JavaScript',
            '.jsx': 'JavaScript',
            '.ts': 'JavaScript',
            '.tsx': 'JavaScript',
            '.py': 'Python',
            '.json': 'JSON',
            '.xml': 'XML',
            '.php': 'PHP',
            '.java': 'Java',
            '.cpp': 'CPP',
            '.c': 'C',
            '.cs': 'CSharp'
        }
        
        # File watchers
        self.observers = []
        self.is_monitoring = False
        
        # Initialize logging
        self.setup_logging()
        
        # Initialize directories
        self.ensure_directories()
        
        # Load error patterns
        self.error_patterns = self.load_error_patterns()
        
        self.logger.info("QuickFixGenerator initialized")

    def setup_logging(self):
        """Setup logging configuration."""
        log_file = os.path.join(self.quick_fix_root, "quickfix.log")
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('QuickFixGenerator')

    def load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        config_file = os.path.join(self.quick_fix_root, "config.json")
        default_config = {
            "temp_log_cleanup_days": 7,
            "solution_confidence_threshold": 0.7,
            "auto_apply_fixes": False,
            "backup_enabled": True,
            "monitored_extensions": [".html", ".css", ".js", ".py", ".json"],
            "excluded_paths": ["node_modules", ".git", "__pycache__", ".venv"]
        }
        
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # Merge with defaults
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
            else:
                # Create default config
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=2)
                return default_config
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            return default_config

    def ensure_directories(self):
        """Ensure all required directories exist."""
        for language in self.language_extensions.values():
            lang_dir = os.path.join(self.logs_dir, language)
            os.makedirs(lang_dir, exist_ok=True)

    def load_error_patterns(self) -> Dict[str, List[Dict]]:
        """Load error detection patterns for different languages."""
        return {
            'HTML': [
                {
                    'pattern': r'<(\w+)[^>]*>(?!.*</\1>)',
                    'description': 'Unclosed HTML tag',
                    'severity': 'high',
                    'solutions': [
                        'Add closing tag: </{tag}>',
                        'Make self-closing: <{tag} />',
                        'Check tag nesting structure'
                    ]
                },
                {
                    'pattern': r'-webkit-backdrop-filter:\s*[^;]+;\s*-webkit-backdrop-filter:\s*[^;]+;',
                    'description': 'Duplicate -webkit-backdrop-filter property',
                    'severity': 'medium',
                    'solutions': [
                        'Remove duplicate -webkit-backdrop-filter properties',
                        'Keep only one -webkit-backdrop-filter with standard backdrop-filter',
                        'Use CSS minification to detect duplicates'
                    ]
                },
                {
                    'pattern': r'backdrop-filter:\s*[^;]+;(?!.*-webkit-backdrop-filter)',
                    'description': 'Missing -webkit-backdrop-filter for Safari compatibility',
                    'severity': 'medium',
                    'solutions': [
                        'Add -webkit-backdrop-filter before backdrop-filter',
                        'Use autoprefixer for vendor prefixes',
                        'Check browser compatibility requirements'
                    ]
                },
                {
                    'pattern': r'style\s*=\s*["\'][^"\']*["\']',
                    'description': 'Inline CSS styles detected',
                    'severity': 'low',
                    'solutions': [
                        'Move inline styles to external CSS file',
                        'Create CSS classes for repeated styles',
                        'Use CSS-in-JS for dynamic styles'
                    ]
                }
            ],
            'CSS': [
                {
                    'pattern': r'([a-zA-Z-]+):\s*[^;]+;\s*\1:\s*[^;]+;',
                    'description': 'Duplicate CSS property',
                    'severity': 'medium',
                    'solutions': [
                        'Remove duplicate property declarations',
                        'Keep the most specific/important declaration',
                        'Use CSS linting tools'
                    ]
                },
                {
                    'pattern': r'backdrop-filter:\s*[^;]+;(?!.*-webkit-backdrop-filter)',
                    'description': 'Missing vendor prefix for backdrop-filter',
                    'severity': 'medium',
                    'solutions': [
                        'Add -webkit-backdrop-filter for Safari support',
                        'Use autoprefixer for automatic vendor prefixes',
                        'Check caniuse.com for browser support'
                    ]
                }
            ],
            'JavaScript': [
                {
                    'pattern': r'console\.(log|error|warn|info)\s*\(',
                    'description': 'Console statements in production code',
                    'severity': 'low',
                    'solutions': [
                        'Remove console statements for production',
                        'Use proper logging library',
                        'Add build step to strip console statements'
                    ]
                },
                {
                    'pattern': r'var\s+\w+\s*=',
                    'description': 'Using var instead of let/const',
                    'severity': 'low',
                    'solutions': [
                        'Replace var with const for constants',
                        'Replace var with let for variables',
                        'Use ESLint to enforce modern syntax'
                    ]
                }
            ],
            'Python': [
                {
                    'pattern': r'except\s*:',
                    'description': 'Bare except clause',
                    'severity': 'high',
                    'solutions': [
                        'Use specific exception types: except ValueError:',
                        'Use except Exception: for general exceptions',
                        'Add proper error handling and logging'
                    ]
                },
                {
                    'pattern': r'print\s*\(',
                    'description': 'Print statements in production code',
                    'severity': 'low',
                    'solutions': [
                        'Replace with proper logging: logging.info()',
                        'Remove debug print statements',
                        'Use logging module with appropriate levels'
                    ]
                }
            ]
        }

    def detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        ext = Path(file_path).suffix.lower()
        return self.language_extensions.get(ext, 'Unknown')

    def analyze_file(self, file_path: str) -> List[Dict]:
        """Analyze a file for common errors and issues."""
        if not os.path.exists(file_path):
            return []

        language = self.detect_language(file_path)
        if language == 'Unknown':
            return []

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            self.logger.error(f"Error reading file {file_path}: {e}")
            return []

        issues = []
        patterns = self.error_patterns.get(language, [])

        for pattern_info in patterns:
            matches = re.finditer(pattern_info['pattern'], content, re.MULTILINE | re.IGNORECASE)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                issue = {
                    'file_path': file_path,
                    'language': language,
                    'line_number': line_num,
                    'pattern': pattern_info['pattern'],
                    'description': pattern_info['description'],
                    'severity': pattern_info['severity'],
                    'solutions': pattern_info['solutions'],
                    'matched_text': match.group(),
                    'timestamp': datetime.now().isoformat(),
                    'hash': self.generate_issue_hash(file_path, pattern_info['description'], line_num)
                }
                issues.append(issue)

        return issues

    def generate_issue_hash(self, file_path: str, description: str, line_num: int) -> str:
        """Generate unique hash for an issue."""
        content = f"{file_path}:{description}:{line_num}"
        return hashlib.md5(content.encode()).hexdigest()

    def log_to_temp(self, issues: List[Dict]):
        """Log issues to temporary log files."""
        for issue in issues:
            language = issue['language']
            temp_log_file = os.path.join(self.logs_dir, language, f"TempLogList.{language.lower()}")
            
            # Load existing temp log
            temp_log = self.load_log_file(temp_log_file)
            
            # Check if issue already exists
            existing_issue = None
            for logged_issue in temp_log.get('issues', []):
                if logged_issue['hash'] == issue['hash']:
                    existing_issue = logged_issue
                    break
            
            if existing_issue:
                # Update existing issue
                existing_issue['count'] += 1
                existing_issue['last_occurrence'] = issue['timestamp']
            else:
                # Add new issue
                issue['count'] = 1
                issue['first_occurrence'] = issue['timestamp']
                issue['last_occurrence'] = issue['timestamp']
                temp_log.setdefault('issues', []).append(issue)
            
            # Save updated temp log
            self.save_log_file(temp_log_file, temp_log)

    def log_to_master(self, issue: Dict, solution_applied: str = None, success: bool = None):
        """Log issue to master archive with solution tracking."""
        language = issue['language']
        master_log_file = os.path.join(self.logs_dir, language, f"MasterArchiveList.{language.lower()}")
        
        # Load existing master log
        master_log = self.load_log_file(master_log_file)
        
        # Find existing issue in master
        existing_issue = None
        for logged_issue in master_log.get('issues', []):
            if logged_issue.get('description') == issue['description']:
                existing_issue = logged_issue
                break
        
        if existing_issue:
            # Update existing issue
            existing_issue['total_count'] += 1
            existing_issue['last_seen'] = issue['timestamp']
            
            if solution_applied:
                # Track solution effectiveness
                solution_info = None
                for sol in existing_issue.get('solution_stats', []):
                    if sol['solution'] == solution_applied:
                        solution_info = sol
                        break
                
                if solution_info:
                    solution_info['applied_count'] += 1
                    if success is not None:
                        if success:
                            solution_info['success_count'] += 1
                        solution_info['success_rate'] = solution_info['success_count'] / solution_info['applied_count']
                else:
                    # New solution
                    new_solution = {
                        'solution': solution_applied,
                        'applied_count': 1,
                        'success_count': 1 if success else 0,
                        'success_rate': 1.0 if success else 0.0
                    }
                    existing_issue.setdefault('solution_stats', []).append(new_solution)
        else:
            # Create new master issue
            new_master_issue = {
                'description': issue['description'],
                'pattern': issue['pattern'],
                'severity': issue['severity'],
                'language': issue['language'],
                'total_count': 1,
                'first_seen': issue['timestamp'],
                'last_seen': issue['timestamp'],
                'base_solutions': issue['solutions'],
                'solution_stats': []
            }
            
            if solution_applied:
                new_master_issue['solution_stats'] = [{
                    'solution': solution_applied,
                    'applied_count': 1,
                    'success_count': 1 if success else 0,
                    'success_rate': 1.0 if success else 0.0
                }]
            
            master_log.setdefault('issues', []).append(new_master_issue)
        
        # Sort solutions by success rate
        for issue_data in master_log.get('issues', []):
            if 'solution_stats' in issue_data:
                issue_data['solution_stats'].sort(key=lambda x: x['success_rate'], reverse=True)
        
        # Save updated master log
        self.save_log_file(master_log_file, master_log)

    def load_log_file(self, file_path: str) -> Dict:
        """Load log file or return empty structure."""
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading log file {file_path}: {e}")
        
        return {
            'created': datetime.now().isoformat(),
            'updated': datetime.now().isoformat(),
            'issues': []
        }

    def save_log_file(self, file_path: str, data: Dict):
        """Save log file with updated timestamp."""
        try:
            data['updated'] = datetime.now().isoformat()
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Error saving log file {file_path}: {e}")

    def cleanup_temp_logs(self):
        """Clean up old temporary log entries."""
        cutoff_date = datetime.now() - timedelta(days=self.temp_log_cleanup_days)
        
        for language_dir in os.listdir(self.logs_dir):
            lang_path = os.path.join(self.logs_dir, language_dir)
            if not os.path.isdir(lang_path):
                continue
                
            temp_log_file = os.path.join(lang_path, f"TempLogList.{language_dir.lower()}")
            if not os.path.exists(temp_log_file):
                continue
            
            temp_log = self.load_log_file(temp_log_file)
            original_count = len(temp_log.get('issues', []))
            
            # Filter out old issues
            temp_log['issues'] = [
                issue for issue in temp_log.get('issues', [])
                if datetime.fromisoformat(issue['last_occurrence']) > cutoff_date
            ]
            
            cleaned_count = original_count - len(temp_log['issues'])
            if cleaned_count > 0:
                self.logger.info(f"Cleaned {cleaned_count} old issues from {temp_log_file}")
                self.save_log_file(temp_log_file, temp_log)

    def get_ranked_solutions(self, issue_description: str, language: str) -> List[Dict]:
        """Get ranked solutions for an issue from master archive."""
        master_log_file = os.path.join(self.logs_dir, language, f"MasterArchiveList.{language.lower()}")
        master_log = self.load_log_file(master_log_file)
        
        for issue in master_log.get('issues', []):
            if issue['description'] == issue_description:
                # Combine base solutions with tracked solutions
                solutions = []
                
                # Add tracked solutions with stats
                for sol_stat in issue.get('solution_stats', []):
                    solutions.append({
                        'solution': sol_stat['solution'],
                        'success_rate': sol_stat['success_rate'],
                        'applied_count': sol_stat['applied_count'],
                        'type': 'tracked'
                    })
                
                # Add base solutions not yet tracked
                for base_sol in issue.get('base_solutions', []):
                    if not any(s['solution'] == base_sol for s in solutions):
                        solutions.append({
                            'solution': base_sol,
                            'success_rate': 0.5,  # Default rating
                            'applied_count': 0,
                            'type': 'base'
                        })
                
                # Sort by success rate, then by applied count
                solutions.sort(key=lambda x: (x['success_rate'], x['applied_count']), reverse=True)
                return solutions
        
        return []

    def process_file(self, file_path: str):
        """Process a single file for issues."""
        self.logger.info(f"Processing file: {file_path}")
        
        issues = self.analyze_file(file_path)
        if issues:
            self.logger.info(f"Found {len(issues)} issues in {file_path}")
            self.log_to_temp(issues)
            
            # Also log to master for tracking
            for issue in issues:
                self.log_to_master(issue)
        else:
            self.logger.debug(f"No issues found in {file_path}")


class FileWatchHandler(FileSystemEventHandler):
    """File system event handler for automatic monitoring."""
    
    def __init__(self, quick_fix_generator: QuickFixGenerator):
        self.qfg = quick_fix_generator
        super().__init__()

    def on_modified(self, event):
        if event.is_directory:
            return
        
        file_path = event.src_path
        file_ext = Path(file_path).suffix.lower()
        
        # Check if file extension is monitored
        if file_ext in self.qfg.config.get('monitored_extensions', []):
            # Check if path should be excluded
            excluded_paths = self.qfg.config.get('excluded_paths', [])
            if not any(excluded in file_path for excluded in excluded_paths):
                # Process file after a short delay to avoid multiple triggers
                threading.Timer(1.0, self.qfg.process_file, args=[file_path]).start()


if __name__ == "__main__":
    # Example usage
    qfg = QuickFixGenerator()
    
    # Process the price_alerts.html file that was just fixed
    test_file = r"c:\Users\moore\OneDrive\Desktop\GoddessPro_Ecosystem\agents\Genesis_Financial_Wallet\web\templates\price_alerts.html"
    if os.path.exists(test_file):
        qfg.process_file(test_file)
        print("Processed price_alerts.html file")
    
    # Clean up old temp logs
    qfg.cleanup_temp_logs()
    print("QuickFixGenerator ready!")