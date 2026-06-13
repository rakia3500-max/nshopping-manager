# -*- coding: utf-8 -*-
"""
[INTENT] 키워드 검색 의도 분류 + 콘텐츠 제안
=============================================
수집 키워드를 정보형/비교형/거래형으로 분류하고,
정보형·비교형 키워드는 블로그/가이드 콘텐츠 주제로 연결한다.
→ "순위 추적"이 "콘텐츠 기획"으로 이어지는 루프.
"""
from __future__ import annotations

from integrations.schema_gen import parse_gemini_json

INTENT_LABELS = ["정보형", "비교형", "거래형"]

INTENT_PROMPT = """당신은 이커머스 SEO 전략가입니다. 아래 네이버 쇼핑 키워드들의 검색 의도를 분류하세요.

[키워드 목록]
{keywords}

[분류 기준]
- 정보형: 지식/방법을 찾는 의도 (예: "드론 자격증 취득 방법") → 블로그/가이드 콘텐츠 타겟
- 비교형: 선택지를 비교하는 의도 (예: "미니4프로 vs 에어3") → 비교 리뷰 콘텐츠 타겟
- 거래형: 구매 직전 의도 (예: "DJI 미니4프로 최저가") → 상품 페이지/광고 타겟

[작성 규칙]
1. 모든 키워드를 빠짐없이 분류
2. intent는 반드시 "정보형", "비교형", "거래형" 중 하나
3. suggestion: 정보형/비교형은 구체적 콘텐츠 제목 1개 제안(드론 전문몰 관점),
   거래형은 "상품페이지 최적화" 또는 "광고 입찰 검토"로 표기
4. confidence: 분류 확신도 (높음/중간/낮음)

[출력 형식 — 반드시 준수]
다른 설명 없이 아래 JSON 배열만 출력:
[{{"keyword": "...", "intent": "...", "suggestion": "...", "confidence": "..."}}, ...]"""


def classify_keywords(generate_fn, keywords: list[str]):
    """키워드 목록 → 인텐트 분류 결과. Returns (list | None, 오류 메시지)"""
    kws = [k.strip() for k in keywords if k.strip()]
    if not kws:
        return None, "키워드가 비어 있습니다."
    if len(kws) > 60:
        kws = kws[:60]  # 토큰 한도 보호
    try:
        raw = generate_fn(INTENT_PROMPT.format(keywords="\n".join(f"- {k}" for k in kws)))
    except Exception as e:
        return None, f"Gemini 호출 실패: {e}"
    data = parse_gemini_json(raw)
    if not isinstance(data, list):
        return None, "AI 응답을 JSON으로 해석하지 못했습니다. 다시 시도해주세요."
    cleaned = []
    for x in data:
        if not isinstance(x, dict):
            continue
        kw = str(x.get("keyword", "")).strip()
        intent = str(x.get("intent", "")).strip()
        if kw and intent in INTENT_LABELS:
            cleaned.append({
                "keyword": kw, "intent": intent,
                "suggestion": str(x.get("suggestion", "")).strip(),
                "confidence": str(x.get("confidence", "중간")).strip(),
            })
    if not cleaned:
        return None, "유효한 분류 결과가 없습니다."
    return cleaned, ""
