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

# Tag a release and push (triggers CI to publish to PyPI + create GitHub release)
release VERSION:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Tagging v{{VERSION}} and pushing..."
    git tag -a "v{{VERSION}}" -m "Release v{{VERSION}}"
    git push origin "v{{VERSION}}"
    echo "Pushed v{{VERSION}} — CI will publish to PyPI and create a GitHub release."

# Show PyPI URL and sha256 for updating the Homebrew formula
bump-formula VERSION:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Fetching sha256 for kleo-receipts {{VERSION}} from PyPI..."
    JSON=$(curl -sL "https://pypi.org/pypi/kleo-receipts/{{VERSION}}/json")
    URL=$(echo "$JSON" | python3 -c "import json,sys; [print(u['url']) for u in json.load(sys.stdin)['urls'] if u['packagetype']=='sdist']")
    SHA=$(echo "$JSON" | python3 -c "import json,sys; [print(u['digests']['sha256']) for u in json.load(sys.stdin)['urls'] if u['packagetype']=='sdist']")
    echo ""
    echo "Update Formula/kleo-receipts.rb in yesawoo/homebrew-tap:"
    echo "  url \"$URL\""
    echo "  sha256 \"$SHA\""

# Verify the sdist contains only expected files
verify-build:
    #!/usr/bin/env bash
    set -euo pipefail
    uv build
    echo "Contents of sdist:"
    tar tzf dist/kleo_receipts-*.tar.gz

# Clean build artifacts
clean:
    rm -rf dist/ build/ *.egg-info .ruff_cache .mypy_cache __pycache__
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
