from typing import List
from datetime import datetime
from pathlib import Path as PathLib
import subprocess

from fastapi import APIRouter, Path, HTTPException, Query, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse, RedirectResponse, PlainTextResponse
from pydantic import BaseModel

from backloop.models import Comment, CommentRequest, FileEditRequest, GitDiff, CommentStatus, ReviewInfo
from backloop.api.responses import SuccessResponse
from backloop.event_manager import EventType
from backloop.config import settings


class ApprovalRequest(BaseModel):
    timestamp: str


def create_review_router() -> APIRouter:
    """Create a router for all review-related API endpoints."""
    router = APIRouter()
    STATIC_DIR = PathLib(__file__).parent.parent / "static"

    def _resolve_repo_path(repo_root: PathLib, raw_path: str) -> PathLib:
        """Resolve a user-supplied path within the repository root."""
        candidate = PathLib(raw_path)
        if not candidate.is_absolute():
            candidate = repo_root / candidate
        candidate = candidate.resolve()
        try:
            candidate.relative_to(repo_root)
        except ValueError:
            raise HTTPException(status_code=400, detail="Path is outside repository root")
        return candidate

    @router.get("/health")
    async def health_check() -> dict:
        """Health check endpoint for monitoring and testing."""
        return {"status": "ok"}

    @router.get("/favicon.ico")
    async def get_favicon() -> FileResponse:
        favicon_path = STATIC_DIR / "favicon.ico"
        if not favicon_path.exists():
            raise HTTPException(status_code=404, detail="Favicon not found")
        return FileResponse(favicon_path, media_type="image/x-icon")

    @router.get("/static/favicon.svg")
    async def get_favicon_svg() -> FileResponse:
        favicon_path = STATIC_DIR / "favicon.svg"
        if not favicon_path.exists():
            raise HTTPException(status_code=404, detail="Favicon not found")
        return FileResponse(favicon_path, media_type="image/svg+xml")

    @router.get("/")
    async def redirect_to_latest_review(request: Request) -> RedirectResponse:
        review_service = request.app.state.review_service
        recent_review = review_service.get_most_recent_review()
        if not recent_review:
            raise HTTPException(status_code=404, detail="No active reviews found")
        return RedirectResponse(url=f"/review/{recent_review.id}")

    @router.get("/review/{review_id}")
    async def redirect_to_review_view(request: Request, review_id: str = Path(...)) -> RedirectResponse:
        review_service = request.app.state.review_service
        review_session = review_service.get_review_session(review_id)
        if not review_session:
            raise HTTPException(status_code=404, detail="Review not found")
        return RedirectResponse(url=f"/review/{review_id}/view?{review_session.view_params}")

    @router.get("/review/{review_id}/view")
    async def get_review_view(request: Request, review_id: str = Path(...)) -> FileResponse:
        review_service = request.app.state.review_service
        if not review_service.get_review_session(review_id):
            raise HTTPException(status_code=404, detail="Review not found")
        review_path = STATIC_DIR / "templates" / "review.html"
        return FileResponse(review_path)

    @router.get("/review/{review_id}/api/info")
    async def get_review_info(request: Request, review_id: str = Path(...)) -> ReviewInfo:
        review_service = request.app.state.review_service
        review_session = review_service.get_review_session(review_id)
        if not review_session:
            raise HTTPException(status_code=404, detail="Review not found")

        return ReviewInfo(
            review_id=review_session.id,
            title=review_session.title,
            is_live=review_session.is_live,
            created_at=review_session.created_at,
        )

    @router.get("/review/{review_id}/api/diff")
    async def get_review_diff(
        request: Request,
        review_id: str = Path(...),
        commit: str | None = Query(None),
        range: str | None = Query(None),
        live: bool = Query(False),
        since: str | None = Query(None),
    ) -> GitDiff:
        review_service = request.app.state.review_service
        review_session = review_service.get_review_session(review_id)
        if not review_session:
            raise HTTPException(status_code=404, detail="Review not found")

        # Check if query parameters are provided - if so, use them to compute the diff
        param_count = sum(1 for p in [commit, range, live] if p)

        if param_count > 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot specify multiple parameters. Use exactly one of: commit, range, or live"
            )

        if commit:
            return review_session.git_service.get_commit_diff(commit)
        elif range:
            return review_session.git_service.get_range_diff(range)
        elif live:
            since_param = since or "HEAD"
            return review_session.git_service.get_live_diff(since_param)
        else:
            # No query parameters provided, use the session's cached diff
            return review_session.diff

    @router.get("/review/{review_id}/api/comments")
    async def get_review_comments(
        request: Request, review_id: str = Path(...), file_path: str | None = None
    ) -> List[Comment]:
        review_service = request.app.state.review_service
        review_session = review_service.get_review_session(review_id)
        if not review_session:
            raise HTTPException(status_code=404, detail="Review not found")
        return review_session.comment_service.get_comments(file_path=file_path)

    @router.post("/review/{review_id}/api/comments")
    async def create_review_comment(
        request: Request, payload: CommentRequest, review_id: str = Path(...)
    ) -> SuccessResponse[dict]:
        review_service = request.app.state.review_service
        mcp_service = request.app.state.mcp_service
        review_session = review_service.get_review_session(review_id)
        if not review_session:
            raise HTTPException(status_code=404, detail="Review not found")

        comment, queue_pos = review_session.comment_service.add_comment(payload, review_id)
        mcp_service.add_comment_to_queue(comment)

        return SuccessResponse(
            data={"comment": comment.model_dump(), "queue_position": queue_pos},
            message="Comment created successfully",
        )

    @router.delete("/review/{review_id}/api/comments/{comment_id}")
    async def delete_review_comment(
        request: Request, review_id: str = Path(...), comment_id: str = Path(...)
    ) -> SuccessResponse[dict]:
        review_service = request.app.state.review_service
        review_session = review_service.get_review_session(review_id)
        if not review_session:
            raise HTTPException(status_code=404, detail="Review not found")

        success = review_session.comment_service.delete_comment(comment_id)
        if not success:
            raise HTTPException(status_code=404, detail="Comment not found")

        return SuccessResponse(
            data={"comment_id": comment_id},
            message="Comment deleted successfully",
        )

    @router.post("/review/{review_id}/approve")
    async def approve_review(
        request: Request, payload: ApprovalRequest, review_id: str = Path(...)
    ) -> SuccessResponse[dict]:
        review_service = request.app.state.review_service
        mcp_service = request.app.state.mcp_service
        event_manager = request.app.state.event_manager
        if not review_service.get_review_session(review_id):
            raise HTTPException(status_code=404, detail="Review not found")
        
        mcp_service.approve_review(review_id)
        await event_manager.emit_event(
            EventType.REVIEW_APPROVED,
            {"review_id": review_id, "timestamp": payload.timestamp},
            review_id=review_id,
        )
        return SuccessResponse(
            data={"status": "approved", "timestamp": payload.timestamp},
            message=f"Review {review_id} has been approved successfully",
        )

    @router.get("/review/{review_id}/api/file-content")
    async def get_review_file_content(
        request: Request,
        review_id: str = Path(...),
        path: str = Query(..., description="Path to the file relative to the repository root"),
    ) -> PlainTextResponse:
        review_service = request.app.state.review_service
        review_session = review_service.get_review_session(review_id)
        if not review_session:
            raise HTTPException(status_code=404, detail="Review not found")

        repo_root = review_session.git_service.repo_path.resolve()
        file_path = _resolve_repo_path(repo_root, path)

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="Path is not a file")

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=415, detail="File is not a UTF-8 text file")

        return PlainTextResponse(content)

    @router.post("/review/{review_id}/api/edit")
    async def edit_review_file(
        request: Request,
        payload: FileEditRequest,
        review_id: str = Path(...),
    ) -> SuccessResponse[dict]:
        review_service = request.app.state.review_service
        review_session = review_service.get_review_session(review_id)
        if not review_session:
            raise HTTPException(status_code=404, detail="Review not found")

        repo_root = review_session.git_service.repo_path.resolve()
        target_path = _resolve_repo_path(repo_root, payload.filename)

        if not target_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        if target_path.is_dir():
            raise HTTPException(status_code=400, detail="Cannot edit a directory")

        patch_lines = payload.patch.splitlines()
        if len(patch_lines) < 2 or not patch_lines[0].startswith("--- ") or not patch_lines[1].startswith("+++ "):
            raise HTTPException(status_code=400, detail="Invalid patch format")

        relative_path = target_path.relative_to(repo_root).as_posix()
        patch_lines[0] = f"--- a/{relative_path}"
        patch_lines[1] = f"+++ b/{relative_path}"
        sanitized_patch = "\n".join(patch_lines)
        if payload.patch.endswith("\n"):
            sanitized_patch += "\n"

        try:
            subprocess.run(
                ["git", "apply", "--whitespace=nowarn", "-"],
                input=sanitized_patch,
                text=True,
                cwd=str(repo_root),
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.strip() or exc.stdout.strip() or "Unknown git apply error"
            raise HTTPException(status_code=409, detail=f"Failed to apply patch: {detail}") from exc

        if review_session.is_live:
            review_session.refresh_diff()

        return SuccessResponse(
            data={"filename": relative_path},
            message=f"File {relative_path} edited successfully",
        )

    @router.websocket("/review/{review_id}/ws")
    async def websocket_endpoint(websocket: WebSocket, review_id: str = Path(...)) -> None:
        review_service = websocket.app.state.review_service
        event_manager = websocket.app.state.event_manager
        if not review_service.get_review_session(review_id):
            await websocket.close(code=1008, reason="Review not found")
            return

        await websocket.accept()
        subscriber = await event_manager.subscribe(review_id=review_id)
        try:
            while True:
                events = await event_manager.wait_for_events(subscriber, timeout=30.0)
                for event in events:
                    await websocket.send_json(event.to_dict())
        except WebSocketDisconnect:
            pass
        finally:
            await event_manager.unsubscribe(subscriber.id)

    return router
