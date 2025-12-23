from __future__ import annotations

import os
from dataclasses import dataclass

from postcode_mcp.app.settings import Settings, get_settings
from postcode_mcp.infra.cache import Cache
from postcode_mcp.infra.http import HttpClient
from postcode_mcp.infra.providers.juso import JusoProvider
from postcode_mcp.infra.providers.juso_detail import JusoDetailProvider
from postcode_mcp.infra.providers.juso_eng import JusoEnglishProvider
from postcode_mcp.services.postcode_service import PostcodeService
from postcode_mcp.services.address_service import AddressService


@dataclass(frozen=True)
class Container:
    settings: Settings
    cache: Cache
    http: HttpClient
    juso: JusoProvider
    juso_detail: JusoDetailProvider | None
    juso_english: JusoEnglishProvider | None
    postcode_service: PostcodeService
    address_service: AddressService


def build_container() -> Container:
    settings = get_settings()

    cache = Cache(maxsize=settings.cache_maxsize, ttl_seconds=settings.cache_ttl_seconds)
    http = HttpClient(timeout_seconds=settings.http_timeout_seconds, user_agent=settings.http_user_agent)

    juso = JusoProvider(
        http=http,
        confm_key=settings.juso_road_key,
        count_per_page=settings.juso_count_per_page,
        first_sort=settings.juso_first_sort,
        add_info_yn=settings.juso_add_info_yn,
        cache=cache,
    )

    juso_detail = None
    if settings.juso_detail_key:
        juso_detail = JusoDetailProvider(http=http, confm_key=settings.juso_detail_key, timeout_seconds=settings.http_timeout_seconds)

    # English provider (키 + URL 둘 다 있어야 활성)
    juso_english = None
    eng_url = (os.getenv("JUSO_ENG_API_URL") or "").strip()
    if settings.juso_eng_key and eng_url:
        juso_english = JusoEnglishProvider(
            http=http,
            confm_key=settings.juso_eng_key,
            count_per_page=settings.juso_count_per_page,
            first_sort=settings.juso_first_sort,
            add_info_yn=settings.juso_add_info_yn,
            api_url=eng_url,
            timeout_seconds=settings.http_timeout_seconds,
            cache=cache,
        )

    postcode_service = PostcodeService(juso=juso)
    address_service = AddressService(
        postcode_service=postcode_service,
        detail_provider=juso_detail,
        english_provider=juso_english,
    )

    return Container(
        settings=settings,
        cache=cache,
        http=http,
        juso=juso,
        juso_detail=juso_detail,
        juso_english=juso_english,
        postcode_service=postcode_service,
        address_service=address_service,
    )
