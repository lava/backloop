import asyncio
import time
from pathlib import Path
from typing import Optional, List

from mcp.server.fastmcp import FastMCP

from reviewer.git_service import GitService
from reviewer.models import GitDiff, Comment


mcp = FastMCP("Git Review Server")
git_service = GitService()

# Global state for managing comments
_pending_comments: List[Comment] = []
_comment_event = asyncio.Event()


@mcp.tool()
def startreview(
    commit: Optional[str] = None,
    range: Optional[str] = None,
    since: Optional[str] = None
) -> str:
    """Start a code review session by getting git diff data.
    
    Parameters:
    - commit: Review changes for a specific commit (e.g., 'abc123', 'HEAD', 'main')
    - range: Review changes for a commit range (e.g., 'main..feature', 'abc123..def456')
    - since: Review live changes since a commit (defaults to 'HEAD')
    
    Note: Exactly one parameter must be specified.
    """
    param_count = sum(1 for param in [commit, range, since] if param is not None)
    
    if param_count == 0:
        if since is None:
            since = "HEAD"
        git_service.get_live_diff(since)
    elif param_count > 1:
        raise ValueError("Cannot specify multiple parameters. Use exactly one of: commit, range, or since")
    elif commit:
        git_service.get_commit_diff(commit)
    elif range:
        git_service.get_range_diff(range)
    else:
        assert since is not None
        git_service.get_live_diff(since)
    
    return "Review session started successfully! Next step: Call the 'await_comments' tool to wait for review comments from the user."


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
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()