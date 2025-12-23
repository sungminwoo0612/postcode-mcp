from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AddressCandidate:
    road_addr: str
    jibun_addr: str | None
    postcode5: str
    building_name: str | None
    confidence: float

    # detail lookup keys (addrDetailApi 필수 재료)
    admCd: str | None = None
    rnMgtSn: str | None = None
    udrtYn: str | None = None
    buldMnnm: str | None = None
    buldSlno: str | None = None
    bdMgtSn: str | None = None

    # optional (검색API가 제공하면 같이 보관)
    engAddr: str | None = None


@dataclass(frozen=True)
class ResolveResult:
    best: AddressCandidate | None
    candidates: list[AddressCandidate]
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        def c_to_dict(c: AddressCandidate) -> dict[str, Any]:
            return {
                "road_addr": c.road_addr,
                "jibun_addr": c.jibun_addr,
                "postcode5": c.postcode5,
                "building_name": c.building_name,
                "confidence": c.confidence,
                
                # detail keys
                "admCd": c.admCd,
                "rnMgtSn": c.rnMgtSn,
                "udrtYn": c.udrtYn,
                "buldMnnm": c.buldMnnm,
                "buldSlno": c.buldSlno,
                "bdMgtSn": c.bdMgtSn,
                
                # optional
                "engAddr": c.engAddr,
            }

        return {
            "best": c_to_dict(self.best) if self.best else None,
            "candidates": [c_to_dict(c) for c in self.candidates],
            "message": self.message,
        }
