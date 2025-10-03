"""Integration tests for API endpoints."""

import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backloop.api.router import create_api_router
from backloop.models import CommentRequest, FileEditRequest


@pytest.fixture
def api_client(git_repo_with_commits: Path) -> TestClient:
    """Create a test client for the API."""
    from fastapi import FastAPI

    app = FastAPI()
    router = create_api_router()
    app.include_router(router)

    return TestClient(app)


class TestDiffEndpoints:
    """Test diff-related API endpoints."""

    def test_get_diff_requires_parameters(self, api_client: TestClient) -> None:
        """Test that /api/diff requires commit or range parameter."""
        response = api_client.get("/api/diff")
        assert response.status_code == 400
        assert "Must specify either 'commit' or 'range'" in response.json()["detail"]

    def test_get_diff_cannot_use_both_parameters(
        self, api_client: TestClient
    ) -> None:
        """Test that /api/diff cannot use both commit and range."""
        response = api_client.get("/api/diff?commit=HEAD&range=main..feature")
        assert response.status_code == 400
        assert "Cannot specify both" in response.json()["detail"]

    def test_get_diff_mock(self, api_client: TestClient) -> None:
        """Test getting mock diff data."""
        response = api_client.get("/api/diff?mock=true&commit=HEAD")
        assert response.status_code == 200

        data = response.json()
        assert "files" in data
        assert isinstance(data["files"], list)

    def test_get_live_diff_default(
        self, api_client: TestClient, git_repo_with_commits: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test getting live diff (defaults to since HEAD)."""
        # Change to repo directory
        monkeypatch.chdir(git_repo_with_commits)

        response = api_client.get("/api/diff/live")
        assert response.status_code == 200

        data = response.json()
        assert "files" in data
        assert "message" in data
        assert "Live changes" in data["message"]

    def test_get_live_diff_mock(self, api_client: TestClient) -> None:
        """Test getting mock live diff."""
        response = api_client.get("/api/diff/live?mock=true")
        assert response.status_code == 200

        data = response.json()
        assert "files" in data


class TestFileEndpoints:
    """Test file-related API endpoints."""

    def test_edit_file_not_found(self, api_client: TestClient) -> None:
        """Test editing a non-existent file."""
        request = FileEditRequest(
            filename="/nonexistent/file.txt",
            patch="--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new\n",
        )

        response = api_client.post("/api/edit", json=request.model_dump())
        assert response.status_code == 404
        assert "File not found" in response.json()["detail"]

    def test_edit_file_success(
        self, api_client: TestClient, git_repo_with_commits: Path
    ) -> None:
        """Test successfully editing a file."""
        # Create a test file
        test_file = git_repo_with_commits / "edit_test.txt"
        test_file.write_text("old content\n")

        # Create a patch
        patch = """--- a/edit_test.txt
+++ b/edit_test.txt
@@ -1 +1 @@
-old content
+new content
"""

        request = FileEditRequest(
            filename=str(test_file),
            patch=patch,
        )

        response = api_client.post("/api/edit", json=request.model_dump())
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "success"
        assert "edited successfully" in data["message"]

        # Verify file was actually edited
        assert test_file.read_text() == "new content\n"

    def test_edit_file_patch_conflict(
        self, api_client: TestClient, git_repo_with_commits: Path
    ) -> None:
        """Test editing a file with a conflicting patch."""
        # Create a test file
        test_file = git_repo_with_commits / "conflict_test.txt"
        test_file.write_text("different content\n")

        # Create a patch that won't apply
        patch = """--- a/conflict_test.txt
+++ b/conflict_test.txt
@@ -1 +1 @@
-old content
+new content
"""

        request = FileEditRequest(
            filename=str(test_file),
            patch=patch,
        )

        response = api_client.post("/api/edit", json=request.model_dump())
        # Should fail because patch doesn't match
        assert response.status_code in [400, 409]

    def test_get_file_content(
        self, api_client: TestClient, git_repo_with_commits: Path
    ) -> None:
        """Test getting file content."""
        # Use existing file from fixture
        file_path = git_repo_with_commits / "file1.txt"

        response = api_client.get(f"/api/file-content?path={file_path}")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        assert len(response.text) > 0

    def test_get_file_content_not_found(self, api_client: TestClient) -> None:
        """Test getting content of non-existent file."""
        response = api_client.get("/api/file-content?path=/nonexistent/file.txt")
        # May return 404 or 500 depending on whether parent dir exists
        assert response.status_code in [404, 500]

    def test_get_file_content_directory(
        self, api_client: TestClient, git_repo_with_commits: Path
    ) -> None:
        """Test that getting content of a directory fails."""
        response = api_client.get(f"/api/file-content?path={git_repo_with_commits}")
        # May return 400 or 500 depending on error handling
        assert response.status_code in [400, 500]


class TestAPIResponseFormats:
    """Test API response formats and structures."""

    def test_diff_response_structure(
        self, api_client: TestClient, monkeypatch: pytest.MonkeyPatch, git_repo_with_commits: Path
    ) -> None:
        """Test that diff response has expected structure."""
        monkeypatch.chdir(git_repo_with_commits)

        response = api_client.get("/api/diff/live")
        assert response.status_code == 200

        data = response.json()

        # Check top-level structure
        assert "files" in data
        assert "commit_hash" in data
        assert "author" in data
        assert "message" in data

        # Check files structure if any exist
        if len(data["files"]) > 0:
            file = data["files"][0]
            assert "path" in file
            assert "additions" in file
            assert "deletions" in file
            assert "chunks" in file
            assert "is_binary" in file
            assert "is_renamed" in file

    def test_edit_response_structure(
        self, api_client: TestClient, git_repo_with_commits: Path
    ) -> None:
        """Test that edit response has expected structure."""
        test_file = git_repo_with_commits / "edit_response_test.txt"
        test_file.write_text("content\n")

        patch = """--- a/edit_response_test.txt
+++ b/edit_response_test.txt
@@ -1 +1 @@
-content
+new content
"""

        request = FileEditRequest(filename=str(test_file), patch=patch)
        response = api_client.post("/api/edit", json=request.model_dump())

        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "message" in data
        assert "filename" in data
        assert "patch_output" in data

    def test_error_response_structure(self, api_client: TestClient) -> None:
        """Test that error responses have expected structure."""
        response = api_client.get("/api/diff")

        assert response.status_code == 400

        data = response.json()
        assert "detail" in data


class TestAPIEdgeCases:
    """Test edge cases and error handling."""

    def test_edit_relative_path_conversion(
        self, api_client: TestClient, git_repo_with_commits: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that relative paths are converted to absolute."""
        monkeypatch.chdir(git_repo_with_commits)

        test_file = git_repo_with_commits / "relative_test.txt"
        test_file.write_text("content\n")

        patch = """--- a/relative_test.txt
+++ b/relative_test.txt
@@ -1 +1 @@
-content
+new content
"""

        # Use relative path
        request = FileEditRequest(filename="relative_test.txt", patch=patch)
        response = api_client.post("/api/edit", json=request.model_dump())

        assert response.status_code == 200

    def test_get_file_content_relative_path(
        self, api_client: TestClient, git_repo_with_commits: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test getting file content with relative path."""
        monkeypatch.chdir(git_repo_with_commits)

        response = api_client.get("/api/file-content?path=file1.txt")
        assert response.status_code == 200
