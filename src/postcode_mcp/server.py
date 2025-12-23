from __future__ import annotations

import logging

from fastmcp import FastMCP

from postcode_mcp.app.container import build_container
from postcode_mcp.app.logger import configure_logging
from postcode_mcp.tools.postcode_tools import register_postcode_tools

configure_logging()
log = logging.getLogger(__name__)

mcp = FastMCP("postcode-mcp")

try:
    _container = build_container()
    register_postcode_tools(mcp, _container)
    log.info("Postcode tools registered successfully")
except Exception as e:
    log.error("Failed to register postcode tools: %s", e, exc_info=True)
    raise


if __name__ == "__main__":
    # default: STDIO (FastMCP 문서상 run() 기본)
    mcp.run(
        transport="http",
        host="127.0.0.1",
        port=3334,
        path="/mcp",
    )