"""Configuration loading, merging, writing, and server state management."""

from __future__ import annotations

import json
import os
import sys
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "kleo"
CONFIG_FILE = CONFIG_DIR / "config.toml"
STATE_FILE = CONFIG_DIR / "state.json"

# Environment variable names
ENV_EVERY = "KLEO_EVERY"
ENV_TAG = "KLEO_TAG"
ENV_STRATEGY = "KLEO_STRATEGY"
ENV_PRINTER_NAME = "KLEO_PRINTER_NAME"
ENV_PRINTER_HOST = "KLEO_PRINTER_HOST"
ENV_THINGS_AUTH_TOKEN = "KLEO_THINGS_AUTH_TOKEN"

# Valid config keys: section.field -> (env_var, type)
VALID_KEYS: dict[str, tuple[str | None, type]] = {
    "schedule.every": (ENV_EVERY, str),
    "schedule.tag": (ENV_TAG, str),
    "schedule.strategy": (ENV_STRATEGY, str),
    "printer.auto": (None, bool),
    "printer.printer_name": (ENV_PRINTER_NAME, str),
    "printer.host": (ENV_PRINTER_HOST, str),
    "printer.connection": (None, str),
    "things.auth_token": (ENV_THINGS_AUTH_TOKEN, str),
    "service.dry_run": (None, bool),
    "service.now": (None, bool),
}


@dataclass
class KleoConfig:
    """Resolved configuration for kleo."""

    every: str = "1 day at 09:00"
    tag: str = "5m"
    strategy: str = "random"
    auto: bool = True
    printer_name: str | None = None
    host: str | None = None
    connection: str = "dummy"
    things_auth_token: str | None = None
    dry_run: bool = False
    now: bool = True


def load_config() -> KleoConfig:
    """Load config from file + env vars + defaults.

    Priority: file values > env vars > KleoConfig defaults.
    Returns defaults if file is missing. Warns on parse errors.
    """
    file_data: dict[str, dict[str, object]] = {}
    if CONFIG_FILE.exists():
        try:
            file_data = tomllib.loads(CONFIG_FILE.read_text())
        except tomllib.TOMLDecodeError as e:
            print(f"Warning: Could not parse {CONFIG_FILE}: {e}", file=sys.stderr)

    return _merge_config(file_data)


def _merge_config(file_data: dict[str, dict[str, object]]) -> KleoConfig:
    """Merge file data + env vars into a KleoConfig.

    Flattens nested TOML sections and applies priority:
    file > env > defaults.
    """
    config = KleoConfig()

    # Map from section.field -> config attribute name
    field_map: dict[str, str] = {
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

    for key, attr in field_map.items():
        section, field_name = key.split(".")
        env_var, field_type = VALID_KEYS[key]

        # Check file first (highest priority)
        section_data = file_data.get(section, {})
        if field_name in section_data:
            value = section_data[field_name]
            setattr(config, attr, value)
            continue

        # Check env var (middle priority)
        if env_var:
            env_value = os.environ.get(env_var)
            if env_value is not None:
                if field_type is bool:
                    setattr(config, attr, _parse_bool(env_value))
                else:
                    setattr(config, attr, env_value)
                continue

        # Otherwise, keep the dataclass default

    return config


def config_source(key: str) -> str:
    """Return the source of a config value: 'file', 'env', or 'default'."""
    section, field_name = key.split(".")
    env_var, _ = VALID_KEYS[key]

    # Check file
    if CONFIG_FILE.exists():
        try:
            file_data = tomllib.loads(CONFIG_FILE.read_text())
            section_data = file_data.get(section, {})
            if field_name in section_data:
                return "file"
        except tomllib.TOMLDecodeError:
            pass

    # Check env
    if env_var and os.environ.get(env_var) is not None:
        return "env"

    return "default"


def set_config_value(key: str, value: str) -> None:
    """Set a config value in the TOML file.

    Args:
        key: Dotted key like 'schedule.every' or 'printer.auto'.
        value: String value to set (bools coerced from 'true'/'false').

    Raises:
        ValueError: If the key is not a valid config key.
    """
    if key not in VALID_KEYS:
        available = ", ".join(sorted(VALID_KEYS.keys()))
        raise ValueError(f"Unknown config key '{key}'. Valid keys: {available}")

    _, field_type = VALID_KEYS[key]
    section, field_name = key.split(".")

    # Load existing data
    data: dict[str, dict[str, object]] = {}
    if CONFIG_FILE.exists():
        try:
            data = tomllib.loads(CONFIG_FILE.read_text())
        except tomllib.TOMLDecodeError:
            pass

    # Ensure section exists
    if section not in data:
        data[section] = {}

    # Coerce value
    if field_type is bool:
        data[section][field_name] = _parse_bool(value)
    else:
        data[section][field_name] = value

    _write_config_toml(data, CONFIG_FILE)


def _parse_bool(value: str) -> bool:
    """Parse a string as a boolean."""
    return value.lower() in ("true", "1", "yes", "on")


def _write_config_toml(data: dict[str, dict[str, object]], path: Path) -> None:
    """Write a simple TOML file (handles str, bool, int only)."""
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    for section, fields in data.items():
        if not isinstance(fields, dict):
            continue
        lines.append(f"[{section}]")
        for key, val in fields.items():
            if isinstance(val, bool):
                lines.append(f"{key} = {str(val).lower()}")
            elif isinstance(val, int):
                lines.append(f"{key} = {val}")
            elif isinstance(val, str):
                lines.append(f'{key} = "{val}"')
        lines.append("")

    path.write_text("\n".join(lines))


# --- Server State ---


@dataclass
class ServerState:
    """State written by the server, read by `kleo status`."""

    pid: int | None = None
    started_at: str | None = None
    last_tick_at: str | None = None
    last_tick_status: str | None = None  # "ok", "no_tasks", "error"
    last_error: str | None = None
    last_task_title: str | None = None
    tick_count: int = 0
    next_run_at: str | None = None

    def save(self) -> None:
        """Write state to STATE_FILE as JSON."""
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls) -> ServerState:
        """Load state from STATE_FILE. Returns default if missing/corrupt."""
        if not STATE_FILE.exists():
            return cls()
        try:
            data = json.loads(STATE_FILE.read_text())
            return cls(
                **{k: v for k, v in data.items() if k in cls.__dataclass_fields__}
            )
        except (json.JSONDecodeError, TypeError):
            return cls()

    def clear(self) -> None:
        """Remove the state file."""
        if STATE_FILE.exists():
            STATE_FILE.unlink()
