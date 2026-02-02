"""Task selection strategies for kleo-receipts server mode."""

from __future__ import annotations

from kleo.strategies.base import SelectionStrategy
from kleo.strategies.random import RandomStrategy

# Registry of available strategies
_STRATEGIES: dict[str, type[SelectionStrategy]] = {
    "random": RandomStrategy,
}


def get_strategy(name: str) -> SelectionStrategy:
    """Get a strategy instance by name.

    Args:
        name: The strategy name (e.g., "random").

    Returns:
        An instance of the requested strategy.

    Raises:
        ValueError: If the strategy name is not recognized.
    """
    strategy_class = _STRATEGIES.get(name.lower())
    if strategy_class is None:
        available = ", ".join(sorted(_STRATEGIES.keys()))
        raise ValueError(f"Unknown strategy '{name}'. Available: {available}")
    return strategy_class()


def list_strategies() -> list[str]:
    """Return a list of available strategy names."""
    return sorted(_STRATEGIES.keys())


__all__ = [
    "SelectionStrategy",
    "RandomStrategy",
    "get_strategy",
    "list_strategies",
]
