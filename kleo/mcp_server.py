"""MCP server for Kleo receipt printer integration."""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from kleo.config import load_config
from kleo.discovery import discover_printers as discover_network_printers
from kleo.discovery import filter_receipt_printers
from kleo.printer import PrinterConfig, get_printer, resolve_printer_config
from kleo.ticket import Task, TicketPrinter

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "kleo",
    instructions=(
        "Kleo prints task tickets to Epson receipt printers. "
        "Use list_things_tasks to browse available tasks, then "
        "print_things_task with a task ID to print a ticket."
    ),
)


def _get_printer_config() -> PrinterConfig | None:
    """Resolve printer config from kleo config file."""
    cfg = load_config()
    return resolve_printer_config(
        auto=cfg.auto,
        printer_name=cfg.printer_name,
        host=cfg.host,
        connection=cfg.connection,
    )


@mcp.tool()
def print_things_task(task_id: str) -> str:
    """Fetch a Things task by UUID and print its ticket to a receipt printer.

    Args:
        task_id: The Things task UUID to print.

    Returns:
        A message indicating success or describing the error.
    """
    try:
        import things
    except ImportError:
        return "Things.py library is not installed. Install with: uv add things.py"

    cfg = load_config()

    # Fetch the specific task
    try:
        todos = things.todos(uuid=task_id)
    except Exception as e:
        return f"Failed to fetch task from Things: {e}"

    if not todos:
        return f"Task not found: {task_id}"

    todo = todos[0]
    task = Task(
        title=todo.get("title", "Untitled"),
        description=todo.get("notes") or None,
        task_id=todo.get("uuid"),
        auth_token=cfg.things_auth_token,
        tags=list(todo.get("tags") or []),
    )

    # Resolve printer
    try:
        printer_config = _get_printer_config()
    except ValueError as e:
        return f"Printer error: {e}"

    # Print the ticket
    try:
        with get_printer(printer_config) as printer:
            ticket_printer = TicketPrinter(printer)
            if printer_config and printer_config.connection_type != "dummy":
                ticket_printer.print_task(task)
                return f"Printed ticket for: {task.title}"
            else:
                preview = ticket_printer.print_preview(task)
                return f"Dummy mode preview:\n{preview}"
    except Exception as e:
        return f"Print error: {e}"


@mcp.tool()
def list_things_tasks(tag: str = "5m") -> list[dict[str, str | None]] | str:
    """List available Things tasks filtered by tag.

    Args:
        tag: The Things tag to filter by (default: "5m").

    Returns:
        List of tasks with uuid, title, and notes fields, or an error message.
    """
    try:
        import things
    except ImportError:
        return "Things.py library is not installed. Install with: uv add things.py"

    try:
        todos = things.todos(tag=tag, status="incomplete")
    except Exception as e:
        return f"Failed to fetch tasks from Things: {e}"

    return [
        {
            "uuid": todo.get("uuid"),
            "title": todo.get("title", "Untitled"),
            "notes": todo.get("notes") or None,
        }
        for todo in todos
    ]


@mcp.tool()
def discover_printers() -> list[dict[str, str | int | bool]] | str:
    """Find receipt printers on the network via Bonjour/mDNS.

    Returns:
        List of discovered printers with name, host, port, and receipt
        printer status, or an error message.
    """
    try:
        printers = discover_network_printers()
    except Exception as e:
        return f"Discovery error: {e}"

    receipt = filter_receipt_printers(printers)
    receipt_hosts = {p.host for p in receipt}

    return [
        {
            "name": p.display_name,
            "host": p.host,
            "port": p.port,
            "is_receipt_printer": p.host in receipt_hosts,
        }
        for p in printers
    ]


if __name__ == "__main__":
    mcp.run()
