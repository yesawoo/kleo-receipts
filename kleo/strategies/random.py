"""Random task selection strategy."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from kleo.strategies.base import SelectionStrategy

if TYPE_CHECKING:
    from kleo.ticket import Task


class RandomStrategy(SelectionStrategy):
    """Selects a random task from the available tasks."""

    @property
    def name(self) -> str:
        return "random"

    def select(self, tasks: list[Task]) -> Task | None:
        """Select a random task from the list.

        Args:
            tasks: List of available tasks to choose from.

        Returns:
            A randomly selected task, or None if the list is empty.
        """
        return random.choice(tasks) if tasks else None
