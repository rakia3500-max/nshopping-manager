# -*- coding: utf-8 -*-
"""
[GEO] AI 인용 점유율 트래커
============================
네이버 순위 추적의 GEO(Generative Engine Optimization) 버전.

소비자가 AI에게 물어볼 법한 질의("입문용 드론 추천해줘, 어디서 사?")를
Gemini에 보내고, 응답에 자사 브랜드(드론박스/빛드론)와 경쟁사가
인용되는지 + 몇 번째로 언급되는지를 기록한다.

- 브랜드 별칭 매칭은 utils/brand.py 와 동일한 전처리(공백 제거 + 소문자) 사용
- 결과는 auth 스프레드시트의 `geo_results` 시트에 누적 저장 (멀티유저: user_id 구분)
- Gemini 호출 함수는 외부에서 주입(generate_fn)받아 streamlit_app의
  _gemini_generate 를 그대로 재사용 (의존성 역전 -- 단독 테스트 가능)
"""
from __future__ import annotations

import time
import random
import logging
import datetime as dt

from utils.brand import parse_brand_list, _clean

log = logging.getLogger(__name__)

# ── 소비자 질의 시나리오 (필요 시 UI에서 커스텀 가능) ────────────────────────
DEFAULT_PROMPT_TEMPLATES = [
    ("추천", "{kw} 추천해줘. 한국에서 어디서 구매하는 게 좋을지 구체적인 온라인 쇼핑몰이나 판매처 이름도 함께 알려줘."),
    ("구매처", "한국에서 {kw} 구매하려고 하는데, 믿을 만한 판매점이나 쇼핑몰 이름을 알려줘. 공식 딜러나 전문점이 있으면 같이 알려줘."),
]


# ── 브랜드 그룹 구성 ─────────────────────────────────────────────────────────
def build_brand_groups(brand1_str: str, brand2_str: str, competitors_str: str) -> dict:
    """
    {대표이름: [별칭 리스트]} 형태로 변환.
    - 자사 2개 브랜드: 쉼표 목록 전체가 한 그룹 (첫 항목이 대표 이름)
    - 경쟁사: 각각 독립 그룹. 단, 한글 브랜드 바로 뒤에 오는 영문(ASCII) 표기는
      해당 브랜드의 별칭으로 묶임. 예) "다다사, dadasa, 효로로" → 다다사=[다다사, dadasa]
    """
    groups = {}
    b1 = parse_brand_list(brand1_str)
    b2 = parse_brand_list(brand2_str)
    if b1:
        groups[b1[0]] = b1  # 첫 항목을 대표 이름으로
    if b2:
        groups[b2[0]] = b2
    last_rep = None
    for comp in parse_brand_list(competitors_str):
        is_ascii = comp.isascii()
        if (is_ascii and last_rep is not None and not last_rep.isascii()):
            groups[last_rep].append(comp)  # 직전 한글 브랜드의 영문 별칭
        else:
            groups[comp] = [comp]
            last_rep = comp
    return groups


def _find_first_index(text_clean: str, aliases: list[str]) -> int:
    """전처리된 응답에서 별칭 중 가장 먼저 등장하는 위치. 없으면 -1."""
    best = -1
    for a in aliases:
        ac = _clean(a)
        if not ac:
            continue
        idx = text_clean.find(ac)
        if idx >= 0 and (best < 0 or idx < best):
            best = idx
    return best


def _extract_snippet(original_text: str, aliases: list[str], width: int = 90) -> str:
    """원문에서 별칭이 포함된 주변 문장 일부를 추출 (대소문자 무시)."""
    low = original_text.lower()
    for a in aliases:
        al = a.lower().strip()
        if not al:
            continue
        idx = low.find(al)
        if idx >= 0:
            start = max(0, idx - width // 3)
            end = min(len(original_text), idx + len(al) + width)
            snippet = original_text[start:end].replace("\n", " ").strip()
            return ("…" if start > 0 else "") + snippet + ("…" if end < len(original_text) else "")
    return ""


# ── 핵심: AI 인용 체크 실행 ──────────────────────────────────────────────────
def run_geo_check(
    generate_fn,
    keywords: list[str],
    brand1_str: str,
    brand2_str: str,
    competitors_str: str,
    prompt_templates=None,
    progress_cb=None,
    sleep_range=(0.6, 1.4),
):
    """
    Parameters
    ----------
    generate_fn : Callable[[str], str]
        프롬프트를 받아 AI 응답 텍스트를 반환하는 함수 (예: _gemini_generate 래퍼)
    keywords : 검사할 키워드 목록
    progress_cb : Callable[[done:int, total:int, msg:str], None] -- UI 진행 표시용

    Returns
    -------
    (rows, errors)
        rows  : 롱 포맷 결과. (date, keyword, prompt_type, brand, mentioned,
                mention_order, snippet) -- 키워드×프롬프트×브랜드당 1행
        errors: [(keyword, prompt_type, 오류메시지), ...]
    """
    templates = prompt_templates or DEFAULT_PROMPT_TEMPLATES
    groups = build_brand_groups(brand1_str, brand2_str, competitors_str)
    today = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=9)).strftime("%Y-%m-%d")
    run_at = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")

    rows, errors = [], []
    total = len(keywords) * len(templates)
    done = 0

    for kw in keywords:
        for ptype, tmpl in templates:
            done += 1
            if progress_cb:
                progress_cb(done, total, f"'{kw}' · {ptype} 질의 중…")
            try:
                answer = generate_fn(tmpl.format(kw=kw))
            except Exception as e:
                log.warning("[geo] '%s'(%s) 질의 실패: %s", kw, ptype, e)
                errors.append((kw, ptype, str(e)[:200]))
                continue

            clean = _clean(answer or "")
            # 브랜드별 최초 등장 위치 → 언급 순서 산출
            positions = {name: _find_first_index(clean, aliases) for name, aliases in groups.items()}
            mentioned_sorted = sorted(
                [(n, p) for n, p in positions.items() if p >= 0], key=lambda x: x[1]
            )
            order_map = {n: i + 1 for i, (n, _p) in enumerate(mentioned_sorted)}

            for name, aliases in groups.items():
                hit = positions[name] >= 0
                rows.append({
                    "run_at": run_at,
                    "date": today,
                    "keyword": kw,
                    "prompt_type": ptype,
                    "brand": name,
                    "mentioned": 1 if hit else 0,
                    "mention_order": order_map.get(name, 0),
                    "snippet": _extract_snippet(answer, aliases) if hit else "",
                })
            time.sleep(random.uniform(*sleep_range))

    return rows, errors


