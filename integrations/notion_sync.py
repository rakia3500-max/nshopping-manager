# -*- coding: utf-8 -*-
"""
Notion Database 연동 — 키워드별 일일 순위 요약 저장

저장 구조: 키워드 1개 = Notion 페이지 1개 (날짜별)
- 같은 날짜+키워드가 이미 있으면 덮어씀
- 원본 행 데이터가 아닌 키워드별 최저 순위(최고 성적) 집계값 저장
"""
import logging
import time
from datetime import datetime, timedelta

import pandas as pd

log = logging.getLogger(__name__)

# Notion Database 속성 스키마 (키워드 요약 구조)
_SCHEMA = {
    "Date":    {"date": {}},
    "Vol":     {"number": {"format": "number"}},
    "CTR":     {"number": {"format": "number"}},
    "DBRank":  {"number": {"format": "number"}},   # 드론박스 최고 순위
    "BIRank":  {"number": {"format": "number"}},   # 빛드론 최고 순위
    "DARank":  {"number": {"format": "number"}},   # 다다사 최고 순위
    "HRRank":  {"number": {"format": "number"}},   # 효로로 최고 순위
    "DVRank":  {"number": {"format": "number"}},   # 드론뷰 최고 순위
    "Top1Mall": {"rich_text": {}},                 # 1위 쇼핑몰
    "Top1Title":{"rich_text": {}},                 # 1위 상품명
    "IsMine":   {"checkbox": {}},
}


def _client(token):
    from notion_client import Client
    return Client(auth=token, log_level=logging.WARNING)


def ensure_schema(token, database_id):
    """없는 속성만 추가, 타이틀 컬럼을 'Keyword'로 자동 변경"""
    try:
        c = _client(token)
        db = c.databases.retrieve(database_id=database_id)
        existing = set(db["properties"].keys())

        props_update = {}

        # 타이틀 컬럼이 'Keyword'가 아니면 찾아서 이름 변경
        if "Keyword" not in existing:
            title_col = next(
                (k for k, v in db["properties"].items() if v.get("type") == "title"),
                None
            )
            if title_col:
                props_update[title_col] = {"name": "Keyword"}
                log.info("[notion] '%s' 컬럼 → 'Keyword' 이름 변경", title_col)

        for k, v in _SCHEMA.items():
            if k not in existing:
                props_update[k] = v

        if props_update:
            c.databases.update(database_id=database_id, properties=props_update)
            log.info("[notion] 스키마 업데이트 완료: %s", list(props_update.keys()))
    except Exception as e:
        log.warning("[notion] 스키마 확인 오류 (무시): %s", e)


def _delete_existing_pages(c, database_id, date_str):
    """같은 날짜의 기존 페이지 삭제 (덮어쓰기 구현)"""
    try:
        cursor = None
        while True:
            kwargs = dict(
                database_id=database_id,
                filter={"property": "Date", "date": {"equals": date_str}},
                page_size=100,
            )
            if cursor:
                kwargs["start_cursor"] = cursor
            resp = c.databases.query(**kwargs)
            for page in resp["results"]:
                c.pages.update(page["id"], archived=True)
                time.sleep(0.1)
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")
        log.info("[notion] %s 기존 데이터 삭제 완료", date_str)
    except Exception as e:
        log.warning("[notion] 기존 데이터 삭제 오류: %s", e)


