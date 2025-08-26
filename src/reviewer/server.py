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
async def get_diff(
    commit: Optional[str] = None,
    range: Optional[str] = None
) -> GitDiff:
    """Get diff data for a commit or commit range.
    
    Parameters:
    - commit: Show changes for a specific commit (e.g., 'abc123', 'HEAD', 'main')
    - range: Show changes for a commit range (e.g., 'main..feature', 'abc123..def456')
    
    Note: Exactly one of commit or range must be specified.
    """
    if not commit and not range:
        raise HTTPException(status_code=400, detail="Must specify either 'commit' or 'range' parameter")
    
    if commit and range:
        raise HTTPException(status_code=400, detail="Cannot specify both 'commit' and 'range' parameters")
    
    try:
        if commit:
            return git_service.get_commit_diff(commit)
        else:
            assert range is not None  # We've already validated this above
            return git_service.get_range_diff(range)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/diff/live")
async def get_live_diff(since: str = "HEAD") -> GitDiff:
    """Get diff between current filesystem state and a commit.
    
    Parameters:
    - since: The commit to compare against (defaults to 'HEAD')
    
    This includes both staged and unstaged changes in the working directory.
    """
    try:
        return git_service.get_live_diff(since)
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