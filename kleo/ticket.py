"""Task ticket formatting for receipt printers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from escpos.escpos import Escpos


@dataclass
class Task:
    """Represents a task to be printed on a ticket."""

    title: str
    description: str | None = None
    priority: str = "normal"  # low, normal, high, urgent
    due_date: datetime | None = None
    tags: list[str] = field(default_factory=list)
    task_id: str | None = None
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def priority_symbol(self) -> str:
        """Get a symbol representing the priority level."""
        symbols = {
            "low": "[ ]",
            "normal": "[*]",
            "high": "[!]",
            "urgent": "[!!!]",
        }
        return symbols.get(self.priority, "[*]")


class TicketPrinter:
    """Handles formatting and printing task tickets."""

    # Standard thermal receipt paper is 80mm or 58mm wide
    # 80mm = ~48 characters at standard font
    # 58mm = ~32 characters at standard font
    DEFAULT_WIDTH = 48

    def __init__(self, printer: Escpos, width: int = DEFAULT_WIDTH) -> None:
        self.printer = printer
        self.width = width

    def _center(self, text: str) -> str:
        """Center text within the ticket width."""
        return text.center(self.width)

    def _separator(self, char: str = "-") -> str:
        """Create a separator line."""
        return char * self.width

    def _wrap_text(self, text: str, indent: int = 0) -> list[str]:
        """Wrap text to fit within ticket width."""
        import textwrap

        return textwrap.wrap(text, width=self.width - indent)

    def print_task(self, task: Task) -> None:
        """Print a task ticket.

        Args:
            task: The task to print.
        """
        p = self.printer

        # Header
        p.set(align="center", bold=True, double_height=True, double_width=True)
        p.text("TASK TICKET\n")
        p.set(align="center", bold=False, double_height=False, double_width=False)
        p.text(self._separator("=") + "\n")

        # Task ID and Priority
        if task.task_id:
            p.set(align="left", bold=True)
            p.text(f"ID: {task.task_id}\n")

        p.set(align="left", bold=True)
        p.text(f"Priority: {task.priority.upper()} {task.priority_symbol}\n")
        p.text(self._separator("-") + "\n")

        # Title
        p.set(align="center", bold=True, double_height=True)
        for line in self._wrap_text(task.title):
            p.text(line + "\n")
        p.set(bold=False, double_height=False)
        p.text("\n")

        # Description
        if task.description:
            p.set(align="left")
            p.text("Description:\n")
            for line in self._wrap_text(task.description, indent=2):
                p.text(f"  {line}\n")
            p.text("\n")

        # Tags
        if task.tags:
            p.set(align="left", bold=True)
            p.text("Tags: ")
            p.set(bold=False)
            p.text(", ".join(f"#{tag}" for tag in task.tags) + "\n")
            p.text("\n")

        # Due date
        if task.due_date:
            p.set(align="left", bold=True)
            p.text("Due: ")
            p.set(bold=False)
            p.text(task.due_date.strftime("%Y-%m-%d %H:%M") + "\n")

        # Footer
        p.text(self._separator("-") + "\n")
        p.set(align="center", font="b")
        p.text(f"Created: {task.created_at.strftime('%Y-%m-%d %H:%M')}\n")
        p.text(self._separator("=") + "\n")

        # Cut the paper
        p.cut()

    def print_preview(self, task: Task) -> str:
        """Generate a text preview of the ticket without printing.

        Args:
            task: The task to preview.

        Returns:
            String representation of what would be printed.
        """
        lines = []
        sep_eq = "=" * self.width
        sep_dash = "-" * self.width

        lines.append(self._center("TASK TICKET"))
        lines.append(sep_eq)

        if task.task_id:
            lines.append(f"ID: {task.task_id}")

        lines.append(f"Priority: {task.priority.upper()} {task.priority_symbol}")
        lines.append(sep_dash)

        for line in self._wrap_text(task.title):
            lines.append(self._center(line))
        lines.append("")

        if task.description:
            lines.append("Description:")
            for line in self._wrap_text(task.description, indent=2):
                lines.append(f"  {line}")
            lines.append("")

        if task.tags:
            lines.append("Tags: " + ", ".join(f"#{tag}" for tag in task.tags))
            lines.append("")

        if task.due_date:
            lines.append(f"Due: {task.due_date.strftime('%Y-%m-%d %H:%M')}")

        lines.append(sep_dash)
        lines.append(self._center(f"Created: {task.created_at.strftime('%Y-%m-%d %H:%M')}"))
        lines.append(sep_eq)

        return "\n".join(lines)
