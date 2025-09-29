import asyncio
import threading
import time
import socket
from typing import Dict, List, Union
from datetime import datetime
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backloop.models import Comment, CommentRequest, GitDiff, ReviewApproved, CommentStatus
from backloop.api.responses import SuccessResponse, CommentResponse
from backloop.review_session import ReviewSession
from backloop.utils.settings import settings  
from fastapi import HTTPException, Path, APIRouter, Query
from fastapi.responses import FileResponse, RedirectResponse
from pathlib import Path as PathLib
from backloop.api.router import create_api_router
from backloop.event_manager import EventManager, EventType
from backloop.file_watcher import FileWatcher

# Request models
class ApprovalRequest(BaseModel):
    timestamp: str


class ReviewManager:
    """Manages multiple review sessions and their mounted FastAPI instances."""
    
    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        """Initialize the review manager."""
        self.active_reviews: Dict[str, ReviewSession] = {}
        self._main_app: FastAPI | None = None
        self._web_server_port: int | None = None
        self._web_server_thread: threading.Thread | None = None
        self._pending_comments: asyncio.Queue[Comment] = asyncio.Queue()
        self._review_approved: Dict[str, bool] = {}  # Track approval status per review
        self._event_loop = loop
        self.event_manager = EventManager()  # Add event manager
        self.file_watcher = FileWatcher(self.event_manager, loop)  # Add file watcher
        
        # Start watching the current directory
        self.file_watcher.start_watching(str(PathLib.cwd()))
    
    def get_free_port(self) -> int:
        """Get a free port number."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port
    
    def create_review_session(self,
                            commit: str | None = None,
                            range: str | None = None,
                            since: str | None = None) -> ReviewSession:
        """Create a new review session and store it for dynamic routing."""
        # Create the review session
        review_session = ReviewSession(commit=commit, range=range, since=since)
        
        # Store it in active reviews
        self.active_reviews[review_session.id] = review_session
        
        return review_session
    
    def get_review_session(self, review_id: str) -> ReviewSession | None:
        """Get a review session by ID."""
        return self.active_reviews.get(review_id)
    
    def get_most_recent_review(self) -> ReviewSession | None:
        """Get the most recently created review session."""
        if not self.active_reviews:
            return None
        return max(self.active_reviews.values(), key=lambda r: r.created_at)
    
    def create_dynamic_router(self) -> APIRouter:
        """Create a dynamic router that handles all review paths."""
        router = APIRouter()

        # Get the static directory
        STATIC_DIR = PathLib(__file__).parent / "static"
        
        @router.get("/")
        async def redirect_to_latest_review() -> RedirectResponse:
            """Redirect to the most recent review."""
            recent_review = self.get_most_recent_review()
            if not recent_review:
                raise HTTPException(status_code=404, detail="No active reviews found")
            return RedirectResponse(url=f"/review/{recent_review.id}")
        
        
        @router.get("/review/{review_id}")
        async def redirect_to_review_view(review_id: str = Path(...)) -> RedirectResponse:
            """Redirect to the review view with proper parameters."""
            review_session = self.get_review_session(review_id)
            if not review_session:
                raise HTTPException(status_code=404, detail="Review not found")
            return RedirectResponse(url=f"/review/{review_id}/view?{review_session.view_params}")
        
        @router.get("/review/{review_id}/view")
        async def get_review_view(review_id: str = Path(...)) -> FileResponse:
            """Serve the review.html file for a specific review."""
            review_session = self.get_review_session(review_id)
            if not review_session:
                raise HTTPException(status_code=404, detail="Review not found")
            
            review_path = STATIC_DIR / "templates" / "review.html"
            if not review_path.exists():
                raise HTTPException(status_code=404, detail=f"review.html not found at {review_path}")
            return FileResponse(review_path)
        
        @router.get("/review/{review_id}/api/diff")
        async def get_review_diff(review_id: str = Path(...)) -> GitDiff:
            """Get diff data for a specific review session."""
            review_session = self.get_review_session(review_id)
            if not review_session:
                raise HTTPException(status_code=404, detail="Review not found")
            return review_session.diff
        
        @router.get("/review/{review_id}/api/comments")
        async def get_review_comments(review_id: str = Path(...), file_path: str | None = None) -> List[Comment]:
            """Get comments for a specific review session."""
            review_session = self.get_review_session(review_id)
            if not review_session:
                raise HTTPException(status_code=404, detail="Review not found")
            return review_session.comment_service.get_comments(file_path=file_path)
        
        @router.post("/review/{review_id}/api/comments")
        async def create_review_comment(request: CommentRequest, review_id: str = Path(...)) -> SuccessResponse[dict]:
            """Create a comment for a specific review session and return it with queue position."""
            review_session = self.get_review_session(review_id)
            if not review_session:
                raise HTTPException(status_code=404, detail="Review not found")
            comment, queue_position = review_session.comment_service.add_comment(request)
            
            # Add comment to pending queue for MCP server
            self.add_comment_to_queue(comment)
            
            return SuccessResponse(
                data={
                    "comment": comment.model_dump(),
                    "queue_position": queue_position
                },
                message="Comment created successfully"
            )
        
        @router.get("/review/{review_id}/api/comments/{comment_id}")
        async def get_review_comment(review_id: str = Path(...), comment_id: str = Path(...)) -> Comment:
            """Get a specific comment for a review session."""
            review_session = self.get_review_session(review_id)
            if not review_session:
                raise HTTPException(status_code=404, detail="Review not found")
            comment = review_session.comment_service.get_comment(comment_id)
            if not comment:
                raise HTTPException(status_code=404, detail="Comment not found")
            return comment
        
        @router.put("/review/{review_id}/api/comments/{comment_id}")
        async def update_review_comment(content: str, review_id: str = Path(...), comment_id: str = Path(...)) -> Comment:
            """Update a comment for a review session."""
            review_session = self.get_review_session(review_id)
            if not review_session:
                raise HTTPException(status_code=404, detail="Review not found")
            comment = review_session.comment_service.update_comment(comment_id, content)
            if not comment:
                raise HTTPException(status_code=404, detail="Comment not found")
            return comment
        
        @router.delete("/review/{review_id}/api/comments/{comment_id}")
        async def delete_review_comment(review_id: str = Path(...), comment_id: str = Path(...)) -> SuccessResponse[None]:
            """Delete a comment from a review session."""
            review_session = self.get_review_session(review_id)
            if not review_session:
                raise HTTPException(status_code=404, detail="Review not found")
            success = review_session.comment_service.delete_comment(comment_id)
            if not success:
                raise HTTPException(status_code=404, detail="Comment not found")
            return SuccessResponse(data=None, message="Comment deleted successfully")
        
        @router.post("/review/{review_id}/approve")
        async def approve_review(request: ApprovalRequest, review_id: str = Path(...)) -> SuccessResponse[dict]:
            """Approve the current review."""
            review_session = self.get_review_session(review_id)
            if not review_session:
                raise HTTPException(status_code=404, detail="Review not found")
            
            try:
                # Log the approval
                approval_time = datetime.fromisoformat(request.timestamp.replace('Z', '+00:00'))
                
                # In a real implementation, you might want to:
                # - Store the approval in a database
                # - Send notifications
                # - Update review status
                # - Integrate with external systems
                
                print(f"Review {review_id} approved at {approval_time}")
                
                # Mark review as approved and trigger event for waiting MCP tools
                if settings.debug:
                    print(f"[DEBUG] Marking review {review_id} as approved")
                self._review_approved[review_id] = True
                
                # Emit event for review approval
                await self.event_manager.emit_event(
                    EventType.REVIEW_APPROVED,
                    {
                        "review_id": review_id,
                        "timestamp": request.timestamp
                    },
                    review_id=review_id
                )
                
                # No need for manual event signaling with asyncio.Queue
                
                return SuccessResponse(
                    data={
                        "status": "approved",
                        "timestamp": request.timestamp
                    },
                    message=f"Review {review_id} has been approved successfully"
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to approve review: {str(e)}")
        
        @router.get("/api/events")
        async def get_events(
            last_event_id: str | None = Query(None, description="ID of the last event received"),
            timeout: float = Query(30.0, description="Long-polling timeout in seconds", ge=0, le=60)
        ) -> SuccessResponse[dict]:
            """Long-polling endpoint for server-side events.
            
            Returns any server-side changes since the last event ID.
            Will wait up to 'timeout' seconds for new events before returning empty.
            
            Event types:
            - comment_dequeued: A comment was removed from the review queue
            - file_changed: A file in the repository was modified (future)
            - review_approved: The review was approved
            - review_updated: The review session was updated
            """
            # Subscribe to events
            subscriber = await self.event_manager.subscribe(last_event_id)
            
            try:
                # Wait for events
                events = await self.event_manager.wait_for_events(subscriber, timeout=timeout)
                
                # Convert events to dictionaries
                event_dicts = [event.to_dict() for event in events]
                
                return SuccessResponse(
                    data={
                        "events": event_dicts,
                        "last_event_id": subscriber.last_event_id
                    },
                    message="Events retrieved successfully"
                )
            finally:
                # Unsubscribe when done
                await self.event_manager.unsubscribe(subscriber.id)
        
        return router
    
    def remove_review_session(self, review_id: str) -> bool:
        """Remove a review session and unmount it from the web server."""
        if review_id not in self.active_reviews:
            return False
        
        # Remove from active reviews
        del self.active_reviews[review_id]
        
        # Note: FastAPI doesn't support dynamic unmounting, so we leave the route
        # mounted but it will return 404s after the session is removed
        
        return True
    
    def start_web_server(self) -> int:
        """Start the web server with dynamic review mounting capability."""
        if self._web_server_port is not None:
            return self._web_server_port
        
        # Create the main FastAPI app
        self._main_app = FastAPI(title="Git Review Server", version="0.1.0")
        
        # Add CORS middleware
        self._main_app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Include the shared API router
        api_router = create_api_router()
        self._main_app.include_router(api_router)
        
        # Include the dynamic router that handles all review paths
        dynamic_router = self.create_dynamic_router()
        self._main_app.include_router(dynamic_router)
        
        # Get a free port
        port = self.get_free_port()
        
        # Start the server in a separate thread
        def run_server() -> None:
            assert self._main_app is not None
            uvicorn.run(self._main_app, host="127.0.0.1", port=port, log_level="warning")
        
        self._web_server_thread = threading.Thread(target=run_server, daemon=True)
        self._web_server_thread.start()
        self._web_server_port = port
        
        # Give the server a moment to start
        time.sleep(0.5)
        
        return port
    
    def get_web_server_port(self) -> int | None:
        """Get the current web server port, if running."""
        return self._web_server_port
    
    def add_comment_to_queue(self, comment: Comment) -> None:
        """Add a comment to the pending queue."""
        if settings.debug:
            print(f"[DEBUG] Adding comment to queue: {comment.file_path}:{comment.line_number} - {comment.content[:50]}...")
            print(f"[DEBUG] Queue length after adding: {self._pending_comments.qsize() + 1}")
        
        # Thread-safe way to put comment in queue from FastAPI thread
        if self._event_loop:
            self._event_loop.call_soon_threadsafe(self._pending_comments.put_nowait, comment)
        else:
            self._pending_comments.put_nowait(comment)
    
    async def await_comments(self) -> Union[Comment, ReviewApproved]:
        """Wait for review comments to be posted or review to be approved.
        
        Returns:
        - Comment if a comment is available
        - ReviewApproved if review is approved and no comments pending
        """
        if settings.debug:
            print("[DEBUG] await_comments called, entering wait loop")
        
        while True:
            # Check if the most recent review is approved (before waiting for comments)
            recent_review = self.get_most_recent_review()
            if recent_review and self._review_approved.get(recent_review.id, False):
                # Check if queue is empty - if so, return approval
                if self._pending_comments.empty():
                    if settings.debug:
                        print(f"[DEBUG] Review {recent_review.id} is approved and queue empty, returning ReviewApproved")
                    return ReviewApproved(
                        review_id=recent_review.id,
                        timestamp=datetime.now().isoformat()
                    )
            
            try:
                # Wait for a comment with a short timeout to periodically check approval status
                comment = await asyncio.wait_for(self._pending_comments.get(), timeout=1.0)
                
                if settings.debug:
                    print(f"[DEBUG] Returning comment from queue: {comment.file_path}:{comment.line_number}")
                    print(f"[DEBUG] Remaining comments in queue: {self._pending_comments.qsize()}")
                
                # Update comment status to 'in progress' and remove from comment service queue
                if recent_review:
                    recent_review.comment_service.update_comment_status(comment.id, CommentStatus.IN_PROGRESS)
                    recent_review.comment_service.remove_comment_from_queue(comment.id)
                
                # Emit event for comment being dequeued with updated queue positions
                await self.event_manager.emit_event(
                    EventType.COMMENT_DEQUEUED,
                    {
                        "comment_id": comment.id,
                        "file_path": comment.file_path,
                        "line_number": comment.line_number,
                        "remaining_in_queue": self._pending_comments.qsize(),
                        "status": CommentStatus.IN_PROGRESS
                    },
                    review_id=recent_review.id if recent_review else None
                )
                
                return comment
                
            except asyncio.TimeoutError:
                # Timeout occurred - continue loop to check approval status again
                if settings.debug:
                    print("[DEBUG] Queue timeout, checking approval status...")
                continue