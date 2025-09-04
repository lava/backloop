from typing import Optional
from fastapi import APIRouter, Query

from reviewer.models import GitDiff
from reviewer.review_session import ReviewSession


def create_api_router() -> APIRouter:
    """Create the shared API router used by both standalone and MCP servers."""
    router = APIRouter()

    @router.get("/api/diff")
    async def get_diff(
        commit: Optional[str] = Query(None, description="Review changes for a specific commit"),
        range: Optional[str] = Query(None, description="Review changes for a commit range")
    ) -> GitDiff:
        """Get diff data for specific commits or ranges."""
        from fastapi import HTTPException
        if not commit and not range:
            raise HTTPException(status_code=400, detail="Must specify either 'commit' or 'range' parameter")
        if commit and range:
            raise HTTPException(status_code=400, detail="Cannot specify both 'commit' and 'range' parameters")
        
        # Create a temporary review session with the provided parameters
        review_session = ReviewSession(commit=commit, range=range, since=None)
        return review_session.diff

    @router.get("/api/diff/live")
    async def get_live_diff(
        since: Optional[str] = Query("HEAD", description="Review live changes since a commit")
    ) -> GitDiff:
        """Get live diff data showing changes since a commit (defaults to HEAD)."""
        # Create a temporary review session for live changes
        review_session = ReviewSession(commit=None, range=None, since=since)
        return review_session.diff

    return router