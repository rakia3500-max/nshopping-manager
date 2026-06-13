# -*- coding: utf-8 -*-
"""
[SCHEMA] JSON-LD 스키마 생성기 + 리뷰→FAQ 변환기 (GEO/AEO 도구)
================================================================
- 스키마 구조 생성은 순수 파이썬 (결정적 — AI 환각 없이 Schema.org 규격 준수)
- 리뷰→FAQ 변환만 Gemini 사용 (콘텐츠 생성), 출력은 strict JSON 강제 후 파싱
- 생성물: ① JSON-LD <script> 태그 (자사몰/블로그 <head> 삽입용)
          ② AEO 형식 HTML FAQ 블록 (질문형 헤딩 + 40~60자 직접 답변)
"""
from __future__ import annotations

import json
import re
import logging

log = logging.getLogger(__name__)

SCHEMA_CONTEXT = "https://schema.org"


# ════════════════════════════════════════════════════════════════════════════
# 1. JSON-LD 빌더 (순수 파이썬 — 결정적)
# ════════════════════════════════════════════════════════════════════════════
def build_product_schema(
    name: str,
    description: str = "",
    brand: str = "",
    price: float | str = "",
    currency: str = "KRW",
    url: str = "",
    image: str = "",
    sku: str = "",
    availability: str = "InStock",
    rating_value: float | str = "",
    review_count: int | str = "",
) -> dict:
    """Product + Offer (+ AggregateRating) 스키마"""
    schema = {
        "@context": SCHEMA_CONTEXT,
        "@type": "Product",
        "name": name.strip(),
    }
    if description:
        schema["description"] = description.strip()
    if brand:
        schema["brand"] = {"@type": "Brand", "name": brand.strip()}
    if image:
        schema["image"] = [u.strip() for u in str(image).split(",") if u.strip()]
    if sku:
        schema["sku"] = str(sku).strip()
    if url:
        schema["url"] = url.strip()
    if price not in ("", None):
        schema["offers"] = {
            "@type": "Offer",
            "price": str(price).replace(",", "").strip(),
            "priceCurrency": currency,
            "availability": f"{SCHEMA_CONTEXT}/{availability}",
        }
        if url:
            schema["offers"]["url"] = url.strip()
    if rating_value not in ("", None) and review_count not in ("", None):
        schema["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": str(rating_value),
            "reviewCount": str(review_count),
        }
    return schema


def build_faq_schema(qa_list: list[dict]) -> dict:
    """FAQPage 스키마. qa_list: [{"q": 질문, "a": 답변}, ...]"""
    return {
        "@context": SCHEMA_CONTEXT,
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": qa["q"].strip(),
                "acceptedAnswer": {"@type": "Answer", "text": qa["a"].strip()},
            }
            for qa in qa_list
            if qa.get("q", "").strip() and qa.get("a", "").strip()
        ],
    }


def build_howto_schema(name: str, steps: list[str], total_time_min: int | str = "") -> dict:
    """HowTo 스키마. steps: 단계 텍스트 리스트"""
    schema = {
        "@context": SCHEMA_CONTEXT,
        "@type": "HowTo",
        "name": name.strip(),
        "step": [
            {"@type": "HowToStep", "position": i + 1, "text": s.strip()}
            for i, s in enumerate(steps)
            if s.strip()
        ],
    }
    if total_time_min not in ("", None, 0):
        schema["totalTime"] = f"PT{int(total_time_min)}M"
    return schema


def build_breadcrumb_schema(items: list[tuple[str, str]]) -> dict:
    """BreadcrumbList 스키마. items: [(이름, URL), ...] 순서대로"""
    return {
        "@context": SCHEMA_CONTEXT,
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "name": name.strip(),
                **({"item": url.strip()} if url.strip() else {}),
            }
            for i, (name, url) in enumerate(items)
            if name.strip()
        ],
    }


def to_script_tag(schema: dict) -> str:
    """<head>에 붙여넣을 <script type="application/ld+json"> 태그 생성"""
    body = json.dumps(schema, ensure_ascii=False, indent=2)
    return f'<script type="application/ld+json">\n{body}\n</script>'


