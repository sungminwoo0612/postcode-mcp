from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    # Juso keys
    juso_road_key: str
    juso_detail_key: str | None
    juso_eng_key: str | None
    # juso_confm_key: str

    # Juso common params
    juso_count_per_page: int
    juso_first_sort: str
    juso_add_info_yn: str

    # Cache
    cache_ttl_seconds: int
    cache_maxsize: int

    # HTTP
    http_timeout_seconds: float
    http_user_agent: str


def _clean(s: str | None) -> str:
    return (s or "").strip().strip('"').strip("'")


def _int(name: str, default: int) -> int:
    v = _clean(os.getenv(name, str(default)))
    return int(v)


def _float(name: str, default: float) -> float:
    v = _clean(os.getenv(name, str(default)))
    return float(v)


def get_settings() -> Settings:
    """
    키 분리 + 하위호환:
    - JUSO_ROAD_KEY가 있으면 그걸 사용
    - 없으면 기존 JUSO_CONFM_KEY를 ROAD 키로 사용(호환)
    """
    road_key = _clean(os.getenv("JUSO_ROAD_KEY"))
    legacy_key = _clean(os.getenv("JUSO_CONFM_KEY"))
    if not road_key:
        road_key = legacy_key

    if not road_key:
        raise RuntimeError(
            "Missing JUSO_ROAD_KEY (or legacy JUSO_CONFM_KEY) in environment (.env)."
        )

    detail_key = _clean(os.getenv("JUSO_DETAIL_KEY")) or None
    eng_key = _clean(os.getenv("JUSO_ENG_KEY")) or None

    return Settings(
        # keys
        juso_road_key=road_key,
        juso_detail_key=detail_key,
        juso_eng_key=eng_key,
        # common params
        juso_count_per_page=_int("JUSO_COUNT_PER_PAGE", 10),
        juso_first_sort=_clean(os.getenv("JUSO_FIRST_SORT", "none")),
        juso_add_info_yn=_clean(os.getenv("JUSO_ADD_INFO_YN", "Y")),
        # cache
        cache_ttl_seconds=_int("POSTCODE_CACHE_TTL_SECONDS", 60 * 60 * 24 * 7),
        cache_maxsize=_int("POSTCODE_CACHE_MAXSIZE", 20000),
        # http
        http_timeout_seconds=_float("HTTP_TIMEOUT_SECONDS", 10.0),
        http_user_agent=_clean(os.getenv("HTTP_USER_AGENT", "postcode-mcp/0.1.0")),
    )

if __name__ == "__main__":
    settings = get_settings()
    print(f"DEBUG: juso_eng_key = {settings.juso_eng_key}")
    print(f"DEBUG: JUSO_ENG_KEY env = {os.getenv('JUSO_ENG_KEY')}")
    print(f"DEBUG: JUSO_ENG_API_URL env = {os.getenv('JUSO_ENG_API_URL')}")