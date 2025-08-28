#!/usr/bin/env python3
"""
Setup script for AEGIS CLI.
Creates a convenient 'aegis' command that can be run from anywhere.
"""

import os
import sys
import stat
import shutil
from pathlib import Path


def create_aegis_script():
    """Create the aegis command script."""
    
    # Get the absolute path to the main.py file
    aegis_dir = Path(__file__).parent.absolute()
    main_py_path = aegis_dir / "main.py"
    
    if not main_py_path.exists():
        print(f"❌ Error: main.py not found at {main_py_path}")
        return False
    
    # Create the aegis script content
    script_content = f'''#!/usr/bin/env python3
"""
AEGIS CLI wrapper script.
This script allows running AEGIS from anywhere by calling 'aegis'.
"""

import sys
import os

# Add AEGIS directory to Python path
sys.path.insert(0, "{aegis_dir}")

# Change to AEGIS directory for relative imports
os.chdir("{aegis_dir}")

# Import and run the main CLI
from cli.main import main

if __name__ == "__main__":
    sys.exit(main())
'''
    
    # Determine where to install the script
    if os.name == 'nt':  # Windows
        # On Windows, create aegis.py in the same directory
        script_path = aegis_dir / "aegis.py"
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        # Also create a batch file for easier execution
        batch_content = f'''@echo off
python "{script_path}" %*
'''
        batch_path = aegis_dir / "aegis.bat"
        with open(batch_path, 'w') as f:
            f.write(batch_content)
        
        print(f"✅ Created AEGIS CLI scripts:")
        print(f"   • Python script: {script_path}")
        print(f"   • Batch file: {batch_path}")
        print(f"\n💡 To use AEGIS from anywhere:")
        print(f"   1. Add {aegis_dir} to your PATH environment variable")
        print(f"   2. Then run 'aegis' from any directory")
        
    else:  # Unix-like systems (Linux, macOS, WSL)
        # Try to install in user's local bin directory
        local_bin = Path.home() / ".local" / "bin"
        local_bin.mkdir(parents=True, exist_ok=True)
        
        script_path = local_bin / "aegis"
        
        try:
            with open(script_path, 'w') as f:
                f.write(script_content)
            
            # Make the script executable
            script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)
            
            print(f"✅ Created AEGIS CLI script: {script_path}")
            print(f"\n💡 To use AEGIS from anywhere:")
            print(f"   • Make sure ~/.local/bin is in your PATH")
            print(f"   • Then run 'aegis' from any directory")
            print(f"\n🔧 To add ~/.local/bin to PATH, add this to your shell profile:")
            print(f"   export PATH=\"$HOME/.local/bin:$PATH\"")
            
        except PermissionError:
            # Fallback: create in current directory
            script_path = aegis_dir / "aegis"
            with open(script_path, 'w') as f:
                f.write(script_content)
            script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)
            
            print(f"✅ Created AEGIS CLI script: {script_path}")
            print(f"\n💡 To use AEGIS from anywhere:")
            print(f"   1. Add {aegis_dir} to your PATH")
            print(f"   2. Then run 'aegis' from any directory")
    
    return True


def main():
    """Main setup function."""
    print("🚀 Setting up AEGIS CLI...")
    
    if create_aegis_script():
        print(f"\n🎉 AEGIS CLI setup completed successfully!")
        print(f"\n📚 Quick Start:")
        print(f"   aegis --help          # Show all commands")
        print(f"   aegis health          # Check system health")
        print(f"   aegis config --init   # Initialize configuration")
        print(f"   aegis run --all       # Run complete workflow")
    else:
        print(f"\n❌ AEGIS CLI setup failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()