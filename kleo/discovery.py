"""Network printer discovery via Bonjour/mDNS."""

from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import TYPE_CHECKING

from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

if TYPE_CHECKING:
    from zeroconf import ServiceInfo


# Service types for network printers
PRINTER_SERVICE_TYPES = [
    "_pdl-datastream._tcp.local.",  # Raw printing (port 9100) - most common for Epson
    "_ipp._tcp.local.",  # IPP printing
    "_printer._tcp.local.",  # Generic printer service
]


@dataclass
class DiscoveredPrinter:
    """A printer discovered via mDNS/Bonjour."""

    name: str
    host: str
    port: int
    service_type: str
    addresses: list[str]
    properties: dict[str, str]

    @property
    def display_name(self) -> str:
        """Get a clean display name for the printer."""
        # Remove the service suffix from the name
        return self.name.split(".")[0] if "." in self.name else self.name


class PrinterListener(ServiceListener):
    """Listener for mDNS printer service announcements."""

    def __init__(self) -> None:
        self.printers: dict[str, DiscoveredPrinter] = {}

    def add_service(self, zc: Zeroconf, service_type: str, name: str) -> None:
        info = zc.get_service_info(service_type, name)
        if info:
            self._add_printer(info, service_type)

    def update_service(self, zc: Zeroconf, service_type: str, name: str) -> None:
        info = zc.get_service_info(service_type, name)
        if info:
            self._add_printer(info, service_type)

    def remove_service(self, zc: Zeroconf, service_type: str, name: str) -> None:
        if name in self.printers:
            del self.printers[name]

    def _add_printer(self, info: ServiceInfo, service_type: str) -> None:
        addresses = [socket.inet_ntoa(addr) for addr in info.addresses]
        properties = {}
        if info.properties:
            for key, value in info.properties.items():
                if isinstance(key, bytes):
                    key = key.decode("utf-8", errors="replace")
                if isinstance(value, bytes):
                    value = value.decode("utf-8", errors="replace")
                properties[key] = value

        printer = DiscoveredPrinter(
            name=info.name,
            host=info.server or (addresses[0] if addresses else "unknown"),
            port=info.port,
            service_type=service_type,
            addresses=addresses,
            properties=properties,
        )
        self.printers[info.name] = printer


def discover_printers(timeout: float = 3.0) -> list[DiscoveredPrinter]:
    """Discover network printers via Bonjour/mDNS.

    Args:
        timeout: How long to wait for printer announcements (seconds).

    Returns:
        List of discovered printers.
    """
    import time

    zeroconf = Zeroconf()
    listener = PrinterListener()

    browsers = []
    for service_type in PRINTER_SERVICE_TYPES:
        browser = ServiceBrowser(zeroconf, service_type, listener)
        browsers.append(browser)

    try:
        time.sleep(timeout)
    finally:
        zeroconf.close()

    return list(listener.printers.values())


def find_printer_by_name(name: str, timeout: float = 3.0) -> DiscoveredPrinter | None:
    """Find a specific printer by name.

    Args:
        name: The printer name to search for (e.g., "kleo" or "kleo.local").
        timeout: How long to wait for printer announcements.

    Returns:
        The discovered printer, or None if not found.
    """
    # Normalize the name
    search_name = name.lower().replace(".local", "")

    printers = discover_printers(timeout)
    for printer in printers:
        printer_name = printer.display_name.lower()
        if printer_name == search_name or printer_name.startswith(search_name):
            return printer

    return None
