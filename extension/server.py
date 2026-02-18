"""Claude Desktop Extension entry point for Kleo MCP server."""

import os

from kleo.mcp_server import mcp

# Pass through user_config from Claude Desktop to kleo config via env vars
if things_token := os.environ.get("USER_CONFIG_THINGS_AUTH_TOKEN"):
    os.environ.setdefault("KLEO_THINGS_AUTH_TOKEN", things_token)

if __name__ == "__main__":
    mcp.run()
