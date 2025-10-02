import argparse
import asyncio
import uvicorn
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backloop.models import GitDiff
from backloop.review_session import ReviewSession
from backloop.utils.common import get_random_port
from backloop.api.router import create_api_router
from backloop.review_manager import ReviewManager

app = FastAPI(title="Git Diff Viewer", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent.parent.parent
STATIC_DIR = Path(__file__).parent / "static"

# Request models
class ApprovalRequest(BaseModel):
    timestamp: str

# Simple review session storage for standalone server
current_review_session: ReviewSession | None = None

# Create review manager at module level (without event loop)
review_manager = ReviewManager()

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include the shared API router
app.include_router(create_api_router())

# Include the dynamic router at module level
dynamic_router = review_manager.create_dynamic_router()
app.include_router(dynamic_router)

@app.on_event("startup")
async def startup_event() -> None:
    """Initialize the review manager with event loop."""
    loop = asyncio.get_running_loop()

    # Initialize file watcher with the event loop
    review_manager.initialize_file_watcher(loop)

@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Clean up resources on shutdown."""
    if review_manager.file_watcher:
        review_manager.file_watcher.stop()

def get_or_create_review_session() -> ReviewSession:
    """Get or create a review session for standalone server."""
    global current_review_session
    if current_review_session is None:
        current_review_session = ReviewSession(commit=None, range=None, since="HEAD")
    return current_review_session

@app.get("/")
async def redirect_to_review() -> RedirectResponse:
    """Redirect to the review page with default parameters (live diff since HEAD)."""
    review_session = get_or_create_review_session()
    return RedirectResponse(url=f"/review/{review_session.id}/view?live=true&since=HEAD")

@app.get("/review")
async def get_review_page() -> FileResponse:
    """Serve the review.html page."""
    review_path = STATIC_DIR / "templates" / "review.html"
    if not review_path.exists():
        raise HTTPException(status_code=404, detail="review.html template not found")
    return FileResponse(review_path)

@app.get("/review/{review_id}/view")
async def get_review_view(review_id: str) -> FileResponse:
    """Serve the review.html file for a specific review."""
    review_path = STATIC_DIR / "templates" / "review.html"
    if not review_path.exists():
        raise HTTPException(status_code=404, detail=f"review.html not found at {review_path}")
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




def main() -> None:
    """Entry point for the backloop-server command."""
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