from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from reviewer.review_manager import ReviewManager

app = FastAPI(title="Git Diff Viewer", version="0.1.0")

# Add CORS middleware for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create a review manager and a single review session for standalone mode
review_manager = ReviewManager()
default_session = review_manager.create_review_session()

# Include the dynamic router that will handle the single review at /reviews/{review_id}
dynamic_router = review_manager.create_dynamic_router()
app.include_router(dynamic_router)

# Redirect root to the review
@app.get("/")
async def redirect_to_review() -> RedirectResponse:
    """Redirect to the single review session."""
    return RedirectResponse(url=f"/reviews/{default_session.id}")


def main() -> None:
    """Entry point for the reviewer-server command."""
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()