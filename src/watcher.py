"""
Filesystem Watcher for Project Directory

Monitors the projects directory for changes and emits signals
to update the UI when projects are added, modified, or deleted.
"""

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from app.core.redis_client import RedisClient

logger = logging.getLogger(__name__)


class _ProjectEventHandler(FileSystemEventHandler):
    def __init__(self, watcher: "ProjectWatcher"):
        super().__init__()
        self.watcher = watcher

    def on_created(self, event):
        if not event.is_directory:
            self.watcher._handle_file_change(Path(event.src_path), change_type="created")

    def on_modified(self, event):
        if not event.is_directory:
            self.watcher._handle_file_change(Path(event.src_path), change_type="modified")

    def on_deleted(self, event):
        if not event.is_directory:
            self.watcher._handle_file_change(Path(event.src_path), change_type="deleted")

    def on_moved(self, event):
        if not event.is_directory:
            self.watcher._handle_file_change(Path(event.dest_path), change_type="modified")


class ProjectWatcher(QObject):
    """
    Watches the projects directory for changes using watchdog.

    Signals:
        projects_changed: Emitted when any project file is added, modified, or deleted
        project_updated: Emitted when a specific project is updated (slug)
    """

    projects_changed = Signal()
    project_updated = Signal(str)  # project slug

    def __init__(self, projects_dir: Path, parent=None):
        super().__init__(parent)
        self.projects_dir = projects_dir
        self._observer: Optional[Observer] = None
        self._handler = _ProjectEventHandler(self)
        self._running = False
        self._redis = RedisClient()

    def start(self):
        """Start watching the projects directory."""
        if self._running:
            return
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self._observer = Observer()
        self._observer.schedule(self._handler, str(self.projects_dir), recursive=False)
        self._observer.start()
        self._running = True
        logger.info(f"Started watching: {self.projects_dir}")

    def stop(self):
        """Stop watching."""
        if not self._running:
            return
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
        self._running = False
        logger.info("Stopped watching projects directory")

    def _handle_file_change(self, file_path: Path, change_type: str):
        if file_path.suffix != ".yaml":
            return
        slug = file_path.stem
        self.projects_changed.emit()
        if change_type in ("created", "modified"):
            self.project_updated.emit(slug)
            self._redis.publish_command("project_updated", {"project": slug})
        logger.debug("Project %s: %s", change_type, slug)


# Global watcher instance
_project_watcher: Optional[ProjectWatcher] = None


def get_project_watcher(projects_dir: Path) -> ProjectWatcher:
    """Get or create the global project watcher."""
    global _project_watcher
    
    if _project_watcher is None:
        _project_watcher = ProjectWatcher(projects_dir)
    
    return _project_watcher


def start_watching(projects_dir: Path) -> ProjectWatcher:
    """Start watching the projects directory."""
    watcher = get_project_watcher(projects_dir)
    watcher.start()
    return watcher


def stop_watching():
    """Stop the global watcher."""
    global _project_watcher
    
    if _project_watcher:
        _project_watcher.stop()
        _project_watcher = None
