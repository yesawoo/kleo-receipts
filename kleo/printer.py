"""Printer interface for Epson receipt printers."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from escpos.printer import Usb, Network, Dummy

if TYPE_CHECKING:
    from collections.abc import Iterator
    from escpos.escpos import Escpos


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
