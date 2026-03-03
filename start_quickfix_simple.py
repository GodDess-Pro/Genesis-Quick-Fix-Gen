#!/usr/bin/env python3
"""
QuickFix Generator Simple Startup Script
Start the dashboard server directly
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Ensure data directory exists
data_dir = project_root / "data"
data_dir.mkdir(exist_ok=True)
(data_dir / "diffs").mkdir(exist_ok=True)
(data_dir / "backups").mkdir(exist_ok=True)

try:
    print("🚀 Starting QuickFix Generator Dashboard...")
    print("📊 Dashboard will be available at: http://localhost:5000")
    print("📁 Data directory:", data_dir)
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    
    # Import and start the Flask application
    from dashboard_server import app
    
    # Start the Flask application
    app.run(
        host='127.0.0.1',
        port=5000,
        debug=True,
        threaded=True,
        use_reloader=False
    )
    
except KeyboardInterrupt:
    print("\n👋 QuickFix Generator stopped")
except Exception as e:
    print(f"❌ Error starting QuickFix Generator: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)