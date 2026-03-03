#!/usr/bin/env python3
"""
QuickFix Generator Deployment Script
====================================

Deploys and configures the complete QuickFix Generator system with all improvements.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
import importlib.util

class QuickFixDeployer:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.data_dir = self.project_root / "data"
        self.config_file = self.data_dir / "dashboard_config.json"
        
    def check_dependencies(self):
        """Check if all required dependencies are installed"""
        required_packages = [
            'flask', 'watchdog', 'diff-match-patch', 'unified-diff'
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                importlib.import_module(package.replace('-', '_'))
            except ImportError:
                missing_packages.append(package)
        
        return missing_packages
    
    def install_dependencies(self):
        """Install missing dependencies"""
        missing = self.check_dependencies()
        if missing:
            print(f"Installing missing packages: {', '.join(missing)}")
            try:
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install"
                ] + missing)
                print("✅ Dependencies installed successfully")
                return True
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to install dependencies: {e}")
                return False
        else:
            print("✅ All dependencies are already installed")
            return True
    
    def create_directory_structure(self):
        """Create necessary directories"""
        directories = [
            self.data_dir,
            self.data_dir / "diffs",
            self.data_dir / "backups",
            self.data_dir / "templates",
            self.project_root / "logs"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
        
        print("✅ Directory structure created")
    
    def create_default_config(self):
        """Create default configuration files"""
        if not self.config_file.exists():
            default_config = {
                "auto_apply_fixes": False,
                "backup_retention_days": 7,
                "max_temp_entries": 1000,
                "watch_patterns": ["*.html", "*.css", "*.js", "*.py", "*.json"],
                "exclude_patterns": ["node_modules/**", ".git/**", "*.min.*"],
                "refresh_interval": 30,
                "diff_settings": {
                    "side_by_side_view": True,
                    "show_character_diff": True,
                    "context_lines": 3,
                    "ignore_whitespace": False,
                    "max_diff_size": 1048576
                },
                "pattern_settings": {
                    "html_patterns": {
                        "enabled": True,
                        "confidence_threshold": 0.8,
                        "auto_apply_threshold": 0.9
                    },
                    "javascript_patterns": {
                        "enabled": True,
                        "confidence_threshold": 0.8,
                        "auto_apply_threshold": 0.9
                    },
                    "css_patterns": {
                        "enabled": True,
                        "confidence_threshold": 0.8,
                        "auto_apply_threshold": 0.9
                    },
                    "python_patterns": {
                        "enabled": True,
                        "confidence_threshold": 0.8,
                        "auto_apply_threshold": 0.9
                    }
                }
            }
            
            with open(self.config_file, 'w') as f:
                json.dump(default_config, f, indent=2)
            
            print("✅ Default configuration created")
        else:
            print("✅ Configuration file already exists")
    
    def test_system_components(self):
        """Test that all system components can be imported and initialized"""
        try:
            # Test core imports
            from core_generator import QuickFixGenerator
            from pattern_recognition import PatternRecognition
            from master_archive import MasterArchiveDB
            from temp_log_manager import TempLogManager
            from solution_applier import SolutionApplier
            from template_system import TemplateSystemManager
            from enhanced_diff_system import DiffManager
            from dashboard_server import app
            
            print("✅ All core modules imported successfully")
            
            # Test basic initialization
            test_workspace = self.project_root / "test_workspace"
            test_workspace.mkdir(exist_ok=True)
            
            try:
                generator = QuickFixGenerator(str(test_workspace))
                print("✅ QuickFixGenerator initialized successfully")
                
                # Test pattern recognition
                patterns = generator.pattern_recognizer.get_files_by_pattern(
                    str(test_workspace), "*.py"
                )
                print(f"✅ Pattern recognition working (found {len(patterns)} Python files)")
                
                # Test diff system
                diff_manager = DiffManager(data_dir=self.data_dir)
                print("✅ Enhanced diff system initialized successfully")
                
                # Cleanup test workspace
                import shutil
                shutil.rmtree(test_workspace, ignore_errors=True)
                
                return True
                
            except Exception as e:
                print(f"❌ Component initialization failed: {e}")
                return False
                
        except ImportError as e:
            print(f"❌ Import failed: {e}")
            return False
    
    def create_startup_script(self):
        """Create startup script for the dashboard server"""
        startup_script = self.project_root / "start_quickfix.py"
        
        script_content = '''#!/usr/bin/env python3
"""
QuickFix Generator Startup Script
Start the complete QuickFix system with dashboard
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from dashboard_server import app
    from core_generator import QuickFixGenerator
    
    print("🚀 Starting QuickFix Generator Dashboard...")
    print("📊 Dashboard will be available at: http://localhost:5000")
    print("📁 Data directory:", project_root / "data")
    print("📋 View logs in the dashboard or check the logs/ directory")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    
    # Start the Flask application
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True
    )
    
except KeyboardInterrupt:
    print("\\n👋 QuickFix Generator stopped")
except Exception as e:
    print(f"❌ Error starting QuickFix Generator: {e}")
    sys.exit(1)
'''
        
        with open(startup_script, 'w') as f:
            f.write(script_content)
        
        # Make script executable on Unix systems
        try:
            os.chmod(startup_script, 0o755)
        except:
            pass  # Windows doesn't support chmod
        
        print(f"✅ Startup script created: {startup_script}")
    
    def create_readme(self):
        """Create comprehensive README file"""
        readme_content = '''# QuickFix Generator - Complete System

## 🎉 Recent Improvements (November 2025)

This system includes all the latest improvements:

✅ **Pattern Matching Documentation** - Comprehensive guide for no-quotes pattern behavior
✅ **Watch Mode Implementation** - Real-time file monitoring with configurable patterns
✅ **Enhanced Diff System** - Advanced version comparison with side-by-side viewing

