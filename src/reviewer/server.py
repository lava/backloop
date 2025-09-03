from typing import Optional
from pathlib import Path
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse

from reviewer.models import GitDiff
from reviewer.review_session import ReviewSession
from reviewer.utils import get_random_port

app = FastAPI(title="Git Diff Viewer", version="0.1.0")

# Add CORS middleware for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get the project root directory
BASE_DIR = Path(__file__).parent.parent.parent

@app.get("/")
async def redirect_to_review() -> RedirectResponse:
    """Redirect to the review page with default parameters (live diff since HEAD)."""
    return RedirectResponse(url="/review?live=true&since=HEAD")

@app.get("/review")
async def get_review_page() -> FileResponse:
    """Serve the review.html page."""
    review_path = BASE_DIR / "review.html"
    if not review_path.exists():
        raise HTTPException(status_code=404, detail="review.html not found")
    return FileResponse(review_path)

@app.get("/mock-data.js")
async def get_mock_data() -> FileResponse:
    """Serve the mock data JavaScript file."""
    mock_data_path = BASE_DIR / "mock-data.js"
    if not mock_data_path.exists():
        raise HTTPException(status_code=404, detail="mock-data.js not found")
    return FileResponse(mock_data_path, media_type="application/javascript")

@app.get("/api/diff")
async def get_diff(
    commit: Optional[str] = Query(None, description="Review changes for a specific commit"),
    range: Optional[str] = Query(None, description="Review changes for a commit range")
) -> GitDiff:
    """Get diff data for specific commits or ranges."""
    if not commit and not range:
        raise HTTPException(status_code=400, detail="Must specify either 'commit' or 'range' parameter")
    if commit and range:
        raise HTTPException(status_code=400, detail="Cannot specify both 'commit' and 'range' parameters")
    
    # Create a temporary review session with the provided parameters
    review_session = ReviewSession(commit=commit, range=range, since=None)
    return review_session.diff

@app.get("/api/diff/live")
async def get_live_diff(
    since: Optional[str] = Query("HEAD", description="Review live changes since a commit")
) -> GitDiff:
    """Get live diff data showing changes since a commit (defaults to HEAD)."""
    # Create a temporary review session for live changes
    review_session = ReviewSession(commit=None, range=None, since=since)
    return review_session.diff


def main() -> None:
    """Entry point for the reviewer-server command."""
    import argparse
    import uvicorn
    
    parser = argparse.ArgumentParser(description="Git Diff Reviewer Server")
    parser.add_argument("--port", type=int, help="Port to run the server on (default: random)")
    args = parser.parse_args()
    
    if args.port:
        port = args.port
        print(f"Review server available at: http://127.0.0.1:{port}")
        uvicorn.run(app, host="127.0.0.1", port=port)
    else:
        sock, port = get_random_port()
        print(f"Review server available at: http://127.0.0.1:{port}")
        uvicorn.run(app, fd=sock.fileno())


if __name__ == "__main__":
    main()