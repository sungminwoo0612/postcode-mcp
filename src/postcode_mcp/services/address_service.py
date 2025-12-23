from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from postcode_mcp.infra.providers.juso_detail import DetailAddrRequest, JusoDetailProvider
from postcode_mcp.infra.providers.juso_eng import EngAddrRequest, JusoEnglishProvider


@dataclass(frozen=True)
class AddressResolveResult:
    best: dict[str, Any] | None
    candidates: list[dict[str, Any]]
    detail: dict[str, Any] | None
    english: dict[str, Any] | None  # { common, best, candidates }
    message: str | None
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "best": self.best,
            "candidates": self.candidates,
            "detail": self.detail,
            "english": self.english,
            "message": self.message,
            "meta": self.meta,
        }


class AddressService:
    def __init__(
        self,
        postcode_service: Any,
        detail_provider: JusoDetailProvider | None,
        english_provider: JusoEnglishProvider | None,
    ):
        self._postcode_service = postcode_service
        self._detail_provider = detail_provider
        self._english_provider = english_provider

    def resolve(
        self,
        *,
        query: str,
        hint_city: str | None = None,
        max_candidates: int = 5,
        include_detail: bool = False,
        detail_search_type: str = "dong",
        dong_nm: str | None = None,
        include_english: bool = False,
        english_count_per_page: int = 5,
    ) -> AddressResolveResult:
        base = self._postcode_service.resolve(query=query, hint_city=hint_city, max_candidates=max_candidates)
        base_dict = base.to_dict() if hasattr(base, "to_dict") else base

        best = base_dict.get("best")
        candidates = base_dict.get("candidates") or []
        message = base_dict.get("message")
        meta = base_dict.get("meta") or {}

        # -----------------------
        # Detail (2단계)
        # -----------------------
        detail_block: dict[str, Any] | None = None
        if include_detail:
            if self._detail_provider is None:
                detail_block = {
                    "common": {"errorCode": "NO_DETAIL_PROVIDER", "errorMessage": "Detail API key/provider not configured"},
                    "items": [],
                }
            elif not best:
                detail_block = {
                    "common": {"errorCode": "NO_BEST", "errorMessage": "No best address to resolve detail"},
                    "items": [],
                }
            else:
                admCd = str(best.get("admCd") or "")
                rnMgtSn = str(best.get("rnMgtSn") or "")
                udrtYn = str(best.get("udrtYn") or "")
                buldMnnm = str(best.get("buldMnnm") or "")
                buldSlno = str(best.get("buldSlno") or "")

                if all([admCd, rnMgtSn, udrtYn, buldMnnm]) and buldSlno != "":
                    payload = self._detail_provider.search(
                        DetailAddrRequest(
                            admCd=admCd,
                            rnMgtSn=rnMgtSn,
                            udrtYn=udrtYn,
                            buldMnnm=buldMnnm,
                            buldSlno=buldSlno,
                            searchType=detail_search_type,
                            dongNm=dong_nm,
                        )
                    )
                    common, items = self._detail_provider.extract_items(payload)
                    detail_block = {"common": common, "items": items}
                else:
                    detail_block = {
                        "common": {
                            "errorCode": "MISSING_KEYS",
                            "errorMessage": "Best candidate lacks required keys for detail lookup (need admCd/rnMgtSn/udrtYn/buldMnnm/buldSlno)",
                        },
                        "items": [],
                    }

        # -----------------------
        # English (3단계)
        # -----------------------
        english_block: dict[str, Any] | None = None
        if include_english:
            if self._english_provider is None:
                english_block = {
                    "common": {"errorCode": "NO_ENGLISH_PROVIDER", "errorMessage": "English API key/provider not configured"},
                    "best": None,
                    "candidates": [],
                }
            else:
                # 영문검색 입력: best의 road_addr가 있으면 그걸 우선, 없으면 query
                eng_input = None
                if isinstance(best, dict):
                    eng_input = (best.get("road_addr") or best.get("jibun_addr") or "").strip() or None
                if not eng_input:
                    eng_input = query

                payload = self._english_provider.search(
                    EngAddrRequest(keyword=eng_input, current_page=1, count_per_page=english_count_per_page)
                )
                common, items = self._english_provider.extract_items(payload)
                norm_items = [self._english_provider.normalize_item(it) for it in items]

                english_best = norm_items[0] if norm_items else None
                english_block = {"common": common, "best": english_best, "candidates": norm_items}

        out_meta = {
            **meta,
            "include_detail": include_detail,
            "detail_search_type": detail_search_type,
            "include_english": include_english,
        }

        return AddressResolveResult(
            best=best,
            candidates=candidates,
            detail=detail_block,
            english=english_block,
            message=message,
            meta=out_meta,
        )
