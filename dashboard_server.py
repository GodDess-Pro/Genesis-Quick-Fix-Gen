"""
Flask Backend Server for QuickFix Generator Dashboard
Provides REST API endpoints for the web dashboard interface
"""

from flask import Flask, render_template, jsonify, request, send_from_directory
from werkzeug.security import check_password_hash
from flask_cors import CORS
import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import threading
import logging
from dataclasses import asdict
import sys

# Add the parent directory to the path to import our modules
sys.path.append(str(Path(__file__).parent))

from core_generator import QuickFixGenerator
from master_archive import MasterArchiveDB
from temp_log_manager import TempLogManager
from template_system import TemplateSystemManager
from solution_applier import SolutionApplier
from enhanced_diff_system import DiffManager, EnhancedDiffGenerator
from smart_pattern_learning import SmartPatternLearner
from browser_integration import BrowserIntegration
from team_collaboration import TeamCollaboration
from predictive_analysis import PredictiveAnalyzer

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DashboardServer:
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.workspace_path = self.base_dir.parent.parent  # Go up to workspace root
        
        # Initialize QuickFix components
        self.quick_fix = QuickFixGenerator(str(self.workspace_path))
        self.master_archive = MasterArchiveDB(str(self.base_dir / "data"))
        self.temp_log_manager = TempLogManager(str(self.base_dir / "data"))
        self.template_system = TemplateSystemManager(
            master_archive=self.master_archive,
            workspace_path=str(self.workspace_path)
        )
        self.solution_applier = SolutionApplier(
            workspace_path=str(self.workspace_path),
            master_archive=self.master_archive
        )
        self.diff_manager = DiffManager(data_dir=self.base_dir / "data")

        # Phase 2-4: New feature modules
        data_dir_str = str(self.base_dir / "data")
        self.pattern_learner = SmartPatternLearner(data_dir=data_dir_str)
        self.browser_analyzer = BrowserIntegration(report_dir=data_dir_str)
        self.team_collab = TeamCollaboration(
            collab_dir=data_dir_str,
            current_user="local_user",
        )
        self.predictive_analyzer = PredictiveAnalyzer(history_dir=data_dir_str)
        
        # Configuration
        self.config = {
            'auto_apply_fixes': False,
            'backup_retention_days': 7,
            'max_temp_entries': 1000,
            'watch_patterns': ['*.html', '*.css', '*.js', '*.py', '*.json'],
            'refresh_interval': 30,
            'diff_settings': {
                'side_by_side_view': True,
                'show_character_diff': True,
                'context_lines': 3,
                'ignore_whitespace': False,
                'max_diff_size': 1048576  # 1MB
            }
        }
        
        self.load_config()
        
    def load_config(self):
        """Load configuration from file"""
        config_file = self.base_dir / "data" / "dashboard_config.json"
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    loaded_config = json.load(f)
                    self.config.update(loaded_config)
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
    
    def save_config(self):
        """Save configuration to file"""
        config_file = self.base_dir / "data" / "dashboard_config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

# Global dashboard server instance
dashboard_server = DashboardServer()

