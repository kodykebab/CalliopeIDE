#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Calliope IDE - Main Entry Point

A beginner-friendly CLI for starting the Calliope IDE development environment.
This script provides easy commands to start the backend server and clear instructions
for frontend setup.

Usage:
    python main.py              # Show usage instructions
    python main.py start        # Start the Flask backend server
    python main.py backend      # Start the Flask backend server (alias)
    python main.py --help       # Show detailed help
"""

import argparse
import os
import sys
import subprocess
import importlib.util
from pathlib import Path


def print_banner():
    """Print the Calliope IDE banner."""
    print("=" * 70)
    print("Calliope IDE - Development Environment")
    print("=" * 70)


def print_usage_instructions():
    """Print helpful usage instructions for beginners."""
    print_banner()
    print("\nGetting Started:")
    print("   1. Start the backend:  python main.py start")
    print("   2. In another terminal, start frontend: npm run dev")
    print("\nAvailable Commands:")
    print("   python main.py start    - Start the Flask backend server")
    print("   python main.py backend  - Start the Flask backend server (alias)")
    print("   python main.py --help   - Show detailed help information")
    print("\nFrontend Setup:")
    print("   Install dependencies: npm install")
    print("   Start development:    npm run dev")
    print("   Build for production: npm run build")
    print("\nBackend Requirements:")
    print("   Python 3.7+ required")
    print("   Install with: pip install flask flask-cors flask-sqlalchemy")
    print("                 pip install flask-migrate python-dotenv")
    print("=" * 70)


def check_python_version():
    """Check if Python version is supported."""
    if sys.version_info < (3, 7):
        print("❌ Error: Python 3.7 or higher is required.")
        print(f"   Current version: {sys.version}")
        print("   Please upgrade Python and try again.")
        return False
    return True


def check_dependency(module_name, install_name=None):
    """
    Check if a Python module is available for import.
    
    Args:
        module_name (str): The module name to import
        install_name (str): The pip package name (if different from module_name)
    
    Returns:
        bool: True if module is available, False otherwise
    """
    if install_name is None:
        install_name = module_name
        
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        print(f"Missing dependency: {module_name}")
        print(f"   Install with: pip install {install_name}")
        return False
    return True


def check_backend_dependencies():
    """
    Check if all required backend dependencies are installed.
    
    Returns:
        bool: True if all dependencies are available, False otherwise
    """
    print("Checking backend dependencies...")
    
    dependencies = [
        ('flask', 'flask'),
        ('flask_cors', 'flask-cors'),
        ('flask_sqlalchemy', 'flask-sqlalchemy'),
        ('flask_migrate', 'flask-migrate'),
        ('dotenv', 'python-dotenv'),
    ]
    
    missing_deps = []
    for module_name, install_name in dependencies:
        if not check_dependency(module_name, install_name):
            missing_deps.append(install_name)
    
    if missing_deps:
        print("\n📦 To install missing dependencies, run:")
        print(f"   pip install {' '.join(missing_deps)}")
        return False
    
    print("All backend dependencies are installed!")
    return True


def check_server_file():
    """
    Check if the server start file exists.
    
    Returns:
        bool: True if server file exists, False otherwise
    """
    server_path = Path("server/start.py")
    if not server_path.exists():
        print("Error: Backend server file not found!")
        print(f"   Expected: {server_path.absolute()}")
        print("   Make sure you're running this from the project root directory.")
        return False
    return True


def check_environment():
    """
    Check environment variables and configuration.
    
    Returns:
        bool: True if environment is properly configured, False otherwise
    """
    print("Checking environment configuration...")
    
    # Check for .env file (optional but recommended)
    env_path = Path(".env")
    if env_path.exists():
        print("Found .env configuration file")
    else:
        print("No .env file found (using default settings)")
    
    # Ensure data directory exists for SQLite database
    data_dir = Path("data")
    if not data_dir.exists():
        print(f"Creating data directory: {data_dir.absolute()}")
        try:
            data_dir.mkdir(parents=True, exist_ok=True)
            print("Data directory created successfully")
        except Exception as e:
            print(f"Failed to create data directory: {e}")
            return False
    else:
        print("Data directory exists")
    
    return True


def start_backend_server():
    """
    Start the Flask backend server.
    
    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    print_banner()
    
    # Run all pre-flight checks
    if not check_python_version():
        return 1
    
    if not check_server_file():
        return 1
    
    if not check_backend_dependencies():
        return 1
    
    if not check_environment():
        return 1
    
    print("\nStarting Calliope IDE Backend Server...")
    print("   Press Ctrl+C to stop the server")
    print("=" * 70)
    
    try:
        # Change to the project root directory
        os.chdir(Path(__file__).parent)
        
        # Start the Flask server
        result = subprocess.run([
            sys.executable, 
            "-m", 
            "server.start"
        ], check=False)
        
        return result.returncode
        
    except KeyboardInterrupt:
        print("\n\nServer stopped by user (Ctrl+C)")
        print("=" * 70)
        print("Thank you for using Calliope IDE!")
        return 0
        
    except FileNotFoundError:
        print("Error: Could not start the backend server")
        print("   Make sure you're in the correct project directory")
        return 1
        
    except Exception as e:
        print(f"Unexpected error starting server: {e}")
        print("   Please check your installation and try again")
        return 1


def create_argument_parser():
    """
    Create and configure the command-line argument parser.
    
    Returns:
        argparse.ArgumentParser: Configured argument parser
    """
    parser = argparse.ArgumentParser(
        prog='main.py',
        description='Calliope IDE - Development Environment CLI',
        epilog="""
Examples:
  python main.py                 Show usage instructions
  python main.py start           Start the backend server
  python main.py backend         Start the backend server (alias)
  
For frontend development:
  npm install                    Install frontend dependencies  
  npm run dev                    Start the Next.js development server
  
For more information, visit: https://github.com/your-repo/calliope-ide
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        'command',
        nargs='?',
        choices=['start', 'backend'],
        help='Command to execute (start/backend to launch Flask server)'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='Calliope IDE v0.1.0'
    )
    
    return parser


def main():
    """
    Main entry point for the Calliope IDE CLI.
    
    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    try:
        parser = create_argument_parser()
        args = parser.parse_args()
        
        # If no command provided, show usage instructions
        if args.command is None:
            print_usage_instructions()
            return 0
        
        # Handle start/backend commands
        if args.command in ['start', 'backend']:
            return start_backend_server()
        
        # This should never happen due to argument validation
        print(f"Unknown command: {args.command}")
        return 1
        
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        return 0
        
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
