from __future__ import annotations

import re


_WS = re.compile(r"\s+")
_ZIP5 = re.compile(r"^\d{5}$")


def normalize_query(q: str) -> str:
    q = q.strip()
    q = _WS.sub(" ", q)
    return q


def normalize_postcode(zip_no: str) -> str:
    """
    Juso API는 보통 5자리 zipNo를 반환하지만,
    혹시 '162-47' 같이 들어오면 숫자만 추출해 5자리면 채택.
    """
    raw = (zip_no or "").strip()
    if _ZIP5.match(raw):
        return raw

    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) == 5:
        return digits
    return raw
