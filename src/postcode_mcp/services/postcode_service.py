from __future__ import annotations

from postcode_mcp.core.models import AddressCandidate, ResolveResult
from postcode_mcp.infra.providers.juso import JusoProvider


class PostcodeService:
    def __init__(self, *, juso: JusoProvider) -> None:
        self._juso = juso

    def resolve(
        self, *, query: str, hint_city: str | None = None, max_candidates: int = 5
    ) -> ResolveResult:
        """
        주소 검색을 수행하고 결과를 반환합니다.

        Args:
            query: 검색어 (주소 또는 장소명)
            hint_city: 도시 힌트 (예: "수원", "서울") - 스코어링에 사용
            max_candidates: 최대 후보 개수

        Returns:
            ResolveResult 객체
        """
        # JusoProvider를 통해 검색
        candidates = self._juso.search(query, max_results=max_candidates)

        if not candidates:
            return ResolveResult(
                best=None,
                candidates=[],
                message=f"'{query}'에 대한 검색 결과가 없습니다.",
            )

        # hint_city가 있으면 스코어링 적용
        if hint_city:
            candidates = self._score_by_city(candidates, hint_city)

        # best는 첫 번째 후보
        best = candidates[0] if candidates else None

        return ResolveResult(
            best=best,
            candidates=candidates[:max_candidates],
            message=None,
        )

    def _score_by_city(self, candidates: list[AddressCandidate], hint_city: str) -> list[AddressCandidate]:
        """
        hint_city를 기반으로 후보를 스코어링하고 정렬합니다.
        """
        hint_city = hint_city.strip().lower()

        def score(candidate: AddressCandidate) -> float:
            # road_addr에서 도시명 매칭
            road_addr_lower = candidate.road_addr.lower()
            if hint_city in road_addr_lower:
                # 도시명이 포함된 경우 원래 confidence 유지
                return candidate.confidence
            else:
                # 도시명이 없는 경우 confidence 감소
                return candidate.confidence * 0.5

        # 스코어링 후 정렬
        scored = [(score(c), c) for c in candidates]
        scored.sort(key=lambda x: x[0], reverse=True)

        return [c for _, c in scored]
