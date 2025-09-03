import asyncio
import os
import time
import uuid
import socket
import threading
from pathlib import Path
from typing import Optional, List, Dict

from mcp.server.fastmcp import FastMCP
import uvicorn

from reviewer.git_service import GitService
from reviewer.models import GitDiff, Comment
from reviewer.server import app as review_app


# Global state for web server
_web_server_port: Optional[int] = None
_web_server_thread: Optional[threading.Thread] = None

# MCP server and tools
mcp = FastMCP("Git Review Server")
git_service = GitService()

# Global state for managing comments and review sessions
_pending_comments: List[Comment] = []
_comment_event = asyncio.Event()
_active_reviews: Dict[str, dict] = {}


def get_free_port() -> int:
    """Get a free port number."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


def start_web_server() -> int:
    """Start the web server on a random port and return the port number."""
    global _web_server_port, _web_server_thread
    
    if _web_server_port is not None:
        return _web_server_port
    
    port = get_free_port()
    
    def run_server() -> None:
        uvicorn.run(review_app, host="127.0.0.1", port=port, log_level="warning")
    
    _web_server_thread = threading.Thread(target=run_server, daemon=True)
    _web_server_thread.start()
    _web_server_port = port
    
    # Give the server a moment to start
    time.sleep(0.5)
    
    return port


@mcp.tool()
def startreview(
    commit: Optional[str] = None,
    range: Optional[str] = None,
    since: Optional[str] = None
) -> str:
    """Start a code review session by mounting the review server and getting git diff data.
    
    Parameters:
    - commit: Review changes for a specific commit (e.g., 'abc123', 'HEAD', 'main')
    - range: Review changes for a commit range (e.g., 'main..feature', 'abc123..def456')
    - since: Review live changes since a commit (defaults to 'HEAD')
    
    Note: Exactly one parameter must be specified.
    """
    global _active_reviews
    
    param_count = sum(1 for param in [commit, range, since] if param is not None)
    
    if param_count == 0:
        if since is None:
            since = "HEAD"
        diff = git_service.get_live_diff(since)
    elif param_count > 1:
        raise ValueError("Cannot specify multiple parameters. Use exactly one of: commit, range, or since")
    elif commit:
        diff = git_service.get_commit_diff(commit)
    elif range:
        diff = git_service.get_range_diff(range)
    else:
        assert since is not None
        diff = git_service.get_live_diff(since)
    
    # Generate unique review ID
    review_id = str(uuid.uuid4())[:8]
    
    # Store review session data
    _active_reviews[review_id] = {
        "diff": diff,
        "commit": commit,
        "range": range, 
        "since": since,
        "created_at": time.time()
    }
    
    # Start web server if not already running and get URL
    port = start_web_server()
    review_url = f"http://127.0.0.1:{port}"
    
    return f"""Review session started successfully!

Review ID: {review_id}
Review URL: {review_url}

Instructions: Open the above URL in your browser to view and comment on the diff.

Next step: Call the 'await_comments' tool to wait for review comments from the user."""


@mcp.tool()
async def await_comments(timeout: Optional[int] = None) -> List[Comment]:
    """Wait for review comments to be posted by the user.
    
    Parameters:
    - timeout: Maximum time to wait in seconds (default: no timeout)
    
    Returns list of comments when available.
    """
    global _comment_event, _pending_comments
    
    # Clear the event and wait for new comments
    _comment_event.clear()
    
    try:
        if timeout:
            await asyncio.wait_for(_comment_event.wait(), timeout=timeout)
        else:
            await _comment_event.wait()
            
        # Return and clear pending comments
        comments = _pending_comments.copy()
        _pending_comments.clear()
        return comments
        
    except asyncio.TimeoutError:
        return []



def main() -> None:
    """Entry point for the stdio MCP server."""
    mcp.run('stdio')


if __name__ == "__main__":
    main()