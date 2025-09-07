import asyncio
import time
import threading
from pathlib import Path
from typing import Set, Optional, Dict, Any, Callable, Awaitable
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver, ObservedWatch
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent, FileSystemEvent
from loopback.event_manager import EventManager, EventType


class ReviewFileSystemEventHandler(FileSystemEventHandler):
    """File system event handler for the review system."""
    
    def __init__(self, event_manager: EventManager, loop: asyncio.AbstractEventLoop):
        """Initialize the handler.
        
        Args:
            event_manager: Event manager to emit file change events
            loop: Event loop to use for scheduling coroutines
        """
        self.event_manager = event_manager
        self.loop = loop
        self._last_event_times: Dict[str, float] = {}
        self._debounce_time = 0.5  # Debounce events within 500ms
    
    def _should_emit_event(self, file_path: str) -> bool:
        """Check if we should emit an event for this file change."""
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
            
            if self._should_emit_event(file_path):
                asyncio.run_coroutine_threadsafe(
                    self.event_manager.emit_event(
                        EventType.FILE_CHANGED,
                        {
                            "file_path": file_path,
                            "event_type": "modified",
                            "timestamp": time.time()
                        }
                    ),
                    self.loop
                )


class FileWatcher:
    """Watches files for changes and emits events."""
    
    def __init__(self, event_manager: EventManager, loop: asyncio.AbstractEventLoop):
        """Initialize the file watcher.
        
        Args:
            event_manager: Event manager to emit file change events
            loop: Event loop to use for scheduling coroutines
        """
        self.event_manager = event_manager
        self.loop = loop
        self.observer: Optional[BaseObserver] = None
        self.watch_handles: Dict[str, ObservedWatch] = {}  # Directory -> watch handle
        self._is_watching = False
    
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
        
        handler = ReviewFileSystemEventHandler(self.event_manager, self.loop)
        try:
            watch_handle = self.observer.schedule(
                handler, 
                directory, 
                recursive=True
            )
            self.watch_handles[directory] = watch_handle
            self._is_watching = True
        except Exception as e:
            print(f"Warning: Could not watch directory {directory}: {e}")
    
    def stop(self) -> None:
        """Stop the file watcher."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
        self.watch_handles.clear()
        self._is_watching = False