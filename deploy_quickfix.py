#!/usr/bin/env python3
"""
QuickFix Auto Solution Generator - Deployment Script
Easy setup and launch script for the QuickFix system.
"""

import os
import sys
import subprocess
import json
from pathlib import Path
import shutil


class QuickFixDeployer:
    """Handles deployment and setup of QuickFix system."""
    
    def __init__(self):
        self.current_dir = Path(__file__).parent
        self.workspace_path = None
        self.python_executable = sys.executable
        
    def check_requirements(self):
        """Check if all required packages are installed."""
        required_packages = [
            'flask',
            'watchdog'
        ]
        
        missing_packages = []
        
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            print(f"❌ Missing required packages: {', '.join(missing_packages)}")
            print("\nInstalling missing packages...")
            
            for package in missing_packages:
                try:
                    subprocess.run([self.python_executable, '-m', 'pip', 'install', package], 
                                 check=True, capture_output=True)
                    print(f"✅ Installed {package}")
                except subprocess.CalledProcessError as e:
                    print(f"❌ Failed to install {package}: {e}")
                    return False
        
        return True
    
    def setup_directories(self):
        """Create necessary directories."""
        directories = [
            'logs/HTML',
            'logs/CSS', 
            'logs/JavaScript',
            'logs/Python',
            'templates',
            'backups'
        ]
        
        for directory in directories:
            dir_path = self.current_dir / directory
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"✅ Created directory: {directory}")
    
    def create_config(self):
        """Create default configuration file."""
        config = {
            "monitoring_enabled": True,
            "auto_apply_fixes": False,
            "backup_enabled": True,
            "auto_start_monitoring": False,
            "supported_extensions": [".html", ".css", ".js", ".py"],
            "exclude_patterns": ["node_modules", ".git", "__pycache__", ".venv"],
            "dashboard_port": 5000,
            "dashboard_host": "127.0.0.1"
        }
        
        config_path = self.current_dir / 'config.json'
        
        if not config_path.exists():
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            print("✅ Created default configuration file")
        else:
            print("✅ Configuration file already exists")
    
    def get_workspace_path(self):
        """Get workspace path from user."""
        if len(sys.argv) > 1:
            self.workspace_path = sys.argv[1]
        else:
            while True:
                workspace_input = input("\nEnter workspace path to monitor (or press Enter for current directory): ").strip()
                
                if not workspace_input:
                    self.workspace_path = str(Path.cwd())
                    break
                
                if os.path.exists(workspace_input):
                    self.workspace_path = os.path.abspath(workspace_input)
                    break
                else:
                    print(f"❌ Path '{workspace_input}' does not exist. Please try again.")
        
        print(f"✅ Workspace path set to: {self.workspace_path}")
    
    def test_system(self):
        """Test the QuickFix system components."""
        print("\n🧪 Testing QuickFix components...")
        
        try:
            # Test imports
            sys.path.insert(0, str(self.current_dir))
            
            from quick_fix_generator import QuickFixGenerator
            from solution_applier import SolutionApplier
            from template_system import TemplateSystem
            from dashboard import QuickFixDashboard
            
            # Test initialization
            qfg = QuickFixGenerator(self.workspace_path)
            applier = SolutionApplier(qfg)
            template_system = TemplateSystem(qfg)
            
            print("✅ All components imported successfully")
            print("✅ System initialization successful")
            
            # Test basic functionality
            test_file = self.current_dir / "test_sample.html"
            with open(test_file, 'w') as f:
                f.write("""
<div class="test">
    <style>
        .duplicate { color: red; color: blue; }
    </style>
</div>
""")
            
            issues = qfg.analyze_file(str(test_file))
            if issues:
                print(f"✅ Error detection working - found {len(issues)} test issues")
            
            test_file.unlink()  # Clean up
            
            return True
            
        except Exception as e:
            print(f"❌ System test failed: {e}")
            return False
    
    def create_launch_scripts(self):
        """Create convenient launch scripts."""
        
        # Create Python launch script
        launch_py = self.current_dir / 'launch_quickfix.py'
        launch_content = f'''#!/usr/bin/env python3
"""Launch QuickFix Dashboard"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from dashboard import QuickFixDashboard, create_dashboard_templates

if __name__ == '__main__':
    workspace_path = r"{self.workspace_path}"
    
    print("🚀 Starting QuickFix Dashboard...")
    print(f"📁 Monitoring workspace: {{workspace_path}}")
    
    # Create templates if needed
    create_dashboard_templates()
    
    # Start dashboard
    dashboard = QuickFixDashboard(workspace_path)
    dashboard.run(debug=False)
'''
        
        with open(launch_py, 'w') as f:
            f.write(launch_content)
        
        # Create batch file for Windows
        if os.name == 'nt':
            batch_file = self.current_dir / 'launch_quickfix.bat'
            batch_content = f'''@echo off
echo 🚀 Launching QuickFix Dashboard...
cd /d "{self.current_dir}"
"{self.python_executable}" launch_quickfix.py
pause
'''
            with open(batch_file, 'w') as f:
                f.write(batch_content)
            print("✅ Created Windows batch launcher")
        
        # Create shell script for Unix systems
        shell_script = self.current_dir / 'launch_quickfix.sh'
        shell_content = f'''#!/bin/bash
echo "🚀 Launching QuickFix Dashboard..."
cd "{self.current_dir}"
{self.python_executable} launch_quickfix.py
'''
        with open(shell_script, 'w') as f:
            f.write(shell_content)
        
        # Make executable on Unix systems
        if os.name != 'nt':
            os.chmod(shell_script, 0o755)
            print("✅ Created Unix shell launcher")
        
        print("✅ Created Python launcher")
    
    def deploy(self):
        """Run full deployment process."""
        print("🚀 QuickFix Auto Solution Generator - Deployment")
        print("=" * 50)
        
        # Step 1: Check requirements
        print("\n1️⃣ Checking requirements...")
        if not self.check_requirements():
            print("❌ Deployment failed - missing requirements")
            return False
        
        # Step 2: Setup directories
        print("\n2️⃣ Setting up directories...")
        self.setup_directories()
        
        # Step 3: Create configuration
        print("\n3️⃣ Creating configuration...")
        self.create_config()
        
        # Step 4: Get workspace path
        print("\n4️⃣ Configuring workspace...")
        self.get_workspace_path()
        
        # Step 5: Test system
        print("\n5️⃣ Testing system...")
        if not self.test_system():
            print("❌ Deployment failed - system test failed")
            return False
        
        # Step 6: Create launch scripts
        print("\n6️⃣ Creating launch scripts...")
        self.create_launch_scripts()
        
        # Success!
        print("\n" + "=" * 50)
        print("✅ QuickFix Deployment Successful!")
        print("=" * 50)
        
        print(f"""
🎉 QuickFix Auto Solution Generator is ready to use!

📍 Installation Directory: {self.current_dir}
📁 Monitoring Workspace: {self.workspace_path}

🚀 To start the system:
   • Run: python launch_quickfix.py
   • Or double-click: launch_quickfix.bat (Windows)
   • Or run: ./launch_quickfix.sh (Unix/Linux)

🌐 Dashboard will be available at: http://127.0.0.1:5000

📋 Key Features:
   ✅ Automatic error detection (HTML, CSS, JavaScript, Python)
   ✅ Intelligent fix application with backup/rollback
   ✅ Code redundancy analysis and templating
   ✅ Real-time file monitoring
   ✅ Web dashboard for monitoring and control

📖 See README.md for detailed usage instructions.
""")
        
        return True


def main():
    """Main deployment function."""
    deployer = QuickFixDeployer()
    
    try:
        success = deployer.deploy()
        if success:
            # Ask if user wants to start immediately
            start_now = input("\n🚀 Would you like to start QuickFix now? (y/n): ").lower().strip()
            if start_now in ['y', 'yes']:
                print("\n🌟 Starting QuickFix Dashboard...")
                
                # Import and start dashboard
                sys.path.insert(0, str(deployer.current_dir))
                from dashboard import QuickFixDashboard, create_dashboard_templates
                
                create_dashboard_templates()
                dashboard = QuickFixDashboard(deployer.workspace_path)
                dashboard.run(debug=False)
        else:
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n\n⛔ Deployment cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Deployment failed with error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()