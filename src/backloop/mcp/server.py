import asyncio
import threading
from typing import Union
from pathlib import Path

import uvicorn
from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backloop.models import Comment, ReviewApproved, CommentStatus
from backloop.event_manager import EventManager, EventType
from backloop.services.review_service import ReviewService
from backloop.services.mcp_service import McpService
from backloop.api.review_router import create_review_router
from backloop.file_watcher import FileWatcher
from backloop.utils.common import get_random_port, debug_write, get_base_directory

# MCP server and services
mcp = FastMCP("backloop-mcp")
event_manager: EventManager | None = None
review_service: ReviewService | None = None
mcp_service: McpService | None = None
file_watcher: FileWatcher | None = None
web_server_port: int | None = None
web_server_thread: threading.Thread | None = None


def get_services() -> tuple[ReviewService, McpService, EventManager]:
    """Get or create the services with event loop."""
    global event_manager, review_service, mcp_service, file_watcher
    if event_manager is None:
        base_dir = get_base_directory()
        debug_write(f"[DEBUG] Initializing MCP services for directory: {base_dir}")
        loop = asyncio.get_running_loop()
        event_manager = EventManager()
        review_service = ReviewService(event_manager)
        mcp_service = McpService(review_service, event_manager, loop)

        # Initialize file watcher
        file_watcher = FileWatcher(event_manager, loop)
        file_watcher.start_watching(str(base_dir))

        # Start the review service's event listener
        review_service.start_event_listener()

        debug_write(f"[DEBUG] MCP services initialization complete")
    assert review_service is not None
    assert mcp_service is not None
    return review_service, mcp_service, event_manager


def start_web_server() -> int:
    """Start the web server in a background thread if not already running."""
    global web_server_port, web_server_thread

    if web_server_port is not None:
        debug_write(f"[DEBUG] Web server already running on port {web_server_port}")
        return web_server_port

    debug_write("[DEBUG] Starting web server...")

    review_svc, mcp_svc, event_mgr = get_services()

    # Create FastAPI app
    app = FastAPI(title="Git Diff Viewer", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    STATIC_DIR = Path(__file__).parent.parent / "static"
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Store services in app state
    app.state.review_service = review_svc
    app.state.mcp_service = mcp_svc
    app.state.event_manager = event_mgr

    # Include the review router
    app.include_router(create_review_router())

    # Get random port
    sock, port = get_random_port()
    sock.close()  # Close socket, uvicorn will reopen it
    web_server_port = port

    debug_write(f"[DEBUG] Got port {port}, starting uvicorn in background thread")

    # Start server in background thread
    def run_server() -> None:
        try:
            debug_write(f"[DEBUG] Background thread starting uvicorn on port {port}")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            uvicorn.run(app, host="127.0.0.1", port=port, log_level="error")
        except Exception as e:
            debug_write(f"[ERROR] Failed to start uvicorn: {e}")

    web_server_thread = threading.Thread(target=run_server, daemon=True)
    web_server_thread.start()

    debug_write(f"[DEBUG] Web server thread started on port {port}")

    return port


@mcp.tool()
def startreview(
    commit: str | None = None, range: str | None = None, since: str | None = None, title: str | None = None
) -> str:
    """Start a code review session.

    # Workflow:
    After starting the session, call the 'await_comments' tool and handle
    comments until the review is approved. After addressing a comment, call
    the 'resolve_comment' tool to mark it as done.

    # Parameters:
    - commit: Review changes for a specific commit (e.g., 'abc123', 'HEAD', 'main')
    - range: Review changes for a commit range (e.g., 'main..feature', 'abc123..def456')
    - since: Review live changes since a commit (defaults to 'HEAD')
    - title: Optional title for the review (will be used as the page title)

    Note: Exactly one of commit, range, or since must be specified.

    # Usage:
    This is typically used in one of three ways:
     - Reviewing changes just before committing: startreview(since='HEAD')
     - Reviewing changes just after committing changes: startreview(since='HEAD~1')
     - Reviewing a PR before pushing it: startreview(range='origin/main..HEAD')
    """
    # Get services
    review_svc, mcp_svc, event_mgr = get_services()

    # Create a new review session
    review_session = review_svc.create_review_session(
        commit=commit, range=range, since=since, title=title
    )

    # Start web server if not already running and get URL
    port = start_web_server()
    review_url = f"http://127.0.0.1:{port}/review/{review_session.id}"

    return f"""Review session started at {review_url}."""


@mcp.tool()
async def await_comments() -> Union[dict, str]:
    """Wait for review comments to be posted by the user.

    Blocks until either:
    - A comment is available (returns dict with comment details)
    - The review is approved and no comments remain (returns "REVIEW APPROVED")
    """
    review_svc, mcp_svc, event_mgr = get_services()
    result = await mcp_svc.await_comments()

    if isinstance(result, ReviewApproved):
        return "REVIEW APPROVED"
    elif isinstance(result, Comment):
        # Return comment with file name, line number, and review context
        return {
            "review_id": result.review_id,
            "id": result.id,
            "file_path": result.file_path,
            "line_number": result.line_number,
            "side": result.side,
            "content": result.content,
            "author": result.author,
        }
    else:
        # This shouldn't happen but handle it gracefully
        return "UNKNOWN RESULT"


@mcp.tool()
async def resolve_comment(comment_id: str, reply_message: str | None = None) -> str:
    """Mark a comment as resolved and emit an event to update the frontend.

    Parameters:
    - comment_id: The ID of the comment to mark as resolved
    - reply_message: OPTIONAL message to include with the resolution. Only use
      this when adding non-trivial context or encountering unforeseen issues.
      Do not send trivial replies like "ok", "done", "fixed the issue".

    Returns a status message indicating success or failure.
    """
    review_svc, mcp_svc, event_mgr = get_services()

    # Find the review session that contains this comment
    comment_found = False
    updated_comment = None

    for review_session in review_svc.active_reviews.values():
        comment = review_session.comment_service.get_comment(comment_id)
        if comment:
            # Update the comment status to RESOLVED and add reply message if provided
            updated_comment = review_session.comment_service.update_comment_status(
                comment_id, CommentStatus.RESOLVED, reply_message=reply_message
            )
            comment_found = True

            # Emit event for comment being resolved
            await event_mgr.emit_event(
                EventType.COMMENT_RESOLVED,
                {
                    "comment_id": comment_id,
                    "file_path": comment.file_path,
                    "line_number": comment.line_number,
                    "status": CommentStatus.RESOLVED.value,
                    "reply_message": reply_message,
                },
                review_id=review_session.id,
            )
            break

    if comment_found and updated_comment:
        if reply_message:
            return f"Comment {comment_id} has been marked as resolved with reply: {reply_message}"
        return f"Comment {comment_id} has been marked as resolved."
    else:
        return f"Comment {comment_id} not found in any active review session."


def main() -> None:
    """Entry point for the stdio MCP server."""
    mcp.run("stdio")


if __name__ == "__main__":
    main()
