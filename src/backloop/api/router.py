from pathlib import Path
import tempfile
import subprocess
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from backloop.models import GitDiff, FileEditRequest
from backloop.api.responses import SuccessResponse, FileEditResponse
from backloop.review_session import ReviewSession
from backloop.mock_data import get_mock_diff


def create_api_router() -> APIRouter:
    """Create the shared API router used by both standalone and MCP servers."""
    router = APIRouter()

    @router.get("/api/diff")
    async def get_diff(
        commit: str | None = Query(
            None, description="Review changes for a specific commit"
        ),
        range: str | None = Query(
            None, description="Review changes for a commit range"
        ),
        mock: bool = Query(False, description="Return mock data for testing"),
    ) -> GitDiff:
        """Get diff data for specific commits or ranges."""
        if mock:
            return get_mock_diff()

        if not commit and not range:
            raise HTTPException(
                status_code=400,
                detail="Must specify either 'commit' or 'range' parameter",
            )
        if commit and range:
            raise HTTPException(
                status_code=400,
                detail="Cannot specify both 'commit' and 'range' parameters",
            )

        review_session = ReviewSession(commit=commit, range=range, since=None)
        return review_session.diff

    @router.get("/api/diff/live")
    async def get_live_diff(
        since: str | None = Query(
            "HEAD", description="Review live changes since a commit"
        ),
        mock: bool = Query(False, description="Return mock data for testing"),
    ) -> GitDiff:
        """Get live diff data showing changes since a commit (defaults to HEAD)."""
        if mock:
            return get_mock_diff()

        review_session = ReviewSession(commit=None, range=None, since=since)
        return review_session.diff

    @router.post("/api/edit")
    async def edit_file(request: FileEditRequest) -> FileEditResponse:
        """Edit a file by applying a unified diff patch using the system patch command."""
        try:
            file_path = Path(request.filename)
            if not file_path.is_absolute():
                file_path = Path.cwd() / file_path

            if not file_path.exists():
                raise HTTPException(
                    status_code=404, detail=f"File not found: {request.filename}"
                )

            if not file_path.is_file():
                raise HTTPException(
                    status_code=400, detail=f"Path is not a file: {request.filename}"
                )

            # --no-backup-if-mismatch: don't create .orig files
            result = subprocess.run(
                ["patch", "--no-backup-if-mismatch", str(file_path)],
                input=request.patch,
                capture_output=True,
                text=True,
                cwd=Path.cwd(),
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout

                # Try to give a more helpful error message
                if "Reversed (or previously applied) patch detected" in error_msg:
                    raise HTTPException(
                        status_code=409,
                        detail="Patch appears to be already applied or reversed",
                    )
                elif "can't find file to patch" in error_msg:
                    raise HTTPException(
                        status_code=404, detail="Cannot find file to patch"
                    )
                elif "Hunk #" in error_msg and "FAILED" in error_msg:
                    raise HTTPException(
                        status_code=409,
                        detail="Patch does not apply cleanly - file content has changed",
                    )
                else:
                    raise HTTPException(
                        status_code=400, detail=f"Failed to apply patch: {error_msg}"
                    )

            return FileEditResponse(
                status="success",
                message=f"File {request.filename} edited successfully",
                filename=request.filename,
                patch_output=result.stdout
                if result.stdout
                else "Patch applied successfully",
            )

        except subprocess.SubprocessError as e:
            raise HTTPException(
                status_code=500, detail=f"Error running patch command: {str(e)}"
            )
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400, detail="File is not a valid UTF-8 text file"
            )
        except PermissionError:
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied accessing {request.filename}",
            )
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=f"Error editing file: {str(e)}")

    @router.get("/api/file-content", response_class=PlainTextResponse)
    async def get_file_content(path: str) -> str:
        """Get the content of a file."""
        try:
            file_path = Path(path)
            if not file_path.is_absolute():
                file_path = Path.cwd() / file_path

            if not file_path.exists():
                raise HTTPException(status_code=404, detail=f"File not found: {path}")

            if not file_path.is_file():
                raise HTTPException(
                    status_code=400, detail=f"Path is not a file: {path}"
                )

            content = file_path.read_text(encoding="utf-8")
            return content

        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400, detail="File is not a valid UTF-8 text file"
            )
        except PermissionError:
            raise HTTPException(
                status_code=403, detail=f"Permission denied reading {path}"
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")

    return router
