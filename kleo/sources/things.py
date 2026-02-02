"""Things app task source using things.py library."""

from __future__ import annotations

from kleo.sources.base import TaskSource
from kleo.ticket import Task


class ThingsSource(TaskSource):
    """Fetches tasks from Things app via things.py library.

    Requires Things app to be installed on macOS. The things.py library
    reads directly from Things' SQLite database.
    """

    def __init__(self, tag: str = "5m") -> None:
        """Initialize the Things source.

        Args:
            tag: The tag to filter tasks by (default: "5m").
        """
        self.tag = tag

    @property
    def name(self) -> str:
        return f"Things (tag: {self.tag})"

    def fetch_tasks(self) -> list[Task]:
        """Fetch incomplete tasks with the configured tag from Things.

        Returns:
            List of tasks matching the tag filter.

        Raises:
            ImportError: If things.py is not installed.
            RuntimeError: If Things database cannot be accessed.
        """
        try:
            import things
        except ImportError as e:
            raise ImportError(
                "things.py library is required for Things integration. "
                "Install with: uv add things.py"
            ) from e

        try:
            todos = things.todos(tag=self.tag, status="incomplete")
        except Exception as e:
            raise RuntimeError(
                f"Failed to fetch tasks from Things: {e}. "
                "Make sure Things app is installed and has been opened at least once."
            ) from e

        return [
            Task(
                title=todo.get("title", "Untitled"),
                description=todo.get("notes") or None,
                task_id=todo.get("uuid"),
                tags=[self.tag],
            )
            for todo in todos
        ]
