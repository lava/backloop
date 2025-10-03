import subprocess
import re
from typing import List, Dict, Any
from pathlib import Path

from backloop.models import GitDiff, DiffFile, DiffChunk, DiffLine, LineType


class GitService:
    """Service for interacting with git repositories."""

    def __init__(self, repo_path: str | None = None) -> None:
        """Initialize with optional repository path."""
        self.repo_path = Path(repo_path) if repo_path else Path.cwd()

    def get_commit_diff(self, commit_hash: str) -> GitDiff:
        """Get diff for a specific commit."""
        # Get commit info
        info_cmd = [
            "git",
            "show",
            "--pretty=format:%H|%an|%s",
            "--no-patch",
            commit_hash,
        ]
        info_result = self._run_git_command(info_cmd)
        commit_parts = (
            info_result.strip().split("|") if info_result.strip() else ["", "", ""]
        )
        commit_info = [part if part else None for part in commit_parts]

        # Get the actual diff
        diff_cmd = ["git", "show", "--pretty=format:", commit_hash]
        diff_output = self._run_git_command(diff_cmd)

        files = self._parse_diff_output(diff_output)

        return GitDiff(
            files=files,
            commit_hash=commit_info[0],
            author=commit_info[1],
            message=commit_info[2],
        )

    def get_range_diff(self, commit_range: str) -> GitDiff:
        """Get diff for a commit range (e.g., 'main..feature')."""
        # Get diff for commit range
        diff_cmd = ["git", "diff", commit_range]
        diff_output = self._run_git_command(diff_cmd)

        # Parse range to get info
        if ".." in commit_range:
            from_ref, to_ref = commit_range.split("..", 1)
            description = f"Range: {from_ref}..{to_ref}"
        else:
            description = f"Range: {commit_range}"

        files = self._parse_diff_output(diff_output)

        return GitDiff(files=files, commit_hash=None, author=None, message=description)

    def get_live_diff(self, since_commit: str = "HEAD") -> GitDiff:
        """Get diff between current filesystem state and a commit."""
        # Get diff from commit to working directory (includes staged + unstaged)
        diff_cmd = ["git", "diff", since_commit]
        diff_output = self._run_git_command(diff_cmd)

        description = f"Live changes since {since_commit}"
        files = self._parse_diff_output(diff_output)

        # Add untracked files
        untracked_files = self._get_untracked_files()
        files.extend(untracked_files)

        return GitDiff(files=files, commit_hash=None, author=None, message=description)

    def get_file_at_commit(self, file_path: str, commit_hash: str) -> str:
        """Get file contents at a specific commit."""
        cmd = ["git", "show", f"{commit_hash}:{file_path}"]
        return self._run_git_command(cmd)

    def _get_untracked_files(self) -> List[DiffFile]:
        """Get untracked files as DiffFile objects."""
        # Get list of untracked files
        cmd = ["git", "ls-files", "--others", "--exclude-standard"]
        output = self._run_git_command(cmd)

        untracked_files = []
        if output.strip():
            for file_path in output.strip().split("\n"):
                if file_path:  # Skip empty lines
                    # Read file content to count lines
                    try:
                        with open(
                            self.repo_path / file_path, "r", encoding="utf-8"
                        ) as f:
                            content = f.read()
                            lines = content.split("\n")
                            # Create a single chunk with all lines as additions
                            diff_lines = []
                            for i, line in enumerate(lines):
                                if (
                                    i < len(lines) - 1 or line
                                ):  # Don't add empty last line
                                    diff_lines.append(
                                        DiffLine(
                                            type=LineType.ADDITION,
                                            oldNum=None,
                                            newNum=i + 1,
                                            content=line,
                                        )
                                    )

                            chunks = []
                            if diff_lines:
                                chunks.append(
                                    DiffChunk(
                                        old_start=1,
                                        old_lines=0,
                                        new_start=1,
                                        new_lines=len(diff_lines),
                                        lines=diff_lines,
                                    )
                                )

                            untracked_files.append(
                                DiffFile(
                                    path=file_path,
                                    old_path=None,
                                    additions=len(diff_lines),
                                    deletions=0,
                                    chunks=chunks,
                                    is_binary=False,
                                    is_renamed=False,
                                    status="untracked",
                                )
                            )
                    except (UnicodeDecodeError, IOError):
                        # Handle binary files or files that can't be read
                        untracked_files.append(
                            DiffFile(
                                path=file_path,
                                old_path=None,
                                additions=0,
                                deletions=0,
                                chunks=[],
                                is_binary=True,
                                is_renamed=False,
                                status="untracked",
                            )
                        )

        return untracked_files

    def _run_git_command(self, cmd: List[str]) -> str:
        """Run a git command and return output."""
        try:
            result = subprocess.run(
                cmd, cwd=self.repo_path, capture_output=True, text=True, check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            # Handle case where file doesn't exist in commit
            if "does not exist" in e.stderr or "bad revision" in e.stderr:
                return ""
            raise RuntimeError(f"Git command failed: {' '.join(cmd)}: {e.stderr}")

    def _parse_diff_output(self, diff_output: str) -> List[DiffFile]:
        """Parse git diff output into structured data."""
        files = []
        current_file: Dict[str, Any] | None = None
        current_chunk: Dict[str, Any] | None = None

        lines = diff_output.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i]

            # File header
            if line.startswith("diff --git"):
                if current_file:
                    # Finalize any pending chunk before finalizing the file
                    if current_chunk:
                        current_file["chunks"].append(
                            self._finalize_chunk(current_chunk)
                        )
                        current_chunk = None
                    files.append(self._finalize_file(current_file))

                # Parse file paths
                match = re.match(r"diff --git a/(.*) b/(.*)", line)
                if match:
                    current_file = {
                        "old_path": match.group(1),
                        "path": match.group(2),
                        "chunks": [],
                        "additions": 0,
                        "deletions": 0,
                        "is_binary": False,
                        "is_renamed": False,
                        "status": None,
                    }

            # Binary file detection
            elif line.startswith("Binary files"):
                if current_file:
                    current_file["is_binary"] = True

            # File status detection
            elif line.startswith("new file mode"):
                if current_file:
                    current_file["status"] = "added"
            elif line.startswith("deleted file mode"):
                if current_file:
                    current_file["status"] = "deleted"

            # File rename detection
            elif line.startswith("similarity index") or line.startswith("rename from"):
                if current_file:
                    current_file["is_renamed"] = True
                    current_file["status"] = "renamed"

            # Chunk header
            elif line.startswith("@@"):
                if current_file and current_chunk:
                    current_file["chunks"].append(self._finalize_chunk(current_chunk))

                # Parse chunk header: @@ -old_start,old_lines +new_start,new_lines @@
                match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
                if match:
                    current_chunk = {
                        "old_start": int(match.group(1)),
                        "old_lines": int(match.group(2) or 1),
                        "new_start": int(match.group(3)),
                        "new_lines": int(match.group(4) or 1),
                        "lines": [],
                    }

            # Diff lines
            elif current_chunk is not None and (
                line.startswith(" ") or line.startswith("-") or line.startswith("+")
            ):
                if line.startswith(" "):
                    # Context line
                    old_num = current_chunk.get(
                        "current_old", current_chunk["old_start"]
                    )
                    new_num = current_chunk.get(
                        "current_new", current_chunk["new_start"]
                    )
                    current_chunk["lines"].append(
                        {
                            "type": LineType.CONTEXT,
                            "oldNum": old_num,
                            "newNum": new_num,
                            "content": line[1:],  # Remove prefix
                        }
                    )
                    current_chunk["current_old"] = old_num + 1
                    current_chunk["current_new"] = new_num + 1

                elif line.startswith("-"):
                    # Deletion
                    old_num = current_chunk.get(
                        "current_old", current_chunk["old_start"]
                    )
                    current_chunk["lines"].append(
                        {
                            "type": LineType.DELETION,
                            "oldNum": old_num,
                            "newNum": None,
                            "content": line[1:],  # Remove prefix
                        }
                    )
                    current_chunk["current_old"] = old_num + 1
                    if current_file:
                        current_file["deletions"] += 1

                elif line.startswith("+"):
                    # Addition
                    new_num = current_chunk.get(
                        "current_new", current_chunk["new_start"]
                    )
                    current_chunk["lines"].append(
                        {
                            "type": LineType.ADDITION,
                            "oldNum": None,
                            "newNum": new_num,
                            "content": line[1:],  # Remove prefix
                        }
                    )
                    current_chunk["current_new"] = new_num + 1
                    if current_file:
                        current_file["additions"] += 1

            i += 1

        # Finalize last file and chunk
        if current_chunk and current_file:
            current_file["chunks"].append(self._finalize_chunk(current_chunk))
        if current_file:
            files.append(self._finalize_file(current_file))

        return files

    def _finalize_chunk(self, chunk_data: Dict[str, Any]) -> DiffChunk:
        """Convert chunk dict to DiffChunk model."""
        lines = [DiffLine(**line_data) for line_data in chunk_data["lines"]]
        return DiffChunk(
            old_start=chunk_data["old_start"],
            old_lines=chunk_data["old_lines"],
            new_start=chunk_data["new_start"],
            new_lines=chunk_data["new_lines"],
            lines=lines,
        )

    def _finalize_file(self, file_data: Dict[str, Any]) -> DiffFile:
        """Convert file dict to DiffFile model."""
        return DiffFile(
            path=file_data["path"],
            old_path=file_data["old_path"]
            if file_data["old_path"] != file_data["path"]
            else None,
            additions=file_data["additions"],
            deletions=file_data["deletions"],
            chunks=file_data["chunks"],
            is_binary=file_data["is_binary"],
            is_renamed=file_data["is_renamed"],
            status=file_data["status"],
        )
