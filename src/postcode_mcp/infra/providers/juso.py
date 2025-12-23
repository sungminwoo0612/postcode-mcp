from __future__ import annotations

import logging
from typing import Any

from postcode_mcp.core.errors import UpstreamError, ValidationError
from postcode_mcp.core.models import AddressCandidate
from postcode_mcp.core.text import normalize_postcode, normalize_query
from postcode_mcp.infra.cache import Cache
from postcode_mcp.infra.http import HttpClient

log = logging.getLogger(__name__)

JUSO_API_URL = "http://www.juso.go.kr/addrlink/addrLinkApi.do"


class JusoProvider:
    def __init__(
        self,
        *,
        http: HttpClient,
        confm_key: str,
        count_per_page: int,
        first_sort: str,
        add_info_yn: str,
        cache: Cache,
    ) -> None:
        self._http = http
        self._confm_key = confm_key
        self._count_per_page = count_per_page
        self._first_sort = first_sort
        self._add_info_yn = add_info_yn
        self._cache = cache

    def search(self, keyword: str, *, max_results: int | None = None) -> list[AddressCandidate]:
        """
        행안부 주소검색 API를 호출하여 주소 후보를 반환합니다.

        Args:
            keyword: 검색어 (주소 또는 장소명)
            max_results: 최대 반환 개수 (None이면 count_per_page만큼)

        Returns:
            AddressCandidate 리스트
        """
        keyword = normalize_query(keyword)
        if not keyword:
            raise ValidationError("검색어가 비어있습니다.")

        max_results = max_results or self._count_per_page
        max_results = min(max_results, self._count_per_page)

        # 캐시 키 생성
        cache_key = f"juso:{keyword}:{max_results}:{self._first_sort}"

        # 캐시 확인
        cached = self._cache.get(cache_key)
        if cached is not None:
            log.debug("Cache hit for keyword: %s", keyword)
            return list(cached) if isinstance(cached, (list, tuple)) else []

        # API 호출
        candidates: list[AddressCandidate] = []
        current_page = 1
        total_count = 0

        while len(candidates) < max_results:
            params = {
                "confmKey": self._confm_key,
                "keyword": keyword,
                "currentPage": str(current_page),
                "countPerPage": str(self._count_per_page),
                "resultType": "json",
                "firstSort": self._first_sort,
                "addInfoYn": self._add_info_yn,
            }

            try:
                response = self._http.get_json(JUSO_API_URL, params=params)
            except UpstreamError as e:
                log.error("Juso API error: %s", e)
                raise

            # 응답 파싱
            results = response.get("results", {})
            common = results.get("common", {})
            error_code = common.get("errorCode", "0")

            if error_code != "0":
                error_message = common.get("errorMessage", "Unknown error")
                log.error("Juso API error: %s - %s", error_code, error_message)
                raise UpstreamError(f"Juso API error {error_code}: {error_message}")

            juso_list = results.get("juso", [])
            if not juso_list:
                break

            total_count = int(common.get("totalCount", "0"))

            def _pick_str(v: Any) -> str | None:
                if v is None:
                    return None
                s = str(v).strip()
                return s if s else None

            for juso_item in juso_list:
                if len(candidates) >= max_results:
                    break

                road_addr = _pick_str(juso_item.get("roadAddr")) or ""
                jibun_addr = _pick_str(juso_item.get("jibunAddr"))
                zip_no = normalize_postcode(_pick_str(juso_item.get("zipNo")) or "")
                bd_nm = _pick_str(juso_item.get("bdNm"))

                if not road_addr or not zip_no:
                    continue

                candidate = AddressCandidate(
                    road_addr=road_addr,
                    jibun_addr=jibun_addr,
                    postcode5=zip_no,
                    building_name=bd_nm,
                    confidence=1.0,
                    # detail keys
                    admCd=_pick_str(juso_item.get("admCd")),
                    rnMgtSn=_pick_str(juso_item.get("rnMgtSn")),
                    udrtYn=_pick_str(juso_item.get("udrtYn")),
                    buldMnnm=_pick_str(juso_item.get("buldMnnm")),
                    buldSlno=_pick_str(juso_item.get("buldSlno")),
                    bdMgtSn=_pick_str(juso_item.get("bdMgtSn")),
                    # optional
                    engAddr=_pick_str(juso_item.get("engAddr")),
                )
                candidates.append(candidate)

            # 더 이상 결과가 없으면 종료
            if len(juso_list) < self._count_per_page or len(candidates) >= total_count:
                break

            current_page += 1

        # 캐시 저장
        if candidates:
            self._cache.set(cache_key, candidates)

        return candidates

