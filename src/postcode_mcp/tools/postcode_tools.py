from __future__ import annotations

from typing import Any

from fastmcp import FastMCP
from pydantic import BaseModel, Field, ValidationError as PydanticValidationError

from postcode_mcp.app.container import Container


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

    @mcp.tool(
        name="resolve_postcode_auto",
        description=(
            "장소명/주소 또는 카카오맵 place JSON을 받아 "
            "도로명주소/지번/5자리 우편번호를 찾고, 선택적으로 상세주소·영문주소까지 반환합니다. "
            "카카오 place가 있으면 우선 사용하고, 없으면 Juso 검색만으로 조회합니다."
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