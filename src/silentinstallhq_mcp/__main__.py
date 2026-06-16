"""CLI entry point for the Silent Install HQ MCP server."""

from __future__ import annotations

import argparse
import sys

from silentinstallhq_mcp.config import get_settings
from silentinstallhq_mcp.server import create_mcp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="silentinstallhq-mcp",
        description="MCP server for Silent Install HQ guides and PSADT templates",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default=None,
        help="MCP transport (default: stdio, or SILENTINSTALLHQ_TRANSPORT)",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Bind host for HTTP transports (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Bind port for HTTP transports (default: 8000)",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    settings = get_settings()

    transport = args.transport or settings.transport
    host = args.host or settings.host
    port = args.port or settings.port

    mcp = create_mcp(settings)

    if transport == "stdio":
        mcp.run(transport="stdio")
        return

    if transport == "sse":
        mcp.run(transport="sse", host=host, port=port)
        return

    if transport == "streamable-http":
        mcp.run(transport="streamable-http", host=host, port=port)
        return

    print(f"Unsupported transport: {transport}", file=sys.stderr)
    raise SystemExit(2)


if __name__ == "__main__":
    main()