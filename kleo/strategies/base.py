"""Base class for task selection strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kleo.ticket import Task


class SelectionStrategy(ABC):
    """Abstract base class for task selection strategies.

    Strategies determine which task to print when multiple tasks are available.
    Subclasses must implement the `name` property and `select` method.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this strategy."""
        ...

    @abstractmethod
    def select(self, tasks: list[Task]) -> Task | None:
        """Select a task from the list.

        Args:
            tasks: List of available tasks to choose from.

        Returns:
            The selected task, or None if the list is empty.
        """
        ...

    def on_printed(self, task: Task) -> None:
        """Called after a task is printed.

        Optional hook for stateful strategies that need to track
        what has been printed (e.g., round-robin or weighted strategies).

        Args:
            task: The task that was just printed.
        """
        pass