# --- AUTH ENDPOINTS ---
@app.route('/api/auth/login', methods=['POST'])
def api_auth_login():
    """Basic login endpoint for dashboard users (SQLite users table required)"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    # Connect to users.db (assume same as Node backend)
    db_path = str(dashboard_server.base_dir.parent / 'desktop-app' / 'src' / 'backend' / 'users.db')
    if not os.path.exists(db_path):
        return jsonify({'error': 'User database not found'}), 500
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, password, email, plan FROM users WHERE username = ?', (username,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'Invalid credentials'}), 401
    user_id, user_name, pw_hash, email, plan = row
    if not check_password_hash(pw_hash, password):
        return jsonify({'error': 'Invalid credentials'}), 401
    # For demo: return user info (no JWT issued here)
    return jsonify({'id': user_id, 'username': user_name, 'email': email, 'plan': plan})

@app.route('/')
def index():
    """Serve the main dashboard page"""
    return send_from_directory(str(dashboard_server.base_dir), 'dashboard.html')

@app.route('/api/overview')
def api_overview():
    """Get overview statistics"""
    try:
        # Get statistics from various components
        master_stats = dashboard_server.master_archive.get_statistics()
        temp_stats = dashboard_server.temp_log_manager.get_statistics()
        
        # Calculate success rate
        total_applications = sum(solution.application_count for solution in dashboard_server.master_archive.get_all_solutions())
        successful_applications = sum(
            solution.application_count * solution.success_rate 
            for solution in dashboard_server.master_archive.get_all_solutions()
        )
        success_rate = (successful_applications / total_applications * 100) if total_applications > 0 else 0
        
        # Get today's processed files
        today = datetime.now().date()
        today_entries = [
            entry for entry in dashboard_server.temp_log_manager.get_all_entries()
            if entry.timestamp.date() == today
        ]
        files_processed_today = len(set(entry.file_path for entry in today_entries))
        
        # Count auto fixes (successful applications)
        auto_fixes = sum(
            1 for entry in today_entries
            if entry.solution_applied and entry.application_success
        )
        
        return jsonify({
            'total_solutions': len(master_stats.get('solutions_by_language', {})),
            'success_rate': round(success_rate, 1),
            'files_processed': files_processed_today,
            'auto_fixes': auto_fixes,
            'total_patterns': len(temp_stats.get('patterns_by_language', {})),
            'active_templates': len(dashboard_server.template_system.get_all_templates())
        })
    except Exception as e:
        logger.error(f"Error getting overview: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/recent-activity')
def api_recent_activity():
    """Get recent activity logs"""
    try:
        # Get recent temp log entries
        recent_entries = dashboard_server.temp_log_manager.get_recent_entries(limit=10)
        
        activity = []
        for entry in recent_entries:
            activity.append({
                'time': entry.timestamp.strftime('%H:%M:%S'),
                'file': str(Path(entry.file_path).name),
                'full_path': entry.file_path,
                'pattern': entry.pattern_id,
                'language': entry.language,
                'status': 'success' if entry.application_success else 'failed',
                'has_backup': entry.backup_created,
                'solution_id': entry.solution_id or 'N/A'
            })
        
        return jsonify(activity)
    except Exception as e:
        logger.error(f"Error getting recent activity: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/patterns')
def api_patterns():
    """Get error patterns statistics"""
    try:
        temp_stats = dashboard_server.temp_log_manager.get_statistics()
        patterns_by_language = temp_stats.get('patterns_by_language', {})
        
        patterns = []
        for language, pattern_counts in patterns_by_language.items():
            for pattern_id, count in pattern_counts.items():
                # Calculate success rate for this pattern
                pattern_entries = [
                    entry for entry in dashboard_server.temp_log_manager.get_all_entries()
                    if entry.pattern_id == pattern_id and entry.language == language
                ]
                
                successful_entries = [
                    entry for entry in pattern_entries
                    if entry.application_success
                ]
                
                success_rate = (len(successful_entries) / len(pattern_entries) * 100) if pattern_entries else 0
                
                # Check if trending (more than 5 occurrences in last 24 hours)
                recent_entries = [
                    entry for entry in pattern_entries
                    if entry.timestamp >= datetime.now() - timedelta(hours=24)
                ]
                trending = len(recent_entries) > 5
                
                patterns.append({
                    'id': pattern_id,
                    'language': language,
                    'occurrences': count,
                    'success_rate': round(success_rate, 1),
                    'trending': trending,
                    'recent_count': len(recent_entries)
                })
        
        # Sort by occurrences (most frequent first)
        patterns.sort(key=lambda x: x['occurrences'], reverse=True)
        
        return jsonify(patterns)
    except Exception as e:
        logger.error(f"Error getting patterns: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/solutions')
def api_solutions():
    """Get solutions from master archive"""
    try:
        solutions = dashboard_server.master_archive.get_all_solutions()
        
        solutions_data = []
        for solution in solutions:
            solutions_data.append({
                'id': solution.solution_id,
                'language': solution.language,
                'description': solution.description,
                'success_rate': round(solution.success_rate * 100, 1),
                'applications': solution.application_count,
                'auto_apply': solution.confidence > 0.8,  # Auto-apply if confidence > 80%
                'confidence': round(solution.confidence, 2),
                'created': solution.created_date.strftime('%Y-%m-%d %H:%M:%S'),
                'last_used': solution.last_used.strftime('%Y-%m-%d %H:%M:%S') if solution.last_used else 'Never'
            })
        
        # Sort by success rate and application count
        solutions_data.sort(key=lambda x: (x['success_rate'], x['applications']), reverse=True)
        
        return jsonify(solutions_data)
    except Exception as e:
        logger.error(f"Error getting solutions: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/templates')
def api_templates():
    """Get solution templates"""
    try:
        templates = dashboard_server.template_system.get_all_templates()
        
        templates_data = []
        for template in templates:
            templates_data.append({
                'id': template.template_id,
                'language': template.language,
                'pattern': template.error_pattern,
                'confidence': round(template.confidence, 2),
                'usage_count': template.usage_count,
                'created': template.created_date.strftime('%Y-%m-%d %H:%M:%S'),
                'solution_count': len(template.source_solutions)
            })
        
        # Get redundancy information
        redundant_solutions = len(dashboard_server.template_system.detect_redundant_solutions())
        
        return jsonify({
            'templates': templates_data,
            'total_templates': len(templates),
            'redundant_solutions': redundant_solutions
        })
    except Exception as e:
        logger.error(f"Error getting templates: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/backups')
def api_backups():
    """Get backup files information"""
    try:
        backups = dashboard_server.solution_applier.get_backup_history()
        
        backups_data = []
        for backup in backups:
            file_size = "Unknown"
            if os.path.exists(backup['backup_path']):
                size_bytes = os.path.getsize(backup['backup_path'])
                if size_bytes < 1024:
                    file_size = f"{size_bytes} B"
                elif size_bytes < 1024 * 1024:
                    file_size = f"{size_bytes / 1024:.1f} KB"
                else:
                    file_size = f"{size_bytes / (1024 * 1024):.1f} MB"
            
            backups_data.append({
                'id': backup['backup_id'],
                'original_file': backup['original_file'],
                'backup_path': backup['backup_path'],
                'created': backup['created_at'],
                'size': file_size,
                'solution_id': backup.get('solution_id', 'Unknown'),
                'exists': os.path.exists(backup['backup_path'])
            })
        
        # Sort by creation date (newest first)
        backups_data.sort(key=lambda x: x['created'], reverse=True)
        
        return jsonify(backups_data)
    except Exception as e:
        logger.error(f"Error getting backups: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/logs')
def api_logs():
    """Get activity logs"""
    try:
        # Get logs from temp log manager
        recent_entries = dashboard_server.temp_log_manager.get_recent_entries(limit=50)
        
        logs = []
        for entry in recent_entries:
            level = 'ERROR' if not entry.application_success and entry.solution_applied else 'INFO'
            component = 'SolutionApplier' if entry.solution_applied else 'PatternRecognition'
            
            if entry.solution_applied:
                if entry.application_success:
                    message = f"Successfully applied solution {entry.solution_id}"
                else:
                    message = f"Failed to apply solution {entry.solution_id}"
            else:
                message = f"Detected {entry.pattern_id} pattern"
            
            logs.append({
                'timestamp': entry.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'level': level,
                'component': component,
                'message': message,
                'details': f"{entry.file_path}:{entry.line_number}" if entry.line_number else entry.file_path
            })
        
        return jsonify(logs)
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings', methods=['GET'])
def api_get_settings():
    """Get current settings"""
    return jsonify(dashboard_server.config)

@app.route('/api/settings', methods=['POST'])
def api_save_settings():
    """Save settings"""
    try:
        new_settings = request.json
        dashboard_server.config.update(new_settings)
        dashboard_server.save_config()
        
        return jsonify({'status': 'success', 'message': 'Settings saved successfully'})
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rollback', methods=['POST'])
def api_rollback():
    """Rollback a file to backup"""
    try:
        data = request.json
        backup_id = data.get('backup_id')
        filename = data.get('filename')
        
        if backup_id:
            success = dashboard_server.solution_applier.rollback_from_backup(backup_id)
        elif filename:
            success = dashboard_server.solution_applier.rollback_file(filename)
        else:
            return jsonify({'error': 'Either backup_id or filename is required'}), 400
        
        if success:
            return jsonify({'status': 'success', 'message': 'File rolled back successfully'})
        else:
            return jsonify({'status': 'error', 'message': 'Rollback failed'}), 500
            
    except Exception as e:
        logger.error(f"Error during rollback: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/toggle-auto-apply', methods=['POST'])
def api_toggle_auto_apply():
    """Toggle auto-apply for a solution"""
    try:
        data = request.json
        solution_id = data.get('solution_id')
        enable = data.get('enable', False)
        
        # Update solution in master archive
        success = dashboard_server.master_archive.update_solution_auto_apply(solution_id, enable)
        
        if success:
            action = 'enabled' if enable else 'disabled'
            return jsonify({'status': 'success', 'message': f'Auto-apply {action} for {solution_id}'})
        else:
            return jsonify({'status': 'error', 'message': 'Solution not found'}), 404
            
    except Exception as e:
        logger.error(f"Error toggling auto-apply: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate-templates', methods=['POST'])
def api_generate_templates():
    """Generate new templates from similar solutions"""
    try:
        # Generate templates from master archive
        new_templates = dashboard_server.template_system.generate_templates_from_archive(
            dashboard_server.master_archive
        )
        
        return jsonify({
            'status': 'success',
            'message': f'Generated {len(new_templates)} new templates',
            'templates': [template.template_id for template in new_templates]
        })
        
    except Exception as e:
        logger.error(f"Error generating templates: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/cleanup-backups', methods=['POST'])
def api_cleanup_backups():
    """Clean up old backup files"""
    try:
        retention_days = dashboard_server.config.get('backup_retention_days', 7)
        cleaned_count = dashboard_server.solution_applier.cleanup_old_backups(retention_days)
        
        return jsonify({
            'status': 'success',
            'message': f'Cleaned up {cleaned_count} old backup files'
        })
        
    except Exception as e:
        logger.error(f"Error cleaning up backups: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/export-solutions', methods=['GET'])
def api_export_solutions():
    """Export solutions archive"""
    try:
        export_file = dashboard_server.base_dir / "data" / f"solutions_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        solutions = dashboard_server.master_archive.get_all_solutions()
        export_data = {
            'export_date': datetime.now().isoformat(),
            'total_solutions': len(solutions),
            'solutions': [asdict(solution) for solution in solutions]
        }
        
        with open(export_file, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        return jsonify({
            'status': 'success',
            'message': f'Solutions exported to {export_file.name}',
            'file_path': str(export_file)
        })
        
    except Exception as e:
        logger.error(f"Error exporting solutions: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/scan-workspace', methods=['POST'])
def api_scan_workspace():
    """Manually scan workspace for issues"""
    try:
        data = request.json
        file_patterns = data.get('patterns', dashboard_server.config['watch_patterns'])
        
        # Start background scan
        def scan_workspace():
            dashboard_server.quick_fix.scan_workspace(file_patterns)
        
        scan_thread = threading.Thread(target=scan_workspace)
        scan_thread.daemon = True
        scan_thread.start()
        
        return jsonify({
            'status': 'success',
            'message': 'Workspace scan started in background'
        })
        
    except Exception as e:
        logger.error(f"Error starting workspace scan: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/solution-details/<solution_id>')
def api_solution_details(solution_id):
    """Get detailed information about a solution"""
    try:
        solution = dashboard_server.master_archive.get_solution(solution_id)
        if not solution:
            return jsonify({'error': 'Solution not found'}), 404
        
        solution_data = asdict(solution)
        # Convert datetime objects to strings
        for key, value in solution_data.items():
            if isinstance(value, datetime):
                solution_data[key] = value.isoformat()
        
        return jsonify(solution_data)
        
    except Exception as e:
        logger.error(f"Error getting solution details: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/diff/files', methods=['POST'])
def api_diff_files():
    """Create diff between two files"""
    try:
        data = request.json
        old_file = data.get('old_file')
        new_file = data.get('new_file')
        old_version = data.get('old_version')
        new_version = data.get('new_version')
        output_format = data.get('format', 'json')  # json, html, text
        
        if not old_file or not new_file:
            return jsonify({'error': 'Both old_file and new_file are required'}), 400
        
        # Create diff
        diff_result = dashboard_server.diff_manager.create_diff(
            old_file, new_file, old_version, new_version, save_html=True
        )
        
        if output_format == 'html':
            html_content = dashboard_server.diff_manager.diff_generator.generate_side_by_side_html(diff_result)
            return html_content, 200, {'Content-Type': 'text/html'}
        elif output_format == 'text':
            text_content = dashboard_server.diff_manager.diff_generator.generate_unified_diff_text(diff_result)
            return text_content, 200, {'Content-Type': 'text/plain'}
        else:
            # JSON format (default)
            diff_data = asdict(diff_result)
            # Convert datetime objects to strings
            for key, value in diff_data.items():
                if isinstance(value, datetime):
                    diff_data[key] = value.isoformat()
            return jsonify(diff_data)
            
    except Exception as e:
        logger.error(f"Error creating diff: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/diff/backup', methods=['POST'])
def api_diff_backup():
    """Create diff between original file and backup"""
    try:
        data = request.json
        backup_id = data.get('backup_id')
        original_file = data.get('original_file')
        output_format = data.get('format', 'json')
        
        if not backup_id and not original_file:
            return jsonify({'error': 'Either backup_id or original_file is required'}), 400
        
        # Get backup information
        if backup_id:
            backup_info = dashboard_server.solution_applier.get_backup_info(backup_id)
            if not backup_info:
                return jsonify({'error': 'Backup not found'}), 404
            
            original_file = backup_info['original_file']
            backup_file = backup_info['backup_path']
        else:
            # Find most recent backup for the file
            backups = dashboard_server.solution_applier.get_backup_history()
            file_backups = [b for b in backups if b['original_file'] == original_file]
            if not file_backups:
                return jsonify({'error': 'No backups found for file'}), 404
            
            # Use most recent backup
            backup_file = file_backups[0]['backup_path']
            backup_id = file_backups[0]['backup_id']
        
        # Create diff
        diff_result = dashboard_server.diff_manager.create_diff(
            backup_file, original_file, 
            old_version=f"Backup ({backup_id})", 
            new_version="Current",
            save_html=True
        )
        
        if output_format == 'html':
            html_content = dashboard_server.diff_manager.diff_generator.generate_side_by_side_html(diff_result)
            return html_content, 200, {'Content-Type': 'text/html'}
        elif output_format == 'text':
            text_content = dashboard_server.diff_manager.diff_generator.generate_unified_diff_text(diff_result)
            return text_content, 200, {'Content-Type': 'text/plain'}
        else:
            diff_data = asdict(diff_result)
            for key, value in diff_data.items():
                if isinstance(value, datetime):
                    diff_data[key] = value.isoformat()
            return jsonify(diff_data)
            
    except Exception as e:
        logger.error(f"Error creating backup diff: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/diff/list')
def api_list_diffs():
    """List all saved diff files"""
    try:
        diffs = dashboard_server.diff_manager.list_saved_diffs()
        
        # Convert datetime objects to strings
        for diff in diffs:
            for key, value in diff.items():
                if isinstance(value, datetime):
                    diff[key] = value.isoformat()
        
        return jsonify(diffs)
        
    except Exception as e:
        logger.error(f"Error listing diffs: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/diff/cleanup', methods=['POST'])
def api_cleanup_diffs():
    """Clean up old diff files"""
    try:
        data = request.json or {}
        max_age_days = data.get('max_age_days', 7)
        
        cleaned_count = dashboard_server.diff_manager.cleanup_old_diffs(max_age_days)
        
        return jsonify({
            'status': 'success',
            'message': f'Cleaned up {cleaned_count} old diff files',
            'cleaned_count': cleaned_count
        })
        
    except Exception as e:
        logger.error(f"Error cleaning up diffs: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/diff/text', methods=['POST'])
def api_diff_text():
    """Create diff between two text strings"""
    try:
        data = request.json
        old_text = data.get('old_text', '')
        new_text = data.get('new_text', '')
        old_label = data.get('old_label', 'Original')
        new_label = data.get('new_label', 'Modified')
        output_format = data.get('format', 'json')
        
        # Create diff
        diff_result = dashboard_server.diff_manager.diff_generator.compare_text(
            old_text, new_text, old_label, new_label
        )
        
        if output_format == 'html':
            html_content = dashboard_server.diff_manager.diff_generator.generate_side_by_side_html(diff_result)
            return html_content, 200, {'Content-Type': 'text/html'}
        elif output_format == 'text':
            text_content = dashboard_server.diff_manager.diff_generator.generate_unified_diff_text(diff_result)
            return text_content, 200, {'Content-Type': 'text/plain'}
        else:
            diff_data = asdict(diff_result)
            for key, value in diff_data.items():
                if isinstance(value, datetime):
                    diff_data[key] = value.isoformat()
            return jsonify(diff_data)
            
    except Exception as e:
        logger.error(f"Error creating text diff: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/watch/start', methods=['POST'])
def api_start_watch():
    """Start file watching mode"""
    try:
        data = request.json or {}
        watch_patterns = data.get('watch_patterns')
        exclude_patterns = data.get('exclude_patterns')
        auto_apply = data.get('auto_apply', False)
        auto_apply_threshold = data.get('auto_apply_threshold', 0.9)
        
        # Configure watch mode
        dashboard_server.quick_fix.configure_watch_mode(
            auto_apply=auto_apply,
            auto_apply_threshold=auto_apply_threshold
        )
        
        # Store patterns and start watching
        if watch_patterns:
            dashboard_server.quick_fix.watch_patterns = watch_patterns
        if exclude_patterns:
            dashboard_server.quick_fix.exclude_patterns = exclude_patterns
            
        success = dashboard_server.quick_fix.start_file_watching()
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'File watching started',
                'watch_status': dashboard_server.quick_fix.get_watch_status()
            })
        else:
            return jsonify({'error': 'Failed to start file watching'}), 500
            
    except Exception as e:
        logger.error(f"Error starting watch mode: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/watch/stop', methods=['POST'])
def api_stop_watch():
    """Stop file watching mode"""
    try:
        success = dashboard_server.quick_fix.stop_file_watching()
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'File watching stopped'
            })
        else:
            return jsonify({'error': 'Failed to stop file watching'}), 500
            
    except Exception as e:
        logger.error(f"Error stopping watch mode: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/watch/status')
def api_watch_status():
    """Get current watch mode status"""
    try:
        status = dashboard_server.quick_fix.get_watch_status()
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error getting watch status: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================
# Smart Pattern Learning API  (Phase 2)
# ============================================================

@app.route('/api/learning/analyse', methods=['POST'])
def api_learning_analyse():
    """Analyse a code snippet and update the pattern learner."""
    try:
        data = request.json or {}
        code = data.get('code', '')
        language = data.get('language', 'JavaScript')
        file_path = data.get('file_path', '')
        if not code:
            return jsonify({'error': 'code is required'}), 400
        updated = dashboard_server.pattern_learner.analyse_code_snippet(code, language, file_path)
        return jsonify({'status': 'success', 'patterns_updated': updated})
    except Exception as e:
        logger.error(f"Error in learning/analyse: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/learning/patterns')
def api_learning_patterns():
    """Return all learned patterns."""
    try:
        lang = request.args.get('language')
        min_conf = request.args.get('min_confidence', type=float)
        if lang:
            patterns = dashboard_server.pattern_learner.get_suggestions(lang, min_conf)
        else:
            patterns = dashboard_server.pattern_learner.get_all_patterns()
            if min_conf is not None:
                patterns = [p for p in patterns if p.confidence >= min_conf]
        return jsonify({'patterns': [p.to_dict() for p in patterns]})
    except Exception as e:
        logger.error(f"Error in learning/patterns: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/learning/feedback', methods=['POST'])
def api_learning_feedback():
    """Record user feedback for a learned pattern."""
    try:
        data = request.json or {}
        pattern_id = data.get('pattern_id', '')
        file_path = data.get('file_path', '')
        was_correct = bool(data.get('was_correct', True))
        suggested_fix = data.get('suggested_fix')
        notes = data.get('notes', '')
        if not pattern_id:
            return jsonify({'error': 'pattern_id is required'}), 400
        updated = dashboard_server.pattern_learner.record_feedback(
            pattern_id, file_path, was_correct, suggested_fix, notes
        )
        return jsonify({'status': 'success', 'pattern_updated': updated})
    except Exception as e:
        logger.error(f"Error in learning/feedback: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/learning/stats')
def api_learning_stats():
    """Return learning system statistics."""
    try:
        stats = dashboard_server.pattern_learner.get_learning_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error in learning/stats: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================
# Browser Integration API  (Phase 3)
# ============================================================

@app.route('/api/browser/analyse', methods=['POST'])
def api_browser_analyse():
    """Analyse content for browser-compatibility issues."""
    try:
        data = request.json or {}
        content = data.get('content', '')
        file_type = data.get('file_type', 'html')
        source_name = data.get('source_name', '<inline>')
        if not content:
            return jsonify({'error': 'content is required'}), 400
        result = dashboard_server.browser_analyzer.analyse_content(content, file_type, source_name)
        return jsonify(result.to_dict())
    except Exception as e:
        logger.error(f"Error in browser/analyse: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/browser/analyse-file', methods=['POST'])
def api_browser_analyse_file():
    """Analyse a workspace file for browser-compatibility issues."""
    try:
        data = request.json or {}
        file_path = data.get('file_path', '')
        if not file_path:
            return jsonify({'error': 'file_path is required'}), 400
        result = dashboard_server.browser_analyzer.analyse_file(file_path)
        return jsonify(result.to_dict())
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error in browser/analyse-file: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================
# Team Collaboration API  (Phase 3)
# ============================================================

@app.route('/api/collab/members', methods=['GET'])
def api_collab_members():
    """List all registered team members."""
    try:
        members = dashboard_server.team_collab.list_members()
        return jsonify({'members': [m.to_dict() for m in members]})
    except Exception as e:
        logger.error(f"Error in collab/members: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/collab/members/register', methods=['POST'])
def api_collab_register():
    """Register a new team member."""
    try:
        data = request.json or {}
        username = data.get('username', '')
        display_name = data.get('display_name', username)
        role = data.get('role', 'contributor')
        if not username:
            return jsonify({'error': 'username is required'}), 400
        member = dashboard_server.team_collab.register_member(username, display_name, role)
        return jsonify({'status': 'success', 'member': member.to_dict()})
    except Exception as e:
        logger.error(f"Error in collab/register: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/collab/solutions', methods=['GET'])
def api_collab_solutions():
    """Search shared solutions."""
    try:
        language = request.args.get('language')
        query = request.args.get('q')
        tags_raw = request.args.get('tags')
        tags = tags_raw.split(',') if tags_raw else None
        solutions = dashboard_server.team_collab.search_solutions(language=language, tags=tags, query=query)
        return jsonify({'solutions': [s.to_dict() for s in solutions]})
    except Exception as e:
        logger.error(f"Error in collab/solutions: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/collab/solutions/share', methods=['POST'])
def api_collab_share():
    """Share a new fix solution with the team."""
    try:
        data = request.json or {}
        required = ['title', 'description', 'language', 'error_pattern', 'fix_code']
        for field in required:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        solution = dashboard_server.team_collab.share_solution(
            title=data['title'],
            description=data['description'],
            language=data['language'],
            error_pattern=data['error_pattern'],
            fix_code=data['fix_code'],
            tags=data.get('tags', []),
            author=data.get('author'),
        )
        return jsonify({'status': 'success', 'solution': solution.to_dict()})
    except Exception as e:
        logger.error(f"Error in collab/share: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/collab/solutions/<solution_id>/vote', methods=['POST'])
def api_collab_vote(solution_id):
    """Vote on a shared solution."""
    try:
        data = request.json or {}
        upvote = bool(data.get('upvote', True))
        updated = dashboard_server.team_collab.vote_solution(solution_id, upvote)
        if not updated:
            return jsonify({'error': 'Solution not found'}), 404
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Error in collab/vote: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/collab/solutions/<solution_id>/comments', methods=['GET'])
def api_collab_get_comments(solution_id):
    """Get comments for a solution."""
    try:
        comments = dashboard_server.team_collab.get_comments(solution_id)
        return jsonify({'comments': [c.to_dict() for c in comments]})
    except Exception as e:
        logger.error(f"Error in collab/comments: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/collab/solutions/<solution_id>/comments', methods=['POST'])
def api_collab_add_comment(solution_id):
    """Add a comment to a solution."""
    try:
        data = request.json or {}
        content = data.get('content', '')
        if not content:
            return jsonify({'error': 'content is required'}), 400
        comment = dashboard_server.team_collab.add_comment(
            solution_id=solution_id,
            content=content,
            author=data.get('author'),
            parent_comment_id=data.get('parent_comment_id'),
        )
        if comment is None:
            return jsonify({'error': 'Solution not found'}), 404
        return jsonify({'status': 'success', 'comment': comment.to_dict()})
    except Exception as e:
        logger.error(f"Error adding comment: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/collab/activity')
def api_collab_activity():
    """Return the team activity feed."""
    try:
        limit = request.args.get('limit', 50, type=int)
        feed = dashboard_server.team_collab.get_activity_feed(limit=limit)
        return jsonify({'activity': [a.to_dict() for a in feed]})
    except Exception as e:
        logger.error(f"Error in collab/activity: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/collab/stats')
def api_collab_stats():
    """Return team collaboration statistics."""
    try:
        stats = dashboard_server.team_collab.get_team_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error in collab/stats: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================
# Predictive Analysis API  (Phase 4)
# ============================================================

@app.route('/api/predict/analyse', methods=['POST'])
def api_predict_analyse():
    """Run predictive analysis on a code snippet."""
    try:
        data = request.json or {}
        content = data.get('content', '')
        language = data.get('language', 'Python')
        source_name = data.get('source_name', '<inline>')
        if not content:
            return jsonify({'error': 'content is required'}), 400
        profile = dashboard_server.predictive_analyzer.analyse_content(content, language, source_name)
        return jsonify(profile.to_dict())
    except Exception as e:
        logger.error(f"Error in predict/analyse: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/predict/analyse-file', methods=['POST'])
def api_predict_analyse_file():
    """Run predictive analysis on a workspace file."""
    try:
        data = request.json or {}
        file_path = data.get('file_path', '')
        if not file_path:
            return jsonify({'error': 'file_path is required'}), 400
        profile = dashboard_server.predictive_analyzer.analyse_file(file_path)
        return jsonify(profile.to_dict())
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error in predict/analyse-file: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/predict/high-risk')
def api_predict_high_risk():
    """Return files identified as high-risk based on error history."""
    try:
        threshold = request.args.get('threshold', 0.6, type=float)
        files = dashboard_server.predictive_analyzer.get_high_risk_files(threshold=threshold)
        return jsonify({'high_risk_files': files})
    except Exception as e:
        logger.error(f"Error in predict/high-risk: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/predict/record-error', methods=['POST'])
def api_predict_record_error():
    """Record an error occurrence for history-based prediction."""
    try:
        data = request.json or {}
        file_path = data.get('file_path', '')
        error_type = data.get('error_type', 'unknown')
        severity = data.get('severity', 'medium')
        if not file_path:
            return jsonify({'error': 'file_path is required'}), 400
        dashboard_server.predictive_analyzer.record_error(file_path, error_type, severity)
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Error in predict/record-error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/predict/summary')
def api_predict_summary():
    """Return a high-level predictive analysis summary."""
    try:
        summary = dashboard_server.predictive_analyzer.get_summary()
        return jsonify(summary)
    except Exception as e:
        logger.error(f"Error in predict/summary: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Create data directory if it doesn't exist
    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(exist_ok=True)
    
    print("Starting QuickFix Generator Dashboard...")
    print(f"Dashboard will be available at: http://localhost:5000")
    print(f"Workspace path: {dashboard_server.workspace_path}")
    
    # Start Flask server
    app.run(debug=True, host='0.0.0.0', port=5000)