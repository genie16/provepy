import subprocess
import shutil
import platform
import sys
import argparse
from pathlib import Path

def run_shell(cmd: str, description: str):
    """Runs a shell command and provides feedback."""
    print(f"[*] {description}...")
    # Use shell=True to handle piped commands and PATH updates
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"[ERROR] {result.stderr}", file=sys.stderr)
        sys.exit(1)

def main():
    """Main entry point for the CLI package."""
    parser = argparse.ArgumentParser(description="Lean 4 Project Setup")
    
    # Simplified argument parsing: expects 'init' as a positional argument
    parser.add_argument(
        "command", 
        nargs="?", 
        choices=["init"], 
        help="Initialize Lean and Mathlib"
    )
    
    args = parser.parse_args()
    
    # If no valid command is passed, show help and exit
    if args.command != "init":
        parser.print_help()
        sys.exit(0)

    # --- Core Initialization Logic ---
    system = platform.system()
    
    # 1. Install elan (the Lean version manager)
    if not shutil.which("elan"):
        if system in ["Linux", "Darwin"]:  # Darwin is macOS
            print("Detected Unix-like system.")
            run_shell(
                "curl https://elan.lean-lang.org/elan-init.sh -sSf | sh -s -- -y",
                "Installing elan via shell script"
            )
            # Instruct user to refresh PATH
            print("[WARNING] IMPORTANT: Run 'source $HOME/.elan/env' or restart your terminal.")
            
        elif system == "Windows":
            print("Detected Windows.")
            # Official PowerShell one-liner for Windows elan install
            run_shell(
                "powershell -Command \"iwr -useb https://elan.lean-lang.org/elan-init.ps1 | iex\"",
                "Installing elan via PowerShell"
            )
        else:
            print(f"[ERROR] Unsupported OS: {system}", file=sys.stderr)
            sys.exit(1)

    # 2. Setup Lean Project and Mathlib
    # Note: We use 'lake' which is Lean's build tool included with elan

    # Determine the path to lake since it might not be in PATH yet
    home = Path.home()
    lake_cmd = "lake" # Default assuming it's in PATH
    if not shutil.which("lake"):
        lake_path_unix = home / ".elan" / "bin" / "lake"
        lake_path_windows = home / ".elan" / "bin" / "lake.exe"
        if lake_path_unix.exists():
            lake_cmd = str(lake_path_unix)
        elif lake_path_windows.exists():
            lake_cmd = str(lake_path_windows)
    
    if not Path("provepy_lean_project/lakefile.toml").exists():
        run_shell(f'"{lake_cmd}" +leanprover-community/mathlib4:lean-toolchain new provepy_lean_project math', "Creating Lean project with Mathlib4")
    
    
    print("[SUCCESS] 🚀 Lean 4 and Mathlib are ready!")

if __name__ == "__main__":
    main()