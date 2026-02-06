# kleo-receipts

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

## License

MIT
