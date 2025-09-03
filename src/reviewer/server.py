from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from reviewer.review_session import ReviewSession
from reviewer.router import create_review_router

app = FastAPI(title="Git Diff Viewer", version="0.1.0")

# Add CORS middleware for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create a default review session for standalone mode
default_session = ReviewSession()

# Include the review router at the root level for standalone usage
app.include_router(create_review_router(default_session))


def main() -> None:
    """Entry point for the reviewer-server command."""
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()