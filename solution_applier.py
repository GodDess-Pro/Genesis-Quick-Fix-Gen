#!/usr/bin/env python3
"""
QuickFix Solution Application System
===================================

Automated solution application with backup/rollback mechanisms, 
success tracking, and integration with MasterArchive database.

Author: WorkspaceSentinel QuickFix System
Date: November 17, 2025
"""

import os
import shutil
import datetime
import hashlib
import threading
import re
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from pathlib import Path
import time

from master_archive import MasterSolution, MasterArchiveDB

@dataclass
class BackupInfo:
    """Information about file backup"""
    backup_id: str
    original_path: str
    backup_path: str
    created_at: datetime.datetime
    file_hash: str
    file_size: int
    solution_id: str
    auto_rollback_after: Optional[datetime.datetime] = None

@dataclass
class ApplicationResult:
    """Result of solution application"""
    success: bool
    solution_id: str
    file_path: str
    backup_id: Optional[str]
    applied_at: datetime.datetime
    execution_time: float
    error_message: Optional[str] = None
    changes_made: List[str] = None
    requires_verification: bool = False
    auto_applied: bool = False

    @property
    def backup_created(self) -> bool:
        """True if a backup was created for this application."""
        return self.backup_id is not None

class SolutionApplier:
    """Handles automated application of solutions with backup/rollback"""
    
    def __init__(self, workspace_path: str, master_archive: MasterArchiveDB):
        self.workspace_path = Path(workspace_path)
        self.master_archive = master_archive
        self.backup_dir = self.workspace_path / "QuickFixGenerator" / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Active backups tracking
        self.backups: Dict[str, BackupInfo] = {}
        self.backup_lock = threading.Lock()
        
        # Load existing backups
        self._load_existing_backups()
        
        # Auto-cleanup thread for old backups
        self.cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self.cleanup_thread.start()
        
        print(f"SolutionApplier initialized with backup directory: {self.backup_dir}")
    
    def _load_existing_backups(self):
        """Load information about existing backups"""
        backup_info_file = self.backup_dir / "backup_info.json"
        
        if backup_info_file.exists():
            try:
                with open(backup_info_file, 'r', encoding='utf-8') as f:
                    backup_data = json.load(f)
                
                for backup_id, data in backup_data.items():
                    backup_info = BackupInfo(
                        backup_id=backup_id,
                        original_path=data['original_path'],
                        backup_path=data['backup_path'],
                        created_at=datetime.datetime.fromisoformat(data['created_at']),
                        file_hash=data['file_hash'],
                        file_size=data['file_size'],
                        solution_id=data['solution_id'],
                        auto_rollback_after=datetime.datetime.fromisoformat(data['auto_rollback_after']) if data.get('auto_rollback_after') else None
                    )
                    self.backups[backup_id] = backup_info
                
                print(f"Loaded {len(self.backups)} existing backups")
                
            except Exception as e:
                print(f"Error loading backup info: {e}")
    
    def _save_backup_info(self):
        """Save backup information to disk"""
        backup_info_file = self.backup_dir / "backup_info.json"
        
        try:
            backup_data = {}
            for backup_id, info in self.backups.items():
                backup_data[backup_id] = {
                    'original_path': info.original_path,
                    'backup_path': info.backup_path,
                    'created_at': info.created_at.isoformat(),
                    'file_hash': info.file_hash,
                    'file_size': info.file_size,
                    'solution_id': info.solution_id,
                    'auto_rollback_after': info.auto_rollback_after.isoformat() if info.auto_rollback_after else None
                }
            
            with open(backup_info_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"Error saving backup info: {e}")
    
    def _create_backup(self, file_path: str, solution_id: str, 
                      auto_rollback_hours: Optional[int] = None) -> Optional[BackupInfo]:
        """Create backup of file before applying solution"""
        try:
            original_path = Path(file_path)
            if not original_path.exists():
                print(f"File does not exist: {file_path}")
                return None
            
            # Generate backup ID
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            file_hash = hashlib.md5(original_path.read_bytes()).hexdigest()[:8]
            backup_id = f"{original_path.stem}_{timestamp}_{file_hash}"
            
            # Create backup file
            backup_path = self.backup_dir / f"{backup_id}{original_path.suffix}"
            shutil.copy2(original_path, backup_path)
            
            # Calculate auto-rollback time
            auto_rollback_after = None
            if auto_rollback_hours:
                auto_rollback_after = datetime.datetime.now() + datetime.timedelta(hours=auto_rollback_hours)
            
            # Create backup info
            backup_info = BackupInfo(
                backup_id=backup_id,
                original_path=str(original_path),
                backup_path=str(backup_path),
                created_at=datetime.datetime.now(),
                file_hash=file_hash,
                file_size=original_path.stat().st_size,
                solution_id=solution_id,
                auto_rollback_after=auto_rollback_after
            )
            
            with self.backup_lock:
                self.backups[backup_id] = backup_info
                self._save_backup_info()
            
            print(f"Created backup: {backup_id} for {file_path}")
            return backup_info
            
        except Exception as e:
            print(f"Error creating backup for {file_path}: {e}")
            return None
    
    def _apply_template_solution(self, file_path: str, solution: MasterSolution, 
                               error_context: Dict[str, Any]) -> Tuple[bool, List[str], Optional[str]]:
        """Apply template-based solution to file"""
        changes_made = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Extract template variables from solution
            template = solution.solution_template
            
            # Common template replacements based on error context
            replacements = {}
            
            if 'tag_name' in error_context:
                replacements['tag'] = error_context['tag_name']
            if 'attribute_name' in error_context:
                replacements['attribute'] = error_context['attribute_name']
            if 'line_number' in error_context:
                replacements['line'] = str(error_context['line_number'])
            if 'function_name' in error_context:
                replacements['function'] = error_context['function_name']
            if 'variable_name' in error_context:
                replacements['variable'] = error_context['variable_name']
            
            # Apply template replacements
            applied_template = template
            for key, value in replacements.items():
                applied_template = applied_template.replace(f"{{{key}}}", value)
            
            # Language-specific application logic
            if solution.language == "html":
                content = self._apply_html_solution(content, solution, error_context, applied_template)
            elif solution.language == "css":
                content = self._apply_css_solution(content, solution, error_context, applied_template)
            elif solution.language == "javascript":
                content = self._apply_javascript_solution(content, solution, error_context, applied_template)
            elif solution.language == "python":
                content = self._apply_python_solution(content, solution, error_context, applied_template)
            elif solution.language == "json":
                content = self._apply_json_solution(content, solution, error_context, applied_template)
            else:
                # Generic text replacement
                if 'search_pattern' in error_context and 'replace_with' in error_context:
                    content = content.replace(error_context['search_pattern'], error_context['replace_with'])
                else:
                    return False, [], "Unsupported language or insufficient context"
            
            # Check if changes were made
            if content != original_content:
                # Write modified content
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                changes_made.append(f"Applied {solution.solution_description}")
                return True, changes_made, None
            else:
                return False, [], "No changes needed or template not applicable"
                
        except Exception as e:
            return False, [], str(e)
    
    def _apply_html_solution(self, content: str, solution: MasterSolution, 
                           error_context: Dict[str, Any], template: str) -> str:
        """Apply HTML-specific solution"""
        if solution.error_pattern_id == "html_unclosed_tag":
            # Find unclosed tags and add closing tags
            tag_name = error_context.get('tag_name', 'div')
            
            # Pattern to find unclosed tags
            tag_pattern = rf'<{tag_name}([^>]*)>(?!.*</{tag_name}>)'
            
            def add_closing_tag(match):
                opening_tag = match.group(0)
                # Check if it's a self-closing tag
                if opening_tag.endswith('/>'):
                    return opening_tag
                return f"{opening_tag}\n</{tag_name}>"
            
            content = re.sub(tag_pattern, add_closing_tag, content, flags=re.IGNORECASE | re.DOTALL)
            
        elif solution.error_pattern_id == "html_invalid_attribute":
            # Fix invalid attributes
            if 'attribute_name' in error_context and 'correct_attribute' in error_context:
                content = content.replace(
                    error_context['attribute_name'], 
                    error_context['correct_attribute']
                )
        
        return content
    
    def _apply_css_solution(self, content: str, solution: MasterSolution, 
                          error_context: Dict[str, Any], template: str) -> str:
        """Apply CSS-specific solution"""
        if solution.error_pattern_id == "css_missing_semicolon":
            # Add missing semicolons
            # Find lines without semicolons before closing braces
            lines = content.split('\n')
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped and not stripped.endswith(';') and not stripped.endswith('{') and not stripped.endswith('}'):
                    if i + 1 < len(lines) and lines[i + 1].strip().startswith('}'):
                        lines[i] = line + ';'
            content = '\n'.join(lines)
            
        elif solution.error_pattern_id == "css_invalid_property":
            # Fix invalid CSS properties
            if 'invalid_property' in error_context and 'correct_property' in error_context:
                content = content.replace(
                    error_context['invalid_property'],
                    error_context['correct_property']
                )
        
        return content
    
    def _apply_javascript_solution(self, content: str, solution: MasterSolution, 
                                 error_context: Dict[str, Any], template: str) -> str:
        """Apply JavaScript-specific solution"""
        if solution.error_pattern_id == "js_missing_semicolon":
            # Add missing semicolons
            lines = content.split('\n')
            for i, line in enumerate(lines):
                stripped = line.strip()
                if (stripped and 
                    not stripped.endswith(';') and 
                    not stripped.endswith('{') and 
                    not stripped.endswith('}') and
                    not stripped.startswith('//') and
                    not stripped.startswith('/*')):
                    # Check if next line starts with closing brace or new statement
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if next_line.startswith('}') or next_line.startswith('var') or next_line.startswith('let') or next_line.startswith('const'):
                            lines[i] = line + ';'
            content = '\n'.join(lines)
            
        elif solution.error_pattern_id == "js_undefined_variable":
            # Add variable declarations
            if 'variable_name' in error_context:
                var_name = error_context['variable_name']
                # Add declaration at the beginning of the function or file
                declaration = f"let {var_name};\n"
                content = declaration + content
        
        return content
    
    def _apply_python_solution(self, content: str, solution: MasterSolution, 
                             error_context: Dict[str, Any], template: str) -> str:
        """Apply Python-specific solution"""
        if solution.error_pattern_id == "python_indentation_error":
            # Fix indentation errors
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if line.strip():  # Non-empty line
                    # Count leading spaces
                    leading_spaces = len(line) - len(line.lstrip())
                    # Ensure indentation is multiple of 4
                    if leading_spaces % 4 != 0:
                        correct_spaces = ((leading_spaces // 4) + 1) * 4
                        lines[i] = ' ' * correct_spaces + line.lstrip()
            content = '\n'.join(lines)
            
        elif solution.error_pattern_id == "python_missing_import":
            # Add missing imports
            if 'module_name' in error_context:
                import_line = f"import {error_context['module_name']}\n"
                content = import_line + content
        
        return content
    
    def _apply_json_solution(self, content: str, solution: MasterSolution, 
                           error_context: Dict[str, Any], template: str) -> str:
        """Apply JSON-specific solution"""
        if solution.error_pattern_id == "json_trailing_comma":
            # Remove trailing commas
            content = re.sub(r',(\s*[}\]])', r'\1', content)
            
        elif solution.error_pattern_id == "json_invalid_quotes":
            # Fix quote issues
            content = re.sub(r"'([^']*)':", r'"\1":', content)  # Fix property names
            content = re.sub(r":\s*'([^']*)'", r': "\1"', content)  # Fix values
        
        return content
    
    def apply_solution(self, file_path: str, solution: MasterSolution, 
                      error_context: Dict[str, Any], auto_apply: bool = False) -> ApplicationResult:
        """Apply a solution to a file"""
        start_time = time.time()
        
        try:
            # Create backup if required
            backup_info = None
            if solution.requires_backup:
                # Auto-rollback after 1 hour for auto-applied solutions
                auto_rollback_hours = 1 if auto_apply else None
                backup_info = self._create_backup(file_path, solution.solution_id, auto_rollback_hours)
                
                if not backup_info:
                    return ApplicationResult(
                        success=False,
                        solution_id=solution.solution_id,
                        file_path=file_path,
                        backup_id=None,
                        applied_at=datetime.datetime.now(),
                        execution_time=time.time() - start_time,
                        error_message="Failed to create backup",
                        auto_applied=auto_apply
                    )
            
            # Apply the solution
            success, changes_made, error_message = self._apply_template_solution(
                file_path, solution, error_context
            )
            
            # Record the application in master archive
            self.master_archive.record_solution_application(
                solution.solution_id, file_path, success, time.time() - start_time
            )
            
            return ApplicationResult(
                success=success,
                solution_id=solution.solution_id,
                file_path=file_path,
                backup_id=backup_info.backup_id if backup_info else None,
                applied_at=datetime.datetime.now(),
                execution_time=time.time() - start_time,
                error_message=error_message,
                changes_made=changes_made,
                requires_verification=not success,
                auto_applied=auto_apply
            )
            
        except Exception as e:
            return ApplicationResult(
                success=False,
                solution_id=solution.solution_id,
                file_path=file_path,
                backup_id=None,
                applied_at=datetime.datetime.now(),
                execution_time=time.time() - start_time,
                error_message=str(e),
                auto_applied=auto_apply
            )
    
    def rollback_solution(self, backup_id: str) -> bool:
        """Rollback a solution using backup"""
        with self.backup_lock:
            if backup_id not in self.backups:
                print(f"Backup not found: {backup_id}")
                return False
            
            backup_info = self.backups[backup_id]
            
            try:
                # Restore original file
                shutil.copy2(backup_info.backup_path, backup_info.original_path)
                
                print(f"Rolled back {backup_info.original_path} from backup {backup_id}")
                return True
                
            except Exception as e:
                print(f"Error rolling back {backup_id}: {e}")
                return False
    
    def _cleanup_worker(self):
        """Background worker to clean up old backups and handle auto-rollbacks"""
        while True:
            try:
                current_time = datetime.datetime.now()
                backups_to_remove = []
                
                with self.backup_lock:
                    for backup_id, backup_info in self.backups.items():
                        # Auto-rollback if scheduled
                        if (backup_info.auto_rollback_after and 
                            current_time >= backup_info.auto_rollback_after):
                            print(f"Auto-rolling back solution: {backup_id}")
                            self.rollback_solution(backup_id)
                            backups_to_remove.append(backup_id)
                        
                        # Remove old backups (older than 7 days)
                        elif (current_time - backup_info.created_at).days > 7:
                            backups_to_remove.append(backup_id)
                    
                    # Clean up old backups
                    for backup_id in backups_to_remove:
                        if backup_id in self.backups:
                            backup_info = self.backups[backup_id]
                            try:
                                Path(backup_info.backup_path).unlink(missing_ok=True)
                                del self.backups[backup_id]
                                print(f"Cleaned up old backup: {backup_id}")
                            except Exception as e:
                                print(f"Error cleaning up backup {backup_id}: {e}")
                    
                    if backups_to_remove:
                        self._save_backup_info()
                
                # Sleep for 1 hour before next cleanup
                time.sleep(3600)
                
            except Exception as e:
                print(f"Error in cleanup worker: {e}")
                time.sleep(300)  # Sleep 5 minutes on error
    
    def apply_auto_solutions(self, file_path: str, detected_patterns: List[Tuple[str, Dict[str, Any]]]) -> List[ApplicationResult]:
        """Apply multiple auto-applicable solutions to a file"""
        results = []
        
        for pattern_id, error_context in detected_patterns:
            # Get language from file extension
            file_ext = Path(file_path).suffix.lower()
            language_map = {
                '.html': 'html', '.htm': 'html',
                '.css': 'css',
                '.js': 'javascript', '.jsx': 'javascript',
                '.py': 'python',
                '.json': 'json',
                '.md': 'markdown'
            }
            
            language = language_map.get(file_ext, 'unknown')
            
            if language == 'unknown':
                continue
            
            # Get best auto-applicable solution
            solution = self.master_archive.get_best_solution(
                pattern_id, language, auto_applicable_only=True
            )
            
            if solution:
                result = self.apply_solution(file_path, solution, error_context, auto_apply=True)
                results.append(result)
                
                if result.success:
                    print(f"Auto-applied solution {solution.solution_id} to {file_path}")
                else:
                    print(f"Failed to auto-apply solution {solution.solution_id}: {result.error_message}")
        
        return results
    
    def get_backup_info(self, backup_id: str) -> Optional[BackupInfo]:
        """Get information about a specific backup"""
        return self.backups.get(backup_id)

    def create_backup(self, file_path: str, solution_id: str = "manual") -> Optional[str]:
        """Public wrapper to create a file backup. Returns the backup path or None."""
        info = self._create_backup(file_path, solution_id)
        return str(info.backup_path) if info else None
    
    def list_backups(self, file_path: Optional[str] = None) -> List[BackupInfo]:
        """List all backups, optionally filtered by file path"""
        backups = list(self.backups.values())
        
        if file_path:
            backups = [b for b in backups if b.original_path == str(Path(file_path))]
        
        # Sort by creation time, newest first
        backups.sort(key=lambda x: x.created_at, reverse=True)
        return backups

# Example usage
if __name__ == "__main__":
    from master_archive import MasterArchiveDB
    
    # Initialize components
    workspace_path = "./test_workspace"
    master_archive = MasterArchiveDB(workspace_path)
    applier = SolutionApplier(workspace_path, master_archive)
    
    # Test solution application
    test_file = Path(workspace_path) / "test.html"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Create test HTML file with error
    test_file.write_text("""
    <html>
    <head>
        <title>Test Page</title>
    </head>
    <body>
        <div class="container">
            <h1>Hello World
            <p>This is a test paragraph</p>
        </div>
    </body>
    </html>
    """)
    
    # Get solution from master archive
    solution = master_archive.get_best_solution("html_unclosed_tag", "html")
    
    if solution:
        error_context = {
            'tag_name': 'h1',
            'line_number': 8
        }
        
        result = applier.apply_solution(str(test_file), solution, error_context)
        print(f"Application result: {result}")
        
        # List backups
        backups = applier.list_backups(str(test_file))
        print(f"Backups created: {len(backups)}")
    
    print("Solution applier test completed")