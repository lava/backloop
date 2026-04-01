import subprocess
from pathlib import Path


def _get_git_commit() -> str | None:
    """Get the current git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


# Capture at import time so we know what code was loaded
_COMMIT_HASH = _get_git_commit()


def get_version_info() -> dict:
    """Return version information."""
    return {
        "commit": _COMMIT_HASH,
        "commit_short": _COMMIT_HASH[:8] if _COMMIT_HASH else None,
    }
