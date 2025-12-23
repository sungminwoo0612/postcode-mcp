from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DETAIL_API_URL = "https://business.juso.go.kr/addrlink/addrDetailApi.do"


@dataclass(frozen=True)
class DetailAddrRequest:
    admCd: str
    rnMgtSn: str
    udrtYn: str
    buldMnnm: str
    buldSlno: str
    searchType: str = "dong"      # dong | floorho
    dongNm: str | None = None     # searchType=dong 일 때 사용
    resultType: str = "json"


class JusoDetailProvider:
    """
    상세주소 검색 API (addrDetailApi.do)
    - required: confmKey, admCd, rnMgtSn, udrtYn, buldMnnm, buldSlno
    - optional: searchType(dong|floorho), dongNm
    """

    def __init__(self, http: Any, confm_key: str, timeout_seconds: float | None = None):
        self._http = http
        self._confm_key = confm_key
        self._timeout_seconds = timeout_seconds

    def search(self, req: DetailAddrRequest) -> dict[str, Any]:
        params: dict[str, Any] = {
            "confmKey": self._confm_key,
            "resultType": req.resultType,
            "admCd": req.admCd,
            "rnMgtSn": req.rnMgtSn,
            "udrtYn": req.udrtYn,
            "buldMnnm": req.buldMnnm,
            "buldSlno": req.buldSlno,
            "searchType": req.searchType,
        }
        if req.dongNm:
            params["dongNm"] = req.dongNm

        # HttpClient에 get_json이 있으면 사용, 없으면 requests-like 인터페이스를 시도
        if hasattr(self._http, "get_json"):
            return self._http.get_json(DETAIL_API_URL, params=params)

        if hasattr(self._http, "get"):
            r = self._http.get(DETAIL_API_URL, params=params, timeout=self._timeout_seconds)
            return r.json()

        raise RuntimeError("Http client must provide get_json(url, params=...) or get(url, params=...).")

    @staticmethod
    def extract_items(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """
        returns: (common, items)
        payload shape (json):
          { "results": { "common": {...}, "juso": [ {...}, ... ] } }
        """
        results = payload.get("results") or {}
        common = results.get("common") or {}
        items = results.get("juso") or []
        if not isinstance(items, list):
            items = []
        return common, items
