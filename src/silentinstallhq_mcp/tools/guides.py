"""Guide-related MCP tools."""

from __future__ import annotations

import logging

from mcp.server.fastmcp import Context, FastMCP

from silentinstallhq_mcp.http_client import ScrapeError
from silentinstallhq_mcp.models import (
    GuideDetail,
    GuideSummary,
    PsadtWrapperResult,
    SearchResult,
    SwitchesResult,
)
from silentinstallhq_mcp.scraper.client import GuideNotFoundError, SilentInstallHQClient

logger = logging.getLogger(__name__)


def _scraper(ctx: Context) -> SilentInstallHQClient:
    return ctx.request_context.lifespan_context["scraper"]


def register_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    async def search_guides(ctx: Context, query: str, limit: int = 10) -> SearchResult:
        """Search Silent Install HQ guides by software name or keyword.

        Examples: "Cisco AnyConnect", "PSADT", "Chrome", "GlobalProtect".
        """
        limit = max(1, min(limit, 50))
        try:
            return await _scraper(ctx).search_guides(query, limit=limit)
        except ScrapeError as exc:
            logger.error("search_guides failed: %s", exc)
            raise

    @mcp.tool()
    async def get_guide(ctx: Context, slug: str) -> GuideDetail:
        """Fetch full guide details by slug or URL path.

        Example slugs:
        - cisco-anyconnect-install-and-uninstall-psadt-v4
        - cisco-proximity-silent-install-how-to-guide
        """
        try:
            return await _scraper(ctx).get_guide(slug)
        except GuideNotFoundError as exc:
            logger.error("get_guide not found: %s", exc)
            raise
        except ScrapeError as exc:
            logger.error("get_guide failed: %s", exc)
            raise

    @mcp.tool()
    async def list_recent_guides(ctx: Context, limit: int = 10) -> list[GuideSummary]:
        """List the most recent guides from the Silent Install HQ homepage."""
        limit = max(1, min(limit, 50))
        try:
            return await _scraper(ctx).list_recent_guides(limit=limit)
        except ScrapeError as exc:
            logger.error("list_recent_guides failed: %s", exc)
            raise

    @mcp.tool()
    async def extract_switches(ctx: Context, software_name: str) -> SwitchesResult:
        """Extract common silent install/uninstall switches for a software title.

        Searches guides and returns the best-matching how-to guide switches.
        """
        try:
            return await _scraper(ctx).extract_switches(software_name)
        except ScrapeError as exc:
            logger.error("extract_switches failed: %s", exc)
            raise

    @mcp.tool()
    async def generate_psadt_wrapper(
        ctx: Context,
        software_name: str,
        slug: str | None = None,
        psadt_version: str = "4.1.8",
    ) -> PsadtWrapperResult:
        """Generate a PSADT v4 Invoke-AppDeployToolkit.ps1 wrapper for an application.

        Prefers the official Silent Install HQ PSADT v4 script when available.
        Falls back to a generated wrapper built from silent install switch metadata.

        Args:
            software_name: Application to look up (e.g. "Cisco Proximity", "GlobalProtect").
            slug: Optional guide slug override
                (e.g. cisco-proximity-install-and-uninstall-psadt-v4).
            psadt_version: PSADT module version for generated wrappers (default 4.1.8).
        """
        try:
            return await _scraper(ctx).generate_psadt_wrapper(
                software_name,
                slug=slug,
                psadt_version=psadt_version,
            )
        except GuideNotFoundError as exc:
            logger.error("generate_psadt_wrapper not found: %s", exc)
            raise
        except ScrapeError as exc:
            logger.error("generate_psadt_wrapper failed: %s", exc)
            raise