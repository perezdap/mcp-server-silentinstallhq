"""High-level scraper client for Silent Install HQ."""

from __future__ import annotations

import logging
from datetime import datetime
from urllib.parse import quote_plus, urljoin

from silentinstallhq_mcp.config import Settings
from silentinstallhq_mcp.http_client import HttpClient, ScrapeError
from silentinstallhq_mcp.models import (
    GuideDetail,
    GuideSummary,
    PsadtWrapperResult,
    SearchResult,
    SwitchesResult,
)
from silentinstallhq_mcp.psadt.generator import generate_psadt_v4_wrapper
from silentinstallhq_mcp.scraper.parser import (
    parse_guide_detail,
    parse_guide_summaries,
    rank_guide_for_psadt,
    rank_guide_for_switches,
    slug_from_url,
)
from silentinstallhq_mcp.structured_cache import StructuredCache

logger = logging.getLogger(__name__)


class GuideNotFoundError(ScrapeError):
    """Raised when a guide slug cannot be resolved."""


class SilentInstallHQClient:
    """Scrapes and parses silentinstallhq.com content."""

    def __init__(
        self,
        settings: Settings,
        http: HttpClient,
        structured_cache: StructuredCache,
    ) -> None:
        self.settings = settings
        self.http = http
        self.structured = structured_cache
        self.base_url = settings.base_url.rstrip("/")

    def _search_url(self, query: str) -> str:
        return f"{self.base_url}/?s={quote_plus(query)}"

    def _guide_url(self, slug: str) -> str:
        slug = slug.strip("/")
        if slug.startswith("http"):
            return slug
        return urljoin(f"{self.base_url}/", f"{slug}/")

    async def search_guides(self, query: str, limit: int = 10) -> SearchResult:
        cached = self.structured.get_search(query, limit)
        if cached is not None:
            logger.debug("Structured cache hit for search %r", query)
            return cached

        html, _ = await self.http.fetch_html(self._search_url(query))
        guides = parse_guide_summaries(html, self.base_url)
        result = SearchResult(query=query, total=len(guides), guides=guides[:limit])
        self.structured.set_search(query, limit, result)
        return result

    async def list_recent_guides(self, limit: int = 10) -> list[GuideSummary]:
        cached = self.structured.get_recent(limit)
        if cached is not None:
            logger.debug("Structured cache hit for recent guides (limit=%s)", limit)
            return cached

        html, _ = await self.http.fetch_html(self.base_url)
        guides = parse_guide_summaries(html, self.base_url)[:limit]
        self.structured.set_recent(limit, guides)
        return guides

    async def get_guide(self, slug: str) -> GuideDetail:
        url = self._guide_url(slug)
        normalized_slug = slug_from_url(url)

        cached = self.structured.get_guide(normalized_slug)
        if cached is not None:
            logger.debug("Structured cache hit for guide %s", normalized_slug)
            cached.cache_hit = True
            return cached

        html, _ = await self.http.fetch_html(url)
        try:
            guide = parse_guide_detail(html, url, self.base_url)
        except ValueError as exc:
            raise GuideNotFoundError(str(exc)) from exc

        guide.cache_hit = False
        guide.fetched_at = datetime.utcnow()
        self.structured.set_guide(normalized_slug, guide)
        return guide

    async def extract_switches(self, software_name: str) -> SwitchesResult:
        cached = self.structured.get_switches(software_name)
        if cached is not None:
            logger.debug("Structured cache hit for switches %r", software_name)
            return cached

        search = await self.search_guides(software_name, limit=15)
        best = rank_guide_for_switches(search.guides, software_name)
        if best is None:
            result = SwitchesResult(software_name=software_name)
            self.structured.set_switches(software_name, result)
            return result

        detail = await self.get_guide(best.slug)
        install_commands = []
        if detail.silent_install_switch:
            install_commands.append(detail.silent_install_switch)
        install_commands.extend(cmd.command for cmd in detail.install_commands)
        install_commands = list(dict.fromkeys(cmd for cmd in install_commands if cmd))

        result = SwitchesResult(
            software_name=software_name,
            matched_guide=best,
            software_title=detail.software_title,
            vendor=detail.vendor,
            installer_type=detail.installer_type,
            silent_install_switch=detail.silent_install_switch,
            silent_uninstall_switch=detail.silent_uninstall_switch,
            repair_command=detail.repair_command,
            additional_switches=detail.additional_commands,
            install_commands=install_commands,
            detection_script_url=detail.detection_script_url,
            guide_url=detail.url,
        )
        self.structured.set_switches(software_name, result)
        return result

    async def resolve_slug(self, slug: str) -> str:
        return slug_from_url(self._guide_url(slug))

    async def generate_psadt_wrapper(
        self,
        software_name: str,
        *,
        slug: str | None = None,
        psadt_version: str = "4.1.8",
    ) -> PsadtWrapperResult:
        """Return a PSADT v4 wrapper from SIHQ or generate one from switch metadata."""
        cached = self.structured.get_psadt_wrapper(
            software_name,
            slug=slug,
            psadt_version=psadt_version,
        )
        if cached is not None:
            logger.debug("Structured cache hit for PSADT wrapper %r", software_name)
            return cached

        guide: GuideDetail
        matched_summary: GuideSummary | None = None

        if slug:
            guide = await self.get_guide(slug)
            matched_summary = GuideSummary(
                title=guide.title,
                slug=guide.slug,
                url=guide.url,
                guide_type=guide.guide_type,
            )
        else:
            search = await self.search_guides(software_name, limit=20)
            matched_summary = rank_guide_for_psadt(search.guides, software_name)
            if matched_summary is None:
                raise GuideNotFoundError(f"No guides found for '{software_name}'")
            guide = await self.get_guide(matched_summary.slug)

        if guide.guide_type != "psadt_v4" and guide.psadt_guide_url:
            psadt_slug = slug_from_url(guide.psadt_guide_url)
            guide = await self.get_guide(psadt_slug)
            matched_summary = GuideSummary(
                title=guide.title,
                slug=guide.slug,
                url=guide.url,
                guide_type=guide.guide_type,
            )

        switches: SwitchesResult | None = None
        if not guide.silent_install_switch and not guide.psadt_script:
            switches = await self.extract_switches(software_name)

        silent_install = guide.silent_install_switch or (
            switches.silent_install_switch if switches else None
        )
        silent_uninstall = guide.silent_uninstall_switch or (
            switches.silent_uninstall_switch if switches else None
        )
        detection_url = guide.detection_script_url or (
            switches.detection_script_url if switches else None
        )

        if guide.psadt_script:
            notes = [
                "Script sourced from Silent Install HQ PSADT v4 guide.",
                "Copy into your PSADT package as Invoke-AppDeployToolkit.ps1.",
                "Place vendor installers under the PSADT Files folder before deployment.",
            ]
            if detection_url:
                notes.append(f"Detection script reference: {detection_url}")

            result = PsadtWrapperResult(
                software_name=software_name,
                software_title=guide.software_title or guide.title,
                vendor=guide.vendor,
                installer_type=guide.installer_type,
                source="silentinstallhq",
                psadt_version=guide.psadt_version or psadt_version,
                script=guide.psadt_script,
                guide_slug=guide.slug,
                guide_url=guide.url,
                silent_install_switch=silent_install,
                silent_uninstall_switch=silent_uninstall,
                detection_script_url=detection_url,
                deployment_notes=notes,
            )
            self.structured.set_psadt_wrapper(
                software_name,
                slug=slug,
                psadt_version=psadt_version,
                result=result,
            )
            return result

        if not silent_install:
            raise GuideNotFoundError(
                f"No PSADT v4 script or silent install switches found for '{software_name}'"
            )

        generated = generate_psadt_v4_wrapper(
            software_title=guide.software_title or software_name,
            vendor=guide.vendor,
            installer_type=guide.installer_type,
            silent_install_switch=silent_install,
            silent_uninstall_switch=silent_uninstall,
            psadt_version=psadt_version,
        )
        notes = [
            "Script generated from Silent Install HQ switch metadata.",
            "Review install/uninstall commands before production use.",
            "Place vendor installers under the PSADT Files folder before deployment.",
        ]
        if detection_url:
            notes.append(f"Detection script reference: {detection_url}")

        result = PsadtWrapperResult(
            software_name=software_name,
            software_title=guide.software_title or software_name,
            vendor=guide.vendor,
            installer_type=guide.installer_type,
            source="generated",
            psadt_version=psadt_version,
            script=generated,
            guide_slug=guide.slug,
            guide_url=guide.url,
            silent_install_switch=silent_install,
            silent_uninstall_switch=silent_uninstall,
            detection_script_url=detection_url,
            deployment_notes=notes,
        )
        self.structured.set_psadt_wrapper(
            software_name,
            slug=slug,
            psadt_version=psadt_version,
            result=result,
        )
        return result