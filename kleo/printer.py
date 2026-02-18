"""Printer interface for Epson receipt printers."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING

from escpos.printer import Usb, Network, Dummy

from kleo.discovery import (
    discover_printers as discover_network_printers,
    filter_receipt_printers,
    find_printer_by_name,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from escpos.escpos import Escpos

logger = logging.getLogger(__name__)


class PrinterConfig:
    """Configuration for printer connection."""

    def __init__(
        self,
        *,
        connection_type: str = "usb",
        vendor_id: int = 0x04B8,  # Epson default
        product_id: int = 0x0202,  # Common TM series
        host: str | None = None,
        port: int = 9100,
    ) -> None:
        self.connection_type = connection_type
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.host = host
        self.port = port


@contextmanager
def get_printer(config: PrinterConfig | None = None) -> Iterator[Escpos]:
    """Get a printer connection based on configuration.

    Args:
        config: Printer configuration. If None, uses a dummy printer for testing.

    Yields:
        An Escpos printer instance.
    """
    if config is None:
        yield Dummy()
        return

    printer: Escpos
    match config.connection_type:
        case "usb":
            printer = Usb(config.vendor_id, config.product_id)
        case "network":
            if config.host is None:
                raise ValueError("Network connection requires host")
            printer = Network(config.host, config.port)
        case "dummy":
            printer = Dummy()
        case _:
            raise ValueError(f"Unknown connection type: {config.connection_type}")

    try:
        yield printer
    finally:
        if hasattr(printer, "close"):
            printer.close()


def resolve_printer_config(
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
        ValueError: If printer discovery fails or required options are missing.
    """
    # Handle auto-discovery
    if auto or printer_name:
        logger.info("Discovering printers via Bonjour...")
        if printer_name:
            discovered = find_printer_by_name(printer_name)
            if not discovered:
                raise ValueError(f"Printer '{printer_name}' not found")
            host = discovered.host
            logger.info(
                "Found printer: %s at %s:%s",
                discovered.display_name,
                host,
                discovered.port,
            )
        else:
            printers = discover_network_printers()
            if not printers:
                raise ValueError("No network printers found")
            receipt_printers = filter_receipt_printers(printers)
            if not receipt_printers:
                names = ", ".join(p.display_name for p in printers)
                raise ValueError(
                    f"No receipt printers found. Discovered printers: {names}"
                )
            discovered = receipt_printers[0]
            host = discovered.host
            logger.info(
                "Using printer: %s at %s:%s",
                discovered.display_name,
                host,
                discovered.port,
            )
        connection = "network"

    # Configure printer
    if connection == "dummy":
        return None

    config = PrinterConfig(connection_type=connection)
    if connection == "network":
        if not host:
            raise ValueError("Network connection requires --host, --auto, or --printer")
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


def detect_usb_printers() -> list[dict[str, int]]:
    """Detect connected USB printers.

    Returns:
        List of dicts with vendor_id and product_id for each detected printer.
    """
    try:
        import usb.core

        printers = []
        # Look for Epson printers (vendor ID 0x04B8)
        devices = usb.core.find(find_all=True, idVendor=0x04B8)
        for device in devices:
            printers.append(
                {
                    "vendor_id": device.idVendor,
                    "product_id": device.idProduct,
                }
            )
        return printers
    except ImportError:
        return []
