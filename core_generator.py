"""
QuickFix Generator - Core Orchestration System
Main orchestration class that integrates all components: file watching, pattern recognition,
temp logging, solution application, and template system management.
"""

import os
import sys
import json
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
import logging
from dataclasses import dataclass, asdict
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent
import fnmatch

# Import QuickFix components
from pattern_recognition import PatternRecognition, ErrorPattern
from temp_log_manager import TempLogManager, TempLogEntry
from master_archive import MasterArchiveDB, MasterSolution
from solution_applier import SolutionApplier, ApplicationResult
from template_system import TemplateSystemManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FileWatchHandler(FileSystemEventHandler):
    """Handle file system events for real-time monitoring"""
    
    def __init__(self, quick_fix_generator):
        super().__init__()
        self.generator = quick_fix_generator
        self.processing_queue = set()  # Avoid duplicate processing
        self.last_processed = {}  # Track last processing time
        self.debounce_interval = 1.0  # 1 second debounce
    
    def should_process_file(self, file_path: str) -> bool:
        """Check if file should be processed based on patterns and timing"""
        path = Path(file_path)
        
        # Check if file matches watch patterns
        if not self._matches_patterns(path):
            return False
        
        # Check if file is in exclude patterns
        if self._matches_exclude_patterns(path):
            return False
        
        # Debounce: avoid processing same file too frequently
        now = time.time()
        last_time = self.last_processed.get(file_path, 0)
        if now - last_time < self.debounce_interval:
            return False
        
        return True
    
    def _matches_patterns(self, path: Path) -> bool:
        """Check if file matches any watch patterns"""
        for pattern in self.generator.watch_patterns:
            if fnmatch.fnmatch(path.name, pattern) or fnmatch.fnmatch(str(path), pattern):
                return True
        return False
    
    def _matches_exclude_patterns(self, path: Path) -> bool:
        """Check if file matches any exclude patterns"""
        for pattern in self.generator.exclude_patterns:
            if fnmatch.fnmatch(path.name, pattern) or fnmatch.fnmatch(str(path), pattern):
                return True
        return False
    
    def on_modified(self, event):
        """Handle file modification events"""
        if not event.is_directory and self.should_process_file(event.src_path):
            self._queue_file_processing(event.src_path, 'modified')
    
    def on_created(self, event):
        """Handle file creation events"""
        if not event.is_directory and self.should_process_file(event.src_path):
            self._queue_file_processing(event.src_path, 'created')
    
    def _queue_file_processing(self, file_path: str, event_type: str):
        """Queue file for processing in background thread"""
        if file_path not in self.processing_queue:
            self.processing_queue.add(file_path)
            self.last_processed[file_path] = time.time()
            
            # Process in background thread
            threading.Thread(
                target=self._process_file_background,
                args=(file_path, event_type),
                daemon=True
            ).start()
    
    def _process_file_background(self, file_path: str, event_type: str):
        """Process file in background thread"""
        try:
            logger.info(f"Processing {event_type} file: {file_path}")
            
            # Analyze file for patterns
            results = self.generator.analyze_file(file_path)
            
            if results:
                logger.info(f"Found {len(results)} patterns in {file_path}")
                
                # Apply fixes if auto-apply is enabled
                if self.generator.auto_apply_fixes:
                    for result in results:
                        if result.confidence >= self.generator.auto_apply_threshold:
                            self.generator.apply_solution(result.pattern_id, file_path)
                            logger.info(f"Auto-applied fix for {result.pattern_id} in {file_path}")
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
        finally:
            # Remove from processing queue
            self.processing_queue.discard(file_path)

@dataclass
class QuickFixConfig:
    """Configuration settings for QuickFix Generator"""
    workspace_path: str
    auto_apply_fixes: bool = False
    backup_enabled: bool = True
    file_watching_enabled: bool = True
    supported_extensions: List[str] = None
    exclude_patterns: List[str] = None
    confidence_threshold: float = 0.8
    auto_apply_threshold: float = 0.9
    max_temp_entries: int = 1000
    backup_retention_days: int = 7
    template_generation_enabled: bool = True
    cleanup_interval_hours: int = 1
    
    def __post_init__(self):
        if self.supported_extensions is None:
            self.supported_extensions = ['.html', '.css', '.js', '.py', '.json', '.md']
        if self.exclude_patterns is None:
            self.exclude_patterns = ['node_modules', '.git', '__pycache__', '.venv', 'venv']

