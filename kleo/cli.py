"""CLI interface for Kleo task ticket printer."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Annotated, Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel

from kleo import __version__
from kleo.discovery import discover_printers, find_printer_by_name
from kleo.printer import PrinterConfig, get_printer, detect_usb_printers
from kleo.ticket import Task, TicketPrinter

# Environment variables for configuration
ENV_PRINTER_NAME = "KLEO_PRINTER_NAME"
ENV_PRINTER_HOST = "KLEO_PRINTER_HOST"
ENV_EVERY = "KLEO_EVERY"
ENV_TAG = "KLEO_TAG"
ENV_STRATEGY = "KLEO_STRATEGY"
ENV_THINGS_AUTH_TOKEN = "KLEO_THINGS_AUTH_TOKEN"

app = typer.Typer(
    name="kleo",
    help="Print task tickets to Epson receipt printers.",
    no_args_is_help=True,
)
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
        str,
        typer.Option("--connection", "-c", help="Connection type: usb, network, dummy"),
    ] = "dummy",
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
        bool,
        typer.Option("--auto", "-a", help="Auto-discover network printer via Bonjour"),
    ] = False,
    printer_name: Annotated[
        Optional[str],
        typer.Option("--printer", help="Printer name to find via Bonjour (e.g., 'kleo')"),
    ] = None,
) -> None:
    """Print a task ticket."""
    # Validate priority
    valid_priorities = ["low", "normal", "high", "urgent"]
    if priority.lower() not in valid_priorities:
        rprint(f"[red]Error:[/red] Invalid priority '{priority}'. Must be one of: {', '.join(valid_priorities)}")
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
            rprint("[red]Error:[/red] Invalid due date format. Use YYYY-MM-DD or YYYY-MM-DD HH:MM")
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
        from kleo.printer import Dummy

        with get_printer(PrinterConfig(connection_type="dummy")) as printer:
            ticket_printer = TicketPrinter(printer)
            preview_text = ticket_printer.print_preview(task)
            rprint(Panel(preview_text, title="Ticket Preview", border_style="green"))
        return

    # Check environment variables for defaults
    env_printer = os.environ.get(ENV_PRINTER_NAME)
    env_host = os.environ.get(ENV_PRINTER_HOST)

    # If no printer specified, check environment variables
    if not auto and not printer_name and not host and connection == "dummy":
        if env_printer:
            printer_name = env_printer
            rprint(f"[dim]Using printer from {ENV_PRINTER}={env_printer}[/dim]")
        elif env_host:
            host = env_host
            connection = "network"
            rprint(f"[dim]Using host from {ENV_PRINTER_HOST}={env_host}[/dim]")

    # Handle auto-discovery
    if auto or printer_name:
        rprint("[dim]Discovering printers via Bonjour...[/dim]")
        if printer_name:
            discovered = find_printer_by_name(printer_name)
            if not discovered:
                rprint(f"[red]Error:[/red] Printer '{printer_name}' not found")
                raise typer.Exit(1)
            host = discovered.host
            rprint(f"[green]Found printer:[/green] {discovered.display_name} at {host}:{discovered.port}")
        else:
            printers = discover_printers()
            if not printers:
                rprint("[red]Error:[/red] No network printers found")
                raise typer.Exit(1)
            discovered = printers[0]
            host = discovered.host
            rprint(f"[green]Using printer:[/green] {discovered.display_name} at {host}:{discovered.port}")
        connection = "network"

    # Configure printer
    config = None
    if connection != "dummy":
        config = PrinterConfig(connection_type=connection)
        if connection == "network":
            if not host:
                rprint("[red]Error:[/red] Network connection requires --host, --auto, or --printer")
                raise typer.Exit(1)
            config.host = host
        elif connection == "usb":
            if vendor_id:
                config.vendor_id = int(vendor_id, 16) if vendor_id.startswith("0x") else int(vendor_id)
            if product_id:
                config.product_id = int(product_id, 16) if product_id.startswith("0x") else int(product_id)

    # Print the ticket
    try:
        with get_printer(config) as printer:
            ticket_printer = TicketPrinter(printer)
            if connection == "dummy":
                # For dummy printer, show preview
                preview_text = ticket_printer.print_preview(task)
                rprint(Panel(preview_text, title="Ticket (dummy mode)", border_style="yellow"))
            else:
                ticket_printer.print_task(task)
                rprint("[green]Ticket printed successfully![/green]")
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
        rprint(f"  {i}. Vendor ID: 0x{printer['vendor_id']:04X}, Product ID: 0x{printer['product_id']:04X}")


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
        service_short = printer.service_type.replace("._tcp.local.", "").replace("_", "")
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
        rprint(f"  kleo print-task \"My Task\" --printer {example_name}")
        rprint("  kleo print-task \"My Task\" --auto  [dim]# uses first available[/dim]")


def _resolve_printer_config(
    auto: bool,
    printer_name: str | None,
    host: str | None,
    connection: str,
    vendor_id: str | None = None,
    product_id: str | None = None,
) -> PrinterConfig | None:
    """Resolve printer configuration from CLI options and environment.

    Args:
        auto: Whether to auto-discover via Bonjour.
        printer_name: Specific printer name to find via Bonjour.
        host: Network printer host.
        connection: Connection type (usb, network, dummy).
        vendor_id: USB vendor ID (hex string).
        product_id: USB product ID (hex string).

    Returns:
        PrinterConfig if a printer is configured, None for dummy mode.

    Raises:
        typer.Exit: If printer discovery fails or required options are missing.
    """
    # Check environment variables for defaults
    env_printer = os.environ.get(ENV_PRINTER_NAME)
    env_host = os.environ.get(ENV_PRINTER_HOST)

    # If no printer specified, check environment variables
    if not auto and not printer_name and not host and connection == "dummy":
        if env_printer:
            printer_name = env_printer
            rprint(f"[dim]Using printer from {ENV_PRINTER_NAME}={env_printer}[/dim]")
        elif env_host:
            host = env_host
            connection = "network"
            rprint(f"[dim]Using host from {ENV_PRINTER_HOST}={env_host}[/dim]")

    # Handle auto-discovery
    if auto or printer_name:
        rprint("[dim]Discovering printers via Bonjour...[/dim]")
        if printer_name:
            discovered = find_printer_by_name(printer_name)
            if not discovered:
                rprint(f"[red]Error:[/red] Printer '{printer_name}' not found")
                raise typer.Exit(1)
            host = discovered.host
            rprint(f"[green]Found printer:[/green] {discovered.display_name} at {host}:{discovered.port}")
        else:
            printers = discover_printers()
            if not printers:
                rprint("[red]Error:[/red] No network printers found")
                raise typer.Exit(1)
            discovered = printers[0]
            host = discovered.host
            rprint(f"[green]Using printer:[/green] {discovered.display_name} at {host}:{discovered.port}")
        connection = "network"

    # Configure printer
    if connection == "dummy":
        return None

    config = PrinterConfig(connection_type=connection)
    if connection == "network":
        if not host:
            rprint("[red]Error:[/red] Network connection requires --host, --auto, or --printer")
            raise typer.Exit(1)
        config.host = host
    elif connection == "usb":
        if vendor_id:
            config.vendor_id = int(vendor_id, 16) if vendor_id.startswith("0x") else int(vendor_id)
        if product_id:
            config.product_id = int(product_id, 16) if product_id.startswith("0x") else int(product_id)

    return config


@app.command()
def serve(
    every: Annotated[
        str,
        typer.Option(
            "--every", "-e",
            help="Schedule interval (e.g., '30 minutes', '2 hours', '1 day at 09:00')",
            envvar=ENV_EVERY,
        ),
    ] = "30 minutes",
    tag: Annotated[
        str,
        typer.Option(
            "--tag", "-t",
            help="Things tag to filter tasks by",
            envvar=ENV_TAG,
        ),
    ] = "5m",
    strategy: Annotated[
        str,
        typer.Option(
            "--strategy", "-s",
            help="Task selection strategy (e.g., 'random')",
            envvar=ENV_STRATEGY,
        ),
    ] = "random",
    things_auth_token: Annotated[
        Optional[str],
        typer.Option(
            "--things-auth-token",
            help="Things URL auth token for task completion QR codes",
            envvar=ENV_THINGS_AUTH_TOKEN,
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Run without actually printing"),
    ] = False,
    now: Annotated[
        bool,
        typer.Option("--now/--no-now", help="Print immediately on start"),
    ] = True,
    connection: Annotated[
        str,
        typer.Option("--connection", "-c", help="Connection type: usb, network, dummy"),
    ] = "dummy",
    host: Annotated[
        Optional[str],
        typer.Option("--host", help="Printer host (for network connection)"),
    ] = None,
    auto: Annotated[
        bool,
        typer.Option("--auto", "-a", help="Auto-discover network printer via Bonjour"),
    ] = False,
    printer_name: Annotated[
        Optional[str],
        typer.Option("--printer", help="Printer name to find via Bonjour (e.g., 'kleo')"),
    ] = None,
) -> None:
    """Start server mode to periodically print task tickets from Things.

    Fetches tasks from Things app with the specified tag, selects one using
    the configured strategy, and prints a ticket at the specified interval.

    Examples:
        kleo serve --every "30 minutes" --tag 5m --auto
        kleo serve --every "2 hours" --strategy random --dry-run
        kleo serve --every "1 day at 09:00" --printer kleo
    """
    from kleo.server import ServerConfig, TicketServer
    from kleo.sources import ThingsSource
    from kleo.strategies import get_strategy

    # Resolve printer configuration
    printer_config = _resolve_printer_config(
        auto=auto,
        printer_name=printer_name,
        host=host,
        connection=connection,
    )

    # Warn if no auth token configured
    if not things_auth_token:
        rprint("[yellow]Warning:[/yellow] No Things auth token configured. "
               "QR codes will not be printed for task completion.")
        rprint("[dim]Set KLEO_THINGS_AUTH_TOKEN or use --things-auth-token[/dim]")
        rprint("[dim]Find token in Things: Settings → General → Things URLs[/dim]\n")

    # Create task source
    source = ThingsSource(tag=tag, auth_token=things_auth_token)

    # Get selection strategy
    try:
        selection_strategy = get_strategy(strategy)
    except ValueError as e:
        rprint(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Create server config
    try:
        server_config = ServerConfig(
            every=every,
            printer_config=printer_config,
            dry_run=dry_run,
            run_now=now,
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
