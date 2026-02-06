# CLAUDE.md - kleo-receipts

CLI tool for printing task tickets to Epson receipt printers.

## Development

```bash
uv sync                                    # Install dependencies
uv run kleo --help                         # Show CLI help
uv run kleo print-task "Task" --preview    # Preview without printing
uv run kleo print-task "Task" --auto       # Print via Bonjour discovery
uv run kleo discover                       # Find network printers
```

## Configuration System

Config is loaded from `~/.config/kleo/config.toml` > env vars > defaults.

```bash
uv run kleo config show                    # Show all config with sources
uv run kleo config set schedule.every="2 hours"  # Set a value
uv run kleo config path                    # Show config file path
```

**Config file** (`~/.config/kleo/config.toml`):
```toml
[schedule]
every = "1 day at 09:00"
tag = "5m"
strategy = "random"

[printer]
auto = true
# printer_name = "kleo"
# host = "192.168.1.100"

[things]
# auth_token = "your-token-here"
```

**Valid config keys:** `schedule.every`, `schedule.tag`, `schedule.strategy`, `printer.auto`, `printer.printer_name`, `printer.host`, `printer.connection`, `things.auth_token`, `service.dry_run`, `service.now`

**Key module:** `kleo/config.py` — `KleoConfig` dataclass, `load_config()`, `set_config_value()`, `ServerState`

## Server Mode

Server mode periodically fetches tasks from Things app and prints tickets:

```bash
# Uses config file defaults (daily at 9:00 AM, auto-discover, tag 5m)
uv run kleo serve

# CLI flags override config
uv run kleo serve --every "2 hours" --auto
uv run kleo serve --every "1 day at 09:00" --printer kleo

# Dry run to test without printing
uv run kleo serve --dry-run

# Check server status
uv run kleo status
```

### Homebrew Service

```bash
brew services start kleo-receipts          # Start as background service
brew services stop kleo-receipts           # Stop
kleo status                                # Check status, PID, last tick
```

The Homebrew formula runs `kleo serve` with no args. All config comes from the config file. Server writes state to `~/.config/kleo/state.json` (PID, tick count, last task, next run).

### Schedule Patterns

The `--every` flag supports natural language patterns:
- `"30 seconds"`, `"5 minutes"`, `"2 hours"` - interval-based
- `"1 day"`, `"1 week"` - daily/weekly
- `"1 day at 09:00"` - daily at specific time
- `"monday"`, `"monday at 10:30"` - weekday scheduling

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KLEO_EVERY` | "1 day at 09:00" | Schedule interval |
| `KLEO_TAG` | "5m" | Things tag to filter |
| `KLEO_STRATEGY` | "random" | Task selection strategy |
| `KLEO_PRINTER_NAME` | - | Bonjour printer name |
| `KLEO_PRINTER_HOST` | - | Network printer host |
| `KLEO_THINGS_AUTH_TOKEN` | - | Things URL auth token (required for QR codes) |

### Things Auth Token

To enable "scan to complete" QR codes on tickets, you need a Things URL auth token:

1. Open Things app
2. Go to Settings > General > Things URLs (Mac) or Settings > General > Things URLs (iOS)
3. Enable "Things URLs" if not already enabled
4. Click "Manage" to reveal your auth token
5. Set: `kleo config set things.auth_token=YOUR_TOKEN`

### Architecture

Server mode uses a strategy pattern for task selection:
- `kleo/config.py` - Config loading, merging, writing, server state
- `kleo/sources/` - Task sources (Things app integration)
- `kleo/strategies/` - Selection strategies (random, etc.)
- `kleo/server.py` - Server loop using `schedule` library

## python-escpos Gotchas

### Use `set_with_default()` to reset text formatting

In python-escpos v3+, `p.set()` only modifies parameters you explicitly pass - it does NOT reset others to defaults. This causes issues when switching from double-height/double-width text back to normal.

**Wrong** - double_height persists to subsequent text:
```python
p.set(double_height=True, double_width=True)
p.text("BIG TEXT")
p.set(double_height=False)  # Other settings like double_width may persist!
p.text("normal text")       # May still be double-width
```

**Correct** - use `set_with_default()` to reset all formatting:
```python
p.set(double_height=True, double_width=True)
p.text("BIG TEXT")
p.set_with_default()        # Resets ALL text formatting to defaults
p.text("normal text")       # Guaranteed normal size
```

### Newlines inherit text size

A `\n` printed while `double_height=True` takes up 2 lines of vertical space. Print newlines after resetting to normal size:

```python
p.set(double_height=True)
p.text("HEADER")            # No trailing \n
p.set_with_default()
p.text("\n")                # Newline at normal height
```
