import argparse
import asyncio
import uvicorn
from pathlib import Path
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backloop.utils.common import get_random_port, debug_write, get_base_directory
from backloop.services.review_service import ReviewService
from backloop.services.mcp_service import McpService
from backloop.api.review_router import create_review_router
from backloop.event_manager import EventManager
from backloop.file_watcher import FileWatcher


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage the application's lifespan."""
    loop = asyncio.get_running_loop()

    # Initialize services
    event_manager = EventManager()
    review_service = ReviewService(event_manager)
    mcp_service = McpService(review_service, event_manager, loop)

    # Initialize file watcher
    base_dir = get_base_directory()
    debug_write(f"[DEBUG] Initializing file watcher for directory: {base_dir}")
    file_watcher = FileWatcher(event_manager, loop)
    file_watcher.start_watching(str(base_dir))
    debug_write(f"[DEBUG] File watcher initialization complete")

    # Start the review service's event listener
    review_service.start_event_listener()

    # Store services in app state
    app.state.review_service = review_service
    app.state.mcp_service = mcp_service
    app.state.event_manager = event_manager
    app.state.file_watcher = file_watcher

    # Create a default review session for standalone server
    review_service.create_review_session(since="HEAD")
    
    yield
    
    # Clean up resources on shutdown
    review_service.stop_event_listener()
    file_watcher.stop()


app = FastAPI(title="Git Diff Viewer", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include the review router
app.include_router(create_review_router())


def main() -> None:
    """Entry point for the backloop-server command."""
    parser = argparse.ArgumentParser(description="Git Diff Reviewer Server")
    parser.add_argument("--port", type=int, help="Port to run the server on (default: random)")
    args = parser.parse_args()

    port = args.port
    if not port:
        sock, port = get_random_port()
        print(f"Review server available at: http://127.0.0.1:{port}")
        uvicorn.run(app, fd=sock.fileno())
    else:
        print(f"Review server available at: http://127.0.0.1:{port}")
        uvicorn.run(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
