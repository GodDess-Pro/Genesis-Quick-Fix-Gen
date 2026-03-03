"""
QuickFix Dashboard
Web interface for monitoring and controlling the QuickFix Auto Solution Generator.
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import json
from datetime import datetime, timedelta
import threading
from pathlib import Path
import logging

# Import our QuickFix components
from quick_fix_generator import QuickFixGenerator
from solution_applier import SolutionApplier
from template_system import TemplateSystem


class QuickFixDashboard:
    """Web dashboard for QuickFix system."""
    
    def __init__(self, workspace_path: str):
        self.app = Flask(__name__)
        self.workspace_path = workspace_path
        
        # Initialize QuickFix system
        self.qfg = QuickFixGenerator(workspace_path)
        self.applier = SolutionApplier(self.qfg)
        self.template_system = TemplateSystem(self.qfg)
        
        # Setup routes
        self.setup_routes()
        
        # Dashboard state
        self.dashboard_state = {
            'monitoring_active': False,
            'auto_fix_enabled': False,
            'last_scan': None,
            'stats': {
                'total_files_monitored': 0,
                'issues_detected': 0,
                'fixes_applied': 0,
                'templates_created': 0
            }
        }

    def setup_routes(self):
        """Setup Flask routes."""
        
        @self.app.route('/')
        def dashboard():
            """Main dashboard page."""
            return render_template('dashboard.html', state=self.dashboard_state)
        
        @self.app.route('/api/status')
        def get_status():
            """Get current system status."""
            return jsonify({
                'status': 'active' if self.dashboard_state['monitoring_active'] else 'inactive',
                'auto_fix': self.dashboard_state['auto_fix_enabled'],
                'last_scan': self.dashboard_state['last_scan'],
                'stats': self.dashboard_state['stats'],
                'workspace': self.workspace_path
            })
        
        @self.app.route('/api/toggle-monitoring', methods=['POST'])
        def toggle_monitoring():
            """Toggle file monitoring."""
            try:
                if self.dashboard_state['monitoring_active']:
                    self.qfg.stop_monitoring()
                    self.dashboard_state['monitoring_active'] = False
                    message = "File monitoring stopped"
                else:
                    self.qfg.start_monitoring()
                    self.dashboard_state['monitoring_active'] = True
                    message = "File monitoring started"
                
                return jsonify({
                    'success': True,
                    'message': message,
                    'monitoring_active': self.dashboard_state['monitoring_active']
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f"Error toggling monitoring: {e}"
                })
        
        @self.app.route('/api/toggle-autofix', methods=['POST'])
        def toggle_autofix():
            """Toggle automatic fix application."""
            self.dashboard_state['auto_fix_enabled'] = not self.dashboard_state['auto_fix_enabled']
            self.qfg.config['auto_apply_fixes'] = self.dashboard_state['auto_fix_enabled']
            self.qfg.save_config()
            
            return jsonify({
                'success': True,
                'auto_fix_enabled': self.dashboard_state['auto_fix_enabled'],
                'message': f"Auto-fix {'enabled' if self.dashboard_state['auto_fix_enabled'] else 'disabled'}"
            })
        
        @self.app.route('/api/scan-workspace', methods=['POST'])
        def scan_workspace():
            """Manually scan workspace for issues."""
            try:
                # Get all relevant files
                file_paths = []
                for root, dirs, files in os.walk(self.workspace_path):
                    for file in files:
                        if self.qfg.should_monitor_file(os.path.join(root, file)):
                            file_paths.append(os.path.join(root, file))
                
                # Analyze files for issues
                all_issues = []
                for file_path in file_paths:
                    issues = self.qfg.analyze_file(file_path)
                    all_issues.extend(issues)
                
                # Update stats
                self.dashboard_state['stats']['total_files_monitored'] = len(file_paths)
                self.dashboard_state['stats']['issues_detected'] = len(all_issues)
                self.dashboard_state['last_scan'] = datetime.now().isoformat()
                
                return jsonify({
                    'success': True,
                    'message': f"Scanned {len(file_paths)} files, found {len(all_issues)} issues",
                    'files_scanned': len(file_paths),
                    'issues_found': len(all_issues),
                    'issues': all_issues[:50]  # Return first 50 issues
                })
            
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f"Error scanning workspace: {e}"
                })
        
        @self.app.route('/api/analyze-redundancy', methods=['POST'])
        def analyze_redundancy():
            """Analyze workspace for code redundancy."""
            try:
                # Get all relevant files
                file_paths = []
                for root, dirs, files in os.walk(self.workspace_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if self.qfg.should_monitor_file(file_path):
                            file_paths.append(file_path)
                
                # Analyze redundancy
                analysis = self.template_system.analyze_redundancy(file_paths)
                
                return jsonify({
                    'success': True,
                    'analysis': analysis
                })
            
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f"Error analyzing redundancy: {e}"
                })
        
        @self.app.route('/api/apply-fixes', methods=['POST'])
        def apply_fixes():
            """Apply fixes to specific files."""
            try:
                data = request.get_json()
                file_paths = data.get('files', [])
                
                results = []
                total_fixes = 0
                
                for file_path in file_paths:
                    if os.path.exists(file_path):
                        result = self.applier.apply_fixes(file_path, auto_apply=True)
                        results.append({
                            'file': file_path,
                            'result': result
                        })
                        if result['success']:
                            total_fixes += result['fixes_applied']
                
                # Update stats
                self.dashboard_state['stats']['fixes_applied'] += total_fixes
                
                return jsonify({
                    'success': True,
                    'message': f'Applied {total_fixes} fixes across {len(results)} files',
                    'results': results,
                    'total_fixes': total_fixes
                })
            
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f"Error applying fixes: {e}"
                })
        
        @self.app.route('/api/get-logs')
        def get_logs():
            """Get recent log entries."""
            try:
                logs = []
                
                # Get temp logs
                temp_logs = self.qfg.get_temp_logs()
                logs.extend([{**log, 'type': 'temp'} for log in temp_logs[-50:]])
                
                # Get master archive logs
                master_logs = self.qfg.get_master_logs()
                logs.extend([{**log, 'type': 'master'} for log in master_logs[-50:]])
                
                # Sort by timestamp
                logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
                
                return jsonify({
                    'success': True,
                    'logs': logs[:100]  # Return last 100 entries
                })
            
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f"Error getting logs: {e}",
                    'logs': []
                })
        
        @self.app.route('/api/get-statistics')
        def get_statistics():
            """Get detailed statistics."""
            try:
                # Calculate statistics from logs
                master_logs = self.qfg.get_master_logs()
                
                # Group by language
                language_stats = {}
                severity_stats = {'low': 0, 'medium': 0, 'high': 0}
                success_rate = {}
                
                for log in master_logs:
                    lang = log.get('language', 'unknown')
                    severity = log.get('severity', 'low')
                    
                    if lang not in language_stats:
                        language_stats[lang] = {'total': 0, 'fixed': 0}
                    
                    language_stats[lang]['total'] += 1
                    severity_stats[severity] += 1
                    
                    if log.get('applied_successfully'):
                        language_stats[lang]['fixed'] += 1
                
                # Calculate success rates
                for lang, stats in language_stats.items():
                    if stats['total'] > 0:
                        success_rate[lang] = (stats['fixed'] / stats['total']) * 100
                    else:
                        success_rate[lang] = 0
                
                return jsonify({
                    'success': True,
                    'statistics': {
                        'language_breakdown': language_stats,
                        'severity_breakdown': severity_stats,
                        'success_rates': success_rate,
                        'total_issues': len(master_logs),
                        'issues_today': len([log for log in master_logs if 
                                           datetime.fromisoformat(log.get('timestamp', '1970-01-01'))
                                           > datetime.now() - timedelta(days=1)])
                    }
                })
            
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f"Error getting statistics: {e}"
                })
        
        @self.app.route('/api/backups')
        def list_backups():
            """List available backups."""
            try:
                backups = self.applier.list_backups()
                return jsonify({
                    'success': True,
                    'backups': backups
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f"Error listing backups: {e}",
                    'backups': []
                })
        
        @self.app.route('/api/restore-backup', methods=['POST'])
        def restore_backup():
            """Restore from backup."""
            try:
                data = request.get_json()
                backup_path = data.get('backup_path')
                target_file = data.get('target_file')
                
                if self.applier.rollback_changes(target_file, backup_path):
                    return jsonify({
                        'success': True,
                        'message': f'Successfully restored {target_file} from backup'
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': 'Failed to restore from backup'
                    })
            
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f"Error restoring backup: {e}"
                })
        
        @self.app.route('/static/<path:filename>')
        def serve_static(filename):
            """Serve static files."""
            return send_from_directory('static', filename)

    def run(self, host='127.0.0.1', port=5000, debug=False):
        """Run the dashboard server."""
        print(f"Starting QuickFix Dashboard on http://{host}:{port}")
        print(f"Monitoring workspace: {self.workspace_path}")
        
        # Start monitoring if configured
        if self.qfg.config.get('auto_start_monitoring', False):
            self.qfg.start_monitoring()
            self.dashboard_state['monitoring_active'] = True
        
        # Start the Flask app
        self.app.run(host=host, port=port, debug=debug, threaded=True)


def create_dashboard_templates():
    """Create the HTML template for the dashboard."""
    templates_dir = "templates"
    os.makedirs(templates_dir, exist_ok=True)
    
    dashboard_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>QuickFix Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .status-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            display: inline-block;
            margin-right: 5px;
        }
        .status-active { background-color: #28a745; }
        .status-inactive { background-color: #dc3545; }
        .stats-card { transition: transform 0.2s; }
        .stats-card:hover { transform: translateY(-2px); }
        .log-entry { font-family: monospace; font-size: 0.9em; }
        .log-success { color: #28a745; }
        .log-error { color: #dc3545; }
        .log-warning { color: #ffc107; }
    </style>
</head>
<body>
    <div class="container-fluid">
        <nav class="navbar navbar-dark bg-dark mb-4">
            <div class="navbar-brand">
                <i class="fas fa-tools"></i> QuickFix Dashboard
            </div>
            <div class="navbar-text">
                <span class="status-indicator" id="statusIndicator"></span>
                <span id="statusText">Loading...</span>
            </div>
        </nav>

        <div class="row">
            <!-- Control Panel -->
            <div class="col-md-4">
                <div class="card mb-4">
                    <div class="card-header">
                        <h5><i class="fas fa-cog"></i> Control Panel</h5>
                    </div>
                    <div class="card-body">
                        <div class="d-grid gap-2 mb-3">
                            <button class="btn btn-primary" id="toggleMonitoring">
                                <i class="fas fa-play"></i> Start Monitoring
                            </button>
                            <button class="btn btn-secondary" id="toggleAutoFix">
                                <i class="fas fa-magic"></i> Enable Auto-Fix
                            </button>
                            <button class="btn btn-info" id="scanWorkspace">
                                <i class="fas fa-search"></i> Scan Workspace
                            </button>
                            <button class="btn btn-warning" id="analyzeRedundancy">
                                <i class="fas fa-clone"></i> Analyze Redundancy
                            </button>
                        </div>
                        
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" id="autoStart">
                            <label class="form-check-label" for="autoStart">
                                Auto-start monitoring
                            </label>
                        </div>
                    </div>
                </div>

                <!-- Statistics -->
                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-chart-bar"></i> Statistics</h5>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-6">
                                <div class="stats-card card bg-light text-center p-2 mb-2">
                                    <h6 class="mb-1" id="totalFiles">0</h6>
                                    <small>Files Monitored</small>
                                </div>
                            </div>
                            <div class="col-6">
                                <div class="stats-card card bg-light text-center p-2 mb-2">
                                    <h6 class="mb-1" id="issuesDetected">0</h6>
                                    <small>Issues Found</small>
                                </div>
                            </div>
                            <div class="col-6">
                                <div class="stats-card card bg-light text-center p-2 mb-2">
                                    <h6 class="mb-1" id="fixesApplied">0</h6>
                                    <small>Fixes Applied</small>
                                </div>
                            </div>
                            <div class="col-6">
                                <div class="stats-card card bg-light text-center p-2 mb-2">
                                    <h6 class="mb-1" id="templatesCreated">0</h6>
                                    <small>Templates</small>
                                </div>
                            </div>
                        </div>
                        <div class="mt-3">
                            <small class="text-muted">
                                Last scan: <span id="lastScan">Never</span>
                            </small>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Main Content -->
            <div class="col-md-8">
                <!-- Activity Log -->
                <div class="card mb-4">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <h5><i class="fas fa-list"></i> Activity Log</h5>
                        <button class="btn btn-sm btn-outline-primary" id="refreshLogs">
                            <i class="fas fa-sync"></i> Refresh
                        </button>
                    </div>
                    <div class="card-body" style="max-height: 400px; overflow-y: auto;">
                        <div id="logContainer">
                            <div class="text-center text-muted">
                                <i class="fas fa-spinner fa-spin"></i> Loading logs...
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Issues & Fixes -->
                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-bug"></i> Recent Issues</h5>
                    </div>
                    <div class="card-body">
                        <div id="issuesContainer">
                            <div class="text-center text-muted">
                                Click "Scan Workspace" to find issues
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        let dashboard = {
            state: {
                monitoring: false,
                autoFix: false
            },

            init() {
                this.loadStatus();
                this.loadLogs();
                this.setupEventListeners();
                
                // Auto-refresh every 10 seconds
                setInterval(() => {
                    this.loadStatus();
                    this.loadLogs();
                }, 10000);
            },

            setupEventListeners() {
                document.getElementById('toggleMonitoring').addEventListener('click', () => {
                    this.toggleMonitoring();
                });
                
                document.getElementById('toggleAutoFix').addEventListener('click', () => {
                    this.toggleAutoFix();
                });
                
                document.getElementById('scanWorkspace').addEventListener('click', () => {
                    this.scanWorkspace();
                });
                
                document.getElementById('analyzeRedundancy').addEventListener('click', () => {
                    this.analyzeRedundancy();
                });
                
                document.getElementById('refreshLogs').addEventListener('click', () => {
                    this.loadLogs();
                });
            },

            async loadStatus() {
                try {
                    const response = await fetch('/api/status');
                    const data = await response.json();
                    
                    this.updateStatusIndicator(data.status === 'active');
                    this.updateStats(data.stats);
                    this.updateLastScan(data.last_scan);
                    
                    this.state.monitoring = data.status === 'active';
                    this.state.autoFix = data.auto_fix;
                    
                    this.updateButtons();
                } catch (error) {
                    console.error('Error loading status:', error);
                }
            },

            updateStatusIndicator(active) {
                const indicator = document.getElementById('statusIndicator');
                const text = document.getElementById('statusText');
                
                if (active) {
                    indicator.className = 'status-indicator status-active';
                    text.textContent = 'Monitoring Active';
                } else {
                    indicator.className = 'status-indicator status-inactive';
                    text.textContent = 'Monitoring Inactive';
                }
            },

            updateStats(stats) {
                document.getElementById('totalFiles').textContent = stats.total_files_monitored;
                document.getElementById('issuesDetected').textContent = stats.issues_detected;
                document.getElementById('fixesApplied').textContent = stats.fixes_applied;
                document.getElementById('templatesCreated').textContent = stats.templates_created;
            },

            updateLastScan(lastScan) {
                const element = document.getElementById('lastScan');
                if (lastScan) {
                    const date = new Date(lastScan);
                    element.textContent = date.toLocaleString();
                } else {
                    element.textContent = 'Never';
                }
            },

            updateButtons() {
                const monitorBtn = document.getElementById('toggleMonitoring');
                const autoFixBtn = document.getElementById('toggleAutoFix');
                
                if (this.state.monitoring) {
                    monitorBtn.innerHTML = '<i class="fas fa-stop"></i> Stop Monitoring';
                    monitorBtn.className = 'btn btn-danger';
                } else {
                    monitorBtn.innerHTML = '<i class="fas fa-play"></i> Start Monitoring';
                    monitorBtn.className = 'btn btn-primary';
                }
                
                if (this.state.autoFix) {
                    autoFixBtn.innerHTML = '<i class="fas fa-magic"></i> Disable Auto-Fix';
                    autoFixBtn.className = 'btn btn-warning';
                } else {
                    autoFixBtn.innerHTML = '<i class="fas fa-magic"></i> Enable Auto-Fix';
                    autoFixBtn.className = 'btn btn-secondary';
                }
            },

            async toggleMonitoring() {
                try {
                    const response = await fetch('/api/toggle-monitoring', {
                        method: 'POST'
                    });
                    const data = await response.json();
                    
                    if (data.success) {
                        this.showMessage(data.message, 'success');
                        this.loadStatus();
                    } else {
                        this.showMessage(data.message, 'error');
                    }
                } catch (error) {
                    this.showMessage('Error toggling monitoring', 'error');
                }
            },

            async toggleAutoFix() {
                try {
                    const response = await fetch('/api/toggle-autofix', {
                        method: 'POST'
                    });
                    const data = await response.json();
                    
                    if (data.success) {
                        this.showMessage(data.message, 'success');
                        this.loadStatus();
                    } else {
                        this.showMessage(data.message, 'error');
                    }
                } catch (error) {
                    this.showMessage('Error toggling auto-fix', 'error');
                }
            },

            async scanWorkspace() {
                const btn = document.getElementById('scanWorkspace');
                btn.disabled = true;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Scanning...';
                
                try {
                    const response = await fetch('/api/scan-workspace', {
                        method: 'POST'
                    });
                    const data = await response.json();
                    
                    if (data.success) {
                        this.showMessage(data.message, 'success');
                        this.displayIssues(data.issues);
                        this.loadStatus();
                    } else {
                        this.showMessage(data.message, 'error');
                    }
                } catch (error) {
                    this.showMessage('Error scanning workspace', 'error');
                } finally {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fas fa-search"></i> Scan Workspace';
                }
            },

            async analyzeRedundancy() {
                const btn = document.getElementById('analyzeRedundancy');
                btn.disabled = true;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Analyzing...';
                
                try {
                    const response = await fetch('/api/analyze-redundancy', {
                        method: 'POST'
                    });
                    const data = await response.json();
                    
                    if (data.success) {
                        this.showRedundancyAnalysis(data.analysis);
                    } else {
                        this.showMessage(data.message, 'error');
                    }
                } catch (error) {
                    this.showMessage('Error analyzing redundancy', 'error');
                } finally {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fas fa-clone"></i> Analyze Redundancy';
                }
            },

            async loadLogs() {
                try {
                    const response = await fetch('/api/get-logs');
                    const data = await response.json();
                    
                    if (data.success) {
                        this.displayLogs(data.logs);
                    }
                } catch (error) {
                    console.error('Error loading logs:', error);
                }
            },

            displayLogs(logs) {
                const container = document.getElementById('logContainer');
                
                if (logs.length === 0) {
                    container.innerHTML = '<div class="text-center text-muted">No logs available</div>';
                    return;
                }
                
                let html = '';
                logs.forEach(log => {
                    const timestamp = new Date(log.timestamp).toLocaleTimeString();
                    const severityClass = log.severity === 'high' ? 'log-error' : 
                                         log.severity === 'medium' ? 'log-warning' : 'log-success';
                    
                    html += `
                        <div class="log-entry mb-2 p-2 border rounded">
                            <div class="d-flex justify-content-between">
                                <span class="${severityClass}">
                                    <strong>${log.language || 'Unknown'}</strong>: ${log.description}
                                </span>
                                <small class="text-muted">${timestamp}</small>
                            </div>
                            <small class="text-muted d-block">${log.file_path || ''}</small>
                        </div>
                    `;
                });
                
                container.innerHTML = html;
            },

            displayIssues(issues) {
                const container = document.getElementById('issuesContainer');
                
                if (!issues || issues.length === 0) {
                    container.innerHTML = '<div class="text-center text-muted">No issues found</div>';
                    return;
                }
                
                let html = '';
                issues.forEach(issue => {
                    const severityClass = issue.severity === 'high' ? 'danger' : 
                                         issue.severity === 'medium' ? 'warning' : 'info';
                    
                    html += `
                        <div class="alert alert-${severityClass} mb-2">
                            <div class="d-flex justify-content-between align-items-start">
                                <div>
                                    <strong>${issue.language}</strong>: ${issue.description}
                                    <br><small class="text-muted">Line ${issue.line_number}: ${issue.file_path}</small>
                                </div>
                                <button class="btn btn-sm btn-outline-primary" 
                                        onclick="dashboard.applyFixToFile('${issue.file_path}')">
                                    Fix
                                </button>
                            </div>
                        </div>
                    `;
                });
                
                container.innerHTML = html;
            },

            showRedundancyAnalysis(analysis) {
                let message = `Redundancy Analysis Complete:\\n`;
                message += `Files analyzed: ${analysis.total_files_analyzed}\\n`;
                message += `Redundant patterns: ${analysis.redundant_patterns.length}\\n`;
                message += `Potential line savings: ${analysis.potential_savings.lines_of_code}\\n`;
                message += `Templates suggested: ${analysis.suggested_templates.length}`;
                
                alert(message);
            },

            async applyFixToFile(filePath) {
                try {
                    const response = await fetch('/api/apply-fixes', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            files: [filePath]
                        })
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        this.showMessage(data.message, 'success');
                        this.scanWorkspace(); // Refresh issues
                    } else {
                        this.showMessage(data.message, 'error');
                    }
                } catch (error) {
                    this.showMessage('Error applying fix', 'error');
                }
            },

            showMessage(message, type = 'info') {
                const alertClass = type === 'success' ? 'alert-success' : 
                                  type === 'error' ? 'alert-danger' : 'alert-info';
                
                const alertDiv = document.createElement('div');
                alertDiv.className = `alert ${alertClass} alert-dismissible fade show position-fixed`;
                alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; max-width: 300px;';
                alertDiv.innerHTML = `
                    ${message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                `;
                
                document.body.appendChild(alertDiv);
                
                // Auto-remove after 5 seconds
                setTimeout(() => {
                    if (alertDiv.parentNode) {
                        alertDiv.remove();
                    }
                }, 5000);
            }
        };

        // Initialize dashboard when page loads
        document.addEventListener('DOMContentLoaded', () => {
            dashboard.init();
        });
    </script>
</body>
</html>"""
    
    with open(os.path.join(templates_dir, 'dashboard.html'), 'w', encoding='utf-8') as f:
        f.write(dashboard_html)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        workspace_path = input("Enter workspace path: ").strip()
    else:
        workspace_path = sys.argv[1]
    
    if not os.path.exists(workspace_path):
        print(f"Error: Workspace path '{workspace_path}' does not exist")
        sys.exit(1)
    
    # Create templates
    create_dashboard_templates()
    
    # Start dashboard
    dashboard = QuickFixDashboard(workspace_path)
    dashboard.run(debug=True)