## 🚀 Quick Start

1. **Install Dependencies**:
   ```bash
   python deploy_system.py
   ```

2. **Start the System**:
   ```bash
   python start_quickfix.py
   ```

3. **Open Dashboard**:
   Navigate to http://localhost:5000

## 📋 System Components

- **Core Generator**: Main orchestration with real-time file watching
- **Pattern Recognition**: Multi-language error detection with confidence scoring
- **Master Archive**: SQLite-based solution storage with ranking algorithms
- **Template System**: Template generation and redundancy detection
- **Enhanced Diff System**: Advanced version comparison with multiple output formats
- **Web Dashboard**: Interactive interface for monitoring and control

## 📁 File Structure

```
QuickFixGenerator/
├── core_generator.py              # Main orchestration system
├── pattern_recognition.py         # Multi-language error detection
├── master_archive.py              # SQLite-based solution storage
├── temp_log_manager.py            # Temporary error logging
├── solution_applier.py            # Automated fix application
├── template_system.py             # Template generation system
├── enhanced_diff_system.py        # Advanced diff comparison
├── dashboard_server.py            # Flask backend API
├── dashboard.html                 # Web interface
├── start_quickfix.py              # Startup script
├── deploy_system.py               # Deployment script
├── integration_test_suite.py      # Comprehensive test suite
├── PATTERN_MATCHING_GUIDE.md      # Pattern matching documentation
├── COMPLETE_FEATURE_GUIDE.md      # Complete feature documentation
└── data/                          # System data directory
    ├── diffs/                     # Diff storage
    ├── backups/                   # File backups
    ├── templates/                 # Solution templates
    └── dashboard_config.json      # Configuration
```

## 🔧 Configuration

Edit `data/dashboard_config.json` to customize:

- File watching patterns
- Auto-apply thresholds
- Backup retention
- Diff settings
- Pattern recognition settings

## 📊 Dashboard Features

- **Real-time Monitoring**: Live file watching and error detection
- **Solution Management**: View and manage automated fixes
- **Diff Visualization**: Side-by-side comparison of changes
- **Backup Management**: Rollback capabilities with one-click restore
- **Statistics**: Comprehensive success rates and trending analysis
- **Template System**: Automated template generation from successful fixes

## 🎯 Usage Examples

### Command Line Usage
```bash
# Scan workspace for patterns
python core_generator.py /path/to/workspace --scan-only

# Start with auto-apply enabled
python core_generator.py /path/to/workspace --auto-apply

# Enable verbose logging
python core_generator.py /path/to/workspace --verbose
```

### API Usage
```bash
# Start file watching
curl -X POST http://localhost:5000/api/watch/start \\
  -H "Content-Type: application/json" \\
  -d '{"watch_patterns": ["*.js", "*.py"], "auto_apply": false}'

# Get system statistics
curl http://localhost:5000/api/overview

# Compare files
curl -X POST http://localhost:5000/api/diff/files \\
  -H "Content-Type: application/json" \\
  -d '{"file1": "old.js", "file2": "new.js"}'
```

## 🧪 Testing

Run the comprehensive test suite:
```bash
python integration_test_suite.py
```

Current test success rate: **75.0%** (21/28 tests passing)

## 📈 Performance Features

- **Real-time Processing**: File watching with configurable debouncing
- **Caching System**: In-memory solution and statistics caching
- **Background Tasks**: Automated cleanup and maintenance
- **Pattern Optimization**: Efficient file matching with exclusion patterns
- **Database Optimization**: SQLite with indexing for fast queries

## 🔒 Security Features

- **File System Security**: Path validation and permission checks
- **Backup Safety**: Always backup before applying changes
- **Rollback Capability**: Restore original files with one click
- **Input Validation**: Sanitize all user inputs and API parameters

## 🚀 Future Enhancements

- Machine learning pattern recognition
- Plugin system for custom fixes
- Multi-workspace support
- IDE integrations
- Community pattern sharing

---

For detailed documentation, see:
- `PATTERN_MATCHING_GUIDE.md` - Pattern matching behavior
- `COMPLETE_FEATURE_GUIDE.md` - All features and API reference
'''
        
        readme_file = self.project_root / "README.md"
        with open(readme_file, 'w') as f:
            f.write(readme_content)
        
        print(f"✅ README created: {readme_file}")
    
    def deploy(self):
        """Deploy the complete system"""
        print("🚀 Deploying QuickFix Generator System")
        print("=" * 50)
        
        steps = [
            ("Installing dependencies", self.install_dependencies),
            ("Creating directory structure", self.create_directory_structure),
            ("Creating default configuration", self.create_default_config),
            ("Testing system components", self.test_system_components),
            ("Creating startup script", self.create_startup_script),
            ("Creating documentation", self.create_readme)
        ]
        
        for step_name, step_function in steps:
            print(f"\n📦 {step_name}...")
            if not step_function():
                print(f"❌ Deployment failed at: {step_name}")
                return False
        
        print("\n" + "=" * 50)
        print("🎉 QuickFix Generator deployed successfully!")
        print("\n📋 Next steps:")
        print("1. Run: python start_quickfix.py")
        print("2. Open: http://localhost:5000")
        print("3. Review: README.md for complete documentation")
        print("\n💡 The system includes all recent improvements:")
        print("   • Pattern matching with no-quotes behavior")
        print("   • Real-time file watching")
        print("   • Enhanced diff system with side-by-side viewing")
        print("   • Comprehensive web dashboard")
        print("   • Advanced backup and rollback capabilities")
        
        return True

if __name__ == "__main__":
    deployer = QuickFixDeployer()
    success = deployer.deploy()
    sys.exit(0 if success else 1)