from __future__ import annotations

from typing import Any

from fastmcp import FastMCP
from pydantic import BaseModel, Field, ValidationError as PydanticValidationError

from postcode_mcp.app.container import Container
from postcode_mcp.infra.providers.juso_eng import EngAddrRequest


class ResolvePostcodeArgs(BaseModel):
    query: str = Field(..., description="장소명 또는 주소 문자열")
    hint_city: str | None = Field(None, description="예: 수원, 서울 (스코어링 힌트)")
    max_candidates: int = Field(5, ge=1, le=20, description="후보 반환 최대 개수")


class KakaoPlace(BaseModel):
    id: str | None = None
    place_name: str | None = None
    phone: str | None = None
    address_name: str | None = None
    road_address_name: str | None = None
    x: str | None = None
    y: str | None = None


class ResolvePostcodeAutoArgs(BaseModel):
    query: str | None = Field(None, description="장소명 또는 주소 문자열 (B fallback용)")
    kakao_place: dict[str, Any] | None = Field(None, description="카카오맵 place 단일 객체(원본 JSON 가능)")
    kakao_places: list[dict[str, Any]] | None = Field(None, description="카카오맵 place 리스트(원본 JSON 가능)")
    hint_city: str | None = Field(None, description="예: 수원, 서울 (스코어링 힌트)")
    max_candidates: int = Field(5, ge=1, le=20)

    include_detail: bool = Field(True, description="상세주소 조회 포함 여부")
    detail_search_type: str = Field("dong")
    dong_nm: str | None = Field(None)

    include_english: bool = Field(True, description="영문주소 조회 포함 여부")
    english_count_per_page: int = Field(5, ge=1, le=20, description="영문주소 후보 수")

class EnrichKakaoPlaceArgs(BaseModel):
    """
    카카오맵 키워드 검색 결과(단일 place)에서 road_address_name을 넣어 호출하는 용도.
    - PlayMCP에서 'SearchPlaceByKeywordOpen' 결과를 LLM이 받았을 때 이어붙이기 좋음.
    """
    road_address_name: str = Field(..., description="예: '경기 수원시 팔달구 효원로 241'")
    hint_city: str | None = Field(None, description="예: 수원, 서울")
    max_candidates: int = Field(5, ge=1, le=20)


class NormalizeResult(BaseModel):
    """텍스트 주소를 표준 주소 후보 목록으로 정규화한 결과."""

    normalized: dict[str, Any] | None = Field(
        default=None,
        description="선택된 대표 표준 주소(도로명/지번/우편번호 등)",
    )
    candidates: list[dict[str, Any]] = Field(
        default_factory=list,
        description="정규화된 주소 후보 목록",
    )


def _extract_road_address_from_kakao_payload(
    *,
    kakao_place: dict[str, Any] | None,
    kakao_places: list[dict[str, Any]] | None,
) -> tuple[str | None, dict[str, Any] | None]:
    candidates: list[dict[str, Any]] = []
    if isinstance(kakao_place, dict):
        candidates.append(kakao_place)
    if isinstance(kakao_places, list):
        candidates.extend([p for p in kakao_places if isinstance(p, dict)])

    if not candidates:
        return None, None

    parsed: list[KakaoPlace] = []
    for p in candidates:
        try:
            parsed.append(KakaoPlace.model_validate(p))
        except PydanticValidationError:
            parsed.append(
                KakaoPlace(
                    road_address_name=str(p.get("road_address_name") or "") or None,
                    address_name=str(p.get("address_name") or "") or None,
                    place_name=str(p.get("place_name") or "") or None,
                )
            )

    for idx, kp in enumerate(parsed):
        if kp.road_address_name and kp.road_address_name.strip():
            return kp.road_address_name.strip(), candidates[idx]

    for idx, kp in enumerate(parsed):
        if kp.address_name and kp.address_name.strip():
            return kp.address_name.strip(), candidates[idx]

    return None, None



