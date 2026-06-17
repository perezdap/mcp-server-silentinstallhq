# mcp-server-silentinstallhq

Production-ready [Model Context Protocol](https://modelcontextprotocol.io/) server that queries [Silent Install HQ](https://silentinstallhq.com/) for silent install guides, PSADT v4 templates, command-line switches, uninstall strings, and detection script links.

Privacy-first and local-first: responses are scraped on demand, cached locally in SQLite (24h TTL by default), and rate-limited to be polite to the upstream site.

## Quickstart

```powershell
git clone https://github.com/perezdap/mcp-server-silentinstallhq.git
cd mcp-server-silentinstallhq
uv sync --extra dev
Copy-Item .env.example .env
uv run silentinstallhq-mcp --transport stdio
```

**Cursor** — add to `.cursor/mcp.json` in the cloned repo (or user MCP settings):

```json
{
  "mcpServers": {
    "silentinstallhq": {
      "command": "uv",
      "args": [
        "--directory",
        "${workspaceFolder}",
        "run",
        "silentinstallhq-mcp",
        "--transport",
        "stdio"
      ]
    }
  }
}
```

`${workspaceFolder}` resolves to the open project root in Cursor. For a global install, replace it with the directory where you cloned this repository.

**Docker (HTTP transport for MCPJungle / reverse proxy):**

```powershell
docker compose up -d --build
```

Server listens on `http://127.0.0.1:8010` by default.

## Features

- **FastMCP** server using the official [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- **Tools**
  - `search_guides(query, limit=10)` — search by software name or keyword
  - `get_guide(slug)` — full structured guide (switches, PSADT script, detection links, sections)
  - `list_recent_guides(limit=10)` — latest homepage guides
  - `extract_switches(software_name)` — quick silent install/uninstall switch lookup
  - `generate_psadt_wrapper(software_name, slug=None)` — PSADT v4 `Invoke-AppDeployToolkit.ps1` from SIHQ or generated from switches
- **SQLite cache** with configurable TTL (default 24 hours) for raw HTML and parsed guide/PSADT payloads
- **Rate limiting** (`asyncio.sleep` pacing) plus **httpx connection limits**
- **robots.txt** enforcement before outbound requests
- Identifiable **User-Agent**
- **Transports**: `stdio` (default), `sse`, `streamable-http`
- **Docker** + `docker-compose` for self-hosted stacks (nginx, Cloudflare Zero Trust, Authentik)

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended)

## Installation

```powershell
git clone https://github.com/perezdap/mcp-server-silentinstallhq.git
cd mcp-server-silentinstallhq
uv sync --extra dev
```

Copy environment defaults if needed:

```powershell
Copy-Item .env.example .env
```

## Run locally

### stdio (Cursor, Claude Desktop, local agents)

```powershell
uv run silentinstallhq-mcp --transport stdio
```

### Streamable HTTP (MCPJungle / remote clients)

```powershell
uv run silentinstallhq-mcp --transport streamable-http --host 127.0.0.1 --port 8000
```

### SSE (legacy HTTP clients)

```powershell
uv run silentinstallhq-mcp --transport sse --host 127.0.0.1 --port 8000
```

## Claude Desktop configuration

Edit `%APPDATA%\Claude\claude_desktop_config.json` (Windows) or `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS). Replace `<path-to-clone>` with the directory where you cloned this repo.

```json
{
  "mcpServers": {
    "silentinstallhq": {
      "command": "uv",
      "args": [
        "--directory",
        "<path-to-clone>",
        "run",
        "silentinstallhq-mcp"
      ]
    }
  }
}
```

## MCPJungle registration

MCPJungle proxies remote MCP servers over HTTP/SSE. Run the server with streamable HTTP behind your reverse proxy:

1. Start the container or local process on port `8000` (or map `8010:8000` in compose).
2. Put nginx in front with TLS (Cloudflare Zero Trust / Authentik as needed).
3. In MCPJungle, register a new MCP server:
   - **Name**: `silentinstallhq`
   - **Transport**: `streamable-http` (or `sse` if your MCPJungle build expects SSE)
   - **URL**: `https://mcp.yourdomain.example/mcp` (match your nginx path)
4. Confirm tools appear: `search_guides`, `get_guide`, `list_recent_guides`, `extract_switches`, `generate_psadt_wrapper`.

Example nginx location (adjust upstream name):

```nginx
location /mcp/ {
    proxy_pass http://silentinstallhq-mcp:8000/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_buffering off;
}
```

## Docker

```powershell
docker compose up -d --build
```

The service binds `127.0.0.1:8010` by default. Cache persists in the `silentinstallhq_cache` volume.

## Example tool calls

### Cursor / Claude (natural language)

- "Use silentinstallhq to find the PSADT v4 guide for Cisco AnyConnect."
- "Extract silent install switches for Google Chrome Enterprise."
- "Generate a PSADT v4 wrapper for Cisco Proximity."
- "List the 5 most recent Silent Install HQ guides."

### CrewAI (Python)

```python
from crewai_tools import MCPServerAdapter

with MCPServerAdapter(
    {
        "url": "http://127.0.0.1:8000/mcp",
        "transport": "streamable-http",
    }
) as tools:
    search = tools["search_guides"]
    result = search.run(query="Cisco AnyConnect", limit=5)
    print(result)

    switches = tools["extract_switches"]
    print(switches.run(software_name="GlobalProtect"))

    wrapper = tools["generate_psadt_wrapper"]
    print(wrapper.run(software_name="Cisco Proximity"))
```

### MCP Python client (stdio)

```python
import asyncio
import os
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

repo_dir = Path(os.environ.get("SILENTINSTALLHQ_REPO", Path.cwd())).resolve()

server_params = StdioServerParameters(
    command="uv",
    args=[
        "--directory",
        str(repo_dir),
        "run",
        "silentinstallhq-mcp",
    ],
)

async def main():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "get_guide",
                arguments={"slug": "cisco-anyconnect-install-and-uninstall-psadt-v4"},
            )
            print(result.structuredContent)

asyncio.run(main())
```

## Packaging workflow integration

Use this MCP server during packaging to pull authoritative silent switches and PSADT patterns before generating Intune-ready PSADT packages.

Typical agent workflow:

1. `extract_switches("Cisco AnyConnect")` — get `silent_install_switch`, uninstall string, detection URL
2. `generate_psadt_wrapper("Cisco AnyConnect")` — retrieve or build the PSADT v4 `Invoke-AppDeployToolkit.ps1` script
3. Use the returned switches and script in your packaging tool or agent to align:
   - **Install command** / MSI transforms
   - **Detection script** (registry, file, or custom script from SIHQ link)
   - **Uninstall** command for supersedence / removal rules

Example prompt for your packaging agent:

```text
Query silentinstallhq MCP for "Microsoft FSLogix Apps".
Use extract_switches for install/uninstall commands, then generate_psadt_wrapper for the PSADT v4 script.
Use those values to build an Intune-ready package.
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SILENTINSTALLHQ_TRANSPORT` | `stdio` | `stdio`, `sse`, or `streamable-http` |
| `SILENTINSTALLHQ_HOST` | `0.0.0.0` | HTTP bind host |
| `SILENTINSTALLHQ_PORT` | `8000` | HTTP bind port |
| `SILENTINSTALLHQ_CACHE_DIR` | `./data` | SQLite cache directory |
| `SILENTINSTALLHQ_CACHE_TTL_HOURS` | `24` | Cache TTL |
| `SILENTINSTALLHQ_REQUEST_DELAY_SECONDS` | `1.0` | Minimum delay between upstream requests |
| `SILENTINSTALLHQ_RESPECT_ROBOTS_TXT` | `true` | Enforce robots.txt before scraping |
| `SILENTINSTALLHQ_HTTPX_MAX_CONNECTIONS` | `5` | httpx concurrent connection cap |
| `SILENTINSTALLHQ_HTTPX_MAX_KEEPALIVE_CONNECTIONS` | `2` | httpx keep-alive pool size |
| `SILENTINSTALLHQ_USER_AGENT` | project default | Outbound User-Agent |
| `SILENTINSTALLHQ_LOG_LEVEL` | `INFO` | Logging level |

## Development

```powershell
uv sync --extra dev
uv run pytest
uv run ruff check src tests
```

## Architecture

```text
src/silentinstallhq_mcp/
├── server.py          # FastMCP app + lifespan
├── tools/guides.py    # MCP tool handlers
├── psadt/generator.py     # fallback PSADT v4 wrapper builder
├── scraper/               # httpx fetch + BeautifulSoup parse
├── robots.py              # robots.txt load + enforcement
├── structured_cache.py    # parsed guide / PSADT cache layer
├── cache.py               # SQLite TTL cache
├── http_client.py     # polite HTTP wrapper
└── models.py          # Pydantic response models
```

## License

MIT