#!/usr/bin/env python3
"""
QuickFix TempLogList Management System
=====================================

Temporary error logging system that tracks recent errors, solutions applied, 
success rates, and provides auto-cleanup functionality.

Author: WorkspaceSentinel QuickFix System
Date: November 17, 2025
"""

import json
import os
import datetime
import threading
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import pickle

@dataclass
class TempLogEntry:
    """Individual temporary log entry"""
    entry_id: str
    timestamp: datetime.datetime
    file_path: str
    language: str
    severity: str = "medium"
    line_number: int = 0
    # data (e.g. from core_generator) while remaining backward-compatible.
    error_pattern_id: str = ""
    error_description: str = ""
    context: str = ""
    solutions_attempted: List[Dict[str, Any]] = None
    successful_solution: Optional[str] = None
    resolution_time: Optional[datetime.datetime] = None
    user_feedback: Optional[str] = None
    occurrence_count: int = 1
    last_seen: Optional[datetime.datetime] = None
    auto_applied: bool = False
    requires_manual_review: bool = False
    # Aliases used by core_generator when constructing entries
    pattern_id: Optional[str] = None
    original_content: Optional[str] = None
    confidence: float = 0.0
    # Solution-application tracking fields set by core_generator after creation
    solution_applied: bool = False
    solution_id: Optional[str] = None
    application_success: bool = False
    backup_created: bool = False
    application_timestamp: Optional[datetime.datetime] = None

    def __post_init__(self):
        # Initialise mutable default
        if self.solutions_attempted is None:
            self.solutions_attempted = []
        # Sync alias fields so both names refer to the same value
        if self.pattern_id and not self.error_pattern_id:
            self.error_pattern_id = self.pattern_id
        elif self.error_pattern_id and not self.pattern_id:
            self.pattern_id = self.error_pattern_id
        if self.original_content and not self.context:
            self.context = self.original_content
        elif self.context and not self.original_content:
            self.original_content = self.context