# ── 집계: 일자별 브랜드 인용률 ───────────────────────────────────────────────
def compute_share(df):
    """
    롱 포맷 결과 → 일자별 브랜드 인용률(%) 데이터프레임.
    인용률 = 해당 일자 전체 질의(키워드×프롬프트) 중 브랜드가 언급된 비율.
    반환 컬럼: date, brand, queries, mentions, share
    """
    import pandas as pd
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=["date", "brand", "queries", "mentions", "share"])
    d = df.copy()
    d["mentioned"] = pd.to_numeric(d["mentioned"], errors="coerce").fillna(0).astype(int)
    d["_q"] = d["keyword"].astype(str) + "|" + d["prompt_type"].astype(str)
    q_per_day = d.groupby("date")["_q"].nunique().rename("queries")
    m = d.groupby(["date", "brand"])["mentioned"].sum().rename("mentions").reset_index()
    out = m.merge(q_per_day, on="date")
    out["share"] = (out["mentions"] / out["queries"] * 100).round(1)
    return out


# ── Google Sheets 영속화 (auth 스프레드시트 재사용) ──────────────────────────
GEO_HEADERS = ["user_id", "run_at", "date", "keyword", "prompt_type",
               "brand", "mentioned", "mention_order", "snippet"]

_ws_geo = None


def get_geo_sheet():
    """`geo_results` 워크시트 핸들 (없으면 생성)."""
    global _ws_geo
    if _ws_geo is None:
        from auth.db import get_spreadsheet
        import gspread
        ss = get_spreadsheet()
        try:
            _ws_geo = ss.worksheet("geo_results")
        except gspread.WorksheetNotFound:
            log.info("[geo] 'geo_results' 시트 생성")
            _ws_geo = ss.add_worksheet(title="geo_results", rows=2000, cols=len(GEO_HEADERS))
            _ws_geo.append_row(GEO_HEADERS, value_input_option="RAW")
    return _ws_geo


def save_geo_results(user_id, rows) -> bool:
    """결과를 시트에 일괄 append. 성공 여부 반환 (실패해도 앱은 계속 동작)."""
    if not rows:
        return False
    try:
        ws = get_geo_sheet()
        payload = [[str(user_id)] + [str(r.get(h, "")) for h in GEO_HEADERS[1:]] for r in rows]
        ws.append_rows(payload, value_input_option="RAW")
        log.info("[geo] %d행 저장 완료 (user=%s)", len(payload), user_id)
        return True
    except Exception as e:
        log.warning("[geo] 시트 저장 실패: %s", e)
        return False


def load_geo_history(user_id, days: int = 90):
    """
    해당 사용자의 GEO 이력 로드.
    같은 날 재실행 시 run_at 기준 최신 실행만 남긴다 (append-only 설계).
    """
    import pandas as pd
    try:
        ws = get_geo_sheet()
        records = ws.get_all_records()
    except Exception as e:
        log.warning("[geo] 시트 로드 실패: %s", e)
        return pd.DataFrame(columns=GEO_HEADERS)

    df = pd.DataFrame(records)
    if df.empty or "user_id" not in df.columns:
        return pd.DataFrame(columns=GEO_HEADERS)
    df = df[df["user_id"].astype(str) == str(user_id)].copy()
    if df.empty:
        return df

    cutoff = ((dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=9))
              - dt.timedelta(days=days)).strftime("%Y-%m-%d")
    df = df[df["date"].astype(str) >= cutoff]
    # 동일 (date, keyword, prompt, brand) 중복 → 최신 run_at만 유지
    df = (df.sort_values("run_at")
            .drop_duplicates(subset=["date", "keyword", "prompt_type", "brand"], keep="last"))
    df["mentioned"] = pd.to_numeric(df["mentioned"], errors="coerce").fillna(0).astype(int)
    df["mention_order"] = pd.to_numeric(df["mention_order"], errors="coerce").fillna(0).astype(int)
    return df.reset_index(drop=True)
