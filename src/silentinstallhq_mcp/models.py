"""Pydantic models for structured MCP tool responses."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class GuideSummary(BaseModel):
    """Brief guide metadata for search and list results."""

    title: str
    slug: str
    url: HttpUrl
    excerpt: str | None = None
    guide_type: str | None = None
    published: str | None = None


class SearchResult(BaseModel):
    """Response from search_guides."""

    query: str
    total: int
    guides: list[GuideSummary]


class InstallCommand(BaseModel):
    """A labeled silent install command variant."""

    label: str
    command: str


class UninstallCommand(BaseModel):
    """Version-specific or generic uninstall command."""

    version: str | None = None
    command: str


class GuideSection(BaseModel):
    """A content section from a guide article."""

    heading: str
    content: str
    commands: list[str] = Field(default_factory=list)


class RelatedGuide(BaseModel):
    """Link to a related guide on the same site."""

    label: str
    url: HttpUrl


class GuideDetail(BaseModel):
    """Full structured guide content."""

    title: str
    slug: str
    url: HttpUrl
    guide_type: str | None = None
    published: str | None = None
    updated: str | None = None
    author: str | None = None
    summary: str | None = None

    software_title: str | None = None
    vendor: str | None = None
    architecture: str | None = None
    installer_type: str | None = None

    silent_install_switch: str | None = None
    silent_uninstall_switch: str | None = None
    repair_command: str | None = None
    download_link: str | None = None

    install_commands: list[InstallCommand] = Field(default_factory=list)
    uninstall_commands: list[UninstallCommand] = Field(default_factory=list)
    additional_commands: list[InstallCommand] = Field(default_factory=list)

    psadt_script: str | None = None
    psadt_version: str | None = None
    detection_script_url: str | None = None
    powershell_script_url: str | None = None
    psadt_guide_url: str | None = None

    related_guides: list[RelatedGuide] = Field(default_factory=list)
    sections: list[GuideSection] = Field(default_factory=list)
    raw_metadata: dict[str, Any] = Field(default_factory=dict)

    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    cache_hit: bool = False


class PsadtGuideData(BaseModel):
    """Cached PSADT fields extracted from a guide."""

    slug: str
    url: HttpUrl
    software_title: str | None = None
    vendor: str | None = None
    installer_type: str | None = None
    psadt_version: str | None = None
    psadt_script: str
    silent_install_switch: str | None = None
    silent_uninstall_switch: str | None = None
    detection_script_url: str | None = None


class PsadtWrapperResult(BaseModel):
    """Response from generate_psadt_wrapper."""

    software_name: str
    software_title: str | None = None
    vendor: str | None = None
    installer_type: str | None = None
    source: str = Field(
        description=(
            "silentinstallhq when scraped from a PSADT v4 guide; "
            "generated when built from switch metadata"
        ),
    )
    script_filename: str = "Invoke-AppDeployToolkit.ps1"
    psadt_version: str | None = None
    script: str
    guide_slug: str | None = None
    guide_url: HttpUrl | None = None
    silent_install_switch: str | None = None
    silent_uninstall_switch: str | None = None
    detection_script_url: str | None = None
    deployment_notes: list[str] = Field(default_factory=list)


class SwitchesResult(BaseModel):
    """Response from extract_switches."""

    software_name: str
    matched_guide: GuideSummary | None = None
    software_title: str | None = None
    vendor: str | None = None
    installer_type: str | None = None
    silent_install_switch: str | None = None
    silent_uninstall_switch: str | None = None
    repair_command: str | None = None
    additional_switches: list[InstallCommand] = Field(default_factory=list)
    install_commands: list[str] = Field(default_factory=list)
    detection_script_url: str | None = None
    guide_url: HttpUrl | None = None