"""Server mode for periodic task ticket printing."""

from __future__ import annotations

import os
import re
import signal
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

import logging

import schedule
from rich.console import Console

from kleo.config import ServerState
from kleo.printer import PrinterConfig, get_printer
from kleo.ticket import TicketPrinter

if TYPE_CHECKING:
    from kleo.sources.base import TaskSource
    from kleo.strategies.base import SelectionStrategy

logger = logging.getLogger(__name__)
console = Console()


@dataclass
class ServerConfig:
    """Configuration for the ticket server."""

    every: str = "30 minutes"
    printer_config: PrinterConfig | None = None
    dry_run: bool = False
    run_now: bool = True
    mcp_enabled: bool = False
    mcp_port: int = 8177

    # Parsed schedule components (set by _parse_schedule)
    _interval: int = field(default=30, init=False, repr=False)
    _unit: str = field(default="minutes", init=False, repr=False)
    _at_time: str | None = field(default=None, init=False, repr=False)


class TicketServer:
    """Server that periodically prints task tickets.

    Uses the schedule library to run at configured intervals,
    fetching tasks from a source and selecting one to print.
    """

    def __init__(
        self,
        source: TaskSource,
        strategy: SelectionStrategy,
        config: ServerConfig,
    ) -> None:
        self.source = source
        self.strategy = strategy
        self.config = config
        self._running = False
        self._tick_count = 0
        self._mcp_thread: threading.Thread | None = None
        self._state = ServerState(
            pid=os.getpid(),
            started_at=datetime.now().isoformat(),
        )

    def start(self) -> None:
        """Start the server loop."""
        self._running = True
        self._setup_signal_handlers()
        self._configure_schedule()

        # Save initial state
        self._state.save()

        # Start MCP server if enabled
        if self.config.mcp_enabled:
            self._start_mcp_server()

        console.print()
        console.print("[bold green]Kleo Ticket Server Started[/bold green]")
        console.print(f"  Source: [cyan]{self.source.name}[/cyan]")
        console.print(f"  Strategy: [cyan]{self.strategy.name}[/cyan]")
        console.print(f"  Schedule: [cyan]{self.config.every}[/cyan]")
        if self.config.mcp_enabled:
            console.print(
                f"  MCP: [cyan]http://localhost:{self.config.mcp_port}[/cyan]"
            )
        if self.config.dry_run:
            console.print("  Mode: [yellow]DRY RUN (no actual printing)[/yellow]")
        console.print()
        console.print("[dim]Press Ctrl+C to stop[/dim]")
        console.print()

        if self.config.run_now:
            self._tick()

        while self._running:
            schedule.run_pending()
            time.sleep(1)

        # Clear PID on shutdown
        self._state.pid = None
        self._state.save()

        console.print()
        console.print("[bold yellow]Server stopped[/bold yellow]")

    def stop(self) -> None:
        """Stop the server loop."""
        self._running = False

    def _start_mcp_server(self) -> None:
        """Launch the MCP HTTP server in a background daemon thread."""
        from kleo.mcp_server import mcp as mcp_app

        mcp_app.settings.port = self.config.mcp_port

        def _run_mcp() -> None:
            try:
                mcp_app.run(transport="streamable-http")
            except Exception:
                logger.exception("MCP server failed on port %d", self.config.mcp_port)

        self._mcp_thread = threading.Thread(target=_run_mcp, daemon=True)
        self._mcp_thread.start()

    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum: int, frame: object) -> None:
        """Handle shutdown signals."""
        console.print("\n[yellow]Received shutdown signal...[/yellow]")
        self.stop()

    def _configure_schedule(self) -> None:
        """Parse the --every flag and configure the schedule library."""
        self._parse_schedule()

        interval = self.config._interval
        unit = self.config._unit
        at_time = self.config._at_time

        # Build the schedule based on parsed components
        if unit == "seconds":
            job = schedule.every(interval).seconds
        elif unit == "minutes":
            job = schedule.every(interval).minutes
        elif unit == "hours":
            job = schedule.every(interval).hours
        elif unit == "days":
            job = schedule.every(interval).days
            if at_time:
                job = job.at(at_time)
        elif unit == "weeks":
            job = schedule.every(interval).weeks
            if at_time:
                job = job.at(at_time)
        elif unit in (
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ):
            # Day of week scheduling
            day_job = getattr(schedule.every(), unit)
            if at_time:
                job = day_job.at(at_time)
            else:
                job = day_job
        else:
            raise ValueError(f"Unsupported schedule unit: {unit}")

        job.do(self._tick)

    def _parse_schedule(self) -> None:
        """Parse the natural language schedule string.

        Supports patterns like:
        - "30 seconds", "5 minutes", "2 hours", "1 day", "1 week"
        - "1 day at 09:00", "1 week at 10:30"
        - "monday", "tuesday at 14:00"
        """
        every = self.config.every.lower().strip()

        # Check for day-of-week patterns
        days_of_week = (
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        )
        for day in days_of_week:
            if every.startswith(day):
                self.config._unit = day
                self.config._interval = 1
                # Check for "at HH:MM" suffix
                at_match = re.search(r"at\s+(\d{1,2}:\d{2})", every)
                if at_match:
                    self.config._at_time = at_match.group(1)
                return

        # Parse "N unit [at HH:MM]" patterns
        pattern = r"^(\d+)\s*(seconds?|minutes?|hours?|days?|weeks?)\s*(?:at\s+(\d{1,2}:\d{2}))?$"
        match = re.match(pattern, every)

        if not match:
            raise ValueError(
                f"Invalid schedule format: '{self.config.every}'. "
                "Expected formats: '30 minutes', '2 hours', '1 day at 09:00', 'monday at 10:30'"
            )

        interval_str, unit, at_time = match.groups()
        self.config._interval = int(interval_str)

        # Normalize unit to plural
        unit = unit.rstrip("s") + "s"
        self.config._unit = unit

        if at_time:
            self.config._at_time = at_time

    def _tick(self) -> None:
        """Execute one print cycle: fetch, select, print."""
        self._tick_count += 1
        now = datetime.now().strftime("%H:%M:%S")

        console.print(f"[dim][{now}][/dim] Tick #{self._tick_count}")

        # Update state
        self._state.tick_count = self._tick_count
        self._state.last_tick_at = datetime.now().isoformat()

        # Compute next run time
        next_job = schedule.next_run()
        if next_job:
            self._state.next_run_at = str(next_job)

        # Fetch tasks
        try:
            tasks = self.source.fetch_tasks()
        except Exception as e:
            console.print(f"  [red]Error fetching tasks:[/red] {e}")
            self._state.last_tick_status = "error"
            self._state.last_error = str(e)
            self._state.save()
            return

        if not tasks:
            console.print("  [yellow]No tasks available[/yellow]")
            self._state.last_tick_status = "no_tasks"
            self._state.last_error = None
            self._state.save()
            return

        console.print(f"  Found [cyan]{len(tasks)}[/cyan] task(s)")

        # Select a task
        task = self.strategy.select(tasks)
        if task is None:
            console.print("  [yellow]Strategy returned no task[/yellow]")
            self._state.last_tick_status = "no_tasks"
            self._state.save()
            return

        console.print(f"  Selected: [bold]{task.title}[/bold]")

        # Print the task
        if self.config.dry_run:
            console.print("  [yellow]Dry run - skipping print[/yellow]")
            self.strategy.on_printed(task)
            self._state.last_tick_status = "ok"
            self._state.last_error = None
            self._state.last_task_title = task.title
            self._state.save()
            return

        try:
            with get_printer(self.config.printer_config) as printer:
                ticket_printer = TicketPrinter(printer)
                if (
                    self.config.printer_config
                    and self.config.printer_config.connection_type != "dummy"
                ):
                    ticket_printer.print_task(
                        task, triggered_by=f"server:tick#{self._tick_count}"
                    )
                    console.print("  [green]Printed successfully[/green]")
                else:
                    # Dummy mode - show preview
                    preview = ticket_printer.print_preview(task)
                    console.print(f"  [dim]Preview:[/dim]\n{preview}")
            self.strategy.on_printed(task)
            self._state.last_tick_status = "ok"
            self._state.last_error = None
            self._state.last_task_title = task.title
        except Exception as e:
            console.print(f"  [red]Error printing:[/red] {e}")
            self._state.last_tick_status = "error"
            self._state.last_error = str(e)

        self._state.save()
