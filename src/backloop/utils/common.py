import os
import socket
import subprocess
from pathlib import Path
from typing import Tuple


def debug_write(message: str) -> None:
    """Write debug message to /tmp/backloop-debug.txt if BACKLOOP_DEBUG is set."""
    if not os.environ.get("BACKLOOP_DEBUG"):
        return
    with open("/tmp/backloop-debug.txt", "a") as f:
        f.write(f"{message}\n")


def get_random_port() -> Tuple[socket.socket, int]:
    """Get a random available port and return the socket and port number.

    Returns the socket to avoid timing issues where the port might be taken
    between checking and using it. The caller should close the socket when done.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("", 0))
    sock.listen(1)
    port = sock.getsockname()[1]
    return sock, port


def get_base_directory() -> Path:
    """Get the base directory for file operations.

    Currently returns the git repository root, but may be extended in the future
    to support running from subdirectories.

    Returns:
        Path to the base directory for file operations.

    Raises:
        RuntimeError: If not in a git repository or git is not found.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Not a git repository or git is not found: {e.stderr}")
