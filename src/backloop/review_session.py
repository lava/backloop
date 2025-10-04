import uuid
import time

from backloop.models import GitDiff
from backloop.comment_service import CommentService
from backloop.git_service import GitService
from backloop.utils.state_dir import get_state_dir


class ReviewSession:
    """Manages a single review session with its own comment service and git diff data."""

    def __init__(
        self,
        commit: str | None = None,
        range: str | None = None,
        since: str | None = None,
    ) -> None:
        """Initialize a review session.

        Parameters:
        - commit: Review changes for a specific commit
        - range: Review changes for a commit range
        - since: Review live changes since a commit
        """
        self.id = str(uuid.uuid4())[:8]
        self.commit = commit
        self.range = range
        self.since = since
        self.created_at = time.time()

        self.is_live = since is not None or (commit is None and range is None)
        self.view_params = self._build_view_params()

        self.git_service = GitService()
        comment_file = get_state_dir() / f"backloop_comments_{self.id}.json"
        self.comment_service = CommentService(storage_path=str(comment_file))

        self.diff = self._get_diff()

    def _build_view_params(self) -> str:
        """Build query parameters for the view redirect."""
        params = []

        if self.commit:
            params.append(f"commit={self.commit}")
        elif self.range:
            params.append(f"range={self.range}")
        else:
            # Default to live mode
            since_param = self.since or "HEAD"
            params.append(f"live=true&since={since_param}")

        return "&".join(params)

    def _get_diff(self) -> GitDiff:
        """Get the diff data based on the session parameters."""
        param_count = sum(
            1 for param in [self.commit, self.range, self.since] if param is not None
        )

        if param_count == 0:
            # Default to live diff against HEAD
            return self.git_service.get_live_diff("HEAD")
        elif param_count > 1:
            raise ValueError(
                "Cannot specify multiple parameters. Use exactly one of: commit, range, or since"
            )
        elif self.commit:
            return self.git_service.get_commit_diff(self.commit)
        elif self.range:
            return self.git_service.get_range_diff(self.range)
        else:
            assert self.since is not None
            return self.git_service.get_live_diff(self.since)

    def refresh_diff(self) -> None:
        """Recalculate the diff data for the session."""
        self.diff = self._get_diff()
