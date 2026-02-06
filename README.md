# kleo-receipts

Named for [KLEO](https://fallout.fandom.com/wiki/KL-E-0), the Assaultron shopkeeper in Fallout 4. Every good merchant needs a receipt printer.

CLI tool for printing task tickets to Epson receipt printers. Fetches tasks from [Things](https://culturedcode.com/things/) and prints them as physical tickets with QR codes for "scan to complete".

## Install

```bash
brew install yesawoo/tap/kleo-receipts
```

Or with pip:

```bash
pip install kleo-receipts
```

## Usage

```bash
# Discover network printers
kleo discover

# Print a single task ticket
kleo print-task "Fix the login bug" --auto

# Preview without printing
kleo print-task "Fix the login bug" --preview

# Server mode: periodically fetch and print tasks from Things
kleo serve --auto

# Custom schedule and tag filter
kleo serve --every "1 day at 09:00" --tag focus --auto
```

## Background Service (Homebrew)

Run kleo as a background launchd service that auto-starts on login:

```bash
# Start the service
brew services start kleo-receipts

# Check status
kleo status

# Stop the service
brew services stop kleo-receipts
```

The service runs `kleo serve` with no arguments — all configuration comes from the config file. Use `kleo config set` to customize before starting:

```bash
# Configure schedule (default: daily at 9:00 AM)
kleo config set schedule.every="1 day at 09:00"

# Configure tag filter (default: 5m)
kleo config set schedule.tag=focus

# Set Things auth token for QR codes
kleo config set things.auth_token=YOUR_TOKEN

# Disable auto-discovery if using a specific printer
kleo config set printer.printer_name=kleo
```

## Configuration

Kleo loads configuration from `~/.config/kleo/config.toml`, environment variables, and CLI flags (highest priority).

```bash
# Show current config with sources
kleo config show

# Set a value
kleo config set schedule.every="2 hours"

# Show config file path
kleo config path
```

Config file format (`~/.config/kleo/config.toml`):

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

Priority: CLI flags > config file > environment variables > defaults.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KLEO_EVERY` | "1 day at 09:00" | Schedule interval |
| `KLEO_TAG` | "5m" | Things tag to filter |
| `KLEO_STRATEGY` | "random" | Task selection strategy |
| `KLEO_PRINTER_NAME` | - | Bonjour printer name |
| `KLEO_PRINTER_HOST` | - | Network printer host |
| `KLEO_THINGS_AUTH_TOKEN` | - | Things URL auth token (required for QR codes) |

## License

MIT
