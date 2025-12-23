from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ROAD_API_URL = "https://business.juso.go.kr/addrlink/addrEngApi.do"


@dataclass(frozen=True)
class EngAddrRequest:
    keyword: str
    current_page: int = 1
    count_per_page: int = 10
    result_type: str = "json"

    
class JusoEnglishProvider:
    """
    영문주소 검색 API (서버형 조회용)
    - endpoint는 환경변수로 주입 (JUSO_ENG_API_URL)
    - confmKey(영문검색키)로 keyword를 조회
    - 응답은 results.common / results.juso[] 형태를 기대
    """

    def __init__(
        self, 
        http: Any, 
        confm_key: str,
        count_per_page: int,
        first_sort: str,
        add_info_yn: str,
        timeout_seconds: float | None = None,
        api_url: str = ROAD_API_URL,
        cache: Any | None = None,
    ):
        self._http = http
        self._confm_key = confm_key
        self._count_per_page = count_per_page
        self._first_sort = first_sort
        self._add_info_yn = add_info_yn
        self._timeout_seconds = timeout_seconds
        self._api_url = api_url
        self._cache = cache
        
    def search(self, req: EngAddrRequest) -> dict[str, Any]:
        keyword = (req.keyword or "").strip()
        current_page = req.current_page
        count_per_page = req.count_per_page or self._count_per_page
        if not keyword:
            return {"results": {"common": {"errorCode": "EMPTY_KEYWORD", "errorMessage": "keyword is empty"}, "juso": []}}

        cache_key = f"juso:road:{keyword}:{current_page}:{count_per_page}:{self._first_sort}:{self._add_info_yn}"
        if self._cache is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        params: dict[str, Any] = {
            "confmKey": self._confm_key,
            "keyword": keyword,
            "currentPage": str(current_page),
            "countPerPage": str(count_per_page),
            "resultType": "json",
            "firstSort": self._first_sort,
            "addInfoYn": self._add_info_yn,
        }

        api_url = self._api_url or ROAD_API_URL
        if hasattr(self._http, "get_json"):
            payload = self._http.get_json(api_url, params=params)
        elif hasattr(self._http, "get"):
            r = self._http.get(api_url, params=params, timeout=10)
            payload = r.json()
        else:
            raise RuntimeError("Http client must provide get_json(url, params=...) or get(url, params=...).")

        if self._cache is not None:
            self._cache.set(cache_key, payload)

        return payload

    @staticmethod
    def extract_items(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        results = payload.get("results") or {}
        common = results.get("common") or {}
        items = results.get("juso") or []
        if not isinstance(items, list):
            items = []
        return common, items

    @staticmethod
    def normalize_item(item: dict[str, Any]) -> dict[str, Any]:
        """
        우리 서비스 표준 출력 + 상세주소용 코드 필드 보존
        """
        def pick(*keys: str) -> str | None:
            for k in keys:
                v = item.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
            return None

        # 표준(현재 너의 unstructured output과 맞춤)
        road_addr = pick("roadAddr", "roadAddrPart1")
        jibun_addr = pick("jibunAddr")
        postcode5 = pick("zipNo")

        building_name = pick("bdNm")  # building name
        # 상세주소용 코드(핵심)
        admCd = pick("admCd")
        rnMgtSn = pick("rnMgtSn")
        udrtYn = pick("udrtYn")
        buldMnnm = pick("buldMnnm")
        buldSlno = pick("buldSlno")

        # 참고용: 건물관리번호가 필요한 케이스 대비
        bdMgtSn = pick("bdMgtSn")

        return {
            "road_addr": road_addr,
            "jibun_addr": jibun_addr,
            "postcode5": postcode5,
            "building_name": building_name,

            # detail lookup keys (2.5단계 핵심)
            "admCd": admCd,
            "rnMgtSn": rnMgtSn,
            "udrtYn": udrtYn,
            "buldMnnm": buldMnnm,
            "buldSlno": buldSlno,
            "bdMgtSn": bdMgtSn,

            # 원본 보관(디버그/확장용)
            "_raw": item,
        }