from typing import Optional, List, Union

from mcp.server.fastmcp import FastMCP

from reviewer.models import Comment, ReviewApproved
from reviewer.review_manager import ReviewManager

# MCP server and review manager
mcp = FastMCP("Git Review Server")
review_manager = ReviewManager()




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
    # Create a new review session 
    review_session = review_manager.create_review_session(
        commit=commit, 
        range=range, 
        since=since
    )
    
    # Start web server if not already running and get URL
    port = review_manager.start_web_server()
    review_url = f"http://127.0.0.1:{port}/review/{review_session.id}"
    
    return f"""Review session started at {review_url}

Next step: Call the 'await_comments' tool to wait for review comments from the user."""


@mcp.tool()
async def await_comments() -> Union[dict, str]:
    """Wait for review comments to be posted by the user.
    
    Blocks until either:
    - A comment is available (returns dict with comment details)
    - The review is approved and no comments remain (returns "REVIEW APPROVED")
    """
    result = await review_manager.await_comments()
    
    if isinstance(result, ReviewApproved):
        return "REVIEW APPROVED"
    elif isinstance(result, Comment):
        # Return comment with file name and line number
        return {
            "file_path": result.file_path,
            "line_number": result.line_number,
            "side": result.side,
            "content": result.content,
            "author": result.author
        }
    else:
        # This shouldn't happen but handle it gracefully
        return "UNKNOWN RESULT"



def main() -> None:
    """Entry point for the stdio MCP server."""
    mcp.run('stdio')


if __name__ == "__main__":
    main()