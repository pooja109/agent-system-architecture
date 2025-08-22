#!/usr/bin/env python3
"""
Email Agent Service Runner
==========================

Alternative Python-based runner for the email agent service.
Useful for environments where shell scripts are not available.
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import List, Optional


class ServiceRunner:
    """Manages email agent service execution."""
    
    def __init__(self) -> None:
        self.service_root = Path(__file__).parent.resolve()
        os.chdir(self.service_root)
        
    def check_environment(self) -> bool:
        """Validate environment configuration."""
        validator_path = self.service_root / "config" / "env_validator.py"
        
        if not validator_path.exists():
            print("⚠️  No environment validator found, skipping validation")
            return True
        
        try:
            result = subprocess.run(
                [sys.executable, str(validator_path)],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print("❌ Environment validation failed!")
                print(result.stdout)
                print(result.stderr)
                return False
                
            print("✅ Environment validation passed")
            return True
            
        except Exception as e:
            print(f"⚠️  Error running validator: {e}")
            return True  # Continue anyway
    
    def install_dependencies(self) -> bool:
        """Install required dependencies."""
        requirements_file = self.service_root / "requirements.txt"
        
        if not requirements_file.exists():
            print("⚠️  No requirements.txt found in service directory")
            return True
        
        print("📦 Installing dependencies...")
        
        try:
            # Upgrade pip first
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
                check=True,
                capture_output=True
            )
            
            # Install requirements
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
                check=True,
                capture_output=True
            )
            
            print("✅ Dependencies installed successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install dependencies: {e}")
            return False
    
    def run(self, args: List[str]) -> int:
        """Run the email agent service."""
        # Validate input arguments
        valid_commands = {"run", "process", "test", "setup", "status", "stats"}
        valid_flags = {"--help", "-h", "--log-level", "--log-format", "--install-deps"}
        
        for arg in args:
            if not arg.startswith("-") and arg not in valid_commands:
                # Check if it's an argument to a command (like email for test)
                continue
            elif arg.startswith("-") and arg not in valid_flags and not arg.startswith("--log-"):
                print(f"❌ Invalid flag: {arg}")
                return 1
        
        # Check if we should install dependencies
        if "--install-deps" in args:
            args.remove("--install-deps")
            if not self.install_dependencies():
                return 1
        
        # Validate environment
        if not self.check_environment():
            print("\n⚠️  Environment validation failed, but continuing...")
            print("   Set REQUIRE_ENV_FILE=true to enforce validation\n")
        
        # Prepare command
        main_script = self.service_root / "main.py"
        
        if not main_script.exists():
            print("❌ Main script not found in service directory")
            return 1
        
        # Default to 'run' command if none provided
        if not args or args[0].startswith("-"):
            args = ["run"] + args
        
        print("\n📧 Starting Email Agent Service")
        print(f"   Command: {' '.join(args)}")
        print("=" * 50)
        
        # Execute main script
        try:
            result = subprocess.run(
                [sys.executable, str(main_script)] + args,
                check=False
            )
            return result.returncode
            
        except KeyboardInterrupt:
            print("\n⚫ Service interrupted by user")
            return 130
        except Exception as e:
            print(f"❌ Error running service: {e}")
            return 1


def main() -> None:
    """Main entry point."""
    runner = ServiceRunner()
    sys.exit(runner.run(sys.argv[1:]))


if __name__ == "__main__":
    main()