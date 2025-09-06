import asyncio
from typing import Optional, List, Union

from mcp.server.fastmcp import FastMCP

from backloop.models import Comment, ReviewApproved, CommentStatus
from backloop.review_manager import ReviewManager
from backloop.event_manager import EventType

# MCP server and review manager
mcp = FastMCP("backloop-mcp")
review_manager: Optional[ReviewManager] = None

def get_review_manager() -> ReviewManager:
    """Get or create the review manager with event loop."""
    global review_manager
    if review_manager is None:
        loop = asyncio.get_running_loop()
        review_manager = ReviewManager(loop)
    return review_manager




@mcp.tool()
def startreview(
    commit: Optional[str] = None,
    range: Optional[str] = None,
    since: Optional[str] = None
) -> str:
    """Start a code review session. After starting the session, call the
    await_comments tool and handle comments until the review is approved.
    
    Parameters:
    - commit: Review changes for a specific commit (e.g., 'abc123', 'HEAD', 'main')
    - range: Review changes for a commit range (e.g., 'main..feature', 'abc123..def456')
    - since: Review live changes since a commit (defaults to 'HEAD')

    Note: Exactly one parameter must be specified.

    Usage: This is typically used in one of three ways:
     - Reviewing changes just before committing: startreview(since='HEAD')
     - Reviewing changes just after committing changes: startreview(since='HEAD~1')
     - Reviewing a PR before pushing it: startreview(range='origin/main..HEAD')
    """
    # Get review manager
    manager = get_review_manager()
    
    # Create a new review session 
    review_session = manager.create_review_session(
        commit=commit, 
        range=range, 
        since=since
    )
    
    # Start web server if not already running and get URL
    port = manager.start_web_server()
    review_url = f"http://127.0.0.1:{port}/review/{review_session.id}"
    
    return f"""Review session started at {review_url}."""


@mcp.tool()
async def await_comments() -> Union[dict, str]:
    """Wait for review comments to be posted by the user.
    
    Blocks until either:
    - A comment is available (returns dict with comment details)
    - The review is approved and no comments remain (returns "REVIEW APPROVED")
    """
    manager = get_review_manager()
    result = await manager.await_comments()
    
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


@mcp.tool()
async def resolve_comment(comment_id: str) -> str:
    """Mark a comment as resolved and emit an event to update the frontend.
    
    Parameters:
    - comment_id: The ID of the comment to mark as resolved
    
    Returns a status message indicating success or failure.
    """
    manager = get_review_manager()
    
    # Find the review session that contains this comment
    comment_found = False
    updated_comment = None
    
    for review_session in manager.active_reviews.values():
        comment = review_session.comment_service.get_comment(comment_id)
        if comment:
            # Update the comment status to RESOLVED
            updated_comment = review_session.comment_service.update_comment_status(comment_id, CommentStatus.RESOLVED)
            comment_found = True
            
            # Emit event for comment being resolved
            await manager.event_manager.emit_event(
                EventType.COMMENT_RESOLVED,
                {
                    "comment_id": comment_id,
                    "file_path": comment.file_path,
                    "line_number": comment.line_number,
                    "status": CommentStatus.RESOLVED
                },
                review_id=review_session.id
            )
            break
    
    if comment_found and updated_comment:
        return f"Comment {comment_id} has been marked as resolved."
    else:
        return f"Comment {comment_id} not found in any active review session."



def main() -> None:
    """Entry point for the stdio MCP server."""
    mcp.run('stdio')


if __name__ == "__main__":
    main()