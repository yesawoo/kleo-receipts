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

## Server Mode

Server mode periodically fetches tasks from Things app and prints tickets:

```bash
# Basic usage - print every 30 minutes
uv run kleo serve --auto

# Custom schedule
uv run kleo serve --every "2 hours" --auto
uv run kleo serve --every "1 day at 09:00" --printer kleo

# Filter by tag (default: "5m")
uv run kleo serve --tag focus --auto

# Dry run to test without printing
uv run kleo serve --dry-run

# Skip immediate print on start
uv run kleo serve --no-now --auto
```

### Schedule Patterns

The `--every` flag supports natural language patterns:
- `"30 seconds"`, `"5 minutes"`, `"2 hours"` - interval-based
- `"1 day"`, `"1 week"` - daily/weekly
- `"1 day at 09:00"` - daily at specific time
- `"monday"`, `"monday at 10:30"` - weekday scheduling

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KLEO_EVERY` | "30 minutes" | Schedule interval |
| `KLEO_TAG` | "5m" | Things tag to filter |
| `KLEO_STRATEGY` | "random" | Task selection strategy |
| `KLEO_PRINTER_NAME` | - | Bonjour printer name |
| `KLEO_PRINTER_HOST` | - | Network printer host |

### Architecture

Server mode uses a strategy pattern for task selection:
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
