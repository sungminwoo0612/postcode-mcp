from __future__ import annotations

import os

import pytest

# NOTE:
# - 실제 JUSO API 호출 테스트는 키가 필요하고 네트워크에 의존하므로 "스모크" 위주로 둠.
# - CI에서는 키가 없으면 네트워크 테스트를 스킵.


def _has_juso_key() -> bool:
    return bool(os.getenv("JUSO_ROAD_KEY") or os.getenv("JUSO_CONFM_KEY"))


def test_import_server():
    import postcode_mcp.server  # noqa: F401


@pytest.mark.skipif(not _has_juso_key(), reason="No JUSO_ROAD_KEY/JUSO_CONFM_KEY in env")
def test_live_resolve_smoke():
    from postcode_mcp.app.container import build_container

    c = build_container()
    r = c.postcode_service.resolve(query="경기도 수원시 팔달구 효원로 241", hint_city="수원", max_candidates=3)
    assert r.best is not None
    assert r.best.postcode5 and len(r.best.postcode5) == 5


@pytest.mark.skipif(not _has_juso_key(), reason="No JUSO_ROAD_KEY/JUSO_CONFM_KEY in env")
def test_live_resolve_suwon_cityhall():
    from postcode_mcp.app.container import build_container

    c = build_container()
    res = c.postcode_service.resolve(query="수원시청", hint_city="수원", max_candidates=3)

    assert res.best is not None
    assert res.best.postcode5 and len(res.best.postcode5) == 5
    assert res.candidates, "Expected at least one candidate for 수원시청"