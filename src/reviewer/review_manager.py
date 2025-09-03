import asyncio
import threading
import time
import socket
from typing import Dict, Optional, List
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from reviewer.models import Comment
from reviewer.review_session import ReviewSession  
from reviewer.router import create_review_router


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
        """Create a new review session and mount it to the web server."""
        # Create the review session
        review_session = ReviewSession(commit=commit, range=range, since=since)
        
        # Store it in active reviews
        self.active_reviews[review_session.id] = review_session
        
        # Include the review router to the main app
        if self._main_app is not None:
            review_router = create_review_router(review_session)
            self._main_app.include_router(review_router, prefix=f"/reviews/{review_session.id}")
        
        return review_session
    
    def get_review_session(self, review_id: str) -> Optional[ReviewSession]:
        """Get a review session by ID."""
        return self.active_reviews.get(review_id)
    
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
        
        # Include existing review sessions
        for review_id, review_session in self.active_reviews.items():
            review_router = create_review_router(review_session)
            self._main_app.include_router(review_router, prefix=f"/reviews/{review_id}")
        
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