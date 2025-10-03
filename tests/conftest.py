"""Shared pytest fixtures for testing."""

import tempfile
import subprocess
from pathlib import Path
from typing import Generator
import pytest


@pytest.fixture
def temp_git_repo() -> Generator[Path, None, None]:
    """Create a temporary git repository for testing.

    Yields:
        Path to the temporary git repository
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)

        # Initialize git repo
        subprocess.run(
            ["git", "init"],
            cwd=repo_path,
            capture_output=True,
            check=True,
        )

        # Configure git
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_path,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_path,
            capture_output=True,
            check=True,
        )

        yield repo_path


@pytest.fixture
def git_repo_with_commits(temp_git_repo: Path) -> Path:
    """Create a git repo with some commits for testing.

    Args:
        temp_git_repo: Path to temporary git repository

    Returns:
        Path to the git repository with commits
    """
    repo_path = temp_git_repo

    # Create initial file and commit
    file1 = repo_path / "file1.txt"
    file1.write_text("Line 1\nLine 2\nLine 3\n")
    subprocess.run(["git", "add", "file1.txt"], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )

    # Modify file and create second commit
    file1.write_text("Line 1 modified\nLine 2\nLine 3\nLine 4\n")
    subprocess.run(["git", "add", "file1.txt"], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Second commit"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )

    # Add a second file
    file2 = repo_path / "file2.txt"
    file2.write_text("New file content\n")
    subprocess.run(["git", "add", "file2.txt"], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Add file2"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )

    return repo_path


@pytest.fixture
def temp_storage_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for storage (e.g., comments).

    Yields:
        Path to the temporary storage directory
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_diff_output() -> str:
    """Sample git diff output for testing parsing."""
    return """diff --git a/file1.txt b/file1.txt
index 1234567..abcdefg 100644
--- a/file1.txt
+++ b/file1.txt
@@ -1,3 +1,4 @@
-Line 1
+Line 1 modified
 Line 2
 Line 3
+Line 4
diff --git a/file2.txt b/file2.txt
new file mode 100644
index 0000000..9876543
--- /dev/null
+++ b/file2.txt
@@ -0,0 +1,1 @@
+New file content
"""


@pytest.fixture
def sample_binary_diff() -> str:
    """Sample binary file diff output."""
    return """diff --git a/image.png b/image.png
new file mode 100644
index 0000000..1234567
Binary files /dev/null and b/image.png differ
"""


@pytest.fixture
def sample_rename_diff() -> str:
    """Sample file rename diff output."""
    return """diff --git a/old_name.txt b/new_name.txt
similarity index 100%
rename from old_name.txt
rename to new_name.txt
"""
