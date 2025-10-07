import asyncio
import time
import threading
from pathlib import Path
from typing import Set, Dict, Any, Callable, Awaitable
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver, ObservedWatch
from watchdog.events import (
    FileSystemEventHandler,
    FileModifiedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileSystemEvent,
)
from backloop.event_manager import EventManager, EventType
import pathspec


def debug_write(message: str) -> None:
    """Write debug message to /tmp/backloop-debug.txt."""
    pass


class ReviewFileSystemEventHandler(FileSystemEventHandler):
    """File system event handler for the review system."""

    def __init__(
        self,
        event_manager: EventManager,
        loop: asyncio.AbstractEventLoop,
        repo_root: Path,
        gitignore_spec: pathspec.PathSpec | None = None,
    ) -> None:
        """Initialize the handler.

        Args:
            event_manager: Event manager to emit file change events
            loop: Event loop to use for scheduling coroutines
            repo_root: Root directory of the repository
            gitignore_spec: Compiled gitignore patterns (optional)
        """
        self.event_manager = event_manager
        self.loop = loop
        self.repo_root = repo_root
        self.gitignore_spec = gitignore_spec
        self._last_event_times: Dict[str, float] = {}
        self._debounce_time = 0.5  # Debounce events within 500ms

    def _is_gitignored(self, file_path: str) -> bool:
        """Check if a file is gitignored."""
        if not self.gitignore_spec:
            return False

        try:
            # Convert absolute path to relative path from repo root
            rel_path = Path(file_path).relative_to(self.repo_root)
            return self.gitignore_spec.match_file(str(rel_path))
        except (ValueError, OSError):
            # File is outside repo or other error, don't filter it
            return False

    def _should_emit_event(self, file_path: str) -> bool:
        """Check if we should emit an event for this file change."""
        # Check if file is gitignored
        if self._is_gitignored(file_path):
            return False

        current_time = time.time()
        last_time = self._last_event_times.get(file_path, 0)

        if current_time - last_time < self._debounce_time:
            return False

        self._last_event_times[file_path] = current_time
        return True

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        if isinstance(event, FileModifiedEvent) and not event.is_directory:
            file_path = str(Path(str(event.src_path)).resolve())
            debug_write(f"[DEBUG] File modification detected: {file_path}")

            if self._should_emit_event(file_path):
                debug_write(f"[DEBUG] Emitting FILE_CHANGED event for: {file_path}")
                asyncio.run_coroutine_threadsafe(
                    self.event_manager.emit_event(
                        EventType.FILE_CHANGED,
                        {
                            "file_path": file_path,
                            "event_type": "modified",
                            "timestamp": time.time(),
                        },
                    ),
                    self.loop,
                )
            else:
                debug_write(f"[DEBUG] Skipping event for: {file_path} (gitignored or debounced)")

    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file deletion events."""
        if isinstance(event, FileDeletedEvent) and not event.is_directory:
            file_path = str(Path(str(event.src_path)).resolve())

            if self._should_emit_event(file_path):
                asyncio.run_coroutine_threadsafe(
                    self.event_manager.emit_event(
                        EventType.FILE_REMOVED,
                        {
                            "file_path": file_path,
                            "event_type": "deleted",
                            "timestamp": time.time(),
                        },
                    ),
                    self.loop,
                )


class FileWatcher:
    """Watches files for changes and emits events."""

    def __init__(
        self, event_manager: EventManager, loop: asyncio.AbstractEventLoop
    ) -> None:
        """Initialize the file watcher.

        Args:
            event_manager: Event manager to emit file change events
            loop: Event loop to use for scheduling coroutines
        """
        self.event_manager = event_manager
        self.loop = loop
        self.observer: BaseObserver | None = None
        self.watch_handles: Dict[str, ObservedWatch] = {}  # Directory -> watch handle
        self._is_watching = False

    def _load_gitignore(self, directory: Path) -> pathspec.PathSpec | None:
        """Load and parse .gitignore file if it exists.

        Args:
            directory: Directory to look for .gitignore in

        Returns:
            Compiled pathspec or None if no .gitignore found
        """
        gitignore_path = directory / ".gitignore"
        if not gitignore_path.exists():
            return None

        try:
            with open(gitignore_path, "r") as f:
                patterns = f.read().splitlines()
            return pathspec.PathSpec.from_lines("gitwildmatch", patterns)
        except (OSError, IOError) as e:
            print(f"Warning: Could not read .gitignore: {e}")
            return None

    def start_watching(self, directory: str) -> None:
        """Start watching a directory for changes.

        Args:
            directory: Directory path to watch recursively
        """
        if self._is_watching:
            return

        if self.observer is None:
            self.observer = Observer()
            self.observer.start()

        # Load .gitignore patterns
        dir_path = Path(directory)
        gitignore_spec = self._load_gitignore(dir_path)

        handler = ReviewFileSystemEventHandler(
            self.event_manager, self.loop, dir_path, gitignore_spec
        )
        try:
            watch_handle = self.observer.schedule(handler, directory, recursive=True)
            self.watch_handles[directory] = watch_handle
            self._is_watching = True
            debug_write(f"[DEBUG] Started watching directory: {directory}")
        except Exception as e:
            debug_write(f"[ERROR] Could not watch directory {directory}: {e}")

    def stop(self) -> None:
        """Stop the file watcher."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
        self.watch_handles.clear()
        self._is_watching = False
