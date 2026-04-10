from pathlib import Path

def get_project_root():
    """Searches upwards from the current directory to find the project root."""
    current_dir = Path.cwd()
    for parent in [current_dir, *current_dir.parents]:
        if (parent / "provepy_lean_project" / "lakefile.toml").exists():
            return parent / "provepy_lean_project"
    raise FileNotFoundError("Could not find lakefile.toml. Did you run 'provepy init' in your project root?")
