"""CLI interface for Kleo task ticket printer."""

from __future__ import annotations

import os
import platform
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel

from kleo import __version__
from kleo.config import (
    CONFIG_FILE,
    ServerState,
    config_source,
    load_config,
    set_config_value,
)
from kleo.discovery import discover_printers, find_printer_by_name
from kleo.printer import PrinterConfig, get_printer, detect_usb_printers
from kleo.ticket import Task, TicketPrinter

app = typer.Typer(
    name="kleo",
    help="Print task tickets to Epson receipt printers.",
    no_args_is_help=True,
)
config_app = typer.Typer(
    name="config",
    help="Manage kleo configuration.",
    no_args_is_help=True,
)
app.add_typer(config_app, name="config")
console = Console()


def version_callback(value: bool) -> None:
    if value:
        rprint(f"[bold]kleo[/bold] version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            "-v",
            help="Show version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """Kleo - Print task tickets to Epson receipt printers."""
    pass


# --- config subcommands ---


@config_app.command("show")
def config_show() -> None:
    """Show current configuration with value sources."""
    from rich.table import Table

    cfg = load_config()

    # Map config keys to their resolved values
    key_to_attr: dict[str, str] = {
        "schedule.every": "every",
        "schedule.tag": "tag",
        "schedule.strategy": "strategy",
        "printer.auto": "auto",
        "printer.printer_name": "printer_name",
        "printer.host": "host",
        "printer.connection": "connection",
        "things.auth_token": "things_auth_token",
        "service.dry_run": "dry_run",
        "service.now": "now",
    }

    table = Table(title="Kleo Configuration")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Source", style="dim")

    for key, attr in key_to_attr.items():
        value = getattr(cfg, attr)
        source = config_source(key)
        display_value = str(value) if value is not None else "[dim]-[/dim]"
        source_style = {
            "file": "[bold yellow]file[/bold yellow]",
            "env": "[bold blue]env[/bold blue]",
            "default": "default",
        }
        table.add_row(key, display_value, source_style.get(source, source))

    console.print(table)


@config_app.command("set")
def config_set(
    key_value: Annotated[
        str, typer.Argument(help='KEY=VALUE (e.g., schedule.every="2 hours")')
    ],
) -> None:
    """Set a configuration value."""
    if "=" not in key_value:
        rprint(
            '[red]Error:[/red] Expected KEY=VALUE format (e.g., schedule.every="2 hours")'
        )
        raise typer.Exit(1)

    key, value = key_value.split("=", 1)
    key = key.strip()
    value = value.strip().strip('"').strip("'")

    try:
        set_config_value(key, value)
    except ValueError as e:
        rprint(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    rprint(f"[green]Set[/green] {key} = {value}")


@config_app.command("path")
def config_path() -> None:
    """Show config file path and whether it exists."""
    exists = CONFIG_FILE.exists()
    status = "[green]exists[/green]" if exists else "[dim]not created yet[/dim]"
    rprint(f"{CONFIG_FILE}  ({status})")


# --- status command ---


def _log_base_path() -> Path:
    """Detect Homebrew log path (Apple Silicon vs Intel)."""
    if platform.machine() == "arm64":
        return Path("/opt/homebrew/var/log")
    return Path("/usr/local/var/log")


@app.command()
def status() -> None:
    """Show kleo server status."""
    state = ServerState.load()

    if state.pid is None:
        rprint("[yellow]Server is not running[/yellow]")
        rprint()
        rprint("[dim]Start with:[/dim]")
        rprint("  brew services start kleo-receipts")
        rprint("  kleo serve --auto")
        return

    # Check if PID is alive
    alive = False
    try:
        os.kill(state.pid, 0)
        alive = True
    except (ProcessLookupError, PermissionError):
        pass

    if not alive:
        rprint(f"[red]Server is stopped[/red] (stale PID {state.pid})")
        if state.last_tick_status == "error" and state.last_error:
            rprint(f"  Last error: [red]{state.last_error}[/red]")
        rprint()
        rprint("[dim]Start with:[/dim]")
        rprint("  brew services start kleo-receipts")
        rprint("  kleo serve --auto")
        return

    # Running
    rprint(f"[bold green]Server is running[/bold green] (PID {state.pid})")

    if state.started_at:
        started = datetime.fromisoformat(state.started_at)
        uptime = datetime.now() - started
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        rprint(f"  Uptime: {hours}h {minutes}m {seconds}s")

    rprint(f"  Ticks: {state.tick_count}")

    if state.last_tick_at:
        rprint(f"  Last tick: {state.last_tick_at} ({state.last_tick_status})")

    if state.last_task_title:
        rprint(f"  Last task: {state.last_task_title}")

    if state.last_error:
        rprint(f"  Last error: [red]{state.last_error}[/red]")

    if state.next_run_at:
        rprint(f"  Next run: {state.next_run_at}")

    # Config summary
    cfg = load_config()
    rprint()
    rprint(f"  Schedule: [cyan]{cfg.every}[/cyan]")
    rprint(f"  Tag: [cyan]{cfg.tag}[/cyan]")
    rprint(f"  Strategy: [cyan]{cfg.strategy}[/cyan]")
    rprint(f"  Auto-discover: [cyan]{cfg.auto}[/cyan]")

    # Log file locations
    log_base = _log_base_path()
    log_file = log_base / "kleo-receipts.log"
    error_log = log_base / "kleo-receipts-error.log"
    if log_file.exists() or error_log.exists():
        rprint()
        rprint("[dim]Logs:[/dim]")
        if log_file.exists():
            rprint(f"  {log_file}")
        if error_log.exists():
            rprint(f"  {error_log}")


# --- print-task command ---


@app.command()
def print_task(
    title: Annotated[str, typer.Argument(help="Task title")],
    description: Annotated[
        Optional[str],
        typer.Option("--description", "-d", help="Task description"),
    ] = None,
    priority: Annotated[
        str,
        typer.Option(
            "--priority",
            "-p",
            help="Priority level: low, normal, high, urgent",
        ),
    ] = "normal",
    due: Annotated[
        Optional[str],
        typer.Option("--due", help="Due date (YYYY-MM-DD or YYYY-MM-DD HH:MM)"),
    ] = None,
    tags: Annotated[
        Optional[list[str]],
        typer.Option("--tag", "-t", help="Tags (can be specified multiple times)"),
    ] = None,
    task_id: Annotated[
        Optional[str],
        typer.Option("--id", help="Task ID"),
    ] = None,
    preview: Annotated[
        bool,
        typer.Option("--preview", help="Preview ticket without printing"),
    ] = False,
    connection: Annotated[
        Optional[str],
        typer.Option("--connection", "-c", help="Connection type: usb, network, dummy"),
    ] = None,
    host: Annotated[
        Optional[str],
        typer.Option("--host", help="Printer host (for network connection)"),
    ] = None,
    vendor_id: Annotated[
        Optional[str],
        typer.Option("--vendor-id", help="USB vendor ID (hex, e.g., 0x04B8)"),
    ] = None,
    product_id: Annotated[
        Optional[str],
        typer.Option("--product-id", help="USB product ID (hex, e.g., 0x0202)"),
    ] = None,
    auto: Annotated[
        Optional[bool],
        typer.Option(
            "--auto/--no-auto", "-a", help="Auto-discover network printer via Bonjour"
        ),
    ] = None,
    printer_name: Annotated[
        Optional[str],
        typer.Option(
            "--printer", help="Printer name to find via Bonjour (e.g., 'kleo')"
        ),
    ] = None,
) -> None:
    """Print a task ticket."""
    # Resolve printer settings from config as fallback
    cfg = load_config()
    effective_auto = auto if auto is not None else cfg.auto
    effective_printer_name = (
        printer_name if printer_name is not None else cfg.printer_name
    )
    effective_host = host if host is not None else cfg.host
    effective_connection = connection if connection is not None else cfg.connection

    # Validate priority
    valid_priorities = ["low", "normal", "high", "urgent"]
    if priority.lower() not in valid_priorities:
        rprint(
            f"[red]Error:[/red] Invalid priority '{priority}'. Must be one of: {', '.join(valid_priorities)}"
        )
        raise typer.Exit(1)

    # Parse due date
    due_date = None
    if due:
        try:
            if " " in due:
                due_date = datetime.strptime(due, "%Y-%m-%d %H:%M")
            else:
                due_date = datetime.strptime(due, "%Y-%m-%d")
        except ValueError:
            rprint(
                "[red]Error:[/red] Invalid due date format. Use YYYY-MM-DD or YYYY-MM-DD HH:MM"
            )
            raise typer.Exit(1)

    # Create task
    task = Task(
        title=title,
        description=description,
        priority=priority.lower(),
        due_date=due_date,
        tags=tags or [],
        task_id=task_id,
    )

    # Preview mode
    if preview:
        with get_printer(PrinterConfig(connection_type="dummy")) as printer:
            ticket_printer = TicketPrinter(printer)
            preview_text = ticket_printer.print_preview(task)
            rprint(Panel(preview_text, title="Ticket Preview", border_style="green"))
        return

    # Resolve printer configuration
    printer_config = _resolve_printer_config(
        auto=effective_auto,
        printer_name=effective_printer_name,
        host=effective_host,
        connection=effective_connection,
        vendor_id=vendor_id,
        product_id=product_id,
    )

    # Print the ticket
    try:
        with get_printer(printer_config) as printer:
            ticket_printer = TicketPrinter(printer)
            if printer_config and printer_config.connection_type != "dummy":
                ticket_printer.print_task(task)
                rprint("[green]Ticket printed successfully![/green]")
            else:
                # Dummy mode - show preview
                preview_text = ticket_printer.print_preview(task)
                rprint(
                    Panel(
                        preview_text, title="Ticket (dummy mode)", border_style="yellow"
                    )
                )
    except Exception as e:
        rprint(f"[red]Error printing ticket:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def detect() -> None:
    """Detect connected USB printers."""
    rprint("[bold]Searching for Epson USB printers...[/bold]")
    printers = detect_usb_printers()

    if not printers:
        rprint("[yellow]No Epson USB printers found.[/yellow]")
        rprint("\nMake sure:")
        rprint("  - The printer is connected and powered on")
        rprint("  - You have permission to access USB devices")
        rprint("  - libusb is installed (brew install libusb on macOS)")
        return

    rprint(f"\n[green]Found {len(printers)} printer(s):[/green]")
    for i, printer in enumerate(printers, 1):
        rprint(
            f"  {i}. Vendor ID: 0x{printer['vendor_id']:04X}, Product ID: 0x{printer['product_id']:04X}"
        )


@app.command()
def discover(
    timeout: Annotated[
        float,
        typer.Option("--timeout", "-t", help="Discovery timeout in seconds"),
    ] = 3.0,
) -> None:
    """Discover network printers via Bonjour/mDNS."""
    from rich.table import Table

    rprint(f"[bold]Discovering network printers ({timeout}s timeout)...[/bold]\n")
    printers = discover_printers(timeout=timeout)

    if not printers:
        rprint("[yellow]No network printers found.[/yellow]")
        rprint("\nMake sure:")
        rprint("  - The printer is connected to the network and powered on")
        rprint("  - The printer supports Bonjour/mDNS (most Epson network printers do)")
        rprint("  - Your computer is on the same network as the printer")
        return

    table = Table(title=f"Found {len(printers)} printer(s)")
    table.add_column("Name", style="cyan")
    table.add_column("Host", style="green")
    table.add_column("Port", style="yellow")
    table.add_column("Service", style="dim")

    for printer in printers:
        service_short = printer.service_type.replace("._tcp.local.", "").replace(
            "_", ""
        )
        table.add_row(
            printer.display_name,
            printer.host,
            str(printer.port),
            service_short,
        )

    console.print(table)

    rprint("\n[dim]Use with print-task:[/dim]")
    if printers:
        example_name = printers[0].display_name
        rprint(f'  kleo print-task "My Task" --printer {example_name}')
        rprint('  kleo print-task "My Task" --auto  [dim]# uses first available[/dim]')


def _resolve_printer_config(
    auto: bool,
    printer_name: str | None,
    host: str | None,
    connection: str,
    vendor_id: str | None = None,
    product_id: str | None = None,
) -> PrinterConfig | None:
    """Resolve printer configuration from options.

    Returns:
        PrinterConfig if a printer is configured, None for dummy mode.

    Raises:
        typer.Exit: If printer discovery fails or required options are missing.
    """
    # Handle auto-discovery
    if auto or printer_name:
        rprint("[dim]Discovering printers via Bonjour...[/dim]")
        if printer_name:
            discovered = find_printer_by_name(printer_name)
            if not discovered:
                rprint(f"[red]Error:[/red] Printer '{printer_name}' not found")
                raise typer.Exit(1)
            host = discovered.host
            rprint(
                f"[green]Found printer:[/green] {discovered.display_name} at {host}:{discovered.port}"
            )
        else:
            printers = discover_printers()
            if not printers:
                rprint("[red]Error:[/red] No network printers found")
                raise typer.Exit(1)
            discovered = printers[0]
            host = discovered.host
            rprint(
                f"[green]Using printer:[/green] {discovered.display_name} at {host}:{discovered.port}"
            )
        connection = "network"

    # Configure printer
    if connection == "dummy":
        return None

    config = PrinterConfig(connection_type=connection)
    if connection == "network":
        if not host:
            rprint(
                "[red]Error:[/red] Network connection requires --host, --auto, or --printer"
            )
            raise typer.Exit(1)
        config.host = host
    elif connection == "usb":
        if vendor_id:
            config.vendor_id = (
                int(vendor_id, 16) if vendor_id.startswith("0x") else int(vendor_id)
            )
        if product_id:
            config.product_id = (
                int(product_id, 16) if product_id.startswith("0x") else int(product_id)
            )

    return config


# --- serve command ---


@app.command()
def serve(
    every: Annotated[
        Optional[str],
        typer.Option(
            "--every",
            "-e",
            help="Schedule interval (e.g., '30 minutes', '2 hours', '1 day at 09:00')",
        ),
    ] = None,
    tag: Annotated[
        Optional[str],
        typer.Option(
            "--tag",
            "-t",
            help="Things tag to filter tasks by",
        ),
    ] = None,
    strategy: Annotated[
        Optional[str],
        typer.Option(
            "--strategy",
            "-s",
            help="Task selection strategy (e.g., 'random')",
        ),
    ] = None,
    things_auth_token: Annotated[
        Optional[str],
        typer.Option(
            "--things-auth-token",
            help="Things URL auth token for task completion QR codes",
        ),
    ] = None,
    dry_run: Annotated[
        Optional[bool],
        typer.Option("--dry-run/--no-dry-run", help="Run without actually printing"),
    ] = None,
    now: Annotated[
        Optional[bool],
        typer.Option("--now/--no-now", help="Print immediately on start"),
    ] = None,
    connection: Annotated[
        Optional[str],
        typer.Option("--connection", "-c", help="Connection type: usb, network, dummy"),
    ] = None,
    host: Annotated[
        Optional[str],
        typer.Option("--host", help="Printer host (for network connection)"),
    ] = None,
    auto: Annotated[
        Optional[bool],
        typer.Option(
            "--auto/--no-auto", "-a", help="Auto-discover network printer via Bonjour"
        ),
    ] = None,
    printer_name: Annotated[
        Optional[str],
        typer.Option(
            "--printer", help="Printer name to find via Bonjour (e.g., 'kleo')"
        ),
    ] = None,
) -> None:
    """Start server mode to periodically print task tickets from Things.

    Fetches tasks from Things app with the specified tag, selects one using
    the configured strategy, and prints a ticket at the specified interval.

    Configuration is loaded from ~/.config/kleo/config.toml, with CLI flags
    taking highest priority. Use `kleo config set` to change defaults.

    Examples:
        kleo serve                                     # uses config file defaults
        kleo serve --every "30 minutes" --tag 5m --auto
        kleo serve --every "2 hours" --strategy random --dry-run
        kleo serve --every "1 day at 09:00" --printer kleo
    """
    from kleo.server import ServerConfig, TicketServer
    from kleo.sources import ThingsSource
    from kleo.strategies import get_strategy

    # Load config file + env defaults
    cfg = load_config()

    # CLI overrides config
    effective_every = every if every is not None else cfg.every
    effective_tag = tag if tag is not None else cfg.tag
    effective_strategy = strategy if strategy is not None else cfg.strategy
    effective_auth_token = (
        things_auth_token if things_auth_token is not None else cfg.things_auth_token
    )
    effective_dry_run = dry_run if dry_run is not None else cfg.dry_run
    effective_now = now if now is not None else cfg.now
    effective_auto = auto if auto is not None else cfg.auto
    effective_printer_name = (
        printer_name if printer_name is not None else cfg.printer_name
    )
    effective_host = host if host is not None else cfg.host
    effective_connection = connection if connection is not None else cfg.connection

    # Resolve printer configuration
    printer_config = _resolve_printer_config(
        auto=effective_auto,
        printer_name=effective_printer_name,
        host=effective_host,
        connection=effective_connection,
    )

    # Warn if no auth token configured
    if not effective_auth_token:
        rprint(
            "[yellow]Warning:[/yellow] No Things auth token configured. "
            "QR codes will not be printed for task completion."
        )
        rprint("[dim]Set via: kleo config set things.auth_token=YOUR_TOKEN[/dim]")
        rprint("[dim]Find token in Things: Settings > General > Things URLs[/dim]\n")

    # Create task source
    source = ThingsSource(tag=effective_tag, auth_token=effective_auth_token)

    # Get selection strategy
    try:
        selection_strategy = get_strategy(effective_strategy)
    except ValueError as e:
        rprint(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Create server config
    try:
        server_config = ServerConfig(
            every=effective_every,
            printer_config=printer_config,
            dry_run=effective_dry_run,
            run_now=effective_now,
        )
    except ValueError as e:
        rprint(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Create and start server
    server = TicketServer(
        source=source,
        strategy=selection_strategy,
        config=server_config,
    )

    try:
        server.start()
    except ValueError as e:
        rprint(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