def save_to_notion(df, date_str, token, database_id):
    """
    DataFrame → Notion Database 저장 (키워드별 요약 1건)

    - 같은 날짜 기존 페이지 먼저 삭제 후 재저장
    - is_mine(드론박스|빛드론) 행만 받아서 키워드별로 집계

    Returns:
        (success: bool, message: str)
    """
    if df is None or df.empty:
        return False, "저장할 데이터가 없습니다."
    if not token or not database_id:
        return False, "Notion Token 또는 Database ID가 설정되지 않았습니다."

    try:
        c = _client(token)
        ensure_schema(token, database_id)

        # 같은 날짜 기존 페이지 삭제
        _delete_existing_pages(c, database_id, date_str)

        # 키워드별 집계 (전체 df 기준 — Top1Mall은 경쟁사 포함)
        summary = {}
        for _, row in df.iterrows():
            kw = str(row.get("keyword", "")).strip()
            if not kw:
                continue
            rank = int(row.get("rank", 999))
            is_db  = bool(row.get("is_db",  False))
            is_bit = bool(row.get("is_bit", False))
            is_da  = bool(row.get("is_da",  False))
            is_hr  = bool(row.get("is_hr",  False))
            is_dv  = bool(row.get("is_dv",  False))

            if kw not in summary:
                summary[kw] = {
                    "vol": int(row.get("vol", 0)),
                    "ctr": float(row.get("ctr", 0)),
                    "db_rank": 999, "bi_rank": 999,
                    "da_rank": 999, "hr_rank": 999, "dv_rank": 999,
                    "top1_mall": "", "top1_title": "",
                }
            s = summary[kw]
            # Top1Mall/Top1Title: rank 1인 어떤 쇼핑몰이든 기록 (경쟁사 포함)
            if rank == 1 and not s["top1_mall"]:
                s["top1_mall"]  = str(row.get("mall", ""))
                s["top1_title"] = str(row.get("title", ""))
            if is_db:  s["db_rank"] = min(s["db_rank"], rank)
            if is_bit: s["bi_rank"] = min(s["bi_rank"], rank)
            if is_da:  s["da_rank"] = min(s["da_rank"], rank)
            if is_hr:  s["hr_rank"] = min(s["hr_rank"], rank)
            if is_dv:  s["dv_rank"] = min(s["dv_rank"], rank)

        # is_mine(드론박스 or 빛드론)이 노출된 키워드만 저장
        summary = {kw: s for kw, s in summary.items()
                   if s["db_rank"] < 999 or s["bi_rank"] < 999}

        # 페이지 저장
        ok_count = 0
        err_count = 0

        def _rt(val):
            return [{"text": {"content": str(val)[:2000]}}]

        def _rank_num(v):
            return None if v == 999 else v

        for kw, s in summary.items():
            try:
                is_mine = s["db_rank"] < 999 or s["bi_rank"] < 999
                props = {
                    "Keyword":  {"title": _rt(kw)},
                    "Date":     {"date": {"start": date_str}},
                    "Vol":      {"number": s["vol"]},
                    "CTR":      {"number": s["ctr"]},
                    "DBRank":   {"number": _rank_num(s["db_rank"])},
                    "BIRank":   {"number": _rank_num(s["bi_rank"])},
                    "DARank":   {"number": _rank_num(s["da_rank"])},
                    "HRRank":   {"number": _rank_num(s["hr_rank"])},
                    "DVRank":   {"number": _rank_num(s["dv_rank"])},
                    "Top1Mall":  {"rich_text": _rt(s["top1_mall"])},
                    "Top1Title": {"rich_text": _rt(s["top1_title"])},
                    "IsMine":    {"checkbox": is_mine},
                }
                c.pages.create(
                    parent={"database_id": database_id},
                    properties=props,
                )
                ok_count += 1
                time.sleep(0.35)
            except Exception as e:
                err_count += 1
                log.warning("[notion] 저장 실패 (%s): %s", kw, e)

        msg = f"{ok_count}개 키워드 저장 완료"
        if err_count:
            msg += f" (실패 {err_count}건)"
        return True, msg

    except Exception as e:
        log.error("[notion] 저장 오류: %s", e)
        return False, str(e)


def load_from_notion(token, database_id, date_str=None, days=30):
    """
    Notion Database → DataFrame 조회

    Returns:
        (df: pd.DataFrame, error: str)
    """
    if not token or not database_id:
        return pd.DataFrame(), "Notion Token 또는 Database ID가 없습니다."

    try:
        c = _client(token)

        if date_str:
            filter_obj = {"property": "Date", "date": {"equals": date_str}}
        else:
            cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            filter_obj = {"property": "Date", "date": {"on_or_after": cutoff}}

        pages  = []
        cursor = None
        while True:
            kwargs = dict(
                database_id=database_id,
                filter=filter_obj,
                sorts=[
                    {"property": "Date", "direction": "descending"},
                    {"property": "DBRank", "direction": "ascending"},
                ],
                page_size=100,
            )
            if cursor:
                kwargs["start_cursor"] = cursor
            resp = c.databases.query(**kwargs)
            pages.extend(resp["results"])
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")

        rows = []
        for page in pages:
            p = page["properties"]

            def _title(key):
                t = p.get(key, {}).get("title", [])
                return t[0]["text"]["content"] if t else ""

            def _rt(key):
                t = p.get(key, {}).get("rich_text", [])
                return t[0]["text"]["content"] if t else ""

            def _num(key):
                return p.get(key, {}).get("number") or 0

            def _date(key):
                d = p.get(key, {}).get("date")
                return d["start"] if d else ""

            def _bool(key):
                return bool(p.get(key, {}).get("checkbox", False))

            db_rank = _num("DBRank") or 999
            bi_rank = _num("BIRank") or 999

            rows.append({
                "date":     _date("Date"),
                "keyword":  _title("Keyword"),
                "vol":      _num("Vol"),
                "ctr":      _num("CTR"),
                "rank":     min(db_rank, bi_rank),
                "db_rank":  db_rank,
                "bi_rank":  bi_rank,
                "da_rank":  _num("DARank") or 999,
                "hr_rank":  _num("HRRank") or 999,
                "dv_rank":  _num("DVRank") or 999,
                "top1_mall":_rt("Top1Mall"),
                "is_mine":  _bool("IsMine"),
                "is_db":    db_rank < 999,
                "is_bit":   bi_rank < 999,
            })

        df = pd.DataFrame(rows)
        return df, ""

    except Exception as e:
        log.error("[notion] 조회 오류: %s", e)
        return pd.DataFrame(), str(e)


def get_available_dates(token, database_id, days=90):
    """저장된 날짜 목록 반환"""
    df, err = load_from_notion(token, database_id, days=days)
    if df.empty:
        return [], err
    dates = sorted(df["date"].dropna().unique().tolist(), reverse=True)
    return dates, ""
