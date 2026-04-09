"""
Install git hooks for this repository.
Run once after cloning: python scripts/install_hooks.py
"""

import shutil
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
HOOKS_DIR = ROOT / ".git" / "hooks"
SCRIPTS_DIR = ROOT / "scripts"

hooks = {
    "pre-commit": SCRIPTS_DIR / "pre-commit",
}


def install():
    if not HOOKS_DIR.exists():
        print(f"ERROR: {HOOKS_DIR} not found — are you in a git repository?")
        sys.exit(1)

    for hook_name, src in hooks.items():
        dst = HOOKS_DIR / hook_name
        shutil.copy2(src, dst)
        # Make executable (Linux/Mac)
        dst.chmod(dst.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        print(f"Installed: {dst}")

    print("\nGit hooks installed successfully.")
    print("CLAUDE.md will be auto-updated with DB stats on every commit.")


if __name__ == "__main__":
    install()
