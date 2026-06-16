"""HTML parsing helpers for silentinstallhq.com."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, NavigableString, Tag

from silentinstallhq_mcp.models import (
    GuideDetail,
    GuideSection,
    GuideSummary,
    InstallCommand,
    RelatedGuide,
    UninstallCommand,
)

GUIDE_TYPE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("psadt_v4", re.compile(r"psadt\s*v4|psadt-v4", re.I)),
    ("psadt", re.compile(r"powershell|psadt", re.I)),
    ("how_to", re.compile(r"how-to-guide|silent-install", re.I)),
    ("detection", re.compile(r"detection-script|custom-detection", re.I)),
]


def slug_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    return path or url


def classify_guide(url: str, title: str) -> str | None:
    haystack = f"{url} {title}"
    for guide_type, pattern in GUIDE_TYPE_PATTERNS:
        if pattern.search(haystack):
            return guide_type
    return None


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned or None


def _extract_code_text(element: Tag | None) -> str | None:
    if element is None:
        return None
    code = element.find("code")
    if code:
        return _clean_text(code.get_text())
    return _clean_text(element.get_text())


def _normalize_command(command: str | None) -> str | None:
    if not command:
        return None
    command = command.replace("\u00a0", " ")
    command = re.sub(r"\s+", " ", command).strip()
    return command or None


def parse_guide_summaries(html: str, base_url: str) -> list[GuideSummary]:
    soup = BeautifulSoup(html, "html.parser")
    summaries: list[GuideSummary] = []
    seen: set[str] = set()

    for article in soup.select("article"):
        title_el = article.select_one("h2.entry-title a, h1.entry-title a, .entry-title a")
        if title_el is None:
            continue
        href = title_el.get("href")
        title = _clean_text(title_el.get_text())
        if not href or not title:
            continue

        url = urljoin(base_url, href)
        slug = slug_from_url(url)
        if slug in seen:
            continue
        seen.add(slug)

        excerpt_el = article.select_one(".entry-summary p, .entry-content p")
        excerpt = _clean_text(excerpt_el.get_text()) if excerpt_el else None
        published_el = article.select_one(".posted-on, .entry-meta .posted-on")
        published = _clean_text(published_el.get_text()) if published_el else None

        summaries.append(
            GuideSummary(
                title=title,
                slug=slug,
                url=url,  # type: ignore[arg-type]
                excerpt=excerpt,
                guide_type=classify_guide(url, title),
                published=published,
            )
        )

    if summaries:
        return summaries

    for link in soup.select("a[href]"):
        href = link.get("href", "")
        if not href or "silentinstallhq.com" not in urljoin(base_url, href):
            continue
        url = urljoin(base_url, href)
        if url.rstrip("/") == base_url.rstrip("/"):
            continue
        slug = slug_from_url(url)
        if slug in seen:
            continue
        title = _clean_text(link.get("title") or link.get_text())
        if not title or len(title) < 8:
            continue
        guide_tokens = ("install", "silent", "psadt", "detection", "uninstall")
        if not any(token in slug for token in guide_tokens):
            continue
        seen.add(slug)
        summaries.append(
            GuideSummary(
                title=title,
                slug=slug,
                url=url,  # type: ignore[arg-type]
                guide_type=classify_guide(url, title),
            )
        )

    return summaries


def _parse_metadata_table(table: Tag) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for row in table.select("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        key = _clean_text(cells[0].get_text())
        value = _extract_code_text(cells[1]) or _clean_text(cells[1].get_text())
        if key and value:
            metadata[key.rstrip(":").strip()] = value
    return metadata


def _parse_related_links(table: Tag, base_url: str) -> list[RelatedGuide]:
    related: list[RelatedGuide] = []
    for row in table.select("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        label = _clean_text(cells[0].get_text())
        link = cells[1].find("a", href=True)
        if not label or link is None:
            continue
        related.append(
            RelatedGuide(
                label=label.rstrip(":").strip(),
                url=urljoin(base_url, link["href"]),  # type: ignore[arg-type]
            )
        )
    return related


def _extract_psadt_script(content: Tag) -> tuple[str | None, str | None]:
    for pre in content.find_all("pre"):
        text = pre.get_text("\n").strip()
        is_psadt = (
            "PSAppDeployToolkit" in text
            or "$adtSession" in text
            or "Invoke-AppDeployToolkit" in text
        )
        if is_psadt:
            version_match = re.search(r"DeployAppScriptVersion\s*=\s*['\"]([^'\"]+)['\"]", text)
            return text, version_match.group(1) if version_match else None

    for code in content.find_all("code"):
        text = code.get_text("\n").strip()
        if len(text) > 500 and ("PSAppDeployToolkit" in text or "$adtSession" in text):
            version_match = re.search(r"DeployAppScriptVersion\s*=\s*['\"]([^'\"]+)['\"]", text)
            return text, version_match.group(1) if version_match else None

    return None, None


def _extract_adt_session_vars(script: str) -> dict[str, str]:
    fields = {
        "AppVendor": "vendor",
        "AppName": "software_title",
        "AppVersion": "app_version",
        "AppArch": "architecture",
    }
    metadata: dict[str, str] = {}
    for ps_var, field_name in fields.items():
        match = re.search(rf"{ps_var}\s*=\s*['\"]([^'\"]*)['\"]", script)
        if match and match.group(1):
            metadata[field_name] = match.group(1)
    return metadata


def _parse_sections(content: Tag) -> list[GuideSection]:
    sections: list[GuideSection] = []
    current_heading = "Overview"
    buffer: list[str] = []
    commands: list[str] = []

    def flush() -> None:
        nonlocal buffer, commands
        text = _clean_text(" ".join(buffer))
        if text or commands:
            sections.append(
                GuideSection(
                    heading=current_heading,
                    content=text or "",
                    commands=list(dict.fromkeys(commands)),
                )
            )
        buffer = []
        commands = []

    for child in content.children:
        if isinstance(child, NavigableString):
            text = _clean_text(str(child))
            if text:
                buffer.append(text)
            continue
        if not isinstance(child, Tag):
            continue

        if child.name in {"h2", "h3"}:
            flush()
            current_heading = _clean_text(child.get_text()) or current_heading
            continue

        if child.name in {"script", "style", "div"} and child.get("id", "").startswith("ezoic"):
            continue

        if child.name == "figure" and "wp-block-table" in child.get("class", []):
            for code in child.select("code"):
                command = _normalize_command(code.get_text())
                if command:
                    commands.append(command)
            continue

        if child.name == "p":
            strong = child.find("strong")
            label = _clean_text(strong.get_text()) if strong else None
            code_el = child.find("code")
            if label and code_el:
                command = _normalize_command(code_el.get_text())
                if command:
                    commands.append(command)
            text = _clean_text(child.get_text())
            if text:
                buffer.append(text)
            continue

        text = _clean_text(child.get_text())
        if text:
            buffer.append(text)

    flush()
    return sections


def _parse_uninstall_table(content: Tag) -> list[UninstallCommand]:
    uninstalls: list[UninstallCommand] = []
    for table in content.select("figure.wp-block-table table, table"):
        headers = [_clean_text(th.get_text()) for th in table.select("th")]
        if headers and any(h and "version" in h.lower() for h in headers):
            for row in table.select("tbody tr"):
                cells = [_clean_text(td.get_text()) for td in row.find_all("td")]
                if len(cells) >= 2:
                    command = _normalize_command(cells[1])
                    if command:
                        uninstalls.append(UninstallCommand(version=cells[0], command=command))
    return uninstalls


def parse_guide_detail(html: str, url: str, base_url: str) -> GuideDetail:
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one("article") or soup
    title_el = article.select_one("h1.entry-title, .entry-title")
    title = _clean_text(title_el.get_text()) if title_el else slug_from_url(url)

    meta_el = article.select_one(".entry-meta")
    published = updated = author = None
    if meta_el:
        meta_text = _clean_text(meta_el.get_text()) or ""
        published_match = re.search(r"Published on:\s*([^|]+)", meta_text, re.I)
        updated_match = re.search(r"Last Updated on:\s*([^by]+)", meta_text, re.I)
        author_match = re.search(r"by\s+(.+)$", meta_text, re.I)
        published = _clean_text(published_match.group(1)) if published_match else None
        updated = _clean_text(updated_match.group(1)) if updated_match else None
        author = _clean_text(author_match.group(1)) if author_match else None

    content = article.select_one(".entry-content")
    if content is None:
        raise ValueError(f"No entry content found for {url}")

    summary_el = content.find("p")
    summary = _clean_text(summary_el.get_text()) if summary_el else None

    metadata: dict[str, str] = {}
    related: list[RelatedGuide] = []
    for table in content.select("figure.wp-block-table table, table"):
        parsed = _parse_metadata_table(table)
        if parsed:
            metadata.update(parsed)
            related.extend(_parse_related_links(table, base_url))

    psadt_script, psadt_version = _extract_psadt_script(content)
    adt_vars = _extract_adt_session_vars(psadt_script) if psadt_script else {}

    sections = _parse_sections(content)
    install_commands: list[InstallCommand] = []
    additional_commands: list[InstallCommand] = []

    for section in sections:
        for command in section.commands:
            entry = InstallCommand(label=section.heading, command=command)
            if "uninstall" in section.heading.lower():
                continue
            heading = section.heading.lower()
            is_primary = heading in {"overview", "how to install"} or "silent install" in heading
            if is_primary:
                install_commands.append(entry)
            else:
                additional_commands.append(entry)

    uninstall_commands = _parse_uninstall_table(content)
    if not uninstall_commands and metadata.get("Silent Uninstall Switch"):
        uninstall_commands.append(
            UninstallCommand(command=_normalize_command(metadata["Silent Uninstall Switch"]) or "")
        )

    slug = slug_from_url(url)
    guide_type = classify_guide(url, title or slug)

    return GuideDetail(
        title=title or slug,
        slug=slug,
        url=url,  # type: ignore[arg-type]
        guide_type=guide_type,
        published=published,
        updated=updated,
        author=author,
        summary=summary,
        software_title=metadata.get("Software Title") or adt_vars.get("software_title"),
        vendor=metadata.get("Vendor") or adt_vars.get("vendor"),
        architecture=metadata.get("Architecture") or adt_vars.get("architecture"),
        installer_type=metadata.get("Installer Type"),
        silent_install_switch=_normalize_command(metadata.get("Silent Install Switch")),
        silent_uninstall_switch=_normalize_command(metadata.get("Silent Uninstall Switch")),
        repair_command=_normalize_command(metadata.get("Repair Command")),
        download_link=metadata.get("Download Link"),
        install_commands=install_commands,
        uninstall_commands=uninstall_commands,
        additional_commands=additional_commands,
        psadt_script=psadt_script,
        psadt_version=psadt_version,
        detection_script_url=_related_url(related, "Detection"),
        powershell_script_url=_related_url(related, "PowerShell"),
        psadt_guide_url=_related_url(related, "PSADT"),
        related_guides=related,
        sections=sections,
        raw_metadata=metadata,
    )


def _related_url(related: list[RelatedGuide], keyword: str) -> str | None:
    for item in related:
        if keyword.lower() in item.label.lower():
            return str(item.url)
    return None


def rank_guide_for_switches(guides: list[GuideSummary], software_name: str) -> GuideSummary | None:
    """Pick the best how-to guide for switch extraction."""
    if not guides:
        return None

    query_tokens = [t.lower() for t in re.split(r"[\s\-_/]+", software_name) if t]

    def score(guide: GuideSummary) -> tuple[int, int]:
        title_lower = guide.title.lower()
        slug_lower = guide.slug.lower()
        token_hits = sum(1 for token in query_tokens if token in title_lower or token in slug_lower)
        type_bonus = 0
        if guide.guide_type == "how_to":
            type_bonus = 5
        elif guide.guide_type == "psadt_v4":
            type_bonus = 2
        elif guide.guide_type == "detection":
            type_bonus = -3
        penalty = 0
        if "how-to-guide" in slug_lower or "silent-install" in slug_lower:
            penalty = 3
        return (token_hits + type_bonus + penalty, -len(guide.slug))

    return max(guides, key=score)


def rank_guide_for_psadt(guides: list[GuideSummary], software_name: str) -> GuideSummary | None:
    """Pick the best PSADT v4 guide for wrapper generation."""
    if not guides:
        return None

    query_tokens = [t.lower() for t in re.split(r"[\s\-_/]+", software_name) if t]

    def score(guide: GuideSummary) -> tuple[int, int]:
        title_lower = guide.title.lower()
        slug_lower = guide.slug.lower()
        token_hits = sum(1 for token in query_tokens if token in title_lower or token in slug_lower)
        type_bonus = 0
        if guide.guide_type == "psadt_v4":
            type_bonus = 10
        elif guide.guide_type == "psadt":
            type_bonus = 4
        elif guide.guide_type == "how_to":
            type_bonus = 1
        elif guide.guide_type == "detection":
            type_bonus = -5
        slug_bonus = 3 if "psadt-v4" in slug_lower else 0
        return (token_hits + type_bonus + slug_bonus, -len(guide.slug))

    return max(guides, key=score)