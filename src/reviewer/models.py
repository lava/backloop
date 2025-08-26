from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class LineType(str, Enum):
    """Type of line in a diff."""
    ADDITION = "addition"
    DELETION = "deletion" 
    CONTEXT = "context"


class DiffLine(BaseModel):
    """A single line in a diff chunk."""
    type: LineType
    old_num: Optional[int]
    new_num: Optional[int] 
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
    old_path: Optional[str] = None
    additions: int
    deletions: int
    chunks: List[DiffChunk]
    is_binary: bool = False
    is_renamed: bool = False


class GitDiff(BaseModel):
    """Complete diff information."""
    files: List[DiffFile]
    commit_hash: Optional[str] = None
    author: Optional[str] = None
    message: Optional[str] = None


class Comment(BaseModel):
    """A comment on a specific line."""
    id: str
    file_path: str
    line_number: int
    side: str  # "left" or "right"
    content: str
    author: str = "User"
    timestamp: str


class CommentRequest(BaseModel):
    """Request to create a comment."""
    file_path: str
    line_number: int
    side: str
    content: str
    author: str = "User"