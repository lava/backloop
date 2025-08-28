from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

from reviewer.git_service import GitService
from reviewer.models import GitDiff


mcp = FastMCP("Git Review Server")
git_service = GitService()


@mcp.tool()
def startreview(
    commit: Optional[str] = None,
    range: Optional[str] = None,
    since: Optional[str] = None
) -> GitDiff:
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
        return git_service.get_live_diff(since)
    elif param_count > 1:
        raise ValueError("Cannot specify multiple parameters. Use exactly one of: commit, range, or since")
    
    if commit:
        return git_service.get_commit_diff(commit)
    elif range:
        return git_service.get_range_diff(range)
    else:
        assert since is not None
        return git_service.get_live_diff(since)


def main() -> None:
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()