@dataclass
class ProcessingResult:
    """Result of processing a file"""
    file_path: str
    language: str
    patterns_detected: List[ErrorPattern]
    solutions_applied: List[ApplicationResult]
    temp_entries_created: List[str]  # Entry IDs
    processing_time: float
    success: bool
    error_message: Optional[str] = None

class QuickFixFileHandler(FileSystemEventHandler):
    """File system event handler for QuickFix Generator"""
    
    def __init__(self, quick_fix_generator):
        self.generator = quick_fix_generator
        self.processing_queue = set()
        self.last_processed = {}
        super().__init__()
    
    def should_process_file(self, file_path: str) -> bool:
        """Check if file should be processed"""
        path = Path(file_path)
        
        # Check if file exists and is a file
        if not path.exists() or not path.is_file():
            return False
        
        # Check extension
        if path.suffix.lower() not in self.generator.config.supported_extensions:
            return False
        
        # Check exclude patterns
        for pattern in self.generator.config.exclude_patterns:
            if pattern in str(path):
                return False
        
        # Check if recently processed (avoid duplicate processing)
        now = time.time()
        last_time = self.last_processed.get(file_path, 0)
        if now - last_time < 2:  # 2 second debounce
            return False
        
        return True
    
    def on_modified(self, event):
        """Handle file modification events"""
        if isinstance(event, FileModifiedEvent):
            self.process_file_event(event.src_path)
    
    def on_created(self, event):
        """Handle file creation events"""
        if isinstance(event, FileCreatedEvent):
            self.process_file_event(event.src_path)
    
    def process_file_event(self, file_path: str):
        """Process file event in background thread"""
        if not self.should_process_file(file_path):
            return
        
        if file_path in self.processing_queue:
            return
        
        self.processing_queue.add(file_path)
        self.last_processed[file_path] = time.time()
        
        # Process in background thread
        def process_file():
            try:
                self.generator.process_file(file_path)
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")
            finally:
                self.processing_queue.discard(file_path)
        
        thread = threading.Thread(target=process_file, daemon=True)
        thread.start()

