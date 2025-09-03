from pathlib import Path
from typing import List, Optional

from fastapi import HTTPException, APIRouter
from fastapi.responses import FileResponse

from reviewer.models import GitDiff, Comment, CommentRequest
from reviewer.review_session import ReviewSession


# Get the project root directory (three levels up from src/reviewer/router.py)
BASE_DIR = Path(__file__).parent.parent.parent


def create_review_router(review_session: ReviewSession) -> APIRouter:
    """Create a FastAPI router for a specific review session."""
    router = APIRouter()
    
    @router.get("/")
    async def read_index() -> FileResponse:
        """Serve the main index.html file for this review."""
        index_path = BASE_DIR / "index.html"
        if not index_path.exists():
            raise FileNotFoundError(f"index.html not found at {index_path}")
        return FileResponse(index_path)
    
    @router.get("/api/diff")
    async def get_diff() -> GitDiff:
        """Get diff data for this review session."""
        return review_session.diff

    @router.get("/api/comments")
    async def get_comments(file_path: Optional[str] = None) -> List[Comment]:
        """Get all comments for this review, optionally filtered by file path."""
        return review_session.comment_service.get_comments(file_path=file_path)

    @router.post("/api/comments")
    async def create_comment(request: CommentRequest) -> Comment:
        """Create a new comment for this review."""
        return review_session.comment_service.add_comment(request)

    @router.get("/api/comments/{comment_id}")
    async def get_comment(comment_id: str) -> Comment:
        """Get a specific comment for this review."""
        comment = review_session.comment_service.get_comment(comment_id)
        if not comment:
            raise HTTPException(status_code=404, detail="Comment not found")
        return comment

    @router.put("/api/comments/{comment_id}")
    async def update_comment(comment_id: str, content: str) -> Comment:
        """Update a comment's content for this review."""
        comment = review_session.comment_service.update_comment(comment_id, content)
        if not comment:
            raise HTTPException(status_code=404, detail="Comment not found")
        return comment

    @router.delete("/api/comments/{comment_id}")
    async def delete_comment(comment_id: str) -> dict:
        """Delete a comment from this review."""
        success = review_session.comment_service.delete_comment(comment_id)
        if not success:
            raise HTTPException(status_code=404, detail="Comment not found")
        return {"message": "Comment deleted successfully"}
    
    return router