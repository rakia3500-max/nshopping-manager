# -*- coding: utf-8 -*-
"""
[P6] utils/brand.py -- 브랜드 감지 / 이름 정규화 공통 모듈

이 파일 하나를 수정하면 streamlit_app.py와 main_automation.py 양쪽에
동일한 로직이 적용됩니다.
"""

from __future__ import annotations


# ── 기본 브랜드 정의 (환경변수/Streamlit secrets로 오버라이드 가능) ──────────
DEFAULT_MY_BRAND_1 = "드론박스, DroneBox, DJI 정품판매점 드론박스"
DEFAULT_MY_BRAND_2 = "빛드론, Bit-Drone, Bit Drone, BITDRONE"
DEFAULT_COMPETITORS = "다다사, dadasa, 효로로, 드론뷰"


def _clean(text: str) -> str:
    """공백 제거 + 소문자 변환 (비교 전처리)"""
    return text.replace(" ", "").lower()


def parse_brand_list(brand_str: str) -> list[str]:
    """쉼표 구분 브랜드 문자열을 리스트로 변환"""
    return [x.strip() for x in brand_str.split(",") if x.strip()]


def normalize_mall_name(
    raw_mall: str,
    brand1_str: str = DEFAULT_MY_BRAND_1,
    brand2_str: str = DEFAULT_MY_BRAND_2,
    competitors_str: str = DEFAULT_COMPETITORS,
) -> str:
    """
    쇼핑몰 원시 이름을 정규화된 대표 이름으로 변환.

    예) "DJI온라인판매점드론박스" -> "드론박스"
        "효로로드론샵" -> "효로로"
        "알수없는몰" -> "알수없는몰" (그대로)
    """
    if not isinstance(raw_mall, str):
        return raw_mall

    cm = _clean(raw_mall)

    t_db = [_clean(x) for x in parse_brand_list(brand1_str)]
    t_bit = [_clean(x) for x in parse_brand_list(brand2_str)]
    t_comp = [_clean(x) for x in parse_brand_list(competitors_str)]

    if any(x in cm for x in t_db):
        return "드론박스"
    if any(x in cm for x in t_bit):
        return "빛드론"
    # 경쟁사는 원본 문자열에서 키워드 포함 여부로 매핑
    for comp_raw in parse_brand_list(competitors_str):
        if _clean(comp_raw) in cm:
            return comp_raw
    return raw_mall


def is_my_brand(
    mall_name: str,
    brand1_str: str = DEFAULT_MY_BRAND_1,
    brand2_str: str = DEFAULT_MY_BRAND_2,
) -> bool:
    """자사 브랜드(브랜드1 또는 브랜드2) 여부 반환"""
    cm = _clean(mall_name)
    t_db = [_clean(x) for x in parse_brand_list(brand1_str)]
    t_bit = [_clean(x) for x in parse_brand_list(brand2_str)]
    return any(x in cm for x in t_db + t_bit)


def is_brand1(mall_name: str, brand1_str: str = DEFAULT_MY_BRAND_1) -> bool:
    cm = _clean(mall_name)
    return any(_clean(x) in cm for x in parse_brand_list(brand1_str))


def is_brand2(mall_name: str, brand2_str: str = DEFAULT_MY_BRAND_2) -> bool:
    cm = _clean(mall_name)
    return any(_clean(x) in cm for x in parse_brand_list(brand2_str))


def is_competitor(mall_name: str, competitors_str: str = DEFAULT_COMPETITORS) -> bool:
    """경쟁사 여부 반환"""
    cm = _clean(mall_name)
    return any(_clean(x) in cm for x in parse_brand_list(competitors_str))


def get_mall_label(
    mall_name: str,
    brand1_str: str = DEFAULT_MY_BRAND_1,
    brand2_str: str = DEFAULT_MY_BRAND_2,
    competitors_str: str = DEFAULT_COMPETITORS,
) -> str:
    """
    대시보드 표시용 레이블 반환.
    자사: "드론박스" / "빛드론"
    경쟁사: 해당 이름
    기타: "기타"
    """
    if is_brand1(mall_name, brand1_str):
        return "드론박스"
    if is_brand2(mall_name, brand2_str):
        return "빛드론"
    if is_competitor(mall_name, competitors_str):
        return normalize_mall_name(mall_name, brand1_str, brand2_str, competitors_str)
    return "기타"