class TempLogManager:
    """Manages temporary error logs with auto-cleanup"""
    
    def __init__(self, base_path: str, cleanup_days: int = 7):
        self.base_path = Path(base_path)
        self.cleanup_days = cleanup_days
        self.logs_by_language = {}
        self.cleanup_thread = None
        self.cleanup_running = False
        
        # Create directory structure
        self.temp_logs_dir = self.base_path / "TempLogs"
        self.temp_logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing logs
        self._load_existing_logs()
        
        # Start cleanup thread
        self.start_auto_cleanup()
    
    def _load_existing_logs(self):
        """Load existing temporary logs from disk"""
        for language_file in self.temp_logs_dir.glob("TempLogList.*.json"):
            language = language_file.stem.split('.')[1]
            try:
                with open(language_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Convert timestamps back to datetime objects
                logs = []
                _dt_fields = {
                    'timestamp', 'resolution_time', 'last_seen',
                    'application_timestamp',
                }
                _valid_fields = {f.name for f in TempLogEntry.__dataclass_fields__.values()}
                for entry_data in data.get('entries', []):
                    # Parse datetime strings
                    for dt_key in _dt_fields:
                        if entry_data.get(dt_key):
                            entry_data[dt_key] = datetime.datetime.fromisoformat(entry_data[dt_key])
                    # Drop unknown keys to stay forward/backward compatible
                    entry_data = {k: v for k, v in entry_data.items() if k in _valid_fields}
                    logs.append(TempLogEntry(**entry_data))
                
                self.logs_by_language[language] = {
                    'entries': logs,
                    'metadata': data.get('metadata', {}),
                    'last_updated': datetime.datetime.fromisoformat(data.get('last_updated', datetime.datetime.now().isoformat()))
                }
                
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"Error loading temp logs for {language}: {e}")
                self.logs_by_language[language] = {
                    'entries': [],
                    'metadata': {},
                    'last_updated': datetime.datetime.now()
                }
    
    def add_error_log(self, file_path: str, language: str, error_pattern_id: str, 
                     error_description: str, severity: str, line_number: int, 
                     context: str, auto_applied: bool = False) -> str:
        """Add new error to temporary log"""
        
        # Generate unique entry ID
        content_hash = hashlib.md5(f"{file_path}{error_pattern_id}{line_number}{context}".encode()).hexdigest()[:8]
        entry_id = f"{language}_{content_hash}_{int(time.time())}"
        
        # Check if similar error already exists
        existing_entry = self._find_similar_entry(language, file_path, error_pattern_id, line_number)
        
        if existing_entry:
            # Update existing entry
            existing_entry.occurrence_count += 1
            existing_entry.last_seen = datetime.datetime.now()
            print(f"Updated existing error log: {existing_entry.entry_id} (count: {existing_entry.occurrence_count})")
        else:
            # Create new entry
            new_entry = TempLogEntry(
                entry_id=entry_id,
                timestamp=datetime.datetime.now(),
                file_path=file_path,
                language=language,
                error_pattern_id=error_pattern_id,
                error_description=error_description,
                severity=severity,
                line_number=line_number,
                context=context,
                solutions_attempted=[],
                successful_solution=None,
                resolution_time=None,
                user_feedback=None,
                auto_applied=auto_applied,
                requires_manual_review=severity in ['critical', 'high'] and not auto_applied
            )
            
            # Add to appropriate language log
            if language not in self.logs_by_language:
                self.logs_by_language[language] = {
                    'entries': [],
                    'metadata': {'total_errors': 0, 'resolved_errors': 0},
                    'last_updated': datetime.datetime.now()
                }
            
            self.logs_by_language[language]['entries'].append(new_entry)
            self.logs_by_language[language]['metadata']['total_errors'] += 1
            self.logs_by_language[language]['last_updated'] = datetime.datetime.now()
            
            print(f"Added new error log: {entry_id}")
        
        # Save updated logs
        self._save_language_logs(language)
        return existing_entry.entry_id if existing_entry else entry_id
    
    def add_entry(self, entry: 'TempLogEntry') -> str:
        """Add a pre-built TempLogEntry to the log (used by core_generator)."""
        language = entry.language
        if language not in self.logs_by_language:
            self.logs_by_language[language] = {
                'entries': [],
                'metadata': {'total_errors': 0, 'resolved_errors': 0},
                'last_updated': datetime.datetime.now()
            }
        self.logs_by_language[language]['entries'].append(entry)
        self.logs_by_language[language]['metadata']['total_errors'] += 1
        self.logs_by_language[language]['last_updated'] = datetime.datetime.now()
        self._save_language_logs(language)
        return entry.entry_id

    def update_entry(self, entry: 'TempLogEntry') -> None:
        """Update an existing TempLogEntry in-place (used by core_generator)."""
        language = entry.language
        if language not in self.logs_by_language:
            return
        entries = self.logs_by_language[language]['entries']
        for i, existing in enumerate(entries):
            if existing.entry_id == entry.entry_id:
                entries[i] = entry
                self.logs_by_language[language]['last_updated'] = datetime.datetime.now()
                self._save_language_logs(language)
                return

    def record_solution_attempt(self, entry_id: str, solution_description: str, 
                               success: bool, applied_automatically: bool = False):
        """Record a solution attempt for an error"""
        entry = self._find_entry_by_id(entry_id)
        if not entry:
            print(f"Entry {entry_id} not found")
            return
        
        solution_record = {
            'description': solution_description,
            'timestamp': datetime.datetime.now().isoformat(),
            'success': success,
            'auto_applied': applied_automatically
        }
        
        entry.solutions_attempted.append(solution_record)
        
        if success:
            entry.successful_solution = solution_description
            entry.resolution_time = datetime.datetime.now()
            
            # Update metadata
            language = entry.language
            self.logs_by_language[language]['metadata']['resolved_errors'] += 1
            self.logs_by_language[language]['last_updated'] = datetime.datetime.now()
        
        # Save updated logs
        self._save_language_logs(entry.language)
        print(f"Recorded solution attempt for {entry_id}: {'Success' if success else 'Failed'}")
    
    def add_user_feedback(self, entry_id: str, feedback: str):
        """Add user feedback to an error entry"""
        entry = self._find_entry_by_id(entry_id)
        if entry:
            entry.user_feedback = feedback
            entry.requires_manual_review = False
            self._save_language_logs(entry.language)
            print(f"Added user feedback to {entry_id}")
    
    def get_unresolved_errors(self, language: Optional[str] = None) -> List[TempLogEntry]:
        """Get list of unresolved errors"""
        unresolved = []
        
        languages_to_check = [language] if language else self.logs_by_language.keys()
        
        for lang in languages_to_check:
            if lang in self.logs_by_language:
                for entry in self.logs_by_language[lang]['entries']:
                    if not entry.successful_solution:
                        unresolved.append(entry)
        
        # Sort by severity and occurrence count
        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3, 'style': 4}
        unresolved.sort(key=lambda x: (severity_order.get(x.severity, 5), -x.occurrence_count))
        
        return unresolved
    
    def get_frequent_errors(self, min_occurrences: int = 3, language: Optional[str] = None) -> List[TempLogEntry]:
        """Get frequently occurring errors that might need permanent solutions"""
        frequent = []
        
        languages_to_check = [language] if language else self.logs_by_language.keys()
        
        for lang in languages_to_check:
            if lang in self.logs_by_language:
                for entry in self.logs_by_language[lang]['entries']:
                    if entry.occurrence_count >= min_occurrences:
                        frequent.append(entry)
        
        # Sort by occurrence count
        frequent.sort(key=lambda x: x.occurrence_count, reverse=True)
        return frequent
    
    def get_success_rate_by_pattern(self, language: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """Get success rates for different error patterns"""
        pattern_stats = {}
        
        languages_to_check = [language] if language else self.logs_by_language.keys()
        
        for lang in languages_to_check:
            if lang in self.logs_by_language:
                for entry in self.logs_by_language[lang]['entries']:
                    pattern_id = entry.error_pattern_id
                    
                    if pattern_id not in pattern_stats:
                        pattern_stats[pattern_id] = {
                            'total_occurrences': 0,
                            'resolved_count': 0,
                            'success_rate': 0.0,
                            'avg_resolution_time': None,
                            'common_solutions': {}
                        }
                    
                    stats = pattern_stats[pattern_id]
                    stats['total_occurrences'] += entry.occurrence_count
                    
                    if entry.successful_solution:
                        stats['resolved_count'] += 1
                        
                        # Track successful solutions
                        solution = entry.successful_solution
                        if solution not in stats['common_solutions']:
                            stats['common_solutions'][solution] = 0
                        stats['common_solutions'][solution] += 1
                    
                    # Calculate success rate
                    stats['success_rate'] = stats['resolved_count'] / stats['total_occurrences']
        
        return pattern_stats
    
    def cleanup_old_entries(self, force: bool = False):
        """Remove old entries based on cleanup policy"""
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=self.cleanup_days)
        cleaned_count = 0
        
        for language in list(self.logs_by_language.keys()):
            entries = self.logs_by_language[language]['entries']
            original_count = len(entries)
            
            # Keep entries that are:
            # 1. Recent (within cleanup period)
            # 2. Unresolved and marked for manual review
            # 3. Frequently occurring (might need permanent solution)
            self.logs_by_language[language]['entries'] = [
                entry for entry in entries
                if (entry.timestamp > cutoff_date or
                    (not entry.successful_solution and entry.requires_manual_review) or
                    entry.occurrence_count >= 5 or
                    force == False)
            ]
            
            new_count = len(self.logs_by_language[language]['entries'])
            cleaned_this_lang = original_count - new_count
            cleaned_count += cleaned_this_lang
            
            if cleaned_this_lang > 0:
                print(f"Cleaned {cleaned_this_lang} old entries from {language} temp log")
                self._save_language_logs(language)
        
        print(f"Total cleaned entries: {cleaned_count}")
        return cleaned_count
    
    def start_auto_cleanup(self):
        """Start automatic cleanup thread"""
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            return
        
        self.cleanup_running = True
        self.cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self.cleanup_thread.start()
        print("Started auto-cleanup thread")
    
    def stop_auto_cleanup(self):
        """Stop automatic cleanup thread"""
        self.cleanup_running = False
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=5)
        print("Stopped auto-cleanup thread")
    
    def _cleanup_worker(self):
        """Background cleanup worker"""
        while self.cleanup_running:
            try:
                # Run cleanup every 6 hours
                time.sleep(6 * 3600)
                if self.cleanup_running:
                    self.cleanup_old_entries()
            except Exception as e:
                print(f"Error in cleanup worker: {e}")
    
    def _find_similar_entry(self, language: str, file_path: str, error_pattern_id: str, line_number: int) -> Optional[TempLogEntry]:
        """Find similar existing entry"""
        if language not in self.logs_by_language:
            return None
        
        for entry in self.logs_by_language[language]['entries']:
            if (entry.file_path == file_path and 
                entry.error_pattern_id == error_pattern_id and 
                abs(entry.line_number - line_number) <= 2):  # Allow some line number drift
                return entry
        
        return None
    
    def _find_entry_by_id(self, entry_id: str) -> Optional[TempLogEntry]:
        """Find entry by ID across all languages"""
        for language_data in self.logs_by_language.values():
            for entry in language_data['entries']:
                if entry.entry_id == entry_id:
                    return entry
        return None
    
    def _save_language_logs(self, language: str):
        """Save logs for specific language to disk"""
        if language not in self.logs_by_language:
            return
        
        file_path = self.temp_logs_dir / f"TempLogList.{language}.json"
        
        # Prepare data for JSON serialization
        save_data = {
            'entries': [],
            'metadata': self.logs_by_language[language]['metadata'],
            'last_updated': self.logs_by_language[language]['last_updated'].isoformat(),
            'cleanup_policy_days': self.cleanup_days
        }
        
        for entry in self.logs_by_language[language]['entries']:
            entry_dict = asdict(entry)
            # Convert datetime objects to ISO strings
            entry_dict['timestamp'] = entry.timestamp.isoformat()
            if entry.resolution_time:
                entry_dict['resolution_time'] = entry.resolution_time.isoformat()
            if entry.last_seen:
                entry_dict['last_seen'] = entry.last_seen.isoformat()
            save_data['entries'].append(entry_dict)
        
        # Save to file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)
    
    def export_summary_report(self, output_path: str):
        """Export summary report of temp log statistics"""
        report = {
            'generation_time': datetime.datetime.now().isoformat(),
            'cleanup_policy_days': self.cleanup_days,
            'languages': {},
            'overall_stats': {
                'total_entries': 0,
                'resolved_entries': 0,
                'languages_tracked': len(self.logs_by_language)
            }
        }
        
        for language, data in self.logs_by_language.items():
            entries = data['entries']
            resolved = [e for e in entries if e.successful_solution]
            
            language_stats = {
                'total_entries': len(entries),
                'resolved_entries': len(resolved),
                'resolution_rate': len(resolved) / len(entries) if entries else 0,
                'most_common_errors': {},
                'avg_resolution_time': None,
                'requires_attention': len([e for e in entries if e.requires_manual_review])
            }
            
            # Calculate most common errors
            error_counts = {}
            resolution_times = []
            
            for entry in entries:
                pattern = entry.error_pattern_id
                error_counts[pattern] = error_counts.get(pattern, 0) + entry.occurrence_count
                
                if entry.resolution_time and entry.timestamp:
                    resolution_times.append((entry.resolution_time - entry.timestamp).total_seconds())
            
            language_stats['most_common_errors'] = dict(sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:5])
            
            if resolution_times:
                language_stats['avg_resolution_time'] = sum(resolution_times) / len(resolution_times)
            
            report['languages'][language] = language_stats
            report['overall_stats']['total_entries'] += language_stats['total_entries']
            report['overall_stats']['resolved_entries'] += language_stats['resolved_entries']
        
        # Calculate overall resolution rate
        if report['overall_stats']['total_entries'] > 0:
            report['overall_stats']['resolution_rate'] = (
                report['overall_stats']['resolved_entries'] / 
                report['overall_stats']['total_entries']
            )
        
        # Save report
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"Summary report exported to: {output_path}")
        return report
    
    def get_entries_for_promotion(self, min_occurrences: int = 5, min_success_rate: float = 0.8) -> List[TempLogEntry]:
        """Get entries that should be promoted to master archive"""
        candidates = []
        
        pattern_stats = self.get_success_rate_by_pattern()
        
        for language_data in self.logs_by_language.values():
            for entry in language_data['entries']:
                pattern_stat = pattern_stats.get(entry.error_pattern_id, {})
                
                if (entry.occurrence_count >= min_occurrences and 
                    pattern_stat.get('success_rate', 0) >= min_success_rate and
                    entry.successful_solution):
                    candidates.append(entry)
        
        return candidates
    
    def get_all_entries(self) -> List[TempLogEntry]:
        """Get all entries across all languages"""
        all_entries = []
        for language_data in self.logs_by_language.values():
            all_entries.extend(language_data['entries'])
        return all_entries
    
    def get_recent_entries(self, limit: int = 10) -> List[TempLogEntry]:
        """Get recent entries sorted by timestamp"""
        all_entries = self.get_all_entries()
        # Sort by timestamp (most recent first)
        sorted_entries = sorted(all_entries, key=lambda x: x.timestamp, reverse=True)
        return sorted_entries[:limit]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get temp log statistics"""
        all_entries = self.get_all_entries()
        resolved_entries = [e for e in all_entries if e.successful_solution]
        
        return {
            'total_entries': len(all_entries),
            'resolved_entries': len(resolved_entries),
            'resolution_rate': len(resolved_entries) / len(all_entries) if all_entries else 0,
            'languages_tracked': len(self.logs_by_language),
            'requires_attention': len([e for e in all_entries if e.requires_manual_review])
        }

# Example usage and testing
if __name__ == "__main__":
    # Initialize temp log manager
    manager = TempLogManager("./test_logs", cleanup_days=7)
    
    # Add some test entries
    entry_id = manager.add_error_log(
        file_path="test.html",
        language="html",
        error_pattern_id="html_unclosed_tag",
        error_description="Missing closing div tag",
        severity="high",
        line_number=15,
        context="<div class='container'>\n    <p>Content</p>"
    )
    
    # Record solution attempt
    manager.record_solution_attempt(
        entry_id=entry_id,
        solution_description="Added missing </div> tag",
        success=True,
        applied_automatically=True
    )
    
    # Get statistics
    unresolved = manager.get_unresolved_errors()
    print(f"Unresolved errors: {len(unresolved)}")
    
    success_rates = manager.get_success_rate_by_pattern()
    print(f"Pattern success rates: {success_rates}")
    
    # Export report
    manager.export_summary_report("temp_log_report.json")