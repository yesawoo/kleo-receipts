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
