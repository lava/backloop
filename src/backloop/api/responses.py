from typing import Generic, TypeVar, Union, Any
from pydantic import BaseModel, Field

from backloop.models import Comment

T = TypeVar("T")


class BaseResponse(BaseModel, Generic[T]):
    """Base response model with generic data field."""

    status: str
    data: T
    message: str | None = None


class SuccessResponse(BaseResponse[T]):
    """Standard success response format."""

    status: str = Field(default="success")


class ErrorResponse(BaseModel):
    """Standard error response format."""

    status: str = "error"
    message: str
    error_code: str | None = None
    details: dict | None = None


class CommentResponse(SuccessResponse[Comment]):
    """Response containing a comment."""

    pass


class FileEditResponse(BaseModel):
    """Response for file edit operations."""

    status: str
    message: str
    filename: str
    patch_output: str


class FileContentResponse(BaseModel):
    """Response for file content requests."""

    status: str = "success"
    content: str
    filename: str
