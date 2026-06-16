"""Structured cache tests."""

from datetime import datetime

from silentinstallhq_mcp.cache import CacheStore
from silentinstallhq_mcp.models import GuideDetail, PsadtGuideData, SearchResult
from silentinstallhq_mcp.structured_cache import StructuredCache


def test_structured_cache_roundtrips_guide(tmp_path):
    cache = CacheStore(tmp_path / "cache.sqlite", ttl_seconds=3600)
    structured = StructuredCache(cache)

    guide = GuideDetail(
        title="Cisco Proximity Silent Install (How-To Guide)",
        slug="cisco-proximity-silent-install-how-to-guide",
        url="https://silentinstallhq.com/cisco-proximity-silent-install-how-to-guide/",
        software_title="Cisco Proximity",
        vendor="Cisco Systems, Inc.",
        psadt_script="<# PSADT #>",
        psadt_version="4.1.3",
        fetched_at=datetime.utcnow(),
    )

    structured.set_guide(guide.slug, guide)
    loaded = structured.get_guide(guide.slug)

    assert loaded is not None
    assert loaded.title == guide.title
    assert loaded.psadt_script == guide.psadt_script

    psadt = structured.get_psadt(guide.slug)
    assert isinstance(psadt, PsadtGuideData)
    assert psadt.psadt_script == guide.psadt_script


def test_structured_cache_roundtrips_search(tmp_path):
    cache = CacheStore(tmp_path / "cache.sqlite", ttl_seconds=3600)
    structured = StructuredCache(cache)

    result = SearchResult(query="Cisco", total=1, guides=[])
    structured.set_search("Cisco", 10, result)
    loaded = structured.get_search("cisco", 10)

    assert loaded is not None
    assert loaded.query == "Cisco"