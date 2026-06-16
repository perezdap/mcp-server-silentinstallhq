"""Typed cache helpers for parsed guide and PSADT payloads."""

from __future__ import annotations

from pydantic import BaseModel

from silentinstallhq_mcp.cache import CacheStore
from silentinstallhq_mcp.models import (
    GuideDetail,
    GuideSummary,
    PsadtGuideData,
    PsadtWrapperResult,
    SearchResult,
    SwitchesResult,
)


class StructuredCache:
    """Read/write Pydantic models in the SQLite cache."""

    def __init__(self, store: CacheStore) -> None:
        self.store = store

    def get_model(self, key: str, model: type[BaseModel]) -> BaseModel | None:
        data = self.store.get(key)
        if data is None:
            return None
        return model.model_validate(data)

    def set_model(self, key: str, value: BaseModel) -> None:
        self.store.set(key, value.model_dump(mode="json"))

    def get_guide(self, slug: str) -> GuideDetail | None:
        result = self.get_model(f"guide:{slug}", GuideDetail)
        return result if isinstance(result, GuideDetail) else None

    def set_guide(self, slug: str, guide: GuideDetail) -> None:
        self.set_model(f"guide:{slug}", guide)
        if guide.psadt_script:
            psadt = PsadtGuideData(
                slug=guide.slug,
                url=guide.url,
                software_title=guide.software_title,
                vendor=guide.vendor,
                installer_type=guide.installer_type,
                psadt_version=guide.psadt_version,
                psadt_script=guide.psadt_script,
                silent_install_switch=guide.silent_install_switch,
                silent_uninstall_switch=guide.silent_uninstall_switch,
                detection_script_url=guide.detection_script_url,
            )
            self.set_model(f"psadt:{slug}", psadt)

    def get_psadt(self, slug: str) -> PsadtGuideData | None:
        result = self.get_model(f"psadt:{slug}", PsadtGuideData)
        return result if isinstance(result, PsadtGuideData) else None

    def get_search(self, query: str, limit: int) -> SearchResult | None:
        key = self._search_key(query, limit)
        result = self.get_model(key, SearchResult)
        return result if isinstance(result, SearchResult) else None

    def set_search(self, query: str, limit: int, result: SearchResult) -> None:
        self.set_model(self._search_key(query, limit), result)

    def get_recent(self, limit: int) -> list[GuideSummary] | None:
        data = self.store.get(f"recent:{limit}")
        if not isinstance(data, list):
            return None
        return [GuideSummary.model_validate(item) for item in data]

    def set_recent(self, limit: int, guides: list[GuideSummary]) -> None:
        self.store.set(f"recent:{limit}", [g.model_dump(mode="json") for g in guides])

    def get_switches(self, software_name: str) -> SwitchesResult | None:
        key = self._normalized_key("switches", software_name)
        result = self.get_model(key, SwitchesResult)
        return result if isinstance(result, SwitchesResult) else None

    def set_switches(self, software_name: str, result: SwitchesResult) -> None:
        self.set_model(self._normalized_key("switches", software_name), result)

    def get_psadt_wrapper(
        self,
        software_name: str,
        *,
        slug: str | None,
        psadt_version: str,
    ) -> PsadtWrapperResult | None:
        key = self._psadt_wrapper_key(software_name, slug=slug, psadt_version=psadt_version)
        result = self.get_model(key, PsadtWrapperResult)
        return result if isinstance(result, PsadtWrapperResult) else None

    def set_psadt_wrapper(
        self,
        software_name: str,
        *,
        slug: str | None,
        psadt_version: str,
        result: PsadtWrapperResult,
    ) -> None:
        key = self._psadt_wrapper_key(software_name, slug=slug, psadt_version=psadt_version)
        self.set_model(key, result)

    @staticmethod
    def _normalized_key(prefix: str, value: str) -> str:
        normalized = " ".join(value.strip().lower().split())
        return f"{prefix}:{normalized}"

    @staticmethod
    def _search_key(query: str, limit: int) -> str:
        normalized = " ".join(query.strip().lower().split())
        return f"search:{normalized}:{limit}"

    @staticmethod
    def _psadt_wrapper_key(software_name: str, *, slug: str | None, psadt_version: str) -> str:
        normalized = " ".join(software_name.strip().lower().split())
        slug_part = (slug or "").strip().lower()
        return f"psadt_wrapper:{normalized}:{slug_part}:{psadt_version}"