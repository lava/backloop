from typing import Optional
from pathlib import Path
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from reviewer.models import GitDiff, FileEditRequest
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

    @router.post("/api/edit")
    async def edit_file(request: FileEditRequest) -> dict:
        """Edit a file using diff-like format with line numbers and content verification."""
        try:
            # Resolve the file path
            file_path = Path(request.filename)
            if not file_path.is_absolute():
                # Make it relative to current working directory
                file_path = Path.cwd() / file_path
            
            # Check if file exists
            if not file_path.exists():
                raise HTTPException(status_code=404, detail=f"File not found: {request.filename}")
            
            # Check if it's actually a file
            if not file_path.is_file():
                raise HTTPException(status_code=400, detail=f"Path is not a file: {request.filename}")
            
            # Validate line numbers
            if request.start_line < 1 or request.end_line < request.start_line:
                raise HTTPException(
                    status_code=400, 
                    detail="Invalid line numbers: start_line must be >= 1 and end_line must be >= start_line"
                )
            
            # Read the current content
            lines = file_path.read_text(encoding='utf-8').splitlines(keepends=True)
            total_lines = len(lines)
            
            # Check if line numbers are within file bounds
            if request.end_line > total_lines:
                raise HTTPException(
                    status_code=400, 
                    detail=f"end_line ({request.end_line}) exceeds file length ({total_lines})"
                )
            
            # Extract the lines to be replaced (convert to 0-based indexing)
            start_idx = request.start_line - 1
            end_idx = request.end_line  # end_line is inclusive, so we don't subtract 1
            actual_content = ''.join(lines[start_idx:end_idx])
            
            # Remove trailing newline from actual_content for comparison if expected doesn't have it
            actual_content_for_comparison = actual_content
            if not request.expected_content.endswith('\n') and actual_content.endswith('\n'):
                actual_content_for_comparison = actual_content.rstrip('\n')
            
            # Verify the expected content matches
            if actual_content_for_comparison != request.expected_content:
                raise HTTPException(
                    status_code=409, 
                    detail=f"Content mismatch at lines {request.start_line}-{request.end_line}. "
                           f"Expected content does not match actual content."
                )
            
            # Prepare new content - ensure it ends with newline if original did
            new_content = request.new_content
            if actual_content.endswith('\n') and not new_content.endswith('\n'):
                new_content += '\n'
            
            # Apply the edit
            new_lines = lines[:start_idx] + [new_content] + lines[end_idx:]
            
            # Write back to file
            file_path.write_text(''.join(new_lines), encoding='utf-8')
            
            return {
                "status": "success",
                "message": f"File {request.filename} edited successfully",
                "filename": request.filename,
                "lines_affected": f"{request.start_line}-{request.end_line}"
            }
            
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="File is not a valid UTF-8 text file")
        except PermissionError:
            raise HTTPException(status_code=403, detail=f"Permission denied writing to {request.filename}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error editing file: {str(e)}")

    @router.get("/api/file-content")
    async def get_file_content(path: str) -> str:
        """Get the content of a file."""
        try:
            # Resolve the file path
            file_path = Path(path)
            if not file_path.is_absolute():
                # Make it relative to current working directory
                file_path = Path.cwd() / file_path
            
            # Check if file exists
            if not file_path.exists():
                raise HTTPException(status_code=404, detail=f"File not found: {path}")
            
            # Check if it's actually a file
            if not file_path.is_file():
                raise HTTPException(status_code=400, detail=f"Path is not a file: {path}")
            
            # Read the file content
            content = file_path.read_text(encoding='utf-8')
            return content
            
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="File is not a valid UTF-8 text file")
        except PermissionError:
            raise HTTPException(status_code=403, detail=f"Permission denied reading {path}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")

    return router