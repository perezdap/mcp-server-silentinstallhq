"""Parser unit tests using saved HTML fixtures."""

from pathlib import Path

import pytest

from silentinstallhq_mcp.scraper.parser import (
    parse_guide_detail,
    parse_guide_summaries,
    rank_guide_for_switches,
    slug_from_url,
)

FIXTURES = Path(__file__).parent / "fixtures"
BASE_URL = "https://silentinstallhq.com"


@pytest.fixture
def proximity_html() -> str:
    sample = Path(__file__).resolve().parents[1] / "_sample.html"
    if sample.exists():
        return sample.read_text(encoding="utf-8")
    return (FIXTURES / "cisco-proximity-how-to.html").read_text(encoding="utf-8")


def test_slug_from_url():
    url = "https://silentinstallhq.com/cisco-proximity-silent-install-how-to-guide/"
    assert slug_from_url(url) == "cisco-proximity-silent-install-how-to-guide"


def test_parse_guide_detail_metadata(proximity_html: str):
    url = "https://silentinstallhq.com/cisco-proximity-silent-install-how-to-guide/"
    guide = parse_guide_detail(proximity_html, url, BASE_URL)

    assert "Cisco Proximity" in guide.title
    assert guide.software_title == "Cisco Proximity"
    assert guide.vendor == "Cisco Systems, Inc."
    assert guide.installer_type == "MSI"
    assert guide.silent_install_switch is not None
    assert "/qn" in guide.silent_install_switch
    assert guide.detection_script_url is not None
    assert guide.psadt_guide_url is not None
    assert len(guide.additional_commands) > 0


def test_parse_guide_summaries_from_homepage():
    html = """
    <article>
      <h2 class="entry-title">
        <a href="https://silentinstallhq.com/foo-install-psadt-v4/">Foo Install</a>
      </h2>
      <div class="entry-summary"><p>Summary text here.</p></div>
    </article>
    """
    guides = parse_guide_summaries(html, BASE_URL)
    assert len(guides) == 1
    assert guides[0].slug == "foo-install-psadt-v4"
    assert guides[0].guide_type == "psadt_v4"


def test_rank_guide_for_switches_prefers_how_to():
    guides = parse_guide_summaries(
        """
        <article><h2 class="entry-title"><a href="https://silentinstallhq.com/cisco-proximity-install-psadt-v4/">PSADT</a></h2></article>
        <article><h2 class="entry-title"><a href="https://silentinstallhq.com/cisco-proximity-silent-install-how-to-guide/">How-To</a></h2></article>
        """,
        BASE_URL,
    )
    best = rank_guide_for_switches(guides, "Cisco Proximity")
    assert best is not None
    assert "how-to-guide" in best.slug