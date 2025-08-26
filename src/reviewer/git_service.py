import subprocess
import re
from typing import List, Optional, Dict, Any
from pathlib import Path

from reviewer.models import GitDiff, DiffFile, DiffChunk, DiffLine, LineType


class GitService:
    """Service for interacting with git repositories."""
    
    def __init__(self, repo_path: Optional[str] = None) -> None:
        """Initialize with optional repository path."""
        self.repo_path = Path(repo_path) if repo_path else Path.cwd()
        
    def get_diff(
        self, 
        commit_hash: Optional[str] = None, 
        commit_range: Optional[str] = None,
        staged: bool = False,
        include_working_dir: bool = False
    ) -> GitDiff:
        """Get diff for a commit, range, or changes."""
        commit_info: List[Optional[str]]
        
        if commit_range:
            # Get diff for commit range (e.g., "abc123..def456" or "main..feature")
            diff_cmd = ["git", "diff", commit_range]
            diff_output = self._run_git_command(diff_cmd)
            
            # Parse range to get info
            if ".." in commit_range:
                from_ref, to_ref = commit_range.split("..", 1)
                commit_info = [None, None, f"Range: {from_ref}..{to_ref}"]
            else:
                commit_info = [None, None, f"Range: {commit_range}"]
                
        elif commit_hash:
            # Get diff for specific commit
            diff_cmd = ["git", "show", "--pretty=format:", commit_hash]
            diff_output = self._run_git_command(diff_cmd)
            
            # Get commit info
            info_cmd = ["git", "show", "--pretty=format:%H|%an|%s", "--no-patch", commit_hash]
            info_result = self._run_git_command(info_cmd)
            commit_parts = info_result.strip().split("|") if info_result.strip() else ["", "", ""]
            commit_info = [part if part else None for part in commit_parts]
            
        elif staged:
            # Get staged changes
            diff_cmd = ["git", "diff", "--cached"]
            diff_output = self._run_git_command(diff_cmd)
            commit_info = [None, None, "Staged changes"]
            
        else:
            # Get working directory changes
            diff_cmd = ["git", "diff", "HEAD"]
            diff_output = self._run_git_command(diff_cmd)
            commit_info = [None, None, "Working directory changes"]
        
        # Handle additional working directory changes if requested
        additional_diff_output = ""
        if include_working_dir and (commit_hash or commit_range):
            # Add working directory changes to the diff
            try:
                wd_diff_cmd = ["git", "diff", "HEAD"]
                additional_diff_output = self._run_git_command(wd_diff_cmd)
                if additional_diff_output.strip():
                    # Update description to indicate working dir changes are included
                    if commit_info[2]:
                        commit_info[2] += " + Working directory changes"
                    else:
                        commit_info[2] = "Working directory changes included"
            except Exception:
                # If working directory diff fails, continue without it
                pass
            
        # Parse the main diff
        files = self._parse_diff_output(diff_output)
        
        # If we have additional working directory changes, parse and merge them
        if additional_diff_output.strip():
            additional_files = self._parse_diff_output(additional_diff_output)
            # Merge files - if same file exists in both, combine chunks
            files = self._merge_diff_files(files, additional_files)
        
        return GitDiff(
            files=files,
            commit_hash=commit_info[0],
            author=commit_info[1], 
            message=commit_info[2]
        )
    
    def get_file_at_commit(self, file_path: str, commit_hash: str) -> str:
        """Get file contents at a specific commit."""
        cmd = ["git", "show", f"{commit_hash}:{file_path}"]
        return self._run_git_command(cmd)
    
    def _run_git_command(self, cmd: List[str]) -> str:
        """Run a git command and return output."""
        try:
            result = subprocess.run(
                cmd, 
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
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
        current_file: Optional[Dict[str, Any]] = None
        current_chunk: Optional[Dict[str, Any]] = None
        
        lines = diff_output.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # File header
            if line.startswith('diff --git'):
                if current_file:
                    files.append(self._finalize_file(current_file))
                
                # Parse file paths
                match = re.match(r'diff --git a/(.*) b/(.*)', line)
                if match:
                    current_file = {
                        'old_path': match.group(1),
                        'path': match.group(2),
                        'chunks': [],
                        'additions': 0,
                        'deletions': 0,
                        'is_binary': False,
                        'is_renamed': False
                    }
            
            # Binary file detection
            elif line.startswith('Binary files'):
                if current_file:
                    current_file['is_binary'] = True
            
            # File rename detection
            elif line.startswith('similarity index') or line.startswith('rename from'):
                if current_file:
                    current_file['is_renamed'] = True
            
            # Chunk header
            elif line.startswith('@@'):
                if current_file and current_chunk:
                    current_file['chunks'].append(self._finalize_chunk(current_chunk))
                
                # Parse chunk header: @@ -old_start,old_lines +new_start,new_lines @@
                match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
                if match:
                    current_chunk = {
                        'old_start': int(match.group(1)),
                        'old_lines': int(match.group(2) or 1),
                        'new_start': int(match.group(3)), 
                        'new_lines': int(match.group(4) or 1),
                        'lines': []
                    }
            
            # Diff lines
            elif current_chunk is not None and (line.startswith(' ') or line.startswith('-') or line.startswith('+')):
                if line.startswith(' '):
                    # Context line
                    old_num = current_chunk.get('current_old', current_chunk['old_start'])
                    new_num = current_chunk.get('current_new', current_chunk['new_start'])
                    current_chunk['lines'].append({
                        'type': LineType.CONTEXT,
                        'old_num': old_num,
                        'new_num': new_num,
                        'content': line[1:]  # Remove prefix
                    })
                    current_chunk['current_old'] = old_num + 1
                    current_chunk['current_new'] = new_num + 1
                    
                elif line.startswith('-'):
                    # Deletion
                    old_num = current_chunk.get('current_old', current_chunk['old_start'])
                    current_chunk['lines'].append({
                        'type': LineType.DELETION,
                        'old_num': old_num,
                        'new_num': None,
                        'content': line[1:]  # Remove prefix
                    })
                    current_chunk['current_old'] = old_num + 1
                    if current_file:
                        current_file['deletions'] += 1
                        
                elif line.startswith('+'):
                    # Addition
                    new_num = current_chunk.get('current_new', current_chunk['new_start'])
                    current_chunk['lines'].append({
                        'type': LineType.ADDITION,
                        'old_num': None,
                        'new_num': new_num,
                        'content': line[1:]  # Remove prefix
                    })
                    current_chunk['current_new'] = new_num + 1
                    if current_file:
                        current_file['additions'] += 1
            
            i += 1
        
        # Finalize last file and chunk
        if current_chunk and current_file:
            current_file['chunks'].append(self._finalize_chunk(current_chunk))
        if current_file:
            files.append(self._finalize_file(current_file))
            
        return files
    
    def _finalize_chunk(self, chunk_data: Dict[str, Any]) -> DiffChunk:
        """Convert chunk dict to DiffChunk model."""
        lines = [DiffLine(**line_data) for line_data in chunk_data['lines']]
        return DiffChunk(
            old_start=chunk_data['old_start'],
            old_lines=chunk_data['old_lines'], 
            new_start=chunk_data['new_start'],
            new_lines=chunk_data['new_lines'],
            lines=lines
        )
    
    def _finalize_file(self, file_data: Dict[str, Any]) -> DiffFile:
        """Convert file dict to DiffFile model."""
        return DiffFile(
            path=file_data['path'],
            old_path=file_data['old_path'] if file_data['old_path'] != file_data['path'] else None,
            additions=file_data['additions'],
            deletions=file_data['deletions'], 
            chunks=file_data['chunks'],
            is_binary=file_data['is_binary'],
            is_renamed=file_data['is_renamed']
        )
    
    def _merge_diff_files(self, main_files: List[DiffFile], additional_files: List[DiffFile]) -> List[DiffFile]:
        """Merge two lists of diff files, combining chunks for files that appear in both."""
        merged_files = []
        main_files_dict = {f.path: f for f in main_files}
        
        # Add all main files first
        for file in main_files:
            merged_files.append(file)
        
        # Add additional files, merging if they already exist
        for additional_file in additional_files:
            if additional_file.path in main_files_dict:
                # File exists in both - merge chunks
                main_file = main_files_dict[additional_file.path]
                # Create new file with combined chunks and stats
                merged_file = DiffFile(
                    path=additional_file.path,
                    old_path=main_file.old_path or additional_file.old_path,
                    additions=main_file.additions + additional_file.additions,
                    deletions=main_file.deletions + additional_file.deletions,
                    chunks=main_file.chunks + additional_file.chunks,
                    is_binary=main_file.is_binary or additional_file.is_binary,
                    is_renamed=main_file.is_renamed or additional_file.is_renamed
                )
                # Replace the main file with merged version
                for i, f in enumerate(merged_files):
                    if f.path == additional_file.path:
                        merged_files[i] = merged_file
                        break
            else:
                # New file - just add it
                merged_files.append(additional_file)
        
        return merged_files