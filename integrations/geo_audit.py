# -*- coding: utf-8 -*-
"""
[GEO-AUDIT] 상세페이지 GEO 진단 + AI 크롤러 접근성 점검
========================================================
- audit_html()  : 페이지 HTML을 GEO 관점 6개 신호로 점수화 (AI 불사용 — 결정적)
    사실 밀도 / 구조화 데이터(JSON-LD) / FAQ·질문형 헤딩 / 메타·OG / 이미지 alt / 콘텐츠 분량
- compare 용도  : 자사 vs 경쟁사 URL을 같은 기준으로 채점해 상대 평가
- check_ai_crawlers(): robots.txt에서 주요 AI 크롤러 허용 여부 + llms.txt 존재 점검
"""
from __future__ import annotations

import re
import json
import logging
from urllib.parse import urlparse

import requests

log = logging.getLogger(__name__)

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_MAX_BYTES = 1_500_000

# 사실 밀도: 숫자+단위 패턴 (스펙·수치 인용 가능성)
_FACT_RE = re.compile(
    r"\d[\d,\.]*\s?(?:g|kg|mm|cm|km|m|분|초|시간|일|mAh|Wh|W|원|만원|%|GB|TB|MP|화소|인치|"
    r"fps|Mbps|GHz|개월|년|배|단계|축|매|장|회|점)\b", re.IGNORECASE)
# 질문형 헤딩 패턴
_QHEAD_RE = re.compile(r"(\?|인가요|일까요|할까요|어떻게|무엇|왜\s|방법은|차이는|얼마나)")

AI_CRAWLERS = [
    ("GPTBot", "ChatGPT 학습/검색"),
    ("OAI-SearchBot", "ChatGPT Search"),
    ("ClaudeBot", "Claude"),
    ("anthropic-ai", "Anthropic 학습"),
    ("PerplexityBot", "Perplexity"),
    ("Google-Extended", "Gemini 학습"),
    ("CCBot", "Common Crawl"),
    ("Bytespider", "ByteDance"),
]


def fetch_html(url: str) -> tuple[str, str]:
    """URL의 HTML 반환. Returns (html, error). 실패 시 html=''."""
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    try:
        r = requests.get(url, headers={"User-Agent": _UA}, timeout=15, stream=True)
        if r.status_code != 200:
            return "", f"HTTP {r.status_code}"
        chunks, size = [], 0
        for c in r.iter_content(65536):
            chunks.append(c)
            size += len(c)
            if size > _MAX_BYTES:
                break
        enc = r.encoding or "utf-8"
        return b"".join(chunks).decode(enc, errors="replace"), ""
    except Exception as e:
        return "", f"{type(e).__name__}: {e}"


def _strip_tags(html: str) -> str:
    html = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", html, flags=re.I)
    return re.sub(r"<[^>]+>", " ", html)


def _extract_jsonld_types(html: str) -> list[str]:
    types = []
    for m in re.finditer(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>',
                         html, re.IGNORECASE):
        try:
            data = json.loads(m.group(1).strip())
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for it in items:
            if isinstance(it, dict):
                t = it.get("@type")
                if isinstance(t, list):
                    types.extend(str(x) for x in t)
                elif t:
                    types.append(str(t))
                # @graph 구조 지원
                for g in it.get("@graph", []) or []:
                    if isinstance(g, dict) and g.get("@type"):
                        types.append(str(g["@type"]))
    return types


