import asyncio
import os
import time
import uuid
from pathlib import Path
from typing import Optional, List, Dict

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from mcp.server.fastmcp import FastMCP
from pydantic_settings import BaseSettings

from reviewer.git_service import GitService
from reviewer.models import GitDiff, Comment
from reviewer.server import app as review_app


class Settings(BaseSettings):
    """Configuration settings for the MCP server."""
    host: str = "127.0.0.1"
    port: int = 8000
    
    class Config:
        env_prefix = "MCP_"


settings = Settings()

# 1) Define MCP server and tools
mcp = FastMCP("Git Review Server")
git_service = GitService()

# Global state for managing comments and review sessions
_pending_comments: List[Comment] = []
_comment_event = asyncio.Event()
_active_reviews: Dict[str, dict] = {}

# 2) Build the MCP ASGI app (Streamable HTTP)
mcp_app = mcp.streamable_http_app()

# 3) Create FastAPI app
app = FastAPI(title="Git Review Server")

# 4) Mount the MCP endpoint under /mcp
app.mount("/mcp", mcp_app)

# 5) Mount the existing review server under /reviews
app.mount("/reviews", review_app)


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
    
    # Construct the review URL using configured host and port  
    review_url = f"http://{settings.host}:{settings.port}/reviews"
    
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
    """Entry point for the combined MCP+FastAPI server."""
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()