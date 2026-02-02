"""Base class for task sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kleo.ticket import Task


class TaskSource(ABC):
    """Abstract base class for task sources.

    Task sources fetch tasks from external systems (e.g., Things app,
    Todoist, local files, etc.) and convert them to kleo Task objects.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this source."""
        ...

    @abstractmethod
    def fetch_tasks(self) -> list[Task]:
        """Fetch available tasks from the source.

        Returns:
            List of tasks available for printing.
        """
        ...
