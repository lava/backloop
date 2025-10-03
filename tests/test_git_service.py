"""Unit tests for GitService."""

import subprocess
from pathlib import Path
import pytest

from backloop.git_service import GitService
from backloop.models import LineType, GitDiff


class TestGitService:
    """Test suite for GitService."""

    def test_init_with_repo_path(self, temp_git_repo: Path) -> None:
        """Test GitService initialization with a specific repository path."""
        service = GitService(str(temp_git_repo))
        assert service.repo_path == temp_git_repo

    def test_init_without_repo_path(self) -> None:
        """Test GitService initialization defaults to current directory."""
        service = GitService()
        assert service.repo_path == Path.cwd()

    def test_parse_diff_output_simple(
        self, sample_diff_output: str, temp_git_repo: Path
    ) -> None:
        """Test parsing a simple diff output."""
        service = GitService(str(temp_git_repo))
        files = service._parse_diff_output(sample_diff_output)

        assert len(files) == 2

        # Check first file
        file1 = files[0]
        assert file1.path == "file1.txt"
        assert file1.additions == 2
        assert file1.deletions == 1
        assert len(file1.chunks) == 1

        # Check chunk details
        chunk = file1.chunks[0]
        assert chunk.old_start == 1
        assert chunk.old_lines == 3
        assert chunk.new_start == 1
        assert chunk.new_lines == 4
        assert len(chunk.lines) == 5

        # Check line types
        assert chunk.lines[0].type == LineType.DELETION
        assert chunk.lines[0].content == "Line 1"
        assert chunk.lines[1].type == LineType.ADDITION
        assert chunk.lines[1].content == "Line 1 modified"
        assert chunk.lines[2].type == LineType.CONTEXT
        assert chunk.lines[2].content == "Line 2"

        # Check second file (new file)
        file2 = files[1]
        assert file2.path == "file2.txt"
        assert file2.status == "added"
        assert file2.additions == 1
        assert file2.deletions == 0

    def test_parse_diff_output_binary(
        self, sample_binary_diff: str, temp_git_repo: Path
    ) -> None:
        """Test parsing binary file diff."""
        service = GitService(str(temp_git_repo))
        files = service._parse_diff_output(sample_binary_diff)

        assert len(files) == 1
        file = files[0]
        assert file.path == "image.png"
        assert file.is_binary is True
        assert file.status == "added"

    def test_parse_diff_output_rename(
        self, sample_rename_diff: str, temp_git_repo: Path
    ) -> None:
        """Test parsing file rename diff."""
        service = GitService(str(temp_git_repo))
        files = service._parse_diff_output(sample_rename_diff)

        assert len(files) == 1
        file = files[0]
        assert file.path == "new_name.txt"
        assert file.old_path == "old_name.txt"
        assert file.is_renamed is True
        assert file.status == "renamed"

    def test_get_commit_diff(self, git_repo_with_commits: Path) -> None:
        """Test getting diff for a specific commit."""
        service = GitService(str(git_repo_with_commits))

        # Get the latest commit hash
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=git_repo_with_commits,
            capture_output=True,
            text=True,
            check=True,
        )
        commit_hash = result.stdout.strip()

        diff = service.get_commit_diff(commit_hash)

        assert isinstance(diff, GitDiff)
        assert diff.commit_hash == commit_hash
        assert diff.author == "Test User"
        assert diff.message == "Add file2"
        assert len(diff.files) == 1
        assert diff.files[0].path == "file2.txt"

    def test_get_range_diff(self, git_repo_with_commits: Path) -> None:
        """Test getting diff for a commit range."""
        service = GitService(str(git_repo_with_commits))

        # Get commit hashes
        result = subprocess.run(
            ["git", "log", "--pretty=format:%H", "-n", "3"],
            cwd=git_repo_with_commits,
            capture_output=True,
            text=True,
            check=True,
        )
        commits = result.stdout.strip().split("\n")
        first_commit = commits[-1]
        latest_commit = commits[0]

        # Get diff for range
        diff = service.get_range_diff(f"{first_commit}..{latest_commit}")

        assert isinstance(diff, GitDiff)
        assert diff.commit_hash is None
        assert diff.author is None
        assert diff.message is not None and "Range:" in diff.message
        assert len(diff.files) >= 1

    def test_get_live_diff_with_changes(self, git_repo_with_commits: Path) -> None:
        """Test getting live diff with uncommitted changes."""
        service = GitService(str(git_repo_with_commits))

        # Make a change to a tracked file
        file1 = git_repo_with_commits / "file1.txt"
        file1.write_text("Modified content\n")

        diff = service.get_live_diff("HEAD")

        assert isinstance(diff, GitDiff)
        assert diff.commit_hash is None
        assert diff.message is not None and "Live changes" in diff.message
        assert len(diff.files) >= 1

        # Find the modified file
        modified_file = next((f for f in diff.files if f.path == "file1.txt"), None)
        assert modified_file is not None
        assert modified_file.additions > 0 or modified_file.deletions > 0

    def test_get_live_diff_with_untracked_files(
        self, git_repo_with_commits: Path
    ) -> None:
        """Test that get_live_diff includes untracked files."""
        service = GitService(str(git_repo_with_commits))

        # Create an untracked file
        untracked = git_repo_with_commits / "untracked.txt"
        untracked.write_text("Untracked content\nLine 2\n")

        diff = service.get_live_diff("HEAD")

        # Find the untracked file
        untracked_file = next(
            (f for f in diff.files if f.path == "untracked.txt"), None
        )
        assert untracked_file is not None
        assert untracked_file.status == "untracked"
        assert untracked_file.additions == 2
        assert untracked_file.deletions == 0
        assert len(untracked_file.chunks) == 1

        # Check that all lines are additions
        for line in untracked_file.chunks[0].lines:
            assert line.type == LineType.ADDITION

    def test_get_untracked_files_binary(self, git_repo_with_commits: Path) -> None:
        """Test that binary untracked files are handled correctly."""
        service = GitService(str(git_repo_with_commits))

        # Create a binary file
        binary_file = git_repo_with_commits / "binary.bin"
        binary_file.write_bytes(b"\x00\x01\x02\xff\xfe")

        untracked = service._get_untracked_files()

        binary_diff = next((f for f in untracked if f.path == "binary.bin"), None)
        assert binary_diff is not None
        assert binary_diff.is_binary is True
        assert len(binary_diff.chunks) == 0

    def test_get_untracked_files_respects_gitignore(
        self, git_repo_with_commits: Path
    ) -> None:
        """Test that gitignored files are not included in untracked files."""
        service = GitService(str(git_repo_with_commits))

        # Create .gitignore
        gitignore = git_repo_with_commits / ".gitignore"
        gitignore.write_text("ignored.txt\n")

        # Create ignored file
        ignored = git_repo_with_commits / "ignored.txt"
        ignored.write_text("This should be ignored\n")

        # Create non-ignored file
        not_ignored = git_repo_with_commits / "not_ignored.txt"
        not_ignored.write_text("This should appear\n")

        untracked = service._get_untracked_files()

        # Check that ignored file is not in the list
        ignored_files = [f for f in untracked if f.path == "ignored.txt"]
        assert len(ignored_files) == 0

        # Check that non-ignored file is in the list
        visible_files = [f for f in untracked if f.path == "not_ignored.txt"]
        assert len(visible_files) > 0

    def test_get_file_at_commit(self, git_repo_with_commits: Path) -> None:
        """Test getting file contents at a specific commit."""
        service = GitService(str(git_repo_with_commits))

        # Get the first commit hash
        result = subprocess.run(
            ["git", "log", "--pretty=format:%H", "-n", "3"],
            cwd=git_repo_with_commits,
            capture_output=True,
            text=True,
            check=True,
        )
        commits = result.stdout.strip().split("\n")
        first_commit = commits[-1]

        content = service.get_file_at_commit("file1.txt", first_commit)

        assert "Line 1\n" in content
        assert "Line 2\n" in content
        assert "Line 3\n" in content

    def test_run_git_command_error_handling(self, git_repo_with_commits: Path) -> None:
        """Test that git command errors are handled appropriately."""
        service = GitService(str(git_repo_with_commits))

        # Try to get a non-existent file at HEAD
        result = service._run_git_command(
            ["git", "show", "HEAD:nonexistent.txt"]
        )

        # Should return empty string for non-existent files
        assert result == ""

    def test_parse_empty_diff(self, temp_git_repo: Path) -> None:
        """Test parsing empty diff output."""
        service = GitService(str(temp_git_repo))
        files = service._parse_diff_output("")

        assert len(files) == 0

    def test_parse_diff_with_deleted_file(self, git_repo_with_commits: Path) -> None:
        """Test parsing diff with a deleted file."""
        service = GitService(str(git_repo_with_commits))

        # Delete a file and stage the deletion
        (git_repo_with_commits / "file2.txt").unlink()
        subprocess.run(
            ["git", "add", "file2.txt"],
            cwd=git_repo_with_commits,
            check=True,
        )

        # Get the diff
        diff_output = subprocess.run(
            ["git", "diff", "--staged"],
            cwd=git_repo_with_commits,
            capture_output=True,
            text=True,
            check=True,
        ).stdout

        files = service._parse_diff_output(diff_output)

        deleted_file = next((f for f in files if f.path == "file2.txt"), None)
        assert deleted_file is not None
        assert deleted_file.status == "deleted"

    def test_parse_diff_with_multiple_chunks(
        self, git_repo_with_commits: Path
    ) -> None:
        """Test parsing diff with multiple chunks in one file."""
        service = GitService(str(git_repo_with_commits))

        # Create a file with more content
        large_file = git_repo_with_commits / "large.txt"
        content = "\n".join([f"Line {i}" for i in range(1, 21)])
        large_file.write_text(content + "\n")
        subprocess.run(
            ["git", "add", "large.txt"], cwd=git_repo_with_commits, check=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Add large file"],
            cwd=git_repo_with_commits,
            capture_output=True,
            check=True,
        )

        # Modify in multiple places
        lines = content.split("\n")
        lines[0] = "Line 1 modified"
        lines[10] = "Line 11 modified"
        large_file.write_text("\n".join(lines) + "\n")

        # Get the diff
        diff_output = subprocess.run(
            ["git", "diff", "large.txt"],
            cwd=git_repo_with_commits,
            capture_output=True,
            text=True,
            check=True,
        ).stdout

        files = service._parse_diff_output(diff_output)

        assert len(files) == 1
        # Should have 2 chunks (one for each change)
        assert len(files[0].chunks) == 2
