from enum import Enum
from typing import List

from pydantic import BaseModel, ConfigDict, Field


class CommentStatus(str, Enum):
    """Status of a comment in the review process."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class LineType(str, Enum):
    """Type of line in a diff."""

    ADDITION = "addition"
    DELETION = "deletion"
    CONTEXT = "context"


class DiffLine(BaseModel):
    """A single line in a diff chunk."""

    model_config = ConfigDict(populate_by_name=True)

    type: LineType
    oldNum: int | None = Field(
        None, serialization_alias="oldNum", validation_alias="old_num"
    )
    newNum: int | None = Field(
        None, serialization_alias="newNum", validation_alias="new_num"
    )
    content: str


class DiffChunk(BaseModel):
    """A chunk of lines in a diff, representing a contiguous change area."""

    old_start: int
    old_lines: int
    new_start: int
    new_lines: int
    lines: List[DiffLine]


class DiffFile(BaseModel):
    """A file that has been changed in a diff."""

    path: str
    old_path: str | None = None
    additions: int
    deletions: int
    chunks: List[DiffChunk]
    is_binary: bool = False
    is_renamed: bool = False
    status: str | None = None


class GitDiff(BaseModel):
    """Complete diff information."""

    files: List[DiffFile]
    commit_hash: str | None = None
    author: str | None = None
    message: str | None = None


class ReviewInfo(BaseModel):
    """Metadata about a review session."""

    review_id: str
    title: str | None = None
    is_live: bool
    created_at: float


class Comment(BaseModel):
    """A comment on a specific line."""

    id: str
    review_id: str | None = None
    file_path: str
    line_number: int
    side: str  # "left" or "right"
    content: str
    author: str = "User"
    timestamp: str
    queue_position: int | None = None
    status: CommentStatus = CommentStatus.PENDING
    reply_message: str | None = None


class CommentRequest(BaseModel):
    """Request to create a comment."""

    file_path: str
    line_number: int
    side: str
    content: str
    author: str = "User"


class FileEditRequest(BaseModel):
    """Request to edit a file using unified diff patch format."""

    filename: str
    patch: str  # Unified diff patch to apply to the file


class ReviewApproved(BaseModel):
    """Indicates that a review has been approved."""

    review_id: str
    timestamp: str
