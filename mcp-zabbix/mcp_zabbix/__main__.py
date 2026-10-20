"""`python -m mcp_zabbix` — streamable HTTP :8200/mcp"""

import os

import uvicorn

from mcp_zabbix.server import build_app


def main() -> None:
    host = os.environ.get("MCP_ZABBIX_HOST", "127.0.0.1")  # compose 에서는 0.0.0.0
    port = int(os.environ.get("MCP_ZABBIX_PORT", "8200"))
    uvicorn.run(build_app(), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