def audit_html(html: str, url: str = "") -> dict:
    """HTML → GEO 신호 측정값 + 영역별 점수(각 0~100)"""
    text = _strip_tags(html)
    text_len = len(re.sub(r"\s+", "", text))

    # 1) 사실 밀도 (1,000자당 수치+단위 개수)
    facts = len(_FACT_RE.findall(text))
    fact_density = round(facts / max(text_len, 1) * 1000, 1)

    # 2) 구조화 데이터
    ld_types = _extract_jsonld_types(html)
    has_product = any("Product" in t for t in ld_types)
    has_faq = any("FAQPage" in t for t in ld_types)

    # 3) 헤딩 구조 + 질문형 헤딩
    h1 = len(re.findall(r"<h1[\s>]", html, re.I))
    h23 = re.findall(r"<h[23][^>]*>([\s\S]*?)</h[23]>", html, re.I)
    q_heads = sum(1 for h in h23 if _QHEAD_RE.search(_strip_tags(h)))
    faq_text = bool(re.search(r"자주\s*묻는\s*질문|FAQ", text, re.I))

    # 4) 메타/OG
    title_m = re.search(r"<title[^>]*>([\s\S]*?)</title>", html, re.I)
    title = _strip_tags(title_m.group(1)).strip() if title_m else ""
    meta_desc = bool(re.search(r'<meta[^>]+name=["\']description["\']', html, re.I))
    og = len(re.findall(r'<meta[^>]+property=["\']og:(?:title|description|image)["\']', html, re.I))

    # 5) 이미지 alt 비율
    imgs = re.findall(r"<img\b[^>]*>", html, re.I)
    alts = sum(1 for i in imgs if re.search(r'alt=["\'][^"\']+["\']', i, re.I))
    alt_ratio = round(alts / len(imgs) * 100) if imgs else 0

    scores = {
        "사실 밀도": min(100, int(fact_density * 8)),                      # 12.5/1000자 이상 = 만점
        "구조화 데이터": min(100, (50 if has_product else 0) + (35 if has_faq else 0)
                          + min(15, len(ld_types) * 5)),
        "FAQ·답변형 구조": min(100, (40 if (has_faq or faq_text) else 0) + q_heads * 20),
        "메타·OG": min(100, (30 if 20 <= len(title) <= 70 else (15 if title else 0))
                       + (30 if meta_desc else 0) + og * 13 + (10 if h1 == 1 else 0)),
        "이미지 접근성": alt_ratio,
        "콘텐츠 분량": min(100, int(text_len / 30)),                       # 3,000자 이상 = 만점
    }
    total = round(sum(scores.values()) / len(scores))

    return {
        "url": url, "total": total, "scores": scores,
        "detail": {
            "본문 글자 수": f"{text_len:,}", "수치·스펙 개수": facts,
            "사실 밀도(1천자당)": fact_density,
            "JSON-LD 타입": ", ".join(sorted(set(ld_types))) or "없음",
            "질문형 헤딩": q_heads, "FAQ 블록": "있음" if (has_faq or faq_text) else "없음",
            "title": (title[:60] + "…") if len(title) > 60 else (title or "없음"),
            "meta description": "있음" if meta_desc else "없음",
            "OG 태그": f"{og}/3", "이미지 alt": f"{alt_ratio}% ({alts}/{len(imgs)})",
        },
    }


def audit_url(url: str) -> tuple[dict | None, str]:
    html, err = fetch_html(url)
    if err:
        return None, err
    return audit_html(html, url), ""


# ── AI 크롤러 접근성 점검 ────────────────────────────────────────────────────
def check_ai_crawlers(site_url: str) -> dict:
    """robots.txt의 AI 크롤러 허용 여부 + llms.txt 존재 점검"""
    if not site_url.lower().startswith(("http://", "https://")):
        site_url = "https://" + site_url
    p = urlparse(site_url)
    base = f"{p.scheme}://{p.netloc}"
    out = {"base": base, "robots_found": False, "crawlers": [], "llms_txt": False, "error": ""}

    try:
        r = requests.get(f"{base}/robots.txt", headers={"User-Agent": _UA}, timeout=10)
        robots = r.text if r.status_code == 200 else ""
        out["robots_found"] = bool(robots)
    except Exception as e:
        robots = ""
        out["error"] = f"robots.txt 조회 실패: {e}"

    # robots.txt 파싱: 연속된 User-agent 줄은 같은 규칙 그룹 공유 (표준 동작)
    groups, current_uas, last_was_ua = {}, [], False
    for line in robots.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        m_ua = re.match(r"user-agent\s*:\s*(.+)", line, re.I)
        if m_ua:
            ua = m_ua.group(1).strip().lower()
            current_uas = current_uas + [ua] if last_was_ua else [ua]
            groups.setdefault(ua, [])
            last_was_ua = True
            continue
        m_rule = re.match(r"(dis)?allow\s*:\s*(.*)", line, re.I)
        if m_rule and current_uas:
            for ua in current_uas:
                groups[ua].append((bool(m_rule.group(1)), m_rule.group(2).strip()))
        last_was_ua = False

    def _verdict(bot: str) -> str:
        rules = groups.get(bot.lower()) or groups.get("*") or []
        blocked_all = any(dis and path == "/" for dis, path in rules)
        if not out["robots_found"]:
            return "허용(robots 없음)"
        if blocked_all:
            return "전체 차단"
        if any(dis for dis, _ in rules):
            return "부분 차단"
        return "허용"

    for bot, desc in AI_CRAWLERS:
        out["crawlers"].append({"bot": bot, "용도": desc, "상태": _verdict(bot)})

    try:
        r = requests.get(f"{base}/llms.txt", headers={"User-Agent": _UA}, timeout=10)
        out["llms_txt"] = (r.status_code == 200 and len(r.text.strip()) > 0
                           and "<html" not in r.text[:300].lower())
    except Exception:
        pass
    return out
