"""Integration tests for review-scoped file endpoints."""

from pathlib import Path
from typing import Tuple

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backloop.api.review_router import create_review_router
from backloop.event_manager import EventManager
from backloop.models import FileEditRequest
from backloop.services.mcp_service import McpService
from backloop.services.review_service import ReviewService


@pytest.fixture
def review_client(git_repo_with_commits: Path) -> Tuple[TestClient, str, Path]:
    """Create a FastAPI test client with a review session bound to a git repo."""
    app = FastAPI()
    event_manager = EventManager()
    review_service = ReviewService(event_manager)
    review_session = review_service.create_review_session(since="HEAD")
    review_session.git_service.repo_path = git_repo_with_commits
    review_session.refresh_diff()
    mcp_service = McpService(review_service, event_manager)

    app.state.review_service = review_service
    app.state.event_manager = event_manager
    app.state.mcp_service = mcp_service

    app.include_router(create_review_router())

    client = TestClient(app)
    return client, review_session.id, git_repo_with_commits


class TestReviewFileContent:
    """Tests for retrieving file content within a review."""

    def test_get_file_content_success(self, review_client: Tuple[TestClient, str, Path]) -> None:
        client, review_id, _ = review_client

        response = client.get(f"/review/{review_id}/api/file-content?path=file1.txt")

        assert response.status_code == 200
        assert "Line 1" in response.text

    def test_get_file_content_absolute_path(self, review_client: Tuple[TestClient, str, Path]) -> None:
        client, review_id, repo_path = review_client
        abs_path = repo_path / "file1.txt"

        response = client.get(f"/review/{review_id}/api/file-content?path={abs_path}")

        assert response.status_code == 200
        assert "Line 2" in response.text

    def test_get_file_content_not_found(self, review_client: Tuple[TestClient, str, Path]) -> None:
        client, review_id, _ = review_client

        response = client.get(f"/review/{review_id}/api/file-content?path=missing.txt")

        assert response.status_code == 404

    def test_get_file_content_directory(self, review_client: Tuple[TestClient, str, Path]) -> None:
        client, review_id, repo_path = review_client
        directory = repo_path / "subdir"
        directory.mkdir()

        response = client.get(f"/review/{review_id}/api/file-content?path=subdir")

        assert response.status_code == 400

    def test_get_file_content_outside_repo(self, review_client: Tuple[TestClient, str, Path]) -> None:
        client, review_id, _ = review_client

        response = client.get(f"/review/{review_id}/api/file-content?path=../outside.txt")

        assert response.status_code == 400


class TestReviewFileEdit:
    """Tests for editing files via the review API."""

    def test_edit_file_success(self, review_client: Tuple[TestClient, str, Path]) -> None:
        client, review_id, repo_path = review_client
        patch = """--- a/file1.txt
+++ b/file1.txt
@@ -1,4 +1,4 @@
-Line 1 modified
+Line 1 edited
 Line 2
 Line 3
 Line 4
"""

        request = FileEditRequest(filename="file1.txt", patch=patch)
        response = client.post(
            f"/review/{review_id}/api/edit",
            json=request.model_dump(),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "edited successfully" in data["message"]
        assert (repo_path / "file1.txt").read_text() == "Line 1 edited\nLine 2\nLine 3\nLine 4\n"

    def test_edit_file_absolute_path(self, review_client: Tuple[TestClient, str, Path]) -> None:
        client, review_id, repo_path = review_client
        abs_filename = repo_path / "file1.txt"
        patch = f"""--- a/{abs_filename}
+++ b/{abs_filename}
@@ -1,4 +1,4 @@
-Line 1 modified
+Line 1 absolute
 Line 2
 Line 3
 Line 4
"""

        request = FileEditRequest(filename=str(abs_filename), patch=patch)
        response = client.post(
            f"/review/{review_id}/api/edit",
            json=request.model_dump(),
        )

        assert response.status_code == 200
        assert (repo_path / "file1.txt").read_text() == "Line 1 absolute\nLine 2\nLine 3\nLine 4\n"

    def test_edit_file_not_found(self, review_client: Tuple[TestClient, str, Path]) -> None:
        client, review_id, _ = review_client
        patch = """--- a/missing.txt
+++ b/missing.txt
@@ -0,0 +1,1 @@
+new content
"""

        request = FileEditRequest(filename="missing.txt", patch=patch)
        response = client.post(
            f"/review/{review_id}/api/edit",
            json=request.model_dump(),
        )

        assert response.status_code == 404

    def test_edit_file_patch_conflict(self, review_client: Tuple[TestClient, str, Path]) -> None:
        client, review_id, repo_path = review_client
        patch = """--- a/file1.txt
+++ b/file1.txt
@@ -1,4 +1,4 @@
-Line 1 original
+Line 1 conflict
 Line 2
 Line 3
 Line 4
"""

        request = FileEditRequest(filename="file1.txt", patch=patch)
        response = client.post(
            f"/review/{review_id}/api/edit",
            json=request.model_dump(),
        )

        assert response.status_code == 409
        assert (repo_path / "file1.txt").read_text() == "Line 1 modified\nLine 2\nLine 3\nLine 4\n"

    def test_edit_file_outside_repo(self, review_client: Tuple[TestClient, str, Path]) -> None:
        client, review_id, _ = review_client
        patch = """--- a/../outside.txt
+++ b/../outside.txt
@@ -0,0 +1,1 @@
+danger
"""

        request = FileEditRequest(filename="../outside.txt", patch=patch)
        response = client.post(
            f"/review/{review_id}/api/edit",
            json=request.model_dump(),
        )

        assert response.status_code == 400

    def test_edit_file_invalid_patch(self, review_client: Tuple[TestClient, str, Path]) -> None:
        client, review_id, _ = review_client
        request = FileEditRequest(filename="file1.txt", patch="invalid patch data")

        response = client.post(
            f"/review/{review_id}/api/edit",
            json=request.model_dump(),
        )

        assert response.status_code == 400


class TestStaticAssets:
    """Ensure static routes are exposed."""

    def test_favicon_route(self, review_client: Tuple[TestClient, str, Path]) -> None:
        client, _, _ = review_client

        response = client.get("/favicon.ico")

        assert response.status_code == 200
        assert response.headers.get("content-type", "").startswith("image/")
        assert len(response.content) > 0