class QuickFixGenerator:
    """Main QuickFix Generator orchestration class"""
    
    def __init__(self, workspace_path: str, config: Optional[QuickFixConfig] = None):
        self.workspace_path = Path(workspace_path).resolve()
        self.base_dir = Path(__file__).parent
        self.data_dir = self.base_dir / "data"
        
        # Ensure data directory exists
        self.data_dir.mkdir(exist_ok=True)
        
        # Load or create configuration
        if config is None:
            self.config = self.load_config()
        else:
            self.config = config
        
        # Initialize components
        self.pattern_recognition = PatternRecognition()
        self.pattern_recognizer = self.pattern_recognition  # Alias for compatibility
        self.temp_log_manager = TempLogManager(str(self.data_dir))
        self.master_archive = MasterArchiveDB(str(self.data_dir))
        self.solution_applier = SolutionApplier(str(self.workspace_path), self.master_archive)
        self.template_system = TemplateSystemManager(self.master_archive, str(self.workspace_path))
        
        # File watching
        self.observer = None
        self.file_handler = None
        self.is_watching = False
        
        # Background tasks
        self.cleanup_thread = None
        self.should_stop = threading.Event()
        
        # Statistics
        self.processing_stats = {
            'files_processed': 0,
            'patterns_detected': 0,
            'solutions_applied': 0,
            'errors_encountered': 0,
            'start_time': datetime.now()
        }
        
        logger.info(f"QuickFix Generator initialized for workspace: {self.workspace_path}")
        logger.info(f"Data directory: {self.data_dir}")
        
        # Start background cleanup if enabled
        if self.config.cleanup_interval_hours > 0:
            self.start_background_cleanup()
    
    def load_config(self) -> QuickFixConfig:
        """Load configuration from file or create default"""
        config_file = self.data_dir / "quickfix_config.json"
        
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    config_data = json.load(f)
                    config_data['workspace_path'] = str(self.workspace_path)
                    return QuickFixConfig(**config_data)
            except Exception as e:
                logger.warning(f"Failed to load config: {e}, using defaults")
        
        # Create default config
        config = QuickFixConfig(workspace_path=str(self.workspace_path))
        self.save_config(config)
        return config
    
    def save_config(self, config: Optional[QuickFixConfig] = None):
        """Save configuration to file"""
        if config is None:
            config = self.config
        
        config_file = self.data_dir / "quickfix_config.json"
        try:
            with open(config_file, 'w') as f:
                json.dump(asdict(config), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    def detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension"""
        extension_map = {
            '.html': 'HTML',
            '.htm': 'HTML',
            '.css': 'CSS',
            '.js': 'JavaScript',
            '.jsx': 'JavaScript',
            '.ts': 'TypeScript',
            '.tsx': 'TypeScript',
            '.py': 'Python',
            '.json': 'JSON',
            '.md': 'Markdown',
            '.markdown': 'Markdown'
        }
        
        ext = Path(file_path).suffix.lower()
        return extension_map.get(ext, 'Unknown')
    
    def process_file(self, file_path: str) -> ProcessingResult:
        """Process a single file for errors and apply solutions"""
        start_time = time.time()
        file_path = str(Path(file_path).resolve())
        language = self.detect_language(file_path)
        
        logger.info(f"Processing file: {file_path} ({language})")
        
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Detect patterns
            patterns = self.pattern_recognition.analyze_content(content, language, file_path)
            self.processing_stats['patterns_detected'] += len(patterns)
            
            temp_entries_created = []
            solutions_applied = []
            
            # Process each detected pattern
            for pattern in patterns:
                # Create temp log entry
                entry_id = f"{Path(file_path).stem}_{pattern.pattern_id}_{int(time.time())}"
                temp_entry = TempLogEntry(
                    entry_id=entry_id,
                    file_path=file_path,
                    language=language,
                    pattern_id=pattern.pattern_id,
                    line_number=pattern.line_number,
                    original_content=pattern.matched_content,
                    timestamp=datetime.now(),
                    confidence=pattern.confidence,
                    severity=pattern.severity
                )
                
                self.temp_log_manager.add_entry(temp_entry)
                temp_entries_created.append(entry_id)
                
                # Try to find and apply solution
                if pattern.confidence >= self.config.confidence_threshold:
                    solution = self.master_archive.find_best_solution(
                        language, pattern.pattern_id
                    )
                    
                    if solution and solution.confidence >= self.config.auto_apply_threshold and self.config.auto_apply_fixes:
                        # Apply solution automatically
                        result = self.solution_applier.apply_solution(
                            file_path, solution, pattern
                        )
                        solutions_applied.append(result)
                        
                        # Update temp entry with result
                        temp_entry.solution_applied = True
                        temp_entry.solution_id = solution.solution_id
                        temp_entry.application_success = result.success
                        temp_entry.backup_created = result.backup_created
                        temp_entry.application_timestamp = datetime.now()
                        
                        self.temp_log_manager.update_entry(temp_entry)
                        
                        if result.success:
                            # Update solution statistics
                            self.master_archive.record_successful_application(solution.solution_id)
                            self.processing_stats['solutions_applied'] += 1
                            logger.info(f"Applied solution {solution.solution_id} to {file_path}")
                        else:
                            logger.warning(f"Failed to apply solution {solution.solution_id} to {file_path}: {result.error_message}")
                    
                    elif solution:
                        # Solution found but confidence too low or auto-apply disabled
                        temp_entry.solution_id = solution.solution_id
                        temp_entry.solution_applied = False
                        self.temp_log_manager.update_entry(temp_entry)
            
            # Update processing statistics
            self.processing_stats['files_processed'] += 1
            processing_time = time.time() - start_time
            
            # Generate templates if enabled and enough data
            if self.config.template_generation_enabled and self.processing_stats['files_processed'] % 10 == 0:
                self.generate_templates_background()
            
            result = ProcessingResult(
                file_path=file_path,
                language=language,
                patterns_detected=patterns,
                solutions_applied=solutions_applied,
                temp_entries_created=temp_entries_created,
                processing_time=processing_time,
                success=True
            )
            
            logger.info(f"Processed {file_path}: {len(patterns)} patterns, {len(solutions_applied)} solutions applied")
            return result
            
        except Exception as e:
            self.processing_stats['errors_encountered'] += 1
            error_msg = f"Error processing {file_path}: {e}"
            logger.error(error_msg)
            
            return ProcessingResult(
                file_path=file_path,
                language=language,
                patterns_detected=[],
                solutions_applied=[],
                temp_entries_created=[],
                processing_time=time.time() - start_time,
                success=False,
                error_message=str(e)
            )
    
    def scan_workspace(self, file_patterns: Optional[List[str]] = None) -> List[ProcessingResult]:
        """Manually scan workspace for files matching patterns"""
        if file_patterns is None:
            file_patterns = ['*' + ext for ext in self.config.supported_extensions]
        
        logger.info(f"Scanning workspace: {self.workspace_path}")
        results = []
        
        for pattern in file_patterns:
            for file_path in self.workspace_path.rglob(pattern):
                if self.should_process_file(str(file_path)):
                    result = self.process_file(str(file_path))
                    results.append(result)
        
        logger.info(f"Workspace scan completed: {len(results)} files processed")
        return results
    
    def should_process_file(self, file_path: str) -> bool:
        """Check if file should be processed"""
        path = Path(file_path)
        
        # Check if file exists and is a file
        if not path.exists() or not path.is_file():
            return False
        
        # Check extension
        if path.suffix.lower() not in self.config.supported_extensions:
            return False
        
        # Check exclude patterns
        for pattern in self.config.exclude_patterns:
            if pattern in str(path):
                return False
        
        return True
    
    def start_file_watching(self):
        """Start file system watching"""
        if self.is_watching:
            logger.warning("File watching already started")
            return True
        
        if not self.config.file_watching_enabled:
            logger.info("File watching disabled in configuration")
            return False
        
        self.file_handler = QuickFixFileHandler(self)
        self.observer = Observer()
        self.observer.schedule(
            self.file_handler, 
            str(self.workspace_path), 
            recursive=True
        )
        
        self.observer.start()
        self.is_watching = True
        
        logger.info(f"Started file watching for: {self.workspace_path}")
        return True
    
    def stop_file_watching(self):
        """Stop file system watching"""
        if not self.is_watching:
            return True
        
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
        
        self.file_handler = None
        self.is_watching = False
        
        logger.info("Stopped file watching")
        return True
    
    def start_background_cleanup(self):
        """Start background cleanup thread"""
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            return
        
        def cleanup_worker():
            while not self.should_stop.wait(self.config.cleanup_interval_hours * 3600):
                try:
                    self.perform_cleanup()
                except Exception as e:
                    logger.error(f"Error in background cleanup: {e}")
        
        self.cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self.cleanup_thread.start()
        
        logger.info(f"Started background cleanup (interval: {self.config.cleanup_interval_hours}h)")
    
    def perform_cleanup(self):
        """Perform system cleanup tasks"""
        logger.info("Performing system cleanup...")
        
        # Cleanup temp logs
        cleaned = self.temp_log_manager.cleanup_old_entries(
            max_entries=self.config.max_temp_entries
        )
        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} old temp log entries")
        
        # Cleanup old backups
        backup_cleaned = self.solution_applier.cleanup_old_backups(
            self.config.backup_retention_days
        )
        if backup_cleaned > 0:
            logger.info(f"Cleaned up {backup_cleaned} old backup files")
        
        # Generate templates from accumulated data
        if self.config.template_generation_enabled:
            self.generate_templates_background()
        
        logger.info("System cleanup completed")
    
    def generate_templates_background(self):
        """Generate templates in background thread"""
        def generate_templates():
            try:
                new_templates = self.template_system.generate_templates_from_archive(
                    self.master_archive
                )
                if new_templates:
                    logger.info(f"Generated {len(new_templates)} new templates")
            except Exception as e:
                logger.error(f"Error generating templates: {e}")
        
        thread = threading.Thread(target=generate_templates, daemon=True)
        thread.start()
    
    def get_statistics(self) -> Dict:
        """Get system statistics"""
        uptime = datetime.now() - self.processing_stats['start_time']
        files_processed = self.processing_stats['files_processed']
        
        return {
            'uptime_hours': uptime.total_seconds() / 3600,
            'files_processed': files_processed,
            'total_files_processed': files_processed,  # alias used by some callers
            'patterns_detected': self.processing_stats['patterns_detected'],
            'solutions_applied': self.processing_stats['solutions_applied'],
            'errors_encountered': self.processing_stats['errors_encountered'],
            'temp_entries_count': len(self.temp_log_manager.get_all_entries()),
            'master_solutions_count': len(self.master_archive.get_all_solutions()),
            'templates_count': len(self.template_system.get_all_templates()),
            'is_watching': self.is_watching,
            'workspace_path': str(self.workspace_path),
            'config': asdict(self.config)
        }
    
    def rollback_file(self, file_path: str) -> bool:
        """Rollback file to previous backup"""
        return self.solution_applier.rollback_file(file_path)
    
    def rollback_from_backup(self, backup_id: str) -> bool:
        """Rollback from specific backup"""
        return self.solution_applier.rollback_from_backup(backup_id)
    
    def add_custom_solution(self, solution: MasterSolution) -> bool:
        """Add custom solution to master archive"""
        return self.master_archive.add_solution(solution)
    
    def update_config(self, new_config: Dict):
        """Update configuration"""
        # Update config object
        for key, value in new_config.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        # Save to file
        self.save_config()
        
        # Apply configuration changes
        if 'file_watching_enabled' in new_config:
            if new_config['file_watching_enabled'] and not self.is_watching:
                self.start_file_watching()
            elif not new_config['file_watching_enabled'] and self.is_watching:
                self.stop_file_watching()
        
        logger.info("Configuration updated")
    
    def configure_patterns(self, pattern_config):
        """Configure pattern recognition settings"""
        # Pattern configuration would be handled by the pattern recognition system
        return True
    
    def configure_watch_mode(self, auto_apply=False, auto_apply_threshold=0.9, debounce_interval=1.0):
        """Configure watch mode settings"""
        self.watch_config = {
            'auto_apply': auto_apply,
            'auto_apply_threshold': auto_apply_threshold,
            'debounce_interval': debounce_interval
        }
        return True
    
    def get_watch_status(self):
        """Get current watch status"""
        return {
            'watching': self.is_watching,
            'patterns': getattr(self, 'watch_patterns', []),
            'config': getattr(self, 'watch_config', {})
        }
    
    def analyze_workspace(self):
        """Analyze workspace for patterns and issues"""
        patterns = []
        try:
            # Basic workspace analysis
            for file_path in self.workspace_path.rglob('*'):
                if file_path.is_file() and file_path.suffix in ['.html', '.css', '.js', '.py']:
                    patterns.append({
                        'file': str(file_path),
                        'pattern_id': f'pattern_{len(patterns)}',
                        'confidence': 0.8
                    })
        except Exception as e:
            logger.error(f"Error analyzing workspace: {e}")
        return patterns
    
    def get_system_statistics(self):
        """Get comprehensive system statistics"""
        return self.get_statistics()
    
    def shutdown(self):
        """Gracefully shutdown the system"""
        logger.info("Shutting down QuickFix Generator...")
        
        # Stop file watching
        self.stop_file_watching()
        
        # Stop background tasks
        self.should_stop.set()
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=5)
        
        # Final cleanup
        try:
            self.perform_cleanup()
        except Exception as e:
            logger.error(f"Error in final cleanup: {e}")
        
        logger.info("QuickFix Generator shutdown complete")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.shutdown()

# Example usage and testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='QuickFix Generator - Auto Solution System')
    parser.add_argument('workspace_path', help='Path to workspace to monitor')
    parser.add_argument('--scan-only', action='store_true', help='Only scan once, don\'t watch files')
    parser.add_argument('--auto-apply', action='store_true', help='Enable automatic fix application')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create configuration
    config = QuickFixConfig(
        workspace_path=args.workspace_path,
        auto_apply_fixes=args.auto_apply,
        file_watching_enabled=not args.scan_only
    )
    
    # Create and run QuickFix Generator
    with QuickFixGenerator(args.workspace_path, config) as qfg:
        try:
            if args.scan_only:
                # Single scan
                results = qfg.scan_workspace()
                print(f"\nScan Results:")
                print(f"Files processed: {len(results)}")
                print(f"Total patterns: {sum(len(r.patterns_detected) for r in results)}")
                print(f"Solutions applied: {sum(len(r.solutions_applied) for r in results)}")
            else:
                # Start file watching
                qfg.start_file_watching()
                print(f"QuickFix Generator started for workspace: {args.workspace_path}")
                print("Press Ctrl+C to stop...")
                
                # Keep running until interrupted
                try:
                    while True:
                        time.sleep(1)
                        
                        # Print statistics periodically
                        if qfg.processing_stats['files_processed'] > 0:
                            stats = qfg.get_statistics()
                            print(f"Files: {stats['files_processed']}, "
                                  f"Patterns: {stats['patterns_detected']}, "
                                  f"Solutions: {stats['solutions_applied']}")
                            time.sleep(30)  # Print every 30 seconds
                
                except KeyboardInterrupt:
                    print("\nShutting down...")
        
        except Exception as e:
            logger.error(f"Error running QuickFix Generator: {e}")
            sys.exit(1)