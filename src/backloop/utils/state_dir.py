"""Utilities for managing application state directory."""

import os
from pathlib import Path


def get_state_dir() -> Path:
    """Get the application state directory using XDG_STATE_HOME or fallback to ~/.local/state."""
    xdg_state_home = os.environ.get("XDG_STATE_HOME")

    if xdg_state_home:
        state_dir = Path(xdg_state_home)
    else:
        state_dir = Path.home() / ".local" / "state"

    # Create the backloop subdirectory
    backloop_state_dir = state_dir / "backloop"
    backloop_state_dir.mkdir(parents=True, exist_ok=True)

    return backloop_state_dir
