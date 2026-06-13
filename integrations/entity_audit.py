# -*- coding: utf-8 -*-
"""
[ENTITY] 브랜드 엔티티 일관성 감사
===================================
AI 검색 엔진은 웹 전반에서 일관된 정보를 가진 '엔티티'를 더 신뢰하고 인용한다.
여러 채널(자사몰/블로그/스마트스토어/지도 등)에 흩어진 브랜드 정보가
일관적인지 점검한다.

- NAP(상호/주소/전화) 표기 통일 여부
- 브랜드명 표기 변형 탐지 (빛드론 vs 빛 드론 vs Bit-Drone)
- Organization/LocalBusiness 스키마(sameAs 포함) 생성 → 엔티티 인식 강화
모든 로직은 결정적(AI 불사용).
"""
from __future__ import annotations

import re
import json
import logging

from integrations.geo_audit import fetch_html, _strip_tags

log = logging.getLogger(__name__)

_PHONE_RE = re.compile(r"0\d{1,2}[-\s.]?\d{3,4}[-\s.]?\d{4}")
_BIZNO_RE = re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{5}\b")  # 사업자등록번호


def _norm_phone(p: str) -> str:
    return re.sub(r"[^\d]", "", p)


def _extract_nap(html: str):
    """페이지에서 전화/사업자번호/브랜드 표기 후보 추출"""
    text = _strip_tags(html)
    phones = {_norm_phone(p) for p in _PHONE_RE.findall(text)}
    biznos = {re.sub(r"[^\d]", "", b) for b in _BIZNO_RE.findall(text)}
    return phones, biznos, text


def _name_variants(text: str, brand_aliases: list[str]) -> set:
    """본문에 실제 등장한 브랜드 표기 변형 수집 (띄어쓰기/대소문자 차이 포함)"""
    found = set()
    for alias in brand_aliases:
        core = alias.replace(" ", "")
        # 글자 사이 공백 허용 패턴
        pat = re.compile(r"\s*".join(re.escape(c) for c in core), re.IGNORECASE)
        for m in pat.finditer(text):
            found.add(m.group(0).strip())
    return found


def audit_entity(urls: list[str], brand_aliases: list[str]) -> dict:
    """
    여러 채널 URL을 받아 NAP·브랜드 표기 일관성 점검.
    Returns: {channels: [...], issues: [...], summary: {...}}
    """
    channels, all_phones, all_biznos, all_names = [], set(), set(), set()
    for url in urls:
        u = url.strip()
        if not u:
            continue
        html, err = fetch_html(u)
        if err:
            channels.append({"url": u, "error": err})
            continue
        phones, biznos, text = _extract_nap(html)
        names = _name_variants(text, brand_aliases)
        all_phones |= phones
        all_biznos |= biznos
        all_names |= names
        channels.append({
            "url": u,
            "전화번호": ", ".join(_fmt_phone(p) for p in sorted(phones)) or "—",
            "사업자번호": ", ".join(sorted(biznos)) or "—",
            "브랜드 표기": ", ".join(sorted(names)) or "—",
        })

    issues = []
    valid_channels = [c for c in channels if "error" not in c]
    if len({c["전화번호"] for c in valid_channels if c["전화번호"] != "—"}) > 1:
        issues.append(("전화번호", f"채널별 전화번호 표기가 다릅니다: {sorted(all_phones)}"))
    if len(all_biznos) > 1:
        issues.append(("사업자번호", f"사업자번호가 채널별로 다릅니다: {sorted(all_biznos)}"))
    if len(all_names) > 1:
        issues.append(("브랜드 표기", f"브랜드명 표기 변형이 {len(all_names)}종 발견: {sorted(all_names)} "
                                  "— AI 엔진이 같은 엔티티로 인식하기 어려울 수 있습니다. 대표 표기 1개로 통일 권장."))

    return {
        "channels": channels,
        "issues": issues,
        "summary": {
            "점검 채널 수": len(valid_channels),
            "전화번호 종류": len(all_phones),
            "브랜드 표기 변형": len(all_names),
            "일관성": "양호" if not issues else f"개선 필요 ({len(issues)}건)",
        },
    }


def _fmt_phone(digits: str) -> str:
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    if len(digits) == 11:
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    return digits


def build_organization_schema(
    name: str, url: str = "", logo: str = "", phone: str = "",
    address: str = "", same_as: list[str] | None = None, local_business: bool = False,
) -> dict:
    """
    Organization 또는 LocalBusiness 스키마 생성.
    sameAs에 모든 채널 URL을 넣으면 AI 엔진이 동일 엔티티로 묶어 인식한다.
    """
    schema = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness" if local_business else "Organization",
        "name": name.strip(),
    }
    if url:
        schema["url"] = url.strip()
    if logo:
        schema["logo"] = logo.strip()
    if phone:
        schema["telephone"] = phone.strip()
    if address:
        schema["address"] = {"@type": "PostalAddress", "streetAddress": address.strip(),
                             "addressCountry": "KR"}
    sa = [s.strip() for s in (same_as or []) if s.strip()]
    if sa:
        schema["sameAs"] = sa
    return schema
