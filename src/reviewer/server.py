from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from reviewer.models import GitDiff, Comment, CommentRequest
from reviewer.git_service import GitService
from reviewer.comment_service import CommentService

app = FastAPI(title="Git Diff Viewer", version="0.1.0")

# Add CORS middleware for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get the project root directory (two levels up from src/reviewer/server.py)
BASE_DIR = Path(__file__).parent.parent.parent

# Initialize services
git_service = GitService()
comment_service = CommentService()

@app.get("/")
async def read_index() -> FileResponse:
    """Serve the main index.html file."""
    index_path = BASE_DIR / "index.html"
    if not index_path.exists():
        raise FileNotFoundError(f"index.html not found at {index_path}")
    return FileResponse(index_path)

@app.get("/api/diff")
async def get_diff(commit: Optional[str] = None, staged: bool = False) -> GitDiff:
    """Get diff data for a commit or current changes."""
    try:
        return git_service.get_diff(commit_hash=commit, staged=staged)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/comments")
async def get_comments(file_path: Optional[str] = None) -> List[Comment]:
    """Get all comments, optionally filtered by file path."""
    return comment_service.get_comments(file_path=file_path)

@app.post("/api/comments")
async def create_comment(request: CommentRequest) -> Comment:
    """Create a new comment."""
    return comment_service.add_comment(request)

@app.get("/api/comments/{comment_id}")
async def get_comment(comment_id: str) -> Comment:
    """Get a specific comment."""
    comment = comment_service.get_comment(comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    return comment

@app.put("/api/comments/{comment_id}")
async def update_comment(comment_id: str, content: str) -> Comment:
    """Update a comment's content."""
    comment = comment_service.update_comment(comment_id, content)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    return comment

@app.delete("/api/comments/{comment_id}")
async def delete_comment(comment_id: str) -> dict:
    """Delete a comment."""
    success = comment_service.delete_comment(comment_id)
    if not success:
        raise HTTPException(status_code=404, detail="Comment not found")
    return {"message": "Comment deleted successfully"}

def main() -> None:
    """Entry point for the reviewer-server command."""
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

if __name__ == "__main__":
    main()