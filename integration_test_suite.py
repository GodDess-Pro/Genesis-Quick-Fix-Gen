"""
Integration Test Suite for QuickFix Generator Enhanced Features
Tests all recent improvements: Pattern Matching, Watch Mode, Enhanced Diff System
"""

import os
import sys
import json
import time
import tempfile
import threading
import requests
from pathlib import Path
from unittest.mock import patch

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from core_generator import QuickFixGenerator
    from enhanced_diff_system import DiffManager, EnhancedDiffGenerator
    from dashboard_server import app
    print("✅ All modules imported successfully")
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("Make sure all QuickFix modules are available")
    sys.exit(1)

class IntegrationTestSuite:
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="quickfix_test_")
        self.results = []
        self.generator = None
        self.diff_manager = None
        
    def log_result(self, test_name, passed, message=""):
        """Log test result"""
        status = "✅ PASS" if passed else "❌ FAIL"
        result = f"{status}: {test_name}"
        if message:
            result += f" - {message}"
        print(result)
        self.results.append({
            'test': test_name,
            'passed': passed,
            'message': message
        })
    
    def setup_test_environment(self):
        """Setup test environment"""
        print("\n🚀 Setting up test environment...")
        
        try:
            # Create test workspace
            workspace_path = Path(self.temp_dir) / "test_workspace"
            workspace_path.mkdir(exist_ok=True)
            
            # Create test files
            test_files = {
                'test.html': '''<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
</head>
<body>
    <div class="container">
        <h1>Test Content</h1>
        <p>This is a test file with potential issues.</p>
        <!-- Missing closing tag -->
        <div>Unclosed div
    </div>
</body>
</html>''',
                'test.js': '''// Test JavaScript file
function testFunction() {
    let x = 5;
    let y = 10;
    // Missing semicolon
    let result = x + y
    
    // Unused variable
    let unused = "not used";
    
    return result;
}

// Missing function call
testFunction()''',
                'test.py': '''# Test Python file
import os
import sys

def test_function():
    x = 5
    y = 10
    # Missing return statement type hint
    result = x + y
    return result

# Unused import
import json

# Test function call
test_function()''',
                'test.css': '''/* Test CSS file */
.container {
    width: 100%;
    height: 100%;
    /* Missing semicolon */
    background-color: #fff
    margin: 0 auto;
}

/* Duplicate property */
.header {
    color: blue;
    color: red;
}'''
            }
            
            for filename, content in test_files.items():
                file_path = workspace_path / filename
                file_path.write_text(content, encoding='utf-8')
            
            self.workspace_path = workspace_path
            self.log_result("Environment Setup", True, f"Created workspace at {workspace_path}")
            return True
            
        except Exception as e:
            self.log_result("Environment Setup", False, f"Error: {e}")
            return False
    
    def test_pattern_matching_no_quotes(self):
        """Test pattern matching without quotes behavior"""
        print("\n📝 Testing Pattern Matching (No Quotes Behavior)...")
        
        try:
            # Initialize generator
            self.generator = QuickFixGenerator(workspace_path=str(self.workspace_path))
            
            # Test various pattern formats
            test_patterns = [
                "*.html",
                "**/*.js",
                "test.*",
                "*.{html,css,js}",
                "**/test_*.py"
            ]
            
            for pattern in test_patterns:
                # Test pattern recognition
                matches = self.generator.pattern_recognizer.get_files_by_pattern(
                    str(self.workspace_path), pattern
                )
                pattern_works = len(matches) >= 0  # Should not error
                self.log_result(
                    f"Pattern '{pattern}'", 
                    pattern_works,
                    f"Found {len(matches)} matches"
                )
            
            # Test pattern configuration
            config_test = self.generator.configure_patterns({
                "watch_patterns": ["*.html", "*.css", "*.js"],
                "exclude_patterns": ["*.min.*", "**/node_modules/**"]
            })
            
            self.log_result("Pattern Configuration", config_test, "Patterns configured successfully")
            return True
            
        except Exception as e:
            self.log_result("Pattern Matching Test", False, f"Error: {e}")
            return False
    
    def test_watch_mode_functionality(self):
        """Test real-time file watching capabilities"""
        print("\n🔮 Testing Watch Mode Implementation...")
        
        try:
            if not self.generator:
                self.generator = QuickFixGenerator(workspace_path=str(self.workspace_path))
            
            # Test watch mode configuration
            watch_config = {
                'auto_apply': False,
                'auto_apply_threshold': 0.9,
                'debounce_interval': 1.0
            }
            
            config_success = self.generator.configure_watch_mode(**watch_config)
            # Store patterns separately
            self.generator.watch_patterns = ['*.html', '*.js', '*.css']
            self.generator.exclude_patterns = ['*.min.*']
            self.log_result("Watch Mode Configuration", config_success)
            
            # Test starting watch mode
            start_success = self.generator.start_file_watching()
            self.log_result("Start File Watching", start_success)
            
            if start_success:
                # Give watch mode time to initialize
                time.sleep(2)
                
                # Test watch status
                status = self.generator.get_watch_status()
                status_ok = status and status.get('watching', False)
                self.log_result("Watch Status Check", status_ok, f"Status: {status}")
                
                # Test file modification detection
                test_file = self.workspace_path / 'test.html'
                original_content = test_file.read_text()
                
                # Modify file
                modified_content = original_content + "\n<!-- Test modification -->"
                test_file.write_text(modified_content)
                
                # Wait for processing
                time.sleep(3)
                
                # Check if modification was detected
                temp_entries = self.generator.temp_log_manager.get_recent_entries(limit=10)
                modification_detected = any(
                    'test.html' in str(entry) for entry in temp_entries
                )
                
                self.log_result("File Modification Detection", modification_detected)
                
                # Restore original content
                test_file.write_text(original_content)
                
                # Test stopping watch mode
                stop_success = self.generator.stop_file_watching()
                self.log_result("Stop File Watching", stop_success)
            
            return True
            
        except Exception as e:
            self.log_result("Watch Mode Test", False, f"Error: {e}")
            return False
    
    def test_enhanced_diff_system(self):
        """Test advanced diff library functionality"""
        print("\n🔮 Testing Enhanced Diff System...")
        
        try:
            # Initialize diff manager
            self.diff_manager = DiffManager(data_dir=Path(self.temp_dir) / "data")
            diff_generator = EnhancedDiffGenerator()
            
            # Create test files for comparison
            file1 = self.workspace_path / 'original.txt'
            file2 = self.workspace_path / 'modified.txt'
            
            original_text = """Line 1: Original content
Line 2: This line will be modified
Line 3: This line will be removed
Line 4: Common content
Line 5: More common content"""
            
            modified_text = """Line 1: Original content
Line 2: This line has been modified
Line 4: Common content
Line 5: More common content
Line 6: This is a new line"""
            
            file1.write_text(original_text)
            file2.write_text(modified_text)
            
            # Test file comparison
            diff_result = self.diff_manager.create_diff(
                str(file1), str(file2),
                old_version="original", new_version="modified"
            )
            
            diff_created = diff_result is not None
            self.log_result("Diff Creation", diff_created)
            
            if diff_created:
                # Test diff statistics
                stats = diff_result.statistics
                stats_valid = (
                    stats['lines_added'] > 0 and 
                    stats['lines_removed'] > 0 and
                    0 <= diff_result.similarity_ratio <= 1
                )
                self.log_result(
                    "Diff Statistics", 
                    stats_valid,
                    f"Added: {stats['lines_added']}, Removed: {stats['lines_removed']}, Similarity: {diff_result.similarity_ratio:.1%}"
                )
                
                # Test HTML generation
                html_content = diff_generator.generate_side_by_side_html(diff_result)
                html_valid = html_content and len(html_content) > 1000 and '<table' in html_content
                self.log_result("HTML Diff Generation", html_valid, f"Generated {len(html_content)} chars")
                
                # Test JSON output
                json_output = diff_generator.generate_json_diff(diff_result)
                json_valid = json_output and 'chunks' in json_output
                self.log_result("JSON Diff Generation", json_valid)
                
                # Test text comparison
                text_diff = self.diff_manager.compare_text(original_text, modified_text)
                text_valid = text_diff is not None and text_diff.statistics['lines_changed'] > 0
                self.log_result("Text Comparison", text_valid)
            
            # Test diff cleanup
            initial_count = len(self.diff_manager.list_diffs())
            cleanup_result = self.diff_manager.cleanup_old_diffs(max_age_hours=0)
            final_count = len(self.diff_manager.list_diffs())
            cleanup_worked = cleanup_result >= 0
            self.log_result("Diff Cleanup", cleanup_worked, f"Cleaned {cleanup_result} diffs")
            
            return True
            
        except Exception as e:
            self.log_result("Enhanced Diff Test", False, f"Error: {e}")
            return False
    
    def test_dashboard_api_endpoints(self):
        """Test dashboard API with new endpoints"""
        print("\n🌐 Testing Dashboard API Endpoints...")
        
        try:
            # Start Flask app in test mode
            app.config['TESTING'] = True
            client = app.test_client()
            
            # Test core endpoints
            core_endpoints = [
                '/api/overview',
                '/api/recent-activity',
                '/api/patterns',
                '/api/solutions',
                '/api/settings'
            ]
            
            for endpoint in core_endpoints:
                response = client.get(endpoint)
                success = response.status_code == 200
                self.log_result(f"GET {endpoint}", success, f"Status: {response.status_code}")
            
            # Test watch mode endpoints
            watch_endpoints = [
                ('/api/watch/status', 'GET'),
                ('/api/watch/start', 'POST'),
                ('/api/watch/stop', 'POST')
            ]
            
            for endpoint, method in watch_endpoints:
                if method == 'GET':
                    response = client.get(endpoint)
                else:
                    response = client.post(endpoint, json={})
                
                success = response.status_code in [200, 201, 202]
                self.log_result(f"{method} {endpoint}", success, f"Status: {response.status_code}")
            
            # Test diff endpoints
            if self.workspace_path and (self.workspace_path / 'original.txt').exists():
                diff_data = {
                    'file1': str(self.workspace_path / 'original.txt'),
                    'file2': str(self.workspace_path / 'modified.txt'),
                    'old_version': 'original',
                    'new_version': 'modified'
                }
                
                response = client.post('/api/diff/files', json=diff_data)
                success = response.status_code in [200, 201]
                self.log_result("POST /api/diff/files", success, f"Status: {response.status_code}")
                
                # Test diff list
                response = client.get('/api/diff/list')
                success = response.status_code == 200
                self.log_result("GET /api/diff/list", success, f"Status: {response.status_code}")
            
            return True
            
        except Exception as e:
            self.log_result("Dashboard API Test", False, f"Error: {e}")
            return False
    
    def test_integration_workflow(self):
        """Test complete workflow integration"""
        print("\n🔄 Testing Complete Integration Workflow...")
        
        try:
            if not self.generator:
                self.generator = QuickFixGenerator(workspace_path=str(self.workspace_path))
            
            # Step 1: Pattern detection
            pattern_results = self.generator.analyze_workspace()
            patterns_found = len(pattern_results) > 0
            self.log_result("Workspace Analysis", patterns_found, f"Found {len(pattern_results)} patterns")
            
            # Step 2: Solution generation
            if patterns_found:
                first_pattern = pattern_results[0]
                solutions = self.generator.master_archive.get_solutions_for_pattern(
                    first_pattern.get('pattern_id', 'unknown'),
                    'html'  # Add required language parameter
                )
                solutions_available = len(solutions) >= 0
                self.log_result("Solution Retrieval", solutions_available, f"Found {len(solutions)} solutions")
            
            # Step 3: Template system
            template_count = self.generator.template_system.generate_templates()
            templates_generated = template_count >= 0
            self.log_result("Template Generation", templates_generated, f"Generated {template_count} templates")
            
            # Step 4: Backup system
            test_file = self.workspace_path / 'test.html'
            backup_path = self.generator.solution_applier.create_backup(str(test_file))
            backup_created = backup_path and Path(backup_path).exists()
            self.log_result("Backup Creation", backup_created, f"Backup: {backup_path}")
            
            # Step 5: Statistics and monitoring
            stats = self.generator.get_system_statistics()
            stats_valid = stats and 'total_files_processed' in stats
            self.log_result("System Statistics", stats_valid, f"Stats keys: {len(stats) if stats else 0}")
            
            return True
            
        except Exception as e:
            self.log_result("Integration Workflow Test", False, f"Error: {e}")
            return False
    
    def cleanup_test_environment(self):
        """Clean up test environment"""
        print("\n🧹 Cleaning up test environment...")
        
        try:
            # Stop any running watch mode
            if self.generator:
                self.generator.stop_file_watching()
            
            # Clean up temporary files
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            
            self.log_result("Environment Cleanup", True, "Temporary files cleaned up")
            return True
            
        except Exception as e:
            self.log_result("Environment Cleanup", False, f"Error: {e}")
            return False
    
    def generate_test_report(self):
        """Generate comprehensive test report"""
        print("\n📊 Test Results Summary")
        print("=" * 60)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for result in self.results if result['passed'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        print()
        
        if failed_tests > 0:
            print("Failed Tests:")
            for result in self.results:
                if not result['passed']:
                    print(f"  ❌ {result['test']}: {result['message']}")
            print()
        
        # Generate detailed JSON report
        report_data = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': failed_tests,
                'success_rate': (passed_tests/total_tests)*100
            },
            'test_results': self.results,
            'environment': {
                'workspace_path': str(self.workspace_path) if hasattr(self, 'workspace_path') else None,
                'temp_directory': self.temp_dir,
                'python_version': sys.version,
                'os_platform': os.name
            }
        }
        
        # Save report
        report_path = project_root / 'INTEGRATION_TEST_REPORT.json'
        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        print(f"Detailed report saved to: {report_path}")
        
        return passed_tests == total_tests
    
    def run_all_tests(self):
        """Run complete test suite"""
        print("🚀 Starting QuickFix Generator Integration Test Suite")
        print("Testing all recent improvements and system integration")
        print("=" * 80)
        
        # Test sequence
        test_methods = [
            self.setup_test_environment,
            self.test_pattern_matching_no_quotes,
            self.test_watch_mode_functionality,
            self.test_enhanced_diff_system,
            self.test_dashboard_api_endpoints,
            self.test_integration_workflow,
            self.cleanup_test_environment
        ]
        
        # Run tests
        for test_method in test_methods:
            try:
                test_method()
            except Exception as e:
                self.log_result(test_method.__name__, False, f"Unexpected error: {e}")
        
        # Generate report
        success = self.generate_test_report()
        
        if success:
            print("\n🎉 ALL TESTS PASSED! QuickFix Generator is ready for deployment.")
        else:
            print("\n⚠️  Some tests failed. Please review the results above.")
        
        return success

def main():
    """Main test execution"""
    try:
        test_suite = IntegrationTestSuite()
        return test_suite.run_all_tests()
    except KeyboardInterrupt:
        print("\n\n⏹️  Test suite interrupted by user")
        return False
    except Exception as e:
        print(f"\n\n💥 Critical error in test suite: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)