def validate_schema(schema: dict) -> list[str]:
    """타입별 필수 항목 간이 검증. 문제 목록 반환 (빈 리스트 = 통과)"""
    issues = []
    t = schema.get("@type", "")
    if t == "Product":
        if not schema.get("name"):
            issues.append("Product: name 누락")
        if not schema.get("offers"):
            issues.append("Product: offers(가격) 없음 — 리치 결과 노출에 권장")
        if not schema.get("image"):
            issues.append("Product: image 없음 — 리치 결과 노출에 권장")
    elif t == "FAQPage":
        n = len(schema.get("mainEntity", []))
        if n == 0:
            issues.append("FAQPage: 질문이 없음")
        for i, q in enumerate(schema.get("mainEntity", []), 1):
            ans = q.get("acceptedAnswer", {}).get("text", "")
            if len(ans) < 20:
                issues.append(f"FAQPage: Q{i} 답변이 너무 짧음 (20자 미만)")
    elif t == "HowTo":
        if len(schema.get("step", [])) < 2:
            issues.append("HowTo: 단계가 2개 미만")
    elif t == "BreadcrumbList":
        if len(schema.get("itemListElement", [])) < 2:
            issues.append("BreadcrumbList: 항목이 2개 미만")
    return issues


# ════════════════════════════════════════════════════════════════════════════
# 2. AEO 형식 HTML FAQ 블록
# ════════════════════════════════════════════════════════════════════════════
def faq_to_html(qa_list: list[dict], title: str = "자주 묻는 질문") -> str:
    """
    AEO 적격 형식의 HTML FAQ 블록:
    질문형 <h3> + 직접 답변 첫 문장(40~60자 권장) 구조.
    상세페이지/블로그 본문에 삽입.
    """
    parts = [f'<section class="faq-section">', f"  <h2>{title}</h2>"]
    for qa in qa_list:
        q, a = qa.get("q", "").strip(), qa.get("a", "").strip()
        if not (q and a):
            continue
        parts.append(f"  <h3>{q}</h3>")
        parts.append(f"  <p>{a}</p>")
    parts.append("</section>")
    return "\n".join(parts)


# ════════════════════════════════════════════════════════════════════════════
# 3. 리뷰→FAQ 변환 (Gemini)
# ════════════════════════════════════════════════════════════════════════════
REVIEW_TO_FAQ_PROMPT = """당신은 이커머스 AEO(Answer Engine Optimization) 전문가입니다.
아래 [고객 리뷰/문의]를 분석해 실제 고객들이 궁금해하는 내용 기반의 FAQ를 만드세요.

[상품명]
{product}

[고객 리뷰/문의]
{reviews}

[작성 규칙]
1. 정확히 {n}개의 Q&A를 생성
2. 질문(q): 고객이 검색창이나 AI에 입력할 법한 자연스러운 질문형 문장 (예: "~인가요?", "~할 수 있나요?")
3. 답변(a): 첫 문장은 40~60자의 직접 답변(결론 먼저), 이어서 1~2문장 보충. 전체 80~200자
4. 리뷰에 실제로 언급된 내용만 사용 — 리뷰에 없는 사실을 지어내지 말 것
5. 리뷰에서 판단 불가한 내용은 답변에 "판매처 문의 권장"으로 표기
6. 과장 표현("최고", "완벽") 금지, 사실 위주

[출력 형식 — 반드시 준수]
다른 설명, 인사말, 마크다운 코드펜스 없이 아래 JSON 배열만 출력:
[{{"q": "질문", "a": "답변"}}, ...]"""


def parse_gemini_json(text: str):
    """Gemini 응답에서 JSON 추출 (코드펜스/전후 잡설 제거). 실패 시 None."""
    if not text:
        return None
    t = text.strip()
    # 코드펜스 제거
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t).strip()
    # 첫 [ 또는 { 부터 마지막 ] 또는 } 까지
    m = re.search(r"(\[.*\]|\{.*\})", t, re.DOTALL)
    if m:
        t = m.group(1)
    try:
        return json.loads(t)
    except json.JSONDecodeError as e:
        log.warning("[schema] Gemini JSON 파싱 실패: %s", e)
        return None


def reviews_to_faq(generate_fn, product: str, reviews_text: str, n: int = 10):
    """
    리뷰/문의 텍스트 → Q&A 리스트.
    Returns: (qa_list | None, 오류메시지 | "")
    """
    if not reviews_text.strip():
        return None, "리뷰 텍스트가 비어 있습니다."
    prompt = REVIEW_TO_FAQ_PROMPT.format(
        product=product.strip() or "(미지정)",
        reviews=reviews_text.strip()[:8000],  # 토큰 한도 보호
        n=n,
    )
    try:
        raw = generate_fn(prompt)
    except Exception as e:
        return None, f"Gemini 호출 실패: {e}"
    qa = parse_gemini_json(raw)
    if not isinstance(qa, list):
        return None, "AI 응답을 JSON으로 해석하지 못했습니다. 다시 시도해주세요."
    cleaned = [
        {"q": str(x.get("q", "")).strip(), "a": str(x.get("a", "")).strip()}
        for x in qa
        if isinstance(x, dict) and str(x.get("q", "")).strip() and str(x.get("a", "")).strip()
    ]
    if not cleaned:
        return None, "유효한 Q&A가 생성되지 않았습니다."
    return cleaned, ""
