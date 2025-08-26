import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from reviewer.models import Comment, CommentRequest


class CommentService:
    """Service for managing comments on diff lines."""
    
    def __init__(self, storage_path: Optional[str] = None) -> None:
        """Initialize with optional storage path."""
        self.storage_path = Path(storage_path) if storage_path else Path.cwd() / ".reviewer_comments.json"
        self._comments: Dict[str, Comment] = self._load_comments()
    
    def add_comment(self, request: CommentRequest) -> Comment:
        """Add a new comment."""
        comment_id = str(uuid.uuid4())
        comment = Comment(
            id=comment_id,
            file_path=request.file_path,
            line_number=request.line_number,
            side=request.side,
            content=request.content,
            author=request.author,
            timestamp=datetime.now().isoformat()
        )
        
        self._comments[comment_id] = comment
        self._save_comments()
        return comment
    
    def get_comments(self, file_path: Optional[str] = None) -> List[Comment]:
        """Get all comments, optionally filtered by file path."""
        comments = list(self._comments.values())
        if file_path:
            comments = [c for c in comments if c.file_path == file_path]
        return sorted(comments, key=lambda c: c.timestamp)
    
    def get_comment(self, comment_id: str) -> Optional[Comment]:
        """Get a specific comment by ID."""
        return self._comments.get(comment_id)
    
    def update_comment(self, comment_id: str, content: str) -> Optional[Comment]:
        """Update a comment's content."""
        comment = self._comments.get(comment_id)
        if comment:
            comment.content = content
            comment.timestamp = datetime.now().isoformat()
            self._save_comments()
        return comment
    
    def delete_comment(self, comment_id: str) -> bool:
        """Delete a comment."""
        if comment_id in self._comments:
            del self._comments[comment_id]
            self._save_comments()
            return True
        return False
    
    def _load_comments(self) -> Dict[str, Comment]:
        """Load comments from storage."""
        if not self.storage_path.exists():
            return {}
        
        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
                return {
                    comment_id: Comment(**comment_data) 
                    for comment_id, comment_data in data.items()
                }
        except (json.JSONDecodeError, KeyError, TypeError):
            # If file is corrupted, start fresh
            return {}
    
    def _save_comments(self) -> None:
        """Save comments to storage."""
        # Ensure parent directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert comments to serializable format
        data = {
            comment_id: comment.model_dump()
            for comment_id, comment in self._comments.items()
        }
        
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)