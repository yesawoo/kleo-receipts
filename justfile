# Kleo - Epson receipt printer task ticket system

# Default recipe
default:
    @just --list

# Install dependencies
install:
    uv sync

# Run the CLI
run *ARGS:
    uv run kleo {{ARGS}}

# Discover network printers via Bonjour
discover:
    uv run kleo discover

# Print a test task ticket (dummy mode)
test-print:
    uv run kleo print-task "Test Task" --description "This is a test task ticket" --priority normal --tag test --id TEST-001

# Print a test task ticket using auto-discovery
test-print-auto:
    uv run kleo print-task "Test Task" --description "This is a test task ticket" --priority normal --tag test --id TEST-001 --auto

# Print a test task ticket to specific printer by name
test-print-printer NAME:
    uv run kleo print-task "Test Task" --description "This is a test task ticket" --priority normal --tag test --id TEST-001 --printer "{{NAME}}"

# Print a test task ticket to network printer by host
test-print-host HOST:
    uv run kleo print-task "Test Task" --description "This is a test task ticket" --priority normal --tag test --id TEST-001 --connection network --host {{HOST}}

# Detect USB printers
detect:
    uv run kleo detect

# Run linting
lint:
    uv run ruff check kleo/
    uv run ruff format --check kleo/

# Format code
fmt:
    uv run ruff format kleo/
    uv run ruff check --fix kleo/

# Run type checking
typecheck:
    uv run mypy kleo/

# Build sdist and wheel
build:
    uv build

# Build and publish to PyPI
publish:
    uv build
    uv publish

# Show Homebrew formula URL and sha256 for a given version
bump-formula VERSION:
    #!/usr/bin/env bash
    set -euo pipefail
    URL="https://files.pythonhosted.org/packages/source/k/kleo-receipts/kleo_receipts-{{VERSION}}.tar.gz"
    echo "Fetching sha256 from PyPI..."
    SHA=$(curl -sL "$URL" | shasum -a 256 | cut -d' ' -f1)
    echo "url \"$URL\""
    echo "sha256 \"$SHA\""

# Clean build artifacts
clean:
    rm -rf dist/ build/ *.egg-info .ruff_cache .mypy_cache __pycache__
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
