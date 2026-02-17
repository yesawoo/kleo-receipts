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
        properties: dict[str, str] = {}
        if info.properties:
            for raw_key, raw_value in info.properties.items():
                str_key = (
                    raw_key.decode("utf-8", errors="replace")
                    if isinstance(raw_key, bytes)
                    else str(raw_key)
                )
                str_value = (
                    raw_value.decode("utf-8", errors="replace")
                    if isinstance(raw_value, bytes)
                    else str(raw_value)
                    if raw_value is not None
                    else ""
                )
                properties[str_key] = str_value

        printer = DiscoveredPrinter(
            name=info.name,
            host=info.server or (addresses[0] if addresses else "unknown"),
            port=info.port or 0,
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


def _receipt_score(printer: DiscoveredPrinter) -> int:
    """Score a printer on how likely it is to be a receipt/POS printer.

    Positive score = likely receipt printer, negative = likely not.
    """
    name_lower = printer.display_name.lower()
    props_lower = " ".join(printer.properties.values()).lower()
    combined = f"{name_lower} {props_lower}"

    score = 0

    # Positive signals: receipt/POS/thermal printer indicators
    positive_keywords = [
        "receipt",
        "pos",
        "thermal",
        "epson",
        "tm-t",
        "tm-m",
        "kleo",
        "star ",
        "star-",
        "bixolon",
        "escpos",
        "esc/pos",
    ]
    for kw in positive_keywords:
        if kw in combined:
            score += 10

    # Negative signals: known non-receipt printer brands
    negative_keywords = [
        "brother",
        "hp ",
        "hp-",
        "hewlett",
        "canon",
        "xerox",
        "lexmark",
        "samsung",
        "ricoh",
        "kyocera",
        "dell",
        "konica",
        "laserjet",
        "inkjet",
        "officejet",
        "deskjet",
        "pixma",
    ]
    for kw in negative_keywords:
        if kw in combined:
            score -= 20

    return score


def filter_receipt_printers(
    printers: list[DiscoveredPrinter],
) -> list[DiscoveredPrinter]:
    """Filter and sort printers to prefer receipt/POS printers.

    Returns printers that aren't excluded by negative signals (score >= 0),
    sorted by score descending (best match first).
    """
    scored = [(p, _receipt_score(p)) for p in printers]
    receipt = [(p, s) for p, s in scored if s >= 0]
    receipt.sort(key=lambda x: x[1], reverse=True)
    return [p for p, _ in receipt]


def is_receipt_printer(printer: DiscoveredPrinter) -> bool:
    """Check whether a printer looks like a receipt printer."""
    return _receipt_score(printer) >= 0


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
