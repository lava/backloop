import argparse
import asyncio
import uvicorn
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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
    """Initialize the review manager with event loop and create default review session."""
    loop = asyncio.get_running_loop()

    # Initialize file watcher with the event loop
    review_manager.initialize_file_watcher(loop)

    # Create a default review session for standalone server
    review_manager.create_review_session(commit=None, range=None, since="HEAD")

@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Clean up resources on shutdown."""
    if review_manager.file_watcher:
        review_manager.file_watcher.stop()





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