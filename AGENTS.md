# AI Agent Guide

Instructions for Codex, Claude, Cursor, Grok, and similar tools working in this repository.

## Project summary

Python MCP server ([FastMCP](https://github.com/modelcontextprotocol/python-sdk)) that scrapes [Silent Install HQ](https://silentinstallhq.com/) and exposes tools for silent install guides, PSADT v4 templates, switches, and wrapper generation.

Stack: Python 3.11+, `uv`, `httpx`, `BeautifulSoup`, `Pydantic`, SQLite cache.

## Non-negotiable rules

- Keep this project **Python-only** for application code. Do not add PowerShell/Node helpers unless the user explicitly asks.
- Be polite to Silent Install HQ: respect `robots.txt`, use the configured User-Agent, and preserve rate limiting + caching.
- Do not commit `.env`, `data/`, `.venv/`, cache DBs, or local MCP harness folders (`mcps/`).
- Match existing layout under `src/silentinstallhq_mcp/`. Prefer extending tools in `tools/` and parsing in `scraper/`.
- Write or update `pytest` tests for behavior changes. Run `uv run pytest` and `uv run ruff check src tests` before finishing.
- Surgical edits only. Do not refactor unrelated modules.

## Quick commands

```powershell
uv sync --extra dev
uv run silentinstallhq-mcp --transport stdio
uv run pytest
uv run ruff check src tests
docker compose up -d --build
```

## Architecture

```text
src/silentinstallhq_mcp/
├── server.py            # FastMCP app + lifespan wiring
├── tools/guides.py      # MCP tool registrations
├── scraper/
│   ├── client.py        # search / get / switches / PSADT wrapper
│   └── parser.py        # BeautifulSoup HTML parsing
├── psadt/generator.py   # fallback PSADT v4 script builder
├── http_client.py       # httpx + HTML cache + robots gate
├── robots.py            # robots.txt load/enforce
├── structured_cache.py  # parsed guide / PSADT JSON cache
├── cache.py             # SQLite TTL store
├── models.py            # Pydantic response models
└── config.py            # env-driven settings (SILENTINSTALLHQ_*)
```

## MCP tools

| Tool | Purpose |
|------|---------|
| `search_guides` | Search SIHQ by keyword |
| `get_guide` | Full parsed guide by slug |
| `list_recent_guides` | Homepage recent articles |
| `extract_switches` | Install/uninstall switch lookup |
| `generate_psadt_wrapper` | PSADT v4 script from SIHQ or generated fallback |

## Scraping policy

- **robots.txt** is enforced before every fetch (including cache-backed flows).
- **HTML cache** key: `html:{url}`
- **Structured cache** keys: `guide:{slug}`, `psadt:{slug}`, `search:{query}:{limit}`, `switches:{name}`, `psadt_wrapper:{name}:{slug}:{version}`
- Default TTL: 24 hours (`SILENTINSTALLHQ_CACHE_TTL_HOURS`)
- Default pacing: 1 second between network requests

When adding new scrape targets, wire them through `HttpClient.fetch_html()` so robots, rate limiting, and HTML caching stay centralized. Add structured cache keys for any expensive parse step.

## Adding a new tool

1. Add/extend Pydantic models in `models.py` if the response shape is new.
2. Implement logic in `scraper/client.py` (or a focused module).
3. Register with `@mcp.tool()` in `tools/guides.py`.
4. Add tests under `tests/`.
5. Document in `README.md` (Quickstart + tool list).

## Testing guidance

- Parser tests can use fixtures in `tests/fixtures/`.
- Robots tests should not require live network access (seed cache with robots body).
- Cache tests use `tmp_path` SQLite files.
- Live integration tests against silentinstallhq.com are optional; unit tests must pass offline.

## Related projects

This server pairs with [winget-intune-psadt-packager](https://github.com/perezdap/winget-intune-psadt-packager) for Intune/PSADT packaging workflows. Typical flow:

1. `extract_switches` → install/uninstall strings
2. `generate_psadt_wrapper` → `Invoke-AppDeployToolkit.ps1`
3. Feed results into the packager agent or catalog overrides

## Configuration reference

All settings use the `SILENTINSTALLHQ_` prefix. See `.env.example` and `README.md`.