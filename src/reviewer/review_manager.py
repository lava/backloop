import asyncio
import threading
import time
import socket
from typing import Dict, Optional, List
from datetime import datetime
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from reviewer.models import Comment, CommentRequest, GitDiff
from reviewer.review_session import ReviewSession  
from fastapi import HTTPException, Path, APIRouter
from fastapi.responses import FileResponse, RedirectResponse
from pathlib import Path as PathLib
from reviewer.api_router import create_api_router

# Request models
class ApprovalRequest(BaseModel):
    timestamp: str


class ReviewManager:
    """Manages multiple review sessions and their mounted FastAPI instances."""
    
    def __init__(self) -> None:
        """Initialize the review manager."""
        self.active_reviews: Dict[str, ReviewSession] = {}
        self._main_app: Optional[FastAPI] = None
        self._web_server_port: Optional[int] = None
        self._web_server_thread: Optional[threading.Thread] = None
        self._pending_comments: List[Comment] = []
        self._comment_event = asyncio.Event()
    
    def get_free_port(self) -> int:
        """Get a free port number."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port
    
    def create_review_session(self,
                            commit: Optional[str] = None,
                            range: Optional[str] = None,
                            since: Optional[str] = None) -> ReviewSession:
        """Create a new review session and store it for dynamic routing."""
        # Create the review session
        review_session = ReviewSession(commit=commit, range=range, since=since)
        
        # Store it in active reviews
        self.active_reviews[review_session.id] = review_session
        
        return review_session
    
    def get_review_session(self, review_id: str) -> Optional[ReviewSession]:
        """Get a review session by ID."""
        return self.active_reviews.get(review_id)
    
    def get_most_recent_review(self) -> Optional[ReviewSession]:
        """Get the most recently created review session."""
        if not self.active_reviews:
            return None
        return max(self.active_reviews.values(), key=lambda r: r.created_at)
    
    def create_dynamic_router(self) -> APIRouter:
        """Create a dynamic router that handles all review paths."""
        router = APIRouter()
        
        # Get the project root directory
        BASE_DIR = PathLib(__file__).parent.parent.parent
        
        @router.get("/")
        async def redirect_to_latest_review() -> RedirectResponse:
            """Redirect to the most recent review."""
            recent_review = self.get_most_recent_review()
            if not recent_review:
                raise HTTPException(status_code=404, detail="No active reviews found")
            return RedirectResponse(url=f"/review/{recent_review.id}")
        
        @router.get("/mock")
        async def get_mock_page() -> FileResponse:
            """Serve the mock demo page."""
            mock_path = BASE_DIR / "mock.html"
            if not mock_path.exists():
                raise HTTPException(status_code=404, detail="mock.html not found")
            return FileResponse(mock_path)
        
        @router.get("/mock-data.js")
        async def get_mock_data() -> FileResponse:
            """Serve the mock data JavaScript file."""
            mock_data_path = BASE_DIR / "mock-data.js"
            if not mock_data_path.exists():
                raise HTTPException(status_code=404, detail="mock-data.js not found")
            return FileResponse(mock_data_path, media_type="application/javascript")
        
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
            
            review_path = BASE_DIR / "review.html"
            if not review_path.exists():
                raise HTTPException(status_code=404, detail="review.html not found")
            return FileResponse(review_path)
        
        @router.get("/review/{review_id}/api/diff")
        async def get_review_diff(review_id: str = Path(...)) -> GitDiff:
            """Get diff data for a specific review session."""
            review_session = self.get_review_session(review_id)
            if not review_session:
                raise HTTPException(status_code=404, detail="Review not found")
            return review_session.diff
        
        @router.get("/review/{review_id}/api/comments")
        async def get_review_comments(review_id: str = Path(...), file_path: Optional[str] = None) -> List[Comment]:
            """Get comments for a specific review session."""
            review_session = self.get_review_session(review_id)
            if not review_session:
                raise HTTPException(status_code=404, detail="Review not found")
            return review_session.comment_service.get_comments(file_path=file_path)
        
        @router.post("/review/{review_id}/api/comments")
        async def create_review_comment(request: CommentRequest, review_id: str = Path(...)) -> Comment:
            """Create a comment for a specific review session."""
            review_session = self.get_review_session(review_id)
            if not review_session:
                raise HTTPException(status_code=404, detail="Review not found")
            return review_session.comment_service.add_comment(request)
        
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
        async def delete_review_comment(review_id: str = Path(...), comment_id: str = Path(...)) -> dict:
            """Delete a comment from a review session."""
            review_session = self.get_review_session(review_id)
            if not review_session:
                raise HTTPException(status_code=404, detail="Review not found")
            success = review_session.comment_service.delete_comment(comment_id)
            if not success:
                raise HTTPException(status_code=404, detail="Comment not found")
            return {"message": "Comment deleted successfully"}
        
        @router.post("/review/{review_id}/approve")
        async def approve_review(request: ApprovalRequest, review_id: str = Path(...)) -> dict:
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
                
                return {
                    "status": "approved",
                    "timestamp": request.timestamp,
                    "message": f"Review {review_id} has been approved successfully"
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to approve review: {str(e)}")
        
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
    
    def get_web_server_port(self) -> Optional[int]:
        """Get the current web server port, if running."""
        return self._web_server_port
    
    def add_comment(self, comment: Comment) -> None:
        """Add a comment to the pending list and notify waiters."""
        self._pending_comments.append(comment)
        self._comment_event.set()
    
    async def await_comments(self, timeout: Optional[int] = None) -> List[Comment]:
        """Wait for review comments to be posted."""
        # Clear the event and wait for new comments
        self._comment_event.clear()
        
        try:
            if timeout:
                await asyncio.wait_for(self._comment_event.wait(), timeout=timeout)
            else:
                await self._comment_event.wait()
                
            # Return and clear pending comments
            comments = self._pending_comments.copy()
            self._pending_comments.clear()
            return comments
            
        except asyncio.TimeoutError:
            return []