from typing import Optional
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse
from pydantic import BaseModel

from reviewer.models import GitDiff
from reviewer.review_session import ReviewSession
from reviewer.utils import get_random_port
from reviewer.api_router import create_api_router

app = FastAPI(title="Git Diff Viewer", version="0.1.0")

# Add CORS middleware for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the shared API router
app.include_router(create_api_router())

# Get the project root directory
BASE_DIR = Path(__file__).parent.parent.parent

# Request models
class ApprovalRequest(BaseModel):
    timestamp: str

# Simple review session storage for standalone server
current_review_session: Optional[ReviewSession] = None

def get_or_create_review_session() -> ReviewSession:
    """Get or create a review session for standalone server."""
    global current_review_session
    if current_review_session is None:
        current_review_session = ReviewSession(commit=None, range=None, since="HEAD")
    return current_review_session

@app.get("/")
async def redirect_to_review() -> RedirectResponse:
    """Redirect to the review page with default parameters (live diff since HEAD)."""
    # Create a review session and redirect to it
    review_session = get_or_create_review_session()
    return RedirectResponse(url=f"/review/{review_session.id}/view?live=true&since=HEAD")

@app.get("/review")
async def get_review_page() -> FileResponse:
    """Serve the review.html page."""
    review_path = BASE_DIR / "review.html"
    if not review_path.exists():
        raise HTTPException(status_code=404, detail="review.html not found")
    return FileResponse(review_path)

@app.get("/review/{review_id}/view")
async def get_review_view(review_id: str) -> FileResponse:
    """Serve the review.html file for a specific review."""
    review_path = BASE_DIR / "review.html"
    if not review_path.exists():
        raise HTTPException(status_code=404, detail="review.html not found")
    return FileResponse(review_path)

@app.post("/review/{review_id}/approve")
async def approve_review(request: ApprovalRequest, review_id: str) -> dict:
    """Approve the current review."""
    try:
        # Log the approval
        approval_time = datetime.fromisoformat(request.timestamp.replace('Z', '+00:00'))
        
        print(f"Review {review_id} approved at {approval_time}")
        
        return {
            "status": "approved",
            "timestamp": request.timestamp,
            "message": f"Review {review_id} has been approved successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to approve review: {str(e)}")

@app.get("/mock")
async def get_mock_page() -> FileResponse:
    """Serve the mock demo page."""
    mock_path = BASE_DIR / "mock.html"
    if not mock_path.exists():
        raise HTTPException(status_code=404, detail="mock.html not found")
    return FileResponse(mock_path)

@app.get("/mock-data.js")
async def get_mock_data() -> FileResponse:
    """Serve the mock data JavaScript file."""
    mock_data_path = BASE_DIR / "mock-data.js"
    if not mock_data_path.exists():
        raise HTTPException(status_code=404, detail="mock-data.js not found")
    return FileResponse(mock_data_path, media_type="application/javascript")



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