def register_postcode_tools(mcp: FastMCP, container: Container) -> None:
    address_service = container.address_service
    postcode_service = container.postcode_service
    english_provider = container.juso_english

    @mcp.tool(
        name="normalize_address",
        description=(
            "텍스트로 입력한 주소를 행안부 주소 데이터 기준의 표준 주소 후보로 정규화합니다. "
            "배송지/회원가입 폼의 주소 문자열을 정제하거나, 데이터 파이프라인에서 주소를 표준화할 때 사용합니다."
        ),
    )
    def normalize_address(
        query: str,
        hint_city: str | None = None,
        max_candidates: int = 5,
    ) -> NormalizeResult:
        """
        텍스트 주소 → 표준 주소 후보/정규화 결과.

        - query: 예) '서울 강남구 테헤란로 142'
        - hint_city: 예) '서울', '수원' (스코어링 힌트, 선택)
        """
        base = address_service.resolve(
            query=query,
            hint_city=hint_city,
            max_candidates=max_candidates,
            include_detail=False,
            detail_search_type="dong",
            dong_nm=None,
            include_english=False,
            english_count_per_page=5,
        ).to_dict()

        return NormalizeResult(
            normalized=base.get("best"),
            candidates=base.get("candidates") or [],
        )

    @mcp.tool(
        name="get_postcode",
        description=(
            "표준 주소(도로명 또는 지번)를 바탕으로 5자리 우편번호를 조회합니다. "
            "이미 정규화된 주소에서 우편번호만 추출할 때 사용합니다."
        ),
    )
    def get_postcode(
        road_addr: str | None = None,
        jibun_addr: str | None = None,
        hint_city: str | None = None,
        max_candidates: int = 5,
    ) -> dict[str, Any]:
        """
        표준 주소(또는 도로명/지번) → 우편번호.

        - road_addr 또는 jibun_addr 둘 중 하나는 반드시 제공.
        """
        query_parts = [p for p in (road_addr, jibun_addr) if p]
        if not query_parts:
            return {
                "postcode": None,
                "best": None,
                "candidates": [],
                "message": "road_addr 또는 jibun_addr 중 하나는 반드시 제공해야 합니다.",
            }

        query = query_parts[0]

        base = postcode_service.resolve(
            query=query,
            hint_city=hint_city,
            max_candidates=max_candidates,
        )
        base_dict = base.to_dict() if hasattr(base, "to_dict") else base
        best = base_dict.get("best")

        postcode: str | None = None
        if isinstance(best, dict):
            postcode = best.get("postcode5")

        return {
            "postcode": postcode,
            "best": best,
            "candidates": base_dict.get("candidates") or [],
            "message": base_dict.get("message"),
        }

    @mcp.tool(
        name="get_english_address",
        description=(
            "표준 도로명 주소를 기반으로 영문 주소를 조회합니다. "
            "해외 배송지, 여권 정보, 글로벌 서비스용 주소 데이터 정리에 사용할 수 있습니다."
        ),
    )
    def get_english_address(
        road_addr: str,
        english_count_per_page: int = 5,
    ) -> dict[str, Any]:
        """
        표준 도로명 주소 → 영문 주소.

        - road_addr: 예) '서울특별시 강남구 테헤란로 142'
        """
        if not english_provider:
            return {
                "english_address": None,
                "common": {
                    "errorCode": "NO_ENGLISH_PROVIDER",
                    "errorMessage": "영문 주소 API(juso_eng)가 설정되어 있지 않습니다.",
                },
                "best": None,
                "candidates": [],
            }

        req = EngAddrRequest(
            keyword=road_addr,
            current_page=1,
            count_per_page=english_count_per_page,
        )
        payload = english_provider.search(req)
        common, items = english_provider.extract_items(payload)
        norm_items = [english_provider.normalize_item(it) for it in items]
        english_best = norm_items[0] if norm_items else None

        english_address: str | None = None
        if isinstance(english_best, dict):
            raw = english_best.get("_raw") or {}
            if isinstance(raw, dict):
                english_address = raw.get("engAddr")

        return {
            "english_address": english_address,
            "best": english_best,
            "candidates": norm_items,
            "common": common,
        }

    @mcp.tool(
        name="resolve_from_kakao_place",
        description=(
            "카카오 place JSON 1개에서 주소를 추출해 표준 주소/우편번호/영문주소로 정제·보강합니다. "
            "카카오 검색 결과를 그대로 쓰지 않고, 배송지/회원가입/데이터 정제용 주소 데이터로 가공하는 보조 도구입니다."
        ),
    )
    def resolve_from_kakao_place(
        kakao_place: dict[str, Any],
        hint_city: str | None = None,
        max_candidates: int = 5,
        include_detail: bool = True,
        detail_search_type: str = "dong",
        dong_nm: str | None = None,
        include_english: bool = True,
        english_count_per_page: int = 5,
    ) -> dict[str, Any]:
        """
        카카오 place JSON 1개 → (필요하면) 주소 추출 → 정규화 → 우편번호/영문.

        - 길찾기/장소검색 기능이 아니라, 이미 확보한 place 데이터를 '주소 데이터'로 정제·보강하는 용도.
        """
        addr_from_kakao, picked = _extract_road_address_from_kakao_payload(
            kakao_place=kakao_place,
            kakao_places=None,
        )
        if not addr_from_kakao:
            return {
                "normalized": None,
                "postcode": None,
                "english_address": None,
                "candidates": [],
                "detail": None,
                "english": None,
                "meta": {
                    "strategy": "kakao_place_no_address",
                    "message": "카카오 place에서 사용할 수 있는 주소를 찾지 못했습니다.",
                    "kakao_place_used": picked,
                },
            }

        res = address_service.resolve(
            query=addr_from_kakao,
            hint_city=hint_city,
            max_candidates=max_candidates,
            include_detail=include_detail,
            detail_search_type=detail_search_type,
            dong_nm=dong_nm,
            include_english=include_english,
            english_count_per_page=english_count_per_page,
        ).to_dict()

        best = res.get("best")
        postcode: str | None = None
        if isinstance(best, dict):
            postcode = best.get("postcode5")

        english_address: str | None = None
        english_block = res.get("english")
        if isinstance(english_block, dict):
            best_eng = english_block.get("best")
            if isinstance(best_eng, dict):
                raw = best_eng.get("_raw") or {}
                if isinstance(raw, dict):
                    english_address = raw.get("engAddr")

        meta = {
            **(res.get("meta") or {}),
            "strategy": "kakao_place",
            "input_used": addr_from_kakao,
            "kakao_place_used": picked,
        }

        return {
            "normalized": best,
            "postcode": postcode,
            "english_address": english_address,
            "candidates": res.get("candidates") or [],
            "detail": res.get("detail"),
            "english": english_block,
            "meta": meta,
        }

    @mcp.tool(
        name="resolve_from_kakao_places",
        description=(
            "카카오 place JSON 여러 개를 받아 상위 결과들을 표준 주소/우편번호/영문주소로 정제·보강합니다. "
            "카카오 키워드 검색 결과 목록에 배송지/회원가입용 주소 정보를 일괄로 붙일 때 사용합니다."
        ),
    )
    def resolve_from_kakao_places(
        kakao_places: list[dict[str, Any]],
        hint_city: str | None = None,
        max_candidates: int = 5,
        include_detail: bool = True,
        detail_search_type: str = "dong",
        dong_nm: str | None = None,
        include_english: bool = True,
        english_count_per_page: int = 5,
    ) -> dict[str, Any]:
        """
        카카오 place JSON 여러 개 → 상위 N개 처리 (입력 리스트가 이미 상위 N개라고 가정).

        각 place마다 resolve_from_kakao_place를 적용해, 주소 데이터/우편번호/영문주소를 보강합니다.
        """
        items: list[dict[str, Any]] = []

        for place in kakao_places or []:
            if not isinstance(place, dict):
                continue

            item = resolve_from_kakao_place(
                kakao_place=place,
                hint_city=hint_city,
                max_candidates=max_candidates,
                include_detail=include_detail,
                detail_search_type=detail_search_type,
                dong_nm=dong_nm,
                include_english=include_english,
                english_count_per_page=english_count_per_page,
            )
            # 원본 place도 같이 반환해 LLM이 후처리/매칭하기 좋게 함.
            item["kakao_place"] = place
            items.append(item)

        return {"items": items}

    @mcp.tool(
        name="resolve_postcode_auto",
        description=(
            "배송지/회원가입 폼의 주소 문자열이나 카카오 place JSON을 받아 "
            "도로명주소/지번/5자리 우편번호를 찾고, 필요 시 상세주소·영문주소까지 한 번에 조회하는 편의용 통합 툴입니다. "
            "핵심 주소 정제/보강 로직은 normalize_address/get_postcode/get_english_address/resolve_from_kakao_place 등에 분리되어 있습니다."
        ),
    )
    def resolve_postcode_auto(
        query: str | None = None,
        kakao_place: dict[str, Any] | None = None,
        kakao_places: list[dict[str, Any]] | None = None,
        hint_city: str | None = None,
        max_candidates: int = 5,
        include_detail: bool = True,
        detail_search_type: str = "dong",
        dong_nm: str | None = None,
        include_english: bool = True,
        english_count_per_page: int = 5,
    ) -> dict[str, Any]:
        """
        장소명/주소 또는 카카오 place JSON 입력 → best/candidates + detail(선택) + english(선택) 반환.
        - A 전략: kakao_place/kakao_places에 road_address_name이 있으면 우선 사용
        - B 전략: query 문자열만으로 Juso 검색
        """
        args = ResolvePostcodeAutoArgs(
            query=query,
            kakao_place=kakao_place,
            kakao_places=kakao_places,
            hint_city=hint_city,
            max_candidates=max_candidates,
            include_detail=include_detail,
            detail_search_type=detail_search_type,
            dong_nm=dong_nm,
            include_english=include_english,
            english_count_per_page=english_count_per_page,
        )

        addr_from_kakao, picked_place = _extract_road_address_from_kakao_payload(
            kakao_place=args.kakao_place,
            kakao_places=args.kakao_places,
        )

        # A: 카카오 우선
        if addr_from_kakao:
            res = address_service.resolve(
                query=addr_from_kakao,
                hint_city=args.hint_city,
                max_candidates=args.max_candidates,
                include_detail=args.include_detail,
                detail_search_type=args.detail_search_type,
                dong_nm=args.dong_nm,
                include_english=args.include_english,
                english_count_per_page=args.english_count_per_page,
            ).to_dict()
            res["meta"] = {
                **(res.get("meta") or {}),
                "strategy": "A_kakao_then_juso",
                "input_used": addr_from_kakao,
                "kakao_place_used": picked_place,
            }
            return res

        # B fallback
        if not args.query:
            return {
                "best": None,
                "candidates": [],
                "detail": None,
                "english": None,
                "message": "No usable kakao road address, and query is empty. Provide query or kakao_place(s).",
                "meta": {"strategy": "B_juso_fallback_failed"},
            }

        res = address_service.resolve(
            query=args.query,
            hint_city=args.hint_city,
            max_candidates=args.max_candidates,
            include_detail=args.include_detail,
            detail_search_type=args.detail_search_type,
            dong_nm=args.dong_nm,
            include_english=args.include_english,
            english_count_per_page=args.english_count_per_page,
        ).to_dict()
        res["meta"] = {**(res.get("meta") or {}), "strategy": "B_juso_fallback", "input_used": args.query}
        return res