# -*- coding: utf-8 -*-
"""
[최종 통합 완성본 v9 260624] streamlit_app.py
- Update: 상단/서브 네비 — 시안 A(st.segmented_control 네이티브 세그먼트 탭)로 전면 교체. 기존 st.radio + 커스텀 CSS 방식은
  Streamlit 내부 DOM 구조가 바뀔 때마다 깨지기 쉬워서, 네이티브 위젯 자체가 탭처럼 렌더링되는 방식으로 변경.
- Update: 상단/서브 네비 중앙 정렬 CSS 수정 (radiogroup에 width:100% 추가 — flex centering 미적용 버그 해결)
- Update: AI 프롬프트 고도화 (검색량/클릭률 기반 실무자 맞춤형 '액션 플랜' 제안 기능 추가)
- Update: 차트 렌더링 랙 해결 (기본 14일 조회 + 달력 필터)
- Update: Gemini API 404 에러 방지를 위한 다중 모델 Fallback 로직 적용 (2.5 -> 2.0 -> 1.5 -> pro)
"""

import streamlit as st
import os
# streamlit_option_menu 제거 — 기본 st.radio로 대체
import pandas as pd
import altair as alt
import datetime as dt
import time
import random
import base64
import hmac
import hashlib
import requests
import io
genai = None
_GENAI_OK = False  # SDK 미사용 — REST API로 직접 호출

def _gemini_generate(api_key: str, prompt: str, models=None) -> str:
    """google-generativeai SDK 없이 REST API로 Gemini 호출"""
    import requests as _req
    # 키 유효성 먼저 확인
    _check = _req.get(
        f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
        timeout=10
    )
    if _check.status_code == 400:
        raise RuntimeError("API 키가 유효하지 않습니다. Google AI Studio에서 키를 확인해주세요.")
    if _check.status_code == 403:
        raise RuntimeError("API 키 권한 없음 (403). 키 제한 설정 또는 결제 확인 필요.")
    # 사용 가능한 모델 목록에서 flash 계열 자동 선택
    available = []
    if _check.status_code == 200:
        for m in _check.json().get("models", []):
            name = m.get("name","").replace("models/","")
            if "flash" in name and "generateContent" in str(m.get("supportedGenerationMethods",[])):
                available.append(name)
    if not available:
        available = ['gemini-1.5-flash', 'gemini-2.0-flash']
    last_err = ""
    for model in available[:4]:
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{model}:generateContent?key={api_key}")
        try:
            resp = _req.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=30)
            if resp.status_code != 200:
                last_err = f"{model}: HTTP {resp.status_code} - {resp.text[:150]}"
                continue
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as _e:
            last_err = f"{model}: {_e}"
            continue
    raise RuntimeError(f"Gemini 응답 실패 — {last_err}")
import sys

# [AUTH] 인증 모듈
import os as _os
import json as _json
_AUTH_DIR = _os.path.dirname(_os.path.abspath(__file__))
_SAVED_ID_FILE = _os.path.join(_AUTH_DIR, ".saved_email.json")

def _load_saved_email():
    try:
        if _os.path.exists(_SAVED_ID_FILE):
            with open(_SAVED_ID_FILE, "r", encoding="utf-8") as f:
                return _json.load(f).get("email", "")
    except Exception:
        pass
    return ""

def _save_email(email: str):
    try:
        with open(_SAVED_ID_FILE, "w", encoding="utf-8") as f:
            _json.dump({"email": email}, f)
    except Exception:
        pass

def _delete_saved_email():
    try:
        if _os.path.exists(_SAVED_ID_FILE):
            _os.remove(_SAVED_ID_FILE)
    except Exception:
        pass

import secrets as _secrets
_TOKEN_FILE = _os.path.join(_AUTH_DIR, ".auto_tokens.json")

def _gen_token():
    return _secrets.token_hex(32)

def _save_token(tok, user):
    try:
        d = {}
        if _os.path.exists(_TOKEN_FILE):
            with open(_TOKEN_FILE) as f: d = _json.load(f)
        d[tok] = user
        with open(_TOKEN_FILE, 'w') as f: _json.dump(d, f)
    except Exception: pass

def _load_token(tok):
    try:
        if _os.path.exists(_TOKEN_FILE):
            with open(_TOKEN_FILE) as f: return _json.load(f).get(tok)
    except Exception: pass
    return None

def _delete_token(tok):
    try:
        if _os.path.exists(_TOKEN_FILE):
            with open(_TOKEN_FILE) as f: d = _json.load(f)
            d.pop(tok, None)
            with open(_TOKEN_FILE, 'w') as f: _json.dump(d, f)
    except Exception: pass

try:
    import extra_streamlit_components as _stx_mod
    _COOKIE_OK = True
except Exception:
    _stx_mod = None
    _COOKIE_OK = False
_cookie_manager = None

import threading as _sched_th
_SCHED_CFG_FILE    = _os.path.join(_AUTH_DIR, ".sched_cfg.json")
_SCHED_RESULT_FILE = _os.path.join(_AUTH_DIR, ".sched_result.json")
_SCHED_SINGLETON   = {"thread": None, "stop": False}

def _sched_load_cfg():
    try:
        if _os.path.exists(_SCHED_CFG_FILE):
            with open(_SCHED_CFG_FILE, "r", encoding="utf-8") as f:
                return _json.load(f)
    except Exception:
        pass
    return {"enabled": False, "hour": 9, "minute": 0, "keywords": ""}

def _sched_save_cfg(cfg):
    try:
        with open(_SCHED_CFG_FILE, "w", encoding="utf-8") as f:
            _json.dump(cfg, f, ensure_ascii=False)
    except Exception:
        pass

def _sched_load_result():
    try:
        if _os.path.exists(_SCHED_RESULT_FILE):
            with open(_SCHED_RESULT_FILE, "r", encoding="utf-8") as f:
                return _json.load(f)
    except Exception:
        pass
    return None

def _sched_save_result(data_list, today_str):
    try:
        with open(_SCHED_RESULT_FILE, "w", encoding="utf-8") as f:
            _json.dump({"timestamp": today_str, "count": len(data_list), "data": data_list},
                       f, ensure_ascii=False, default=str)
    except Exception:
        pass

def _sched_run_crawl(keys, keywords_list):
    import logging as _slog
    results = []
    ad_api  = keys.get("naver_ad_api_key", "")
    ad_sec  = keys.get("naver_ad_secret_key", "")
    ad_cid  = keys.get("naver_customer_id", "")
    nav_cid = keys.get("naver_client_id", "")
    nav_sec = keys.get("naver_client_secret", "")
    t_b1    = [x.strip() for x in keys.get("my_brand_1","").split(",") if x.strip()]
    t_b2    = [x.strip() for x in keys.get("my_brand_2","").split(",") if x.strip()]
    today   = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=9)).strftime("%Y-%m-%d")
    for kw in keywords_list:
        try:
            vol, clk, ctr = get_vol(kw, ad_api, ad_sec, ad_cid)
            items = get_rank(kw, nav_cid, nav_sec)
            if items:
                for r, item in enumerate(items, 1):
                    mn = item['mallName'].replace(" ","").lower()
                    results.append({
                        "date": today, "keyword": kw, "vol": vol, "click": clk, "ctr": ctr,
                        "rank": r, "mall": item['mallName'],
                        "title": item['title'].replace("<b>","").replace("</b>",""),
                        "price": item['lprice'], "link": item['link'],
                        "is_db":  any(x.lower().replace(" ","") in mn for x in t_b1),
                        "is_bit": any(x.lower().replace(" ","") in mn for x in t_b2),
                    })
            else:
                # 순위 결과 없어도 검색량은 저장 (미노출 키워드 vol 표시용)
                results.append({
                    "date": today, "keyword": kw, "vol": vol, "click": clk, "ctr": ctr,
                    "rank": 999, "mall": "", "title": "", "price": 0, "link": "",
                    "is_db": False, "is_bit": False,
                })
        except Exception as e:
            _slog.warning(f"[AutoCrawl] '{kw}' 오류: {e}")
    _sched_save_result(results, today)
    _slog.info(f"[AutoCrawl] 완료: {len(results)}건")

def _sched_start(keys):
    if _SCHED_SINGLETON["thread"] and _SCHED_SINGLETON["thread"].is_alive():
        return
    _SCHED_SINGLETON["stop"] = False
    def _loop():
        fired = {"date": ""}
        while not _SCHED_SINGLETON["stop"]:
            try:
                now_kst   = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=9)
                today_str = now_kst.strftime("%Y-%m-%d")
                cfg_live  = _sched_load_cfg()
                if not cfg_live.get("enabled"):
                    break
                target_h  = int(cfg_live.get("hour", 9))
                target_m  = int(cfg_live.get("minute", 0))
                kws_live  = [k.strip() for k in cfg_live.get("keywords","").split("\n") if k.strip()]
                if (now_kst.hour == target_h and now_kst.minute == target_m
                        and fired["date"] != today_str and kws_live):
                    fired["date"] = today_str
                    _sched_run_crawl(keys, kws_live)
            except Exception:
                pass
            _sched_th.Event().wait(30)
    t = _sched_th.Thread(target=_loop, daemon=True, name="km_scheduler")
    t.start()
    _SCHED_SINGLETON["thread"] = t

def _sched_stop():
    _SCHED_SINGLETON["stop"] = True

# [P2] 하드코딩 경로 제거 -- 환경변수로 주입 (미설정 시 Obsidian 로깅 자동 비활성화)
_OBSIDIAN_VAULT = _os.getenv("OBSIDIAN_VAULT_DIR", "")

def _obs_log_change(title: str, detail: str):
    if not _OBSIDIAN_VAULT:
        return
    try:
        path = _os.path.join(_OBSIDIAN_VAULT, "변경_이력.md")
        now  = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")
        entry = f"\n### {now} | {title}\n{detail}\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass

def _obs_log_error(title: str, symptom: str, cause: str = "", fix: str = ""):
    if not _OBSIDIAN_VAULT:
        return
    try:
        path = _os.path.join(_OBSIDIAN_VAULT, "에러_로그.md")
        now  = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")
        entry = (
            f"\n## {now} | {title} | 🔴 미해결\n\n"
            f"**증상**\n{symptom}\n\n"
            f"**원인**\n{cause or '- 조사 필요'}\n\n"
            f"**해결**\n{fix or '- 미해결'}\n\n---\n"
        )
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass

def generate_excel_report(df, title="순위 데이터"):
    import io, xlsxwriter
    output = io.BytesIO()
    wb = xlsxwriter.Workbook(output, {'in_memory': True})
    ws = wb.add_worksheet("순위")
    ws2 = wb.add_worksheet("요약")
    hdr  = wb.add_format({'bold':True,'bg_color':'#2563EB','font_color':'#FFFFFF','border':1,'align':'center','valign':'vcenter','font_size':11})
    good = wb.add_format({'bg_color':'#DCFCE7','border':1,'align':'center'})
    mid  = wb.add_format({'bg_color':'#FEF9C3','border':1,'align':'center'})
    bad  = wb.add_format({'bg_color':'#FEE2E2','border':1,'align':'center'})
    norm = wb.add_format({'border':1,'align':'left'})
    num  = wb.add_format({'border':1,'align':'center'})
    headers = ['날짜','키워드','순위','쇼핑몰','상품명','가격','검색량','클릭수','CTR(%)']
    cols    = ['date','keyword','rank','mall','title','price','vol','click','ctr']
    widths  = [12, 18, 6, 20, 40, 10, 10, 10, 8]
    for i, (h, w) in enumerate(zip(headers, widths)):
        ws.write(0, i, h, hdr)
        ws.set_column(i, i, w)
    ws.freeze_panes(1, 0)
    for row_i, (_, row) in enumerate(df.iterrows(), 1):
        for col_i, col in enumerate(cols):
            val = row.get(col, "")
            if col == 'rank':
                r = int(val) if str(val).lstrip('-').isdigit() else 999
                fmt = good if r <= 3 else (mid if r <= 10 else bad)
                ws.write(row_i, col_i, val, fmt)
            elif col in ('vol','click','price'):
                ws.write(row_i, col_i, val, num)
            else:
                ws.write(row_i, col_i, str(val), norm)
    ws2_hdr = wb.add_format({'bold':True,'bg_color':'#1E293B','font_color':'#FFFFFF','border':1,'align':'center'})
    ws2.write_row(0, 0, ['키워드','최고 순위','평균 순위','검색량'], ws2_hdr)
    ws2.set_column(0, 0, 20); ws2.set_column(1, 3, 12)
    if not df.empty and 'keyword' in df.columns and 'rank' in df.columns:
        summary = df.groupby('keyword').agg(
            최고순위=('rank','min'), 평균순위=('rank','mean'), 검색량=('vol','max')
        ).reset_index().sort_values('최고순위')
        for r_i, (_, r) in enumerate(summary.iterrows(), 1):
            fmt_s = good if r['최고순위'] <= 3 else (mid if r['최고순위'] <= 10 else bad)
            ws2.write(r_i, 0, r['keyword'], norm)
            ws2.write(r_i, 1, r['최고순위'], fmt_s)
            ws2.write(r_i, 2, round(r['평균순위'], 1), num)
            ws2.write(r_i, 3, r['검색량'], num)
    wb.close()
    output.seek(0)
    return output.getvalue()

if _AUTH_DIR not in sys.path:
    sys.path.insert(0, _AUTH_DIR)
from auth.users import (
    register as _auth_register,
    login as _auth_login,
    reset_password as _auth_reset_password,
    save_keys as _auth_save_keys,
    load_keys as _auth_load_keys,
)
from auth.db import init_db as _auth_init_db

sys.stdout.reconfigure(encoding='utf-8')
st.set_page_config(page_title="키워드맵", page_icon="🗺️", layout="wide", initial_sidebar_state="collapsed")
if _COOKIE_OK and _cookie_manager is None:
    try:
        _cookie_manager = _stx_mod.CookieManager(key="km_cookie_mgr")
    except Exception:
        _cookie_manager = None

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
*, *::before, *::after { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important; -webkit-font-smoothing: antialiased; }

/* ── 전체 배경 ── */
div[data-testid="stAppViewContainer"], div[data-testid="stMain"] { background: #FFFBF5 !important; }
header[data-testid="stHeader"] { display: none !important; }
#MainMenu, footer, [data-testid="stToolbar"] { display: none !important; }
.block-container { padding-top: 0 !important; padding-bottom: 3rem !important; max-width: 1320px; }

/* ── 사이드바 완전 숨김 ── */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div,
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="stSidebarNav"],
button[aria-label="Open sidebar"],
button[aria-label="Close sidebar"],
button[aria-label="사이드바 열기"],
button[aria-label="사이드바 닫기"],
[class*="collapsedControl"],
[class*="SidebarCollapsed"] { display: none !important; visibility: hidden !important; width: 0 !important; min-width: 0 !important; max-width: 0 !important; overflow: hidden !important; }
/* 사이드바 공간 제거 — 메인 콘텐츠 왼쪽 여백 없애기 */
.main .block-container { padding-left: 1rem !important; }
section[data-testid="stMain"] { margin-left: 0 !important; padding-left: 0 !important; }

/* ══════════════════════════════
   상단 네비게이션 — 시안 A: 네이티브 세그먼트 탭형 (st.segmented_control)
   라디오 동그라미 숨김 등 fragile한 커스텀 CSS 없이, 위젯 자체가 이미 알약형 탭으로 렌더링됨.
   data-testid="stBaseButton-segmented_control" / "...Active" 는 Streamlit 1.45 기준 안정적인 hook.
══════════════════════════════ */
div.st-key-km_topnav { background: #111; margin: -1px calc(-50vw + 50%) 0; padding: 10px 2rem; border-bottom: 2.5px solid #333; position: relative; }
div.st-key-km_topnav [data-testid="stElementContainer"]:has([data-testid^="stBaseButton-segmented_control"]) {
    display: flex !important; flex-direction: column !important; align-items: center !important;
}
div.st-key-km_topnav [data-testid^="stBaseButton-segmented_control"] {
    background: rgba(255,255,255,0.06) !important; border-color: rgba(255,255,255,0.18) !important;
    color: rgba(255,255,255,0.55) !important; font-size: 0.82rem !important;
}
div.st-key-km_topnav [data-testid^="stBaseButton-segmented_control"]:hover {
    color: #fff !important; background: rgba(255,255,255,0.12) !important;
}
div.st-key-km_topnav [data-testid="stBaseButton-segmented_controlActive"] {
    background: rgba(255,107,43,0.2) !important; border-color: #FF6B2B !important;
    color: #fff !important; font-weight: 700 !important;
}

/* 상단 네비 우측 — 압축 상태 표시 (카테고리 줄과 한 줄로 통합) */
.km-topnav-status {
    position: absolute; top: 50%; right: 2rem; transform: translateY(-50%);
    display: flex; align-items: center; gap: 6px;
    font-size: 0.76rem; font-weight: 600; color: rgba(255,255,255,0.85);
    white-space: nowrap; pointer-events: none; z-index: 2;
}
.km-topnav-status .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex-shrink: 0; }

/* ── 하위 네비게이션 (선택된 카테고리의 세부 메뉴) — 마찬가지로 st.segmented_control ── */
div.st-key-km_subnav { background: #FFF; margin: 0 calc(-50vw + 50%) 1.5rem; padding: 8px 2rem 10px;
    border-bottom: 2.5px solid #111; box-shadow: inset 0 6px 8px -8px rgba(0,0,0,0.25); }
div.st-key-km_subnav [data-testid="stElementContainer"]:has([data-testid^="stBaseButton-segmented_control"]) {
    display: flex !important; flex-direction: column !important; align-items: center !important;
}
div.st-key-km_subnav [data-testid^="stBaseButton-segmented_control"] {
    font-size: 0.78rem !important; padding: 0.3rem 0.85rem !important;
}
div.st-key-km_subnav [data-testid="stBaseButton-segmented_controlActive"] {
    font-weight: 700 !important;
}

/* ── 페이지 헤더 ── */
.km-page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.2rem; padding-bottom: 1rem; border-bottom: 2px solid #111; }
.km-page-title { font-size: 1.3rem !important; font-weight: 700 !important; color: #111 !important; letter-spacing: -0.02em; display: inline-block; border-bottom: 3px solid #FF6B2B; padding-bottom: 4px; }
.km-page-sub { font-size: 0.8rem; color: #888; margin-top: 4px; }

/* ── 브랜드 패널 ── */
.km-brand-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 1.2rem; }
.km-brand-panel { border: 2.5px solid #111; border-radius: 8px; overflow: hidden; }
.km-brand-panel.db { box-shadow: 4px 4px 0 #111; }
.km-brand-panel.bit { box-shadow: 4px 4px 0 #111; }
.km-brand-head { padding: 9px 16px; display: flex; align-items: center; gap: 10px; border-bottom: 2px solid #111; }
.km-brand-panel.db .km-brand-head { background: #FF6B2B; }
.km-brand-panel.bit .km-brand-head { background: #111; }
.km-brand-name { font-size: 13px; font-weight: 600; color: #fff; }
.km-brand-tag { font-size: 10px; padding: 2px 8px; border-radius: 4px; border: 1.5px solid rgba(255,255,255,0.3); color: rgba(255,255,255,0.75); margin-left: auto; }
.km-brand-body { background: #fff; display: grid; grid-template-columns: repeat(4, 1fr); }
.km-brand-stat { padding: 12px 10px; text-align: center; border-right: 1.5px solid #F0EDE8; }
.km-brand-stat:last-child { border-right: none; }
.km-stat-label { font-size: 9px; font-weight: 600; color: #999; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 5px; }
.km-stat-num { font-size: 26px; font-weight: 700; color: #111; line-height: 1; }
.km-stat-num.up { color: #1A7A2A; }
.km-stat-num.dn { color: #C0392B; }
.km-stat-num.ms { color: #C07A00; }
.km-stat-num.ok { color: #1A7A2A; }
.km-stat-sub { font-size: 9px; color: #CCC; margin-top: 3px; }

/* ── 섹션 블록 ── */
.km-block { background: #fff; border: 2.5px solid #111; border-radius: 8px; overflow: hidden; margin-bottom: 14px; box-shadow: 4px 4px 0 #111; }
.km-block-head { display: flex; align-items: center; gap: 8px; padding: 10px 16px; border-bottom: 2px solid #111; background: #111; }
.km-block-title { font-size: 12px; font-weight: 600; color: #fff; }
.km-badge { font-size: 10px; padding: 2px 9px; border-radius: 4px; border: 1.5px solid; font-weight: 600; }
.km-badge-rd { background: #FF5555; color: #fff; border-color: rgba(255,255,255,0.3); }
.km-badge-am { background: #FFD000; color: #111; border-color: rgba(0,0,0,0.15); }
.km-badge-gr { background: #44BB44; color: #fff; border-color: rgba(255,255,255,0.3); }
.km-badge-pp { background: #9B59B6; color: #fff; border-color: rgba(255,255,255,0.3); }
.km-badge-bl { background: #3498DB; color: #fff; border-color: rgba(255,255,255,0.3); }
.km-section-header { display: flex; align-items: center; gap: 8px; padding: 14px 16px 8px; background: #FFFBF5; border-bottom: 1.5px solid #F0EDE8; }
.km-section-title { font-size: 12px; font-weight: 600; color: #111; }
.km-chip-db { font-size: 10px; padding: 3px 8px; border-radius: 4px; border: 1.5px solid #FF6B2B; background: #FFF0E8; color: #C03800; display: inline-block; font-weight: 600; }
.km-chip-bit { font-size: 10px; padding: 3px 8px; border-radius: 4px; border: 1.5px solid #111; background: #F0F0F0; color: #111; display: inline-block; font-weight: 600; }

/* ── 버튼 ── */
div.stButton > button {
    background: #111 !important; color: #fff !important;
    border: 2px solid #111 !important; border-radius: 6px !important;
    font-weight: 600 !important; font-size: 0.875rem !important;
    padding: 0.5rem 1.2rem !important; box-shadow: 2px 2px 0 #555 !important;
    transition: box-shadow 0.1s, transform 0.1s !important;
}
div.stButton > button:hover { box-shadow: 3px 3px 0 #333 !important; }
div.stButton > button:active { transform: translate(1px, 1px) !important; box-shadow: 1px 1px 0 #333 !important; }
div.stButton > button[kind="primary"] {
    background: #FF6B2B !important; border-color: #111 !important; box-shadow: 3px 3px 0 #111 !important;
}
div.stButton > button[kind="secondary"] {
    background: #fff !important; color: #111 !important;
    border: 2px solid #111 !important; box-shadow: 2px 2px 0 #999 !important;
}

/* ── 인풋 ── */
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea {
    background: #FFFFFF !important; border: 2px solid #D1D5DB !important;
    border-radius: 6px !important; color: #111 !important; font-size: 0.9rem !important;
}
[data-testid="stTextInput"] input:focus, [data-testid="stTextArea"] textarea:focus {
    border-color: #FF6B2B !important; box-shadow: 3px 3px 0 rgba(255,107,43,0.2) !important;
}
[data-testid="stTextInput"] label, [data-testid="stTextArea"] label { color: #111 !important; font-weight: 600 !important; font-size: 0.85rem !important; }
[data-testid="stSelectbox"] > div > div { background: #fff !important; border: 2px solid #111 !important; border-radius: 6px !important; }

/* ── 테이블/데이터프레임 ── */
[data-testid="stDataFrame"] { border: 2px solid #111 !important; border-radius: 6px !important; box-shadow: 3px 3px 0 #111 !important; overflow: hidden; background: #fff; }

/* ── 알림 ── */
[data-testid="stAlert"] { border-radius: 6px !important; border: 2px solid #111 !important; border-left-width: 4px !important; box-shadow: 3px 3px 0 #999 !important; }

/* ── Expander ── */
[data-testid="stExpander"] { background: #FFFFFF !important; border: 2px solid #111 !important; border-radius: 6px !important; box-shadow: 3px 3px 0 #999 !important; }

/* ── 탭 ── */
[data-testid="stTabs"] button { color: #888 !important; font-weight: 500 !important; border-bottom: 2.5px solid transparent !important; }
[data-testid="stTabs"] button[aria-selected="true"] { color: #111 !important; border-bottom: 2.5px solid #FF6B2B !important; font-weight: 700 !important; }

/* ── 타이포 ── */
h1 { font-size: 1.5rem !important; font-weight: 700 !important; color: #111 !important; }
h2 { font-size: 1.2rem !important; font-weight: 700 !important; color: #111 !important; }
h3 { font-size: 1rem !important; font-weight: 600 !important; color: #111 !important; }
hr { border-color: #E8E4DE !important; border-width: 1.5px !important; }

/* ── KPI metric ── */
[data-testid="stMetric"] {
    background: #fff !important; border: 2px solid #111 !important; border-radius: 6px !important;
    padding: 1rem 1.2rem !important; box-shadow: 3px 3px 0 #111 !important;
}
[data-testid="stMetricValue"] { font-size: 2rem !important; font-weight: 700 !important; color: #111 !important; }
[data-testid="stMetricLabel"] { font-size: 0.78rem !important; font-weight: 600 !important; color: #888 !important; text-transform: uppercase !important; letter-spacing: 0.06em !important; }

/* ── 반응형 ── */
@media (max-width: 768px) {
    .block-container { padding: 0 0.8rem 3rem !important; }
    .km-brand-grid { grid-template-columns: 1fr !important; }
    .km-brand-body { grid-template-columns: repeat(2, 1fr) !important; }
}
</style>
""", unsafe_allow_html=True)

NOW_KST = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) + dt.timedelta(hours=9)
TODAY_ISO = NOW_KST.strftime("%Y-%m-%d")
TODAY_KOR = NOW_KST.strftime("%Y년 %m월 %d일")

def get_secret(key, default=""):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

if 'crawled_df' not in st.session_state: st.session_state.crawled_df = pd.DataFrame()
if 'history_df' not in st.session_state: st.session_state.history_df = pd.DataFrame()
if 'ai_report_text' not in st.session_state: st.session_state.ai_report_text = ""
if 'authenticated'   not in st.session_state: st.session_state.authenticated  = False
if 'current_user'    not in st.session_state: st.session_state.current_user   = None
if 'user_keys'       not in st.session_state: st.session_state.user_keys      = {}
if 'auth_page'       not in st.session_state: st.session_state.auth_page      = "login"
_auth_init_db()

# ── [AUTH GATE] ────────────────────────────────────────────────────────────────
if not st.session_state.authenticated and _COOKIE_OK and _cookie_manager:
    try:
        _saved_tok = _cookie_manager.get("km_auto_token")
        if _saved_tok:
            _au = _load_token(_saved_tok)
            if _au:
                st.session_state.authenticated = True
                st.session_state.current_user  = _au
                st.session_state.user_keys     = _auth_load_keys(_au["id"])
    except Exception: pass

if not st.session_state.authenticated:
    st.markdown("""
    <style>
    body, .stApp { background: #F3F4F6 !important; }
    .auth-wrap { min-height: 100vh; display: flex; align-items: center; justify-content: center; }
    .auth-card { background: #fff; border-radius: 20px; padding: 48px 44px; width: 100%; max-width: 420px; box-shadow: 0 4px 24px rgba(0,0,0,0.08); }
    .auth-brand { text-align: center; margin-bottom: 36px; }
    .auth-brand-icon { width: 56px; height: 56px; background: #111827; border-radius: 14px; display: inline-flex; align-items: center; justify-content: center; font-size: 26px; margin-bottom: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
    .auth-brand-name { font-size: 22px; font-weight: 800; color: #111827; letter-spacing: -0.5px; margin: 0; }
    .auth-brand-sub { font-size: 11px; color: #9CA3AF; letter-spacing: 0.1em; text-transform: uppercase; margin: 6px 0 0; }
    .auth-divider { display: flex; align-items: center; gap: 12px; margin: 20px 0; }
    .auth-divider span { color: #D1D5DB; font-size: 12px; }
    .auth-divider hr { flex: 1; border: none; border-top: 1px solid #F3F4F6; margin: 0; }
    [data-testid="stTabs"] { background: transparent !important; }
    [data-testid="stTabs"] button { font-size: 0.875rem !important; font-weight: 600 !important; }
    </style>
    """, unsafe_allow_html=True)

    _lc, _cc, _rc = st.columns([1, 1.6, 1])
    with _cc:
        st.markdown("""
        <div class="auth-brand">
            <div class="auth-brand-icon">🗺️</div>
            <p class="auth-brand-name">KeywordMap</p>
            <p class="auth-brand-sub">Naver Shopping Intelligence</p>
        </div>
        """, unsafe_allow_html=True)

        _tab_login, _tab_signup = st.tabs(["로그인", "회원가입"])

        # ── 로그인 탭 ──────────────────────────────────────────
        with _tab_login:
            _saved_email = _load_saved_email()
            with st.form("login_form"):
                _l_email = st.text_input(
                    "이메일", placeholder="your@email.com",
                    value=_saved_email,
                    key="_l_email"
                )
                _l_pw = st.text_input("비밀번호", type="password", key="_l_pw")
                _fc1, _fc2 = st.columns(2)
                with _fc1:
                    _save_id_checked = st.checkbox("아이디 저장", value=bool(_saved_email), key="_save_id_chk")
                with _fc2:
                    _auto_login_checked = st.checkbox("자동 로그인", value=True, key="_auto_login_chk")
                st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
                _submitted = st.form_submit_button("로그인", type="primary", use_container_width=True)

            if _submitted:
                if not _l_email or not _l_pw:
                    st.error("이메일과 비밀번호를 입력해주세요.")
                else:
                    _ok, _msg, _user = _auth_login(_l_email, _l_pw)
                    if _ok:
                        if _save_id_checked:
                            _save_email(_l_email)
                        else:
                            _delete_saved_email()
                        st.session_state.authenticated = True
                        st.session_state.current_user  = _user
                        st.session_state.user_keys     = _auth_load_keys(_user["id"])
                        if _COOKIE_OK and _cookie_manager and _auto_login_checked:
                            try:
                                _tok = _gen_token()
                                _save_token(_tok, _user)
                                _cookie_manager.set("km_auto_token", _tok, max_age=60*60*24*30)
                            except Exception: pass
                        st.rerun()
                    else:
                        st.error(_msg)

        # ── 회원가입 탭 ────────────────────────────────────────
        with _tab_signup:
            _s_name  = st.text_input("쇼핑몰 이름 (표시명)", key="_s_name")
            _s_email = st.text_input("이메일", placeholder="your@email.com", key="_s_email")
            _s_pw  = st.text_input("비밀번호 (8자 이상)", type="password", key="_s_pw")
            _s_pw2 = st.text_input("비밀번호 확인",       type="password", key="_s_pw2")
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            if st.button("회원가입", type="primary", use_container_width=True, key="_s_btn"):
                if not _s_email or not _s_pw:
                    st.error("이메일과 비밀번호를 입력해주세요.")
                elif _s_pw != _s_pw2:
                    st.error("비밀번호가 일치하지 않습니다.")
                else:
                    _ok, _msg = _auth_register(_s_email, _s_pw, _s_name)
                    if _ok:
                        st.success(_msg)
                    else:
                        st.error(_msg)

        # ── 비밀번호 찾기 ──────────────────────────────────────
        with st.expander("🔑 비밀번호를 잊으셨나요?"):
            _r_email = st.text_input("가입한 이메일 입력", placeholder="your@email.com", key="_r_email")
            _r_name  = st.text_input("가입 시 등록한 이름", placeholder="본인 확인용", key="_r_name")
            if st.button("임시 비밀번호 발급", use_container_width=True, key="_r_btn"):
                if not _r_email or not _r_name:
                    st.error("이메일과 가입 시 등록한 이름을 모두 입력해주세요.")
                else:
                    _r_ok, _r_msg, _r_tmp = _auth_reset_password(_r_email, _r_name)
                    if _r_ok:
                        st.success("✅ 임시 비밀번호가 발급됐습니다. 로그인 후 반드시 변경해주세요.")
                        st.code(_r_tmp, language=None)
                        st.caption("위 임시 비밀번호로 로그인 후 ⚙️ 설정에서 비밀번호를 변경하세요.")
                    else:
                        st.error(_r_msg)

        st.markdown(
            "<p style='text-align:center; color:#4b5563; font-size:12px; margin-top:20px;'>"
            "API 키는 암호화되어 안전하게 저장됩니다 🔒</p>",
            unsafe_allow_html=True
        )

    st.stop()

# --- API 엔진 ---
def get_vol(kw, ak, sk, cid):
    if not (ak and sk and cid): return 0, 0, 0
    try:
        ts = str(int(time.time() * 1000))
        sig = base64.b64encode(hmac.new(sk.encode(), f"{ts}.GET./keywordstool".encode(), hashlib.sha256).digest()).decode()
        headers = {**HTTP_HEADERS, "X-Timestamp": ts, "X-API-KEY": ak, "X-Customer": cid, "X-Signature": sig}
        time.sleep(random.uniform(1.2, 2.5))
        res = requests.get(f"https://api.naver.com/keywordstool?hintKeywords={kw.replace(' ', '')}&showDetail=1", headers=headers, timeout=10)
        res.raise_for_status()
        for i in res.json().get('keywordList', []):
            if i['relKeyword'].replace(" ", "") == kw.replace(" ", ""):
                v = int(str(i['monthlyPcQcCnt']).replace("<", "")) + int(str(i['monthlyMobileQcCnt']).replace("<", ""))
                c = float(str(i['monthlyAvePcClkCnt']).replace("<", "")) + float(str(i['monthlyAveMobileClkCnt']).replace("<", ""))
                return v, round(c, 1), round(c / v * 100, 2) if v else 0
    except Exception as e:
        import logging as _log
        _log.warning(f"[get_vol] '{kw}' 오류: {type(e).__name__}: {e}")
    return 0, 0, 0

def get_rank(kw, cid, sec):
    if not (cid and sec): return []
    try:
        headers = {**HTTP_HEADERS, "X-Naver-Client-Id": cid, "X-Naver-Client-Secret": sec}
        time.sleep(random.uniform(0.8, 1.5))
        res = requests.get("https://openapi.naver.com/v1/search/shop.json", headers=headers, params={"query": kw, "display": 100, "sort": "sim"}, timeout=10)
        res.raise_for_status()
        return res.json().get('items', [])
    except Exception as e:
        import logging as _log
        _log.warning(f"[get_rank] '{kw}' 오류: {type(e).__name__}: {e}")
        return []

from integrations.notion_sync import save_to_notion, load_from_notion, get_available_dates
from integrations.slack_notify import send_slack

# ── API 키 변수 초기화 (session_state에서 직접 읽기) ──────────────────────────
_k = st.session_state.user_keys
gemini_key        = _k.get("gemini_key", "")
naver_cid         = _k.get("naver_client_id", "")
naver_csec        = _k.get("naver_client_secret", "")
ad_api_key        = _k.get("naver_ad_api_key", "")
ad_sec_key        = _k.get("naver_ad_secret_key", "")
ad_cus_id         = _k.get("naver_customer_id", "")
notion_token      = _k.get("notion_token", "")
notion_db_id      = _k.get("notion_database_id", "")
slack_webhook_url = _k.get("slack_webhook_url", "")
apps_script_url   = _k.get("apps_script_url", "")
apps_script_token = _k.get("apps_script_token", "")
my_brand_1        = _k.get("my_brand_1", "드론박스, DroneBox")
my_brand_2        = _k.get("my_brand_2", "빛드론, BitDrone")
competitors       = _k.get("competitors", "다다사, 효로로, 드론뷰")

# ── 상단 네비게이션 탭 ─────────────────────────────────────────────────────────
_u = st.session_state.current_user or {}
_api_set = bool(_k.get("naver_client_id"))

# 전 화면 공통 상태 — 시안 1: 카테고리 줄 우측에 압축 표시 (상세는 Dashboard에서 확인)
_mini_lv, _mini_txt, _mini_color = "gray", "확인 중", "#C9C4BB"
try:
    from integrations.system_status import check_config as _cc, overall_level as _ol
    try:
        from auth.encrypt import _get_fernet as _gf
        _mini_enc = _gf() is not None
    except Exception:
        _mini_enc = False
    _mini_items = _cc(_k, _mini_enc)
    _mini_lv = _ol(_mini_items)
    _mini_txt = {"green": "정상", "yellow": "일부 미설정", "red": "필수 누락"}[_mini_lv]
    _mini_color = {"green": "#44BB44", "yellow": "#E6A000", "red": "#FF5555"}[_mini_lv]
except Exception:
    pass

_menu_groups = {
    "📊 현황": ["Dashboard", "일자별 순위 추이", "경쟁사 집중 분석"],
    "🔍 키워드": ["틈새 키워드 발굴기", "키워드 인텐트", "시즌성 분석"],
    "🤖 AI 분석": ["AI Report", "AI 인용 추적", "GEO 진단", "엔티티 감사"],
    "✍️ 콘텐츠 제작": ["SEO태그 생성기", "스키마·FAQ 생성기", "상세페이지 제작기", "GEO/AEO 가이드"],
    "⚙️ 운영": ["Run & Sync", "⚙️ 설정"],
}
# 직전 선택 메뉴가 속한 그룹을 기본 활성 그룹으로 (없으면 첫 그룹)
_prev_menu = st.session_state.get("_active_menu", "Dashboard")
_default_group = next((g for g, items in _menu_groups.items() if _prev_menu in items),
                      list(_menu_groups)[0])

# st.markdown('<div>')...st.markdown('</div>')로 태그를 분리해서 감싸는 방식은 Streamlit이 호출마다
# 별도 컨테이너를 만들어 실제로는 중첩되지 않음(형제 노드로 렌더링) — st.container(key=...)를 써야
# 진짜 부모 div(class="st-key-...")가 생겨서 CSS 하위 선택자가 정상 동작함.
with st.container(key="km_topnav"):
    st.markdown(
        f"<div class='km-topnav-status'><span class='dot' style='background:{_mini_color};'></span>"
        f"{_mini_txt}</div>", unsafe_allow_html=True)
    # segmented_control은 선택된 항목을 다시 누르면 None(선택 해제)을 반환할 수 있음 —
    # 네비게이션에서는 항상 하나가 활성 상태여야 하므로 None이면 직전 활성 그룹으로 되돌림.
    _group_sel = st.segmented_control("카테고리", list(_menu_groups.keys()),
                             default=_default_group,
                             label_visibility="collapsed")
    _active_group = _group_sel if _group_sel is not None else _default_group

# 하위 메뉴: 선택된 그룹의 항목만 표시 (그룹 전환 시 첫 항목 자동 선택)
_sub_items = _menu_groups[_active_group]
_sub_index = _sub_items.index(_prev_menu) if _prev_menu in _sub_items else 0
_sub_default = _sub_items[_sub_index]
with st.container(key="km_subnav"):
    _menu_sel = st.segmented_control("메뉴", _sub_items,
                             default=_sub_default,
                             label_visibility="collapsed",
                             key=f"_sub_{_active_group}")
    selected_menu = _menu_sel if _menu_sel is not None else _sub_default
st.session_state["_active_menu"] = selected_menu
if _mini_lv == "red":
    st.caption("🔴 필수 설정이 누락됐습니다. Dashboard 또는 ⚙️ 설정에서 확인하세요.")

def get_clean_df(df_target):
    if df_target.empty: return df_target
    df_clean = df_target.copy()
    # top1_mall → mall 컬럼 통일 (Notion 요약 구조 호환)
    if 'mall' not in df_clean.columns and 'top1_mall' in df_clean.columns:
        df_clean['mall'] = df_clean['top1_mall']
    if 'mall' not in df_clean.columns: return df_clean
    t_db = [x.strip() for x in my_brand_1.split(',') if x.strip()]
    t_bit = [x.strip() for x in my_brand_2.split(',') if x.strip()]
    t_comp = [x.strip() for x in competitors.split(',') if x.strip()]
    core_malls = t_db + t_bit + t_comp
    def map_mall_name(name):
        if not isinstance(name, str): return name
        for core in core_malls:
            if core in name: return core
        return name
    df_clean['mall'] = df_clean['mall'].apply(map_mall_name)
    return df_clean

notion_token      = _k.get("notion_token", "")
notion_db_id      = _k.get("notion_database_id", "")
slack_webhook_url = _k.get("slack_webhook_url", "")

if st.session_state.history_df.empty and apps_script_url:
    with st.spinner("Google Sheets에서 데이터를 불러오는 중..."):
        try:
            import requests as _r
            _gs_res = _r.get(apps_script_url, params={"token": apps_script_token}, timeout=20)
            _gs_json = _gs_res.json()
            if _gs_json:
                _gs_df = pd.DataFrame(_gs_json)
                if not _gs_df.empty:
                    st.session_state.history_df = _gs_df
        except Exception as _e:
            pass

hist_df    = get_clean_df(st.session_state.history_df)
crawled_df = get_clean_df(st.session_state.crawled_df)
metric_df  = crawled_df.copy() if not crawled_df.empty else (hist_df[hist_df['date'] == hist_df['date'].max()] if not hist_df.empty else pd.DataFrame())

# ── 1. Dashboard ───────────────────────────────────────────────────────────────
if selected_menu == "Dashboard":

    # ── 헤더 ──────────────────────────────────────────────────────────────────
    _hcol1, _hcol2 = st.columns([5, 1])
    with _hcol1:
        st.markdown(f"""
        <div class="km-page-header">
          <div>
            <div class="km-page-title">오늘의 현황</div>
            <div class="km-page-sub">{TODAY_KOR} 기준 · 네이버 쇼핑 자사 순위</div>
          </div>
        </div>""", unsafe_allow_html=True)
    with _hcol2:
        st.markdown("<div style='margin-top:4px;'>", unsafe_allow_html=True)
        if st.button("새로고침", use_container_width=True, type="primary"):
            if notion_token and notion_db_id:
                with st.spinner("불러오는 중..."):
                    _df_r, _err_r = load_from_notion(notion_token, notion_db_id, days=30)
                    if not _df_r.empty:
                        st.session_state.history_df = _df_r
                        st.rerun()
                    else:
                        st.error(f"실패: {_err_r}")
            else:
                st.warning("사이드바에서 Notion 설정을 먼저 입력해주세요.")
        st.markdown("</div>", unsafe_allow_html=True)

    # ── 시스템 상태 상세 (상단 바와 연동, 실제 연결 테스트) ───────────────────
    from integrations.system_status import (
        check_config, overall_level, overall_summary, DOT,
        live_naver, live_gemini, live_apps_script)
    try:
        from auth.encrypt import _get_fernet
        _enc_ok = _get_fernet() is not None
    except Exception:
        _enc_ok = False
    _sys_items = check_config(_k, _enc_ok)
    _sys_lv = overall_level(_sys_items)

    with st.expander(f"{DOT[_sys_lv]} 시스템 상태 상세 — {overall_summary(_sys_items)}",
                     expanded=(_sys_lv == "red")):
        _stat_cols = st.columns(2)
        for _i, _it in enumerate(_sys_items):
            with _stat_cols[_i % 2]:
                _req = " *(필수)*" if _it["required"] else ""
                st.markdown(f"{DOT[_it['level']]} **{_it['name']}**{_req}  \n"
                            f"<span style='font-size:0.8rem;color:#888;'>{_it['detail']}</span>",
                            unsafe_allow_html=True)
        st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
        if st.button("🔌 실제 연결 테스트 (네이버·Gemini·저장소)", key="_sys_live"):
            with st.spinner("실제 API 연결 확인 중…"):
                _lv1, _d1 = live_naver(naver_cid, naver_csec)
                _lv2, _d2 = live_gemini(gemini_key)
                _lv3, _d3 = live_apps_script(apps_script_url, apps_script_token)
            st.markdown(f"{DOT[_lv1]} **네이버 검색 API** — {_d1}")
            st.markdown(f"{DOT[_lv2]} **Gemini AI** — {_d2}")
            st.markdown(f"{DOT[_lv3]} **데이터 저장소** — {_d3}")
        if _sys_lv == "red":
            st.caption("🔴 필수 항목은 ⚙️ 설정 메뉴에서 키를 등록하거나, ENCRYPT_KEY는 Streamlit Secrets에 추가하세요.")

    # ── 데이터 준비 ────────────────────────────────────────────────────────────
    _today_df = metric_df.copy() if not metric_df.empty else pd.DataFrame()
    _prev_df  = pd.DataFrame()
    if not hist_df.empty:
        _dates = sorted(hist_df['date'].dropna().unique().tolist(), reverse=True)
        if len(_dates) > 1:
            _prev_df = hist_df[hist_df['date'] == _dates[1]].copy()

    # 전체 모니터링 키워드 목록 (keywords.txt 기준)
    _kw_file = _os.path.join(_AUTH_DIR, "keywords.txt")
    _all_kws = []
    if _os.path.exists(_kw_file):
        with open(_kw_file, "r", encoding="utf-8") as _f:
            _all_kws = [_l.strip() for _l in _f if _l.strip() and not _l.startswith('#')]
    elif 'save_kws_text' in st.session_state and st.session_state.save_kws_text:
        _all_kws = [_k2.strip() for _k2 in st.session_state.save_kws_text.split('\n') if _k2.strip()]

    # 오늘 자사 상품이 노출된 키워드 (is_db 또는 is_bit = True인 것만)
    if not _today_df.empty:
        if 'is_db' in _today_df.columns and 'is_bit' in _today_df.columns:
            _mine_df = _today_df[_today_df['is_db'].fillna(False) | _today_df['is_bit'].fillna(False)]
        elif 'mall' in _today_df.columns:
            _mb_pat = '|'.join([x.strip() for x in (my_brand_1 + ',' + my_brand_2).split(',') if x.strip()])
            _mine_df = _today_df[_today_df['mall'].str.contains(_mb_pat, na=False, case=False, regex=True)]
        else:
            _mine_df = _today_df
        _today_kws = set(_mine_df['keyword'].unique())
    else:
        _today_kws = set()

    # 순위 변동 계산 — 브랜드별(드론박스/빛드론) 따로
    _improved_rows = []
    _dropped_rows  = []
    if not _today_df.empty and not _prev_df.empty and 'is_db' in _today_df.columns:
        _top1_today = _today_df.sort_values('rank').drop_duplicates('keyword')[['keyword','mall']].rename(columns={'mall':'top_mall'})
        _brand_mall_col = 'top1_mall' if 'top1_mall' in _prev_df.columns else ('mall' if 'mall' in _prev_df.columns else None)
        for _brand_col, _brand_name in [('is_db', '드론박스'), ('is_bit', '빛드론')]:
            _t_brand = _today_df[_today_df[_brand_col].fillna(False)]
            _p_brand = _prev_df[_prev_df[_brand_col].fillna(False)] if _brand_col in _prev_df.columns else pd.DataFrame()
            if _t_brand.empty or _p_brand.empty:
                continue
            _t_best = _t_brand.groupby('keyword')['rank'].min().reset_index().rename(columns={'rank': 'today_rank'})
            _p_best = _p_brand.groupby('keyword')['rank'].min().reset_index().rename(columns={'rank': 'prev_rank'})
            _chg = pd.merge(_t_best, _p_best, on='keyword', how='inner')
            _chg['delta'] = _chg['prev_rank'].astype(int) - _chg['today_rank'].astype(int)
            _chg = pd.merge(_chg, _top1_today, on='keyword', how='left')
            _chg['is_db']  = (_brand_name == '드론박스')
            _chg['is_bit'] = (_brand_name == '빛드론')
            _chg['brand']  = _brand_name
            _improved_rows += _chg[_chg['delta'] > 0].sort_values('delta', ascending=False).to_dict('records')
            _dropped_rows  += _chg[_chg['delta'] < 0].sort_values('delta').to_dict('records')
        _improved_rows.sort(key=lambda x: x['delta'], reverse=True)
        _dropped_rows.sort(key=lambda x: x['delta'])

    # 미노출 키워드 (keywords.txt 에 있지만 오늘 is_mine 없는 것)
    _missing_kws = [_kw for _kw in _all_kws if _kw not in _today_kws]
    # 미노출 키워드의 마지막 알려진 검색량 & 1위 경쟁사 & 1위 제품명
    _vol_map   = {}
    _top1_map  = {}
    _title_map = {}
    # crawled_df + hist_df 합쳐서 최대한 많은 키워드 커버
    _ref_frames = []
    if not crawled_df.empty:
        _ref_frames.append(crawled_df)
    if not hist_df.empty:
        # hist_df는 가장 최신 날짜만 사용
        _h_latest = hist_df[hist_df['date'] == hist_df['date'].max()]
        _ref_frames.append(_h_latest)
    if _ref_frames:
        _ref_df = pd.concat(_ref_frames, ignore_index=True)
        # 검색량
        if 'vol' in _ref_df.columns:
            _vol_map = _ref_df.groupby('keyword')['vol'].max().to_dict()
        # 1위 mall/title: rank 기준 정렬 후 키워드별 첫 행
        _ref_top1 = _ref_df.sort_values('rank').drop_duplicates('keyword')
        _mall_col = 'top1_mall' if 'top1_mall' in _ref_top1.columns else ('mall' if 'mall' in _ref_top1.columns else None)
        if _mall_col:
            _top1_map = _ref_top1.set_index('keyword')[_mall_col].to_dict()
        if 'title' in _ref_top1.columns:
            _title_map = _ref_top1.set_index('keyword')['title'].to_dict()

    # KPI 숫자
    _n_exposed = len(_today_kws)
    _n_up      = len(_improved_rows)
    _n_down    = len(_dropped_rows)
    _n_missing = len(_missing_kws)
    # 드론박스/빛드론 별도 노출 카운트
    _t_db_list  = [x.strip() for x in my_brand_1.split(',') if x.strip()]
    _t_bit_list = [x.strip() for x in my_brand_2.split(',') if x.strip()]
    if not _today_df.empty and 'is_db' in _today_df.columns:
        _n_db  = int(_today_df[_today_df['is_db'].fillna(False)]['keyword'].nunique())
        _n_bit = int(_today_df[_today_df['is_bit'].fillna(False)]['keyword'].nunique())
    elif not _today_df.empty and 'mall' in _today_df.columns:
        _db_pat  = '|'.join(_t_db_list)
        _bit_pat = '|'.join(_t_bit_list)
        _n_db  = int(_today_df[_today_df['mall'].str.contains(_db_pat,  na=False, case=False)]['keyword'].nunique())
        _n_bit = int(_today_df[_today_df['mall'].str.contains(_bit_pat, na=False, case=False)]['keyword'].nunique())
    else:
        _n_db = _n_bit = 0

    # ── 브랜드별 순위 변동 계산 ───────────────────────────────────────────────
    _up_db  = len([r for r in _improved_rows if r.get('is_db',  False)]) if _improved_rows else 0
    _up_bit = len([r for r in _improved_rows if r.get('is_bit', False)]) if _improved_rows else 0
    _dn_db  = len([r for r in _dropped_rows  if r.get('is_db',  False)]) if _dropped_rows  else 0
    _dn_bit = len([r for r in _dropped_rows  if r.get('is_bit', False)]) if _dropped_rows  else 0
    # 브랜드별 미노출 수 (전체 _missing_kws는 합산이므로 여기서는 합계만 절반씩)
    _ms_db  = sum(1 for kw in _missing_kws if kw not in _today_kws)
    _ms_bit = 0  # 브랜드별 미노출 분리가 어려울 경우 0 표시

    # ── 브랜드 패널 (드론박스 / 빛드론) ────────────────────────────────────────
    st.markdown(f"""
    <div class="km-brand-grid">
      <div class="km-brand-panel db">
        <div class="km-brand-head">
          <span class="km-brand-name">드론박스</span>
          <span class="km-brand-tag">DroneBox</span>
        </div>
        <div class="km-brand-body">
          <div class="km-brand-stat">
            <div class="km-stat-label">노출</div>
            <div class="km-stat-num">{_n_db}</div>
            <div class="km-stat-sub">키워드</div>
          </div>
          <div class="km-brand-stat">
            <div class="km-stat-label">상승</div>
            <div class="km-stat-num up">+{_up_db}</div>
            <div class="km-stat-sub">어제 대비</div>
          </div>
          <div class="km-brand-stat">
            <div class="km-stat-label">하락</div>
            <div class="km-stat-num {'dn' if _dn_db else 'ok'}">{'−'+str(_dn_db) if _dn_db else '0'}</div>
            <div class="km-stat-sub">{'즉시 확인' if _dn_db else '이상 없음'}</div>
          </div>
          <div class="km-brand-stat">
            <div class="km-stat-label">미노출</div>
            <div class="km-stat-num ms">{_n_missing}</div>
            <div class="km-stat-sub">기회 발굴</div>
          </div>
        </div>
      </div>
      <div class="km-brand-panel bit">
        <div class="km-brand-head">
          <span class="km-brand-name">빛드론</span>
          <span class="km-brand-tag">BitDrone</span>
        </div>
        <div class="km-brand-body">
          <div class="km-brand-stat">
            <div class="km-stat-label">노출</div>
            <div class="km-stat-num">{_n_bit}</div>
            <div class="km-stat-sub">키워드</div>
          </div>
          <div class="km-brand-stat">
            <div class="km-stat-label">상승</div>
            <div class="km-stat-num up">+{_up_bit}</div>
            <div class="km-stat-sub">어제 대비</div>
          </div>
          <div class="km-brand-stat">
            <div class="km-stat-label">하락</div>
            <div class="km-stat-num {'dn' if _dn_bit else 'ok'}">{'−'+str(_dn_bit) if _dn_bit else '0'}</div>
            <div class="km-stat-sub">{'즉시 확인' if _dn_bit else '이상 없음'}</div>
          </div>
          <div class="km-brand-stat">
            <div class="km-stat-label">미노출</div>
            <div class="km-stat-num ms">{_ms_bit}</div>
            <div class="km-stat-sub">기회 발굴</div>
          </div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    if _today_df.empty and not _all_kws:
        st.info("📌 'Run & Sync' 메뉴에서 수집을 먼저 실행하거나 Notion 새로고침을 눌러주세요.")

    # ── 섹션 1: 순위 하락 키워드 ─────────────────────────────────────────────
    st.markdown(f'<div class="km-block"><div class="km-block-head"><span class="km-block-title">📉 순위 하락 키워드</span><span class="km-badge km-badge-rd">{_n_down}개</span></div>', unsafe_allow_html=True)
    if _dropped_rows:
        _drop_data = []
        for _r in _dropped_rows:
            _drop_data.append({
                "브랜드":   _r.get('brand', '-'),
                "키워드":   _r['keyword'],
                "어제 순위": f"{int(_r['prev_rank'])}위",
                "오늘 순위": f"{int(_r['today_rank'])}위",
                "하락폭":   f"▼{abs(int(_r['delta']))}",
                "현재 1위": _r.get('top_mall', '-'),
            })
        _drop_df = pd.DataFrame(_drop_data)
        st.dataframe(_drop_df, use_container_width=True, hide_index=True)

        # SEO 제안 (Gemini)
        if gemini_key:
            with st.expander("🤖 하락 키워드 SEO 개선 제안 받기"):
                _sel_kw = st.selectbox("키워드 선택", [_r['keyword'] for _r in _dropped_rows], key="_seo_kw_sel")
                if st.button("SEO 제안 생성", key="_seo_btn"):
                    _sel_row = next((_r for _r in _dropped_rows if _r['keyword'] == _sel_kw), None)
                    if _sel_row:
                        with st.spinner("Gemini가 분석 중..."):
                            try:
                                _seo_prompt = f"""네이버 쇼핑 SEO 전문가로서 아래 상황에 맞는 즉시 실행 가능한 개선 방안을 제시해주세요.

키워드: {_sel_kw}
어제 순위: {int(_sel_row['prev_rank'])}위 → 오늘 순위: {int(_sel_row['today_rank'])}위 (▼{abs(int(_sel_row['delta']))} 하락)
현재 1위 경쟁사: {_sel_row.get('top_mall', '알 수 없음')}

다음 항목을 구체적으로 작성해주세요:
1. 순위 하락 가능 원인 (2~3가지)
2. 상품 제목 최적화 방법 (키워드 배치 예시 포함)
3. 즉시 실행할 수 있는 액션 3가지
"""
                                st.markdown(_gemini_generate(gemini_key, _seo_prompt))
                            except Exception as _seo_e:
                                st.error(f"Gemini 오류: {_seo_e}")
        else:
            st.caption("💡 사이드바에 Gemini API Key를 입력하면 SEO 개선 제안을 받을 수 있어요.")
    else:
        st.success("✅ 어제 대비 순위 하락 키워드가 없습니다.")

    st.markdown('</div>', unsafe_allow_html=True)

    # ── 섹션 2: 미노출 키워드 ────────────────────────────────────────────────
    st.markdown(f'<div class="km-block"><div class="km-block-head"><span class="km-block-title">🔍 미노출 키워드</span><span class="km-badge km-badge-am">{_n_missing}개</span></div>', unsafe_allow_html=True)
    if _missing_kws:
        _miss_data = []
        for _kw in _missing_kws:
            _v = _vol_map.get(_kw, 0)
            _miss_data.append({
                "키워드":     _kw,
                "월 검색량":  f"{int(_v):,}" if _v else "-",
                "1위 쇼핑몰": _top1_map.get(_kw, "-"),
                "1위 제품명": _title_map.get(_kw, "-"),
                "상태":       "미노출",
            })
        _miss_df = pd.DataFrame(_miss_data)
        if _vol_map:
            _miss_df['_vol_sort'] = _miss_df['키워드'].map(lambda x: _vol_map.get(x, 0))
            _miss_df = _miss_df.sort_values('_vol_sort', ascending=False).drop(columns=['_vol_sort'])
        st.dataframe(_miss_df, use_container_width=True, hide_index=True)
    elif _all_kws:
        st.success("✅ 모든 키워드에서 자사 상품이 노출 중입니다.")
    else:
        st.caption("keywords.txt에 모니터링 키워드를 등록하면 미노출 현황을 확인할 수 있어요.")

    st.markdown('</div>', unsafe_allow_html=True)

    # ── 섹션 3: 순위 상승 키워드 ─────────────────────────────────────────────
    st.markdown(f'<div class="km-block"><div class="km-block-head"><span class="km-block-title">📈 순위 상승 키워드</span><span class="km-badge km-badge-gr">{_n_up}개</span></div>', unsafe_allow_html=True)
    if _improved_rows:
        _up_data = []
        for _r in _improved_rows:
            _up_data.append({
                "브랜드":   _r.get('brand', '-'),
                "키워드":   _r['keyword'],
                "어제 순위": f"{int(_r['prev_rank'])}위",
                "오늘 순위": f"{int(_r['today_rank'])}위",
                "상승폭":   f"▲{int(_r['delta'])}",
            })
        st.dataframe(pd.DataFrame(_up_data), use_container_width=True, hide_index=True)
    else:
        st.info("어제 대비 순위 상승 키워드가 없습니다.")

    # ── 섹션 4: 경쟁사 1위 탈취 알림 ─────────────────────────────────────────
    _stolen = []
    if not hist_df.empty and not _today_df.empty:
        _h_dates = sorted(hist_df['date'].dropna().unique().tolist(), reverse=True)
        if _h_dates:
            _prev_top1_df = hist_df[hist_df['date'] == _h_dates[0]]
            _mall_col2 = 'top1_mall' if 'top1_mall' in _today_df.columns else ('mall' if 'mall' in _today_df.columns else None)
            _mall_col3 = 'top1_mall' if 'top1_mall' in _prev_top1_df.columns else ('mall' if 'mall' in _prev_top1_df.columns else None)
            if _mall_col2 and _mall_col3:
                _now_top1  = _today_df.sort_values('rank').drop_duplicates('keyword').set_index('keyword')[_mall_col2]
                _prev_top1 = _prev_top1_df.sort_values('rank').drop_duplicates('keyword').set_index('keyword')[_mall_col3]
                _my_brands_pat = '|'.join([x.strip() for x in (my_brand_1+','+my_brand_2).split(',') if x.strip()])
                for kw in _now_top1.index:
                    if kw not in _prev_top1.index: continue
                    _was = str(_prev_top1[kw])
                    _now = str(_now_top1[kw])
                    # 어제는 자사가 1위였는데 오늘은 다른 곳이 1위
                    import re as _re
                    if _re.search(_my_brands_pat, _was, _re.IGNORECASE) and not _re.search(_my_brands_pat, _now, _re.IGNORECASE):
                        _stolen.append({"키워드": kw, "어제 1위": _was, "오늘 1위 (탈취)": _now})

    st.markdown('</div>', unsafe_allow_html=True)

    _n_stolen = len(_stolen)
    st.markdown(f'<div class="km-block"><div class="km-block-head"><span class="km-block-title">⚔️ 경쟁사 1위 탈취</span><span class="km-badge km-badge-rd">{_n_stolen}개</span></div>', unsafe_allow_html=True)
    if _stolen:
        st.dataframe(pd.DataFrame(_stolen), use_container_width=True, hide_index=True)
    else:
        st.success("✅ 자사 1위 키워드를 경쟁사에 빼앗기지 않았습니다.")

    # ── 섹션 5: 기회 키워드 (검색량 높고 순위 20~60위) ──────────────────────
    _opp_data = []
    if not _today_df.empty and _vol_map:
        _mine_today = _today_df[_today_df['is_db'].fillna(False) | _today_df['is_bit'].fillna(False)] if 'is_db' in _today_df.columns else _today_df
        _best_rank_today = _mine_today.groupby('keyword')['rank'].min()
        for kw, rank in _best_rank_today.items():
            if 15 <= rank <= 60:
                vol = _vol_map.get(kw, 0)
                if vol >= 100:
                    _price_rows = _today_df[_today_df['keyword'] == kw].sort_values('rank')
                    _top1_price = int(_price_rows.iloc[0]['price']) if not _price_rows.empty and 'price' in _price_rows.columns else 0
                    _opp_data.append({"키워드": kw, "현재 순위": f"{int(rank)}위", "월 검색량": f"{int(vol):,}", "1위 가격": f"{_top1_price:,}원" if _top1_price else "-"})
    _opp_data.sort(key=lambda x: int(x["월 검색량"].replace(",","")), reverse=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="km-block"><div class="km-block-head"><span class="km-block-title">💡 기회 키워드</span><span class="km-badge km-badge-pp">{len(_opp_data)}개</span></div>', unsafe_allow_html=True)
    st.caption("검색량 100+ · 현재 순위 15~60위 · 조금만 올리면 상위 노출 가능한 키워드")
    if _opp_data:
        st.dataframe(pd.DataFrame(_opp_data), use_container_width=True, hide_index=True)
    else:
        st.info("기회 키워드가 없습니다. (수집 후 확인 가능)")

    # ── 섹션 6: CTR 낮은 키워드 (노출은 되는데 클릭 안 됨) ──────────────────
    _ctr_data = []
    if not _today_df.empty and 'ctr' in _today_df.columns:
        _ctr_kws = _today_df[(_today_df['is_db'].fillna(False) | _today_df['is_bit'].fillna(False)) & (_today_df['ctr'].fillna(0) > 0)] if 'is_db' in _today_df.columns else pd.DataFrame()
        if not _ctr_kws.empty:
            _ctr_best = _ctr_kws.groupby('keyword').agg(순위=('rank','min'), CTR=('ctr','max'), 검색량=('vol','max')).reset_index()
            _ctr_best = _ctr_best[_ctr_best['CTR'] < 2.0].sort_values('검색량', ascending=False)
            for _, row in _ctr_best.iterrows():
                _ctr_data.append({"키워드": row['keyword'], "최고 순위": f"{int(row['순위'])}위", "CTR": f"{row['CTR']:.2f}%", "월 검색량": f"{int(row['검색량']):,}"})
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="km-block"><div class="km-block-head"><span class="km-block-title">📉 CTR 낮은 키워드</span><span class="km-badge km-badge-am">{len(_ctr_data)}개</span></div>', unsafe_allow_html=True)
    st.caption("순위는 있지만 클릭률 2% 미만 — 썸네일·상품명 개선이 필요한 키워드")
    if _ctr_data:
        st.dataframe(pd.DataFrame(_ctr_data), use_container_width=True, hide_index=True)
    else:
        st.info("CTR 데이터가 없습니다. (수집 후 확인 가능)")
    st.markdown('</div>', unsafe_allow_html=True)

# ── 2. 일자별 순위 추이 ────────────────────────────────────────────────────────
elif selected_menu == "일자별 순위 추이":
    st.markdown("<div style='font-size:1.5rem;font-weight:800;color:#111;letter-spacing:-0.03em;margin-bottom:0.2rem;'>일자별 순위 추이</div><div style='font-size:0.82rem;color:#AAA;margin-bottom:1.4rem;'>키워드별 날짜 순위 변화 추적</div>", unsafe_allow_html=True)
    if not hist_df.empty:
        hist_df['date_obj'] = pd.to_datetime(hist_df['date']).dt.date
        min_date = hist_df['date_obj'].min()
        max_date = hist_df['date_obj'].max()
        default_start = max(min_date, max_date - dt.timedelta(days=14))
        col1, col2 = st.columns([1, 2])
        with col1:
            selected_dates = st.date_input("조회할 기간을 선택하세요", value=(default_start, max_date), min_value=min_date, max_value=max_date)
        with col2:
            all_kws = sorted(hist_df['keyword'].unique().tolist())
            selected_kws = st.multiselect("차트에 표시할 키워드 선택/제외", options=all_kws, default=all_kws[:5] if len(all_kws)>5 else all_kws)
        if len(selected_dates) == 2:
            start_date, end_date = selected_dates
            filtered_df = hist_df[(hist_df['date_obj'] >= start_date) & (hist_df['date_obj'] <= end_date)]
            if selected_kws:
                filtered_df = filtered_df[filtered_df['keyword'].isin(selected_kws)]
            if not filtered_df.empty:
                st.markdown("---")
                t_db  = [x.strip() for x in my_brand_1.split(',') if x.strip()]
                t_bit = [x.strip() for x in my_brand_2.split(',') if x.strip()]
                t_comp_list = [x.strip() for x in competitors.split(',') if x.strip()]
                all_brands = t_db + t_bit + t_comp_list
                chart_type = st.selectbox("차트 유형 선택", [
                    "선그래프 - 일자별 순위 추이",
                    "바차트 - 회사별 순위 비교",
                    "버블차트 - 검색량 vs 순위",
                    "히트맵 - 키워드x날짜",
                    "파이차트 - 1위 쇼핑몰 점유율",
                    "스캐터 - 순위 변동 분포",
                ])
                _sort_cols = [c for c in ['keyword','mall','title','date_obj'] if c in filtered_df.columns]
                filtered_df = filtered_df.sort_values(_sort_cols)

                if "선그래프" in chart_type:
                    try:
                        selection = alt.selection_point(fields=['keyword'], bind='legend')
                    except AttributeError:
                        selection = alt.selection_multi(fields=['keyword'], bind='legend')
                    if 'mall' in filtered_df.columns:
                        lf = filtered_df[filtered_df['mall'].str.contains("|".join(t_db+t_bit), na=False, regex=True)]
                    else:
                        lf = filtered_df
                    _gc = [c for c in ['date','keyword','title','mall'] if c in lf.columns]
                    line_df = lf.groupby(_gc, as_index=False)['rank'].min()
                    line_df['데이터유형'] = '실제 수집 데이터'
                    st.caption("키워드를 1~3개로 좁혀서 보시는 것이 좋습니다.")
                    use_ai_pred = st.toggle("AI 추세 예측 (향후 5일)", value=False)
                    if use_ai_pred:
                        import numpy as np
                        future_rows = []
                        _ag = [c for c in ['keyword','title','mall'] if c in line_df.columns]
                        for gk, grp in line_df.groupby(_ag):
                            if not isinstance(gk, tuple): gk = (gk,)
                            kw = gk[0]; ti = gk[1] if len(gk)>1 else ''; ml = gk[2] if len(gk)>2 else ''
                            if len(grp) >= 2:
                                gr = grp.tail(7)
                                poly = np.polyfit(np.arange(len(gr)), gr['rank'].values, 1)
                                ld2 = pd.to_datetime(gr['date'].iloc[-1])
                                lr = gr['rank'].iloc[-1]
                                future_rows.append({'date': ld2.strftime('%Y-%m-%d'), 'keyword': kw, 'title': ti, 'mall': ml, 'rank': lr, '데이터유형': 'AI 예측'})
                                for i in range(1, 6):
                                    future_rows.append({'date': (ld2+dt.timedelta(days=i)).strftime('%Y-%m-%d'), 'keyword': kw, 'title': ti, 'mall': ml, 'rank': max(1, min(100, round(poly[0]*(len(gr)-1+i)+poly[1]))), '데이터유형': 'AI 예측'})
                        if future_rows:
                            line_df = pd.concat([line_df, pd.DataFrame(future_rows)], ignore_index=True)
                    if not line_df.empty:
                        mr = max(int(line_df['rank'].max()+2), 5)
                        bc2 = alt.Chart(line_df).encode(
                            x=alt.X('date:O', title='날짜', axis=alt.Axis(labelAngle=-45)),
                            y=alt.Y('rank:Q', scale=alt.Scale(reverse=True, domain=[mr,1], nice=False), title='순위'),
                            color=alt.Color('keyword:N', legend=alt.Legend(title="키워드", orient="right")),
                            tooltip=['date:N','keyword:N','rank:Q']
                        )
                        chart = bc2.mark_line(point=True, strokeWidth=2).properties(height=450, background="transparent").interactive()
                        st.altair_chart(chart, use_container_width=True, theme="streamlit")
                    else:
                        st.info("자사 데이터가 없습니다.")

                elif "바차트" in chart_type:
                    selected_brands = st.multiselect("비교할 회사 선택", options=all_brands, default=all_brands[:min(4,len(all_brands))])
                    latest_date2 = filtered_df['date'].max()
                    ld_df2 = filtered_df[filtered_df['date']==latest_date2]
                    if 'mall' in ld_df2.columns and selected_brands:
                        bar_rows = []
                        for kw in selected_kws:
                            kd2 = ld_df2[ld_df2['keyword']==kw]
                            for brand in selected_brands:
                                bd2 = kd2[kd2['mall'].str.contains(brand, na=False, case=False)]
                                best2 = int(bd2['rank'].min()) if not bd2.empty else None
                                if best2:
                                    bar_rows.append({'키워드': kw, '회사': brand, '순위': best2})
                        bar_df = pd.DataFrame(bar_rows)
                        if not bar_df.empty:
                            chart = alt.Chart(bar_df).mark_bar().encode(
                                x=alt.X('키워드:N', axis=alt.Axis(labelAngle=-30)),
                                y=alt.Y('순위:Q', scale=alt.Scale(reverse=True, domain=[100,1]), title='순위'),
                                color=alt.Color('회사:N'),
                                xOffset='회사:N',
                                tooltip=['키워드:N','회사:N','순위:Q']
                            ).properties(height=450, background="transparent", title=f"{latest_date2} 기준").interactive()
                            st.altair_chart(chart, use_container_width=True, theme="streamlit")
                        else:
                            st.info("선택한 회사의 데이터가 없습니다.")
                    else:
                        st.info("회사를 선택해주세요.")

                elif "버블차트" in chart_type:
                    latest_date3 = filtered_df['date'].max()
                    bb = filtered_df[filtered_df['date']==latest_date3].copy()
                    bb['vol'] = pd.to_numeric(bb['vol'] if 'vol' in bb.columns else 0, errors='coerce').fillna(0)
                    if 'mall' in bb.columns:
                        bb = bb[bb['mall'].str.contains("|".join(t_db+t_bit), na=False, regex=True)]
                    ba = bb.groupby('keyword', as_index=False).agg({'rank':'min','vol':'first'})
                    ba = ba[ba['rank']<=100]
                    if not ba.empty:
                        chart = alt.Chart(ba).mark_circle().encode(
                            x=alt.X('rank:Q', scale=alt.Scale(reverse=True, domain=[100,1]), title='순위'),
                            y=alt.Y('vol:Q', title='월간 검색량'),
                            size=alt.Size('vol:Q', scale=alt.Scale(range=[50,1000]), legend=None),
                            color=alt.Color('keyword:N', legend=None),
                            tooltip=['keyword:N','rank:Q','vol:Q']
                        ).properties(height=450, background="transparent").interactive()
                        st.altair_chart(chart, use_container_width=True, theme="streamlit")
                        st.caption("오른쪽 위 = 검색량 많고 순위 좋음 (이상적)")
                    else:
                        st.info("데이터가 없습니다.")

                elif "히트맵" in chart_type:
                    if 'mall' in filtered_df.columns:
                        hm = filtered_df[filtered_df['mall'].str.contains("|".join(t_db+t_bit), na=False, regex=True)]
                    else:
                        hm = filtered_df
                    brk = hm.groupby(['date','keyword'], as_index=False)['rank'].min()
                    brk['rank_display'] = brk['rank'].apply(lambda x: str(int(x)) if x<=10 else "10+")
                    brk['rank_color']   = brk['rank'].apply(lambda x: x if x<=10 else 11)
                    base2 = alt.Chart(brk).encode(x=alt.X('date:O', axis=alt.Axis(labelAngle=-45)), y=alt.Y('keyword:N'))
                    rects2 = base2.mark_rect().encode(
                        color=alt.Color('rank_color:Q', scale=alt.Scale(domain=[1,3,5,10,11], range=['#00e5ff','#0ea5e9','#3b82f6','#1e3a8a','#374151']), legend=None),
                        tooltip=['date:N','keyword:N','rank:Q']
                    )
                    text2 = base2.mark_text(baseline='middle', color='#fff', fontWeight='bold').encode(text='rank_display:N')
                    st.altair_chart((rects2+text2).properties(height=max(300, len(selected_kws)*45), background="transparent").interactive(), use_container_width=True, theme="streamlit")

                elif "파이차트" in chart_type:
                    latest_date4 = filtered_df['date'].max()
                    pie_df2 = filtered_df[filtered_df['date']==latest_date4]
                    if 'mall' in pie_df2.columns:
                        t1b = pie_df2[pie_df2['rank']==1][['keyword','mall']].drop_duplicates('keyword').copy()
                        def _lbl(m):
                            for b in all_brands:
                                if b.lower() in str(m).lower(): return b
                            return '기타'
                        t1b['브랜드'] = t1b['mall'].apply(_lbl)
                        pa2 = t1b.groupby('브랜드', as_index=False).size().rename(columns={'size':'키워드수'})
                        chart = alt.Chart(pa2).mark_arc(innerRadius=60).encode(
                            theta=alt.Theta('키워드수:Q'),
                            color=alt.Color('브랜드:N'),
                            tooltip=['브랜드:N','키워드수:Q']
                        ).properties(height=380, background="transparent", title=f"{latest_date4} 1위 점유율")
                        st.altair_chart(chart, use_container_width=True, theme="streamlit")
                    else:
                        st.info("mall 컬럼이 있는 데이터가 필요합니다.")

                elif "스캐터" in chart_type:
                    ds2 = sorted(filtered_df['date'].unique())
                    if len(ds2) >= 2:
                        pd_date2, cd_date2 = ds2[-2], ds2[-1]
                        if 'mall' in filtered_df.columns:
                            sf2 = filtered_df[filtered_df['mall'].str.contains("|".join(t_db+t_bit), na=False, regex=True)]
                        else:
                            sf2 = filtered_df
                        pr2 = sf2[sf2['date']==pd_date2].groupby('keyword')['rank'].min().rename('prev')
                        cr2 = sf2[sf2['date']==cd_date2].groupby('keyword')['rank'].min().rename('curr')
                        sc2 = pd.concat([pr2,cr2],axis=1).dropna().reset_index()
                        sc2['변동'] = sc2['prev'] - sc2['curr']
                        sc2['색상'] = sc2['변동'].apply(lambda x: '상승' if x>0 else ('하락' if x<0 else '유지'))
                        chart = alt.Chart(sc2).mark_circle(size=80).encode(
                            x=alt.X('prev:Q', scale=alt.Scale(reverse=True), title=f'이전({pd_date2})'),
                            y=alt.Y('curr:Q', scale=alt.Scale(reverse=True), title=f'현재({cd_date2})'),
                            color=alt.Color('색상:N', scale=alt.Scale(domain=['상승','유지','하락'], range=['#22c55e','#9ca3af','#ef4444'])),
                            tooltip=['keyword:N','prev:Q','curr:Q','변동:Q']
                        ).properties(height=450, background="transparent").interactive()
                        mx2 = int(max(sc2['prev'].max(), sc2['curr'].max(), 10))
                        diag2 = alt.Chart(pd.DataFrame({'x':[1,mx2],'y':[1,mx2]})).mark_line(strokeDash=[4,4], color='#aaa').encode(x='x:Q', y='y:Q')
                        st.altair_chart((chart+diag2).interactive(), use_container_width=True, theme="streamlit")
                        st.caption("대각선 위 = 순위 상승, 아래 = 순위 하락")
                    else:
                        st.info("스캐터 차트는 최소 2일 이상의 데이터가 필요합니다.")

            else:
                st.warning("선택한 기간/키워드에 해당하는 데이터가 없습니다.")

            st.markdown("---")
            st.markdown("#### 📥 Excel 리포트 다운로드")
            _xl_col1, _xl_col2, _xl_col3 = st.columns(3)
            with _xl_col1:
                if st.button("📊 현재 필터 데이터 Excel", use_container_width=True):
                    if not filtered_df.empty:
                        _xls = generate_excel_report(filtered_df, "순위 데이터")
                        st.download_button("⬇️ 다운로드", data=_xls, file_name=f"키워드맵_{start_date}~{end_date}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                    else:
                        st.warning("데이터가 없습니다.")
            with _xl_col2:
                if st.button("📅 최근 7일 Excel", use_container_width=True):
                    _7d_df = hist_df[hist_df['date_obj'] >= max_date - dt.timedelta(days=7)]
                    if not _7d_df.empty:
                        st.download_button("⬇️ 주간 다운로드", data=generate_excel_report(_7d_df, "주간 리포트"), file_name=f"키워드맵_주간_{max_date}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                    else:
                        st.warning("데이터가 없습니다.")
            with _xl_col3:
                if st.button("📆 최근 30일 Excel", use_container_width=True):
                    _30d_df = hist_df[hist_df['date_obj'] >= max_date - dt.timedelta(days=30)]
                    if not _30d_df.empty:
                        st.download_button("⬇️ 월간 다운로드", data=generate_excel_report(_30d_df, "월간 리포트"), file_name=f"키워드맵_월간_{max_date}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                    else:
                        st.warning("데이터가 없습니다.")
        else:
            st.info("시작일과 종료일을 모두 선택해주세요.")
    else:
        st.warning("과거 데이터가 없습니다. 대시보드에서 데이터 동기화를 먼저 진행해주세요.")

# ── 3. 경쟁사 집중 분석 ────────────────────────────────────────────────────────
elif selected_menu == "경쟁사 집중 분석":
    st.markdown("<div style='font-size:1.5rem;font-weight:800;color:#111;letter-spacing:-0.03em;margin-bottom:0.2rem;'>경쟁사 집중 분석</div><div style='font-size:0.82rem;color:#AAA;margin-bottom:1.4rem;'>1페이지 점유율·순위 혈투·마법 단어 추출</div>", unsafe_allow_html=True)
    if hist_df.empty:
        st.warning("과거 데이터가 없습니다.")
    else:
        latest_date = sorted(hist_df['date'].dropna().unique().tolist(), reverse=True)[0]
        st.markdown(f"**기준일:** {latest_date}")
        target_df = hist_df[hist_df['date'] == latest_date]
        t_db   = [x.strip() for x in my_brand_1.split(',') if x.strip()]
        t_bit  = [x.strip() for x in my_brand_2.split(',') if x.strip()]
        t_comp = [x.strip() for x in competitors.split(',') if x.strip()]
        comp_count = {}
        for brand in t_db + t_bit + t_comp:
            comp_count[brand] = target_df[(target_df['mall'].str.contains(brand, na=False)) & (target_df['rank'] <= 10)]['keyword'].nunique()
        chart_df = pd.DataFrame(list(comp_count.items()), columns=["추적 대상 브랜드", "10위 이내 노출 수"])
        chart_df = chart_df[chart_df["10위 이내 노출 수"] > 0].sort_values("10위 이내 노출 수", ascending=False)
        if not chart_df.empty:
            st.altair_chart(alt.Chart(chart_df).mark_bar(cornerRadiusTopLeft=8, cornerRadiusTopRight=8, color="#3b82f6").encode(x=alt.X('추적 대상 브랜드:N', sort='-y'), y=alt.Y('10위 이내 노출 수:Q'), tooltip=['추적 대상 브랜드','10위 이내 노출 수']).properties(height=500), use_container_width=True)
            st.download_button("📥 차트 데이터 다운로드 (CSV)", data=chart_df.to_csv(index=False).encode('utf-8-sig'), file_name=f"Competitor_Data_{latest_date}.csv", mime="text/csv")
        else:
            st.info("현재 분석 대상 브랜드 중 10위 안에 진입한 상품이 없습니다.")

        st.markdown("---")
        st.subheader("🕵️ 타사 브랜드 X-Ray 정밀 타격")
        all_comp_kws = sorted(hist_df['keyword'].dropna().unique().tolist())
        target_kw = st.selectbox("전략을 분석할 핵심 타겟 키워드", all_comp_kws)
        tab1, tab2, tab3 = st.tabs(["🥊 1:1 라이벌 데스매치", "🍰 1페이지 매대 점유율", "🥷 마법 단어 해킹기"])

        with tab1:
            comp_options = [c for c in t_comp if hist_df[(hist_df['keyword']==target_kw) & (hist_df['mall'].str.contains(c, na=False))].shape[0] > 0] or t_comp
            rival = st.selectbox("비교할 타겟 경쟁사 선택", comp_options)
            dm_df = hist_df[(hist_df['keyword']==target_kw) & (hist_df['mall'].str.contains(f"{('|'.join(t_db+t_bit))}|{rival}", na=False, regex=True))].copy()
            if not dm_df.empty:
                dm_trend = dm_df.groupby(['date','mall'], as_index=False)['rank'].min().sort_values('date')
                max_rank_dm = max(int(dm_trend['rank'].max()+2), 5)
                st.altair_chart(alt.Chart(dm_trend).mark_line(point=True, strokeWidth=4).encode(x=alt.X('date:O',title='날짜',axis=alt.Axis(labelAngle=-45,labelColor="#9ca3af",titleColor="#9ca3af")), y=alt.Y('rank:Q',title='최고 노출 순위',scale=alt.Scale(reverse=True,domain=[max_rank_dm,1],nice=False),axis=alt.Axis(labelColor="#9ca3af",titleColor="#9ca3af")), color=alt.Color('mall:N',title='쇼핑몰',legend=alt.Legend(orient="bottom",labelColor="#d1d5db",titleColor="#9ca3af")), tooltip=[alt.Tooltip('date:N',title='날짜'),alt.Tooltip('mall:N',title='쇼핑몰'),alt.Tooltip('rank:Q',title='최고 랭킹')]).properties(height=450, background="transparent").interactive(), use_container_width=True, theme="streamlit")
            else:
                st.info(f"해당 키워드에 대한 타사({rival}) 비교 데이터가 부족합니다.")

        with tab2:
            share_df = hist_df[(hist_df['date']==latest_date) & (hist_df['keyword']==target_kw) & (hist_df['rank']<=40)].copy()
            share_df = share_df[share_df['mall'].str.contains("|".join(t_db+t_bit+t_comp), na=False, regex=True)].drop_duplicates(subset=['mall','title'])
            if not share_df.empty:
                share_counts = share_df.groupby('mall').size().reset_index(name='1페이지 고유 상품 개수').sort_values(by='1페이지 고유 상품 개수', ascending=False)
                col1, col2 = st.columns([1,1])
                with col1:
                    st.altair_chart(alt.Chart(share_counts).mark_arc(innerRadius=60, cornerRadius=4, stroke="#1e1e2d", strokeWidth=2).encode(theta=alt.Theta(field="1페이지 고유 상품 개수",type="quantitative"), color=alt.Color(field="mall",type="nominal",title="쇼핑몰",legend=alt.Legend(orient="right",labelColor="#d1d5db",titleColor="#9ca3af")), tooltip=['mall:N','1페이지 고유 상품 개수:Q']).properties(height=400, background="transparent"), use_container_width=True, theme="streamlit")
                with col2:
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    st.dataframe(share_counts.reset_index(drop=True), use_container_width=True)
            else:
                st.info("1페이지(40위 이내)에 진입한 브랜드 데이터가 없습니다.")

        with tab3:
            title_df = hist_df[(hist_df['date']==latest_date) & (hist_df['keyword']==target_kw) & (hist_df['rank']<=20)].copy()
            if not title_df.empty:
                import re
                from collections import Counter
                words = []
                for title in title_df['title'].dropna():
                    words.extend([w for w in re.sub(r'[^가-힣a-zA-Z0-9\s]',' ',title).split() if w])
                stop_words = ["dji","및","등","용","수","할","정품","드론","전용","dji온라인판매점","dji공식판매점", target_kw.split()[0].lower()]
                filtered_words = [w for w in words if len(w)>1 and w.lower() not in stop_words]
                word_counts = Counter(filtered_words).most_common(15)
                if word_counts:
                    word_df = pd.DataFrame(word_counts, columns=["추출된 마법 단어","Top 20 내 등장 횟수"])
                    st.altair_chart(alt.Chart(word_df).mark_bar(color="#60a5fa", cornerRadiusTopRight=4, cornerRadiusBottomRight=4).encode(x=alt.X('Top 20 내 등장 횟수:Q',axis=alt.Axis(labelColor="#9ca3af",titleColor="#9ca3af")), y=alt.Y("추출된 마법 단어:N",sort='-x',axis=alt.Axis(labelColor="#d1d5db",titleColor="#9ca3af")), tooltip=["추출된 마법 단어","Top 20 내 등장 횟수"]).properties(height=400, background="transparent"), use_container_width=True, theme="streamlit")
                else:
                    st.info("유의미한 단어 추출 결과가 없습니다.")
            else:
                st.info("상위 20위 데이터가 없습니다.")

# ── 4. 틈새 키워드 발굴기 ──────────────────────────────────────────────────────
elif selected_menu == "틈새 키워드 발굴기":
    st.markdown("<div style='font-size:1.5rem;font-weight:800;color:#111;letter-spacing:-0.03em;margin-bottom:0.2rem;'>틈새 키워드 발굴기</div><div style='font-size:0.82rem;color:#AAA;margin-bottom:1.4rem;'>경쟁 낮고 검색량 높은 꿀 키워드 탐색</div>", unsafe_allow_html=True)
    if 'save_base_kw' not in st.session_state: st.session_state.save_base_kw = "미니드론"
    col1, col2 = st.columns([3, 1])
    with col1:
        base_kw = st.text_input("💡 탐색 기준 단어 입력", value=st.session_state.save_base_kw)
        st.session_state.save_base_kw = base_kw
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        search_btn = st.button("🚀 추천 키워드 탐색 발사", use_container_width=True)
    if search_btn:
        if not (ad_api_key and ad_sec_key and ad_cus_id):
            st.error("네이버 광고 API 정보를 사이드바에서 입력해주세요.")
        else:
            with st.spinner(f"'{base_kw}' 연관 키워드 파싱 중..."):
                try:
                    ts = str(int(time.time() * 1000))
                    sig = base64.b64encode(hmac.new(ad_sec_key.encode(), f"{ts}.GET./keywordstool".encode(), hashlib.sha256).digest()).decode()
                    headers = {**HTTP_HEADERS, "X-Timestamp": ts, "X-API-KEY": ad_api_key, "X-Customer": ad_cus_id, "X-Signature": sig}
                    res = requests.get(f"https://api.naver.com/keywordstool?hintKeywords={base_kw.replace(' ','')}&showDetail=1", headers=headers, timeout=10)
                    res.raise_for_status()
                    results = []
                    for i in res.json().get('keywordList', [])[:300]:
                        v = int(str(i['monthlyPcQcCnt']).replace("< 10","10")) + int(str(i['monthlyMobileQcCnt']).replace("< 10","10"))
                        c = float(str(i['monthlyAvePcClkCnt']).replace("< 10","10")) + float(str(i['monthlyAveMobileClkCnt']).replace("< 10","10"))
                        if v > 50:
                            results.append({"연관 추천 타겟 키워드": i['relKeyword'], "월별 통합 잠재 고객 수 (검색량)": v, "기존 평균 클릭률": c})
                    if results:
                        kw_df = pd.DataFrame(results).sort_values("월별 통합 잠재 고객 수 (검색량)", ascending=False).head(100)
                        st.success(f"잠재 키워드 TOP 100개 발굴 완료!")
                        st.dataframe(kw_df, use_container_width=True)
                        st.download_button("📥 발굴 키워드 다운로드 (CSV)", data=kw_df.to_csv(index=False).encode('utf-8-sig'), file_name=f"{base_kw}_SecretKeywords.csv", mime="text/csv")
                    else:
                        st.warning("유의미한 연관 키워드를 찾지 못했습니다.")
                except Exception as e:
                    st.error(f"API 오류: {str(e)}")

# ── 5. SEO태그 생성기 ──────────────────────────────────────────────────────────
elif selected_menu == "SEO태그 생성기":
    st.markdown("<div style='font-size:1.5rem;font-weight:800;color:#111;letter-spacing:-0.03em;margin-bottom:0.2rem;'>SEO 태그 생성기</div><div style='font-size:0.82rem;color:#AAA;margin-bottom:1.4rem;'>AI 기반 제품 메타태그 & GEO 최적화</div>", unsafe_allow_html=True)
    if 'save_target_kw' not in st.session_state: st.session_state.save_target_kw = ""
    if 'save_target_product' not in st.session_state: st.session_state.save_target_product = ""
    if 'save_mall_name' not in st.session_state: st.session_state.save_mall_name = "드론박스"
    if 'save_usps' not in st.session_state: st.session_state.save_usps = ""
    col1, col2 = st.columns([1, 1])
    with col1:
        kw_options = sorted(hist_df['keyword'].dropna().unique().tolist()) if not hist_df.empty else []
        kw_options.insert(0, "신규 제품 (직접 입력)")
        idx = kw_options.index(st.session_state.save_target_kw) if st.session_state.save_target_kw in kw_options else 0
        selected_kw_option = st.selectbox("🎯 타겟 키워드", options=kw_options, index=idx)
        if selected_kw_option == "신규 제품 (직접 입력)":
            target_kw = st.text_input("💡 신규 키워드 입력", value=st.session_state.save_target_kw if st.session_state.save_target_kw not in kw_options else "", placeholder="예: 미니드론 프로")
        else:
            target_kw = selected_kw_option
        st.session_state.save_target_kw = target_kw
        target_product = st.text_input("📦 내 상품명 (선택)", placeholder="예: DJI 네오 2", value=st.session_state.save_target_product)
        st.session_state.save_target_product = target_product
        mall_name = st.text_input("🏢 우리 쇼핑몰명", value=st.session_state.save_mall_name)
        st.session_state.save_mall_name = mall_name
    with col2:
        usps = st.text_area("✨ 핵심 특장점", placeholder="가벼운 무게, 전방 LiDAR 센서 등", height=110, value=st.session_state.save_usps)
        st.session_state.save_usps = usps
    if st.button("🌟 1등 벤치마킹 SEO & GEO 문구 자동 생성", use_container_width=True, type="primary"):
        if not gemini_key:
            st.error("사이드바에서 Gemini API Key를 입력해주세요.")
        else:
            with st.spinner("SEO & GEO 데이터 생성 중..."):
                top1_title = "조회된 1위 데이터 없음"
                if not hist_df.empty:
                    top1_df = hist_df[(hist_df['keyword']==target_kw) & (hist_df['rank']==1)]
                    if not top1_df.empty:
                        r = top1_df.sort_values('date', ascending=False).iloc[0]
                        top1_title = f"{r['mall']}: {r['title']}"
                if top1_title == "조회된 1위 데이터 없음" and target_kw:
                    try:
                        items = get_rank(target_kw, naver_cid, naver_csec)
                        if items:
                            top1_title = f"{items[0]['mallName']}: {items[0]['title'].replace('<b>','').replace('</b>','')}"
                    except: pass
                prompt = f"""당신은 네이버 쇼핑 및 SEO/GEO 전문 마케터입니다.
[입력]
- 타겟 키워드: {target_kw}
- 내 상품명: {target_product if target_product else '(키워드 기반으로 생성)'}
- 쇼핑몰명: {mall_name}
- 특장점: {usps if usps else '없음'}
- 현재 1등 상품: {top1_title}

[요청] 다음 형식으로만 출력 (마크다운 블록 금지):
Title: (제목)
Author: {mall_name}
Description: (1~2문장 설명)
Keywords: (콤마 구분 15개)
Attributes: (캐럿^ 구분 속성, 500자 이하)
SearchTags: (수직선| 구분 최대 10개 태그)"""
                try:
                    response_text = _gemini_generate(gemini_key, prompt)
                    if not response_text:
                        st.error("API 응답 실패. 키를 확인하세요.")
                    else:
                        st.success("✨ SEO & GEO 태그 생성 완료!")
                        import re as _re
                        _FIELDS = "Title|Author|Description|Keywords|Attributes|SearchTags"
                        res_dict = {m.group(1): m.group(2).strip() for m in _re.compile(rf'^({_FIELDS}):\s*(.*?)(?=\n(?:{_FIELDS}):|$)', _re.DOTALL|_re.MULTILINE).finditer(response_text)}
                        st.markdown("<br>", unsafe_allow_html=True)
                        def render_row(label, value):
                            c1, c2 = st.columns([1, 4])
                            c1.markdown(f"**{label}**")
                            c2.code(value, language='text')
                            st.divider()
                        render_row("타이틀 (Title)", res_dict.get('Title','생성 실패'))
                        render_row("Author", res_dict.get('Author', mall_name))
                        render_row("Description", res_dict.get('Description','생성 실패'))
                        render_row("Keywords", res_dict.get('Keywords','생성 실패'))
                        render_row("Attributes (^)", res_dict.get('Attributes','생성 실패'))
                        render_row("SearchTags (|)", res_dict.get('SearchTags','생성 실패'))
                        st.info("💡 위 결과를 스마트스토어 SEO 태그 설정에 붙여넣으세요.")
                except Exception as e:
                    st.error(f"생성 중 오류: {e}")

# ── 6. Run & Sync ──────────────────────────────────────────────────────────────
elif selected_menu == "Run & Sync":
    st.markdown("<div style='font-size:1.5rem;font-weight:800;color:#111;letter-spacing:-0.03em;margin-bottom:0.2rem;'>Run & Sync</div><div style='font-size:0.82rem;color:#AAA;margin-bottom:1.4rem;'>실시간 순위 수집 · Notion 동기화</div>", unsafe_allow_html=True)

    st.markdown("---")

    with st.expander("📥 Google Sheets / CSV 데이터 가져오기", expanded=False):
        st.markdown("**방법 1** — 구글 시트 링크로 바로 가져오기")
        _gs_url = st.text_input("구글 시트 공유 링크 붙여넣기", placeholder="https://docs.google.com/spreadsheets/d/...", key="_gs_url_input")
        st.caption("⚠️ 시트 공유 설정이 **'링크가 있는 모든 사용자'→ 뷰어** 로 되어 있어야 합니다.")
        _gs_sheet_name = st.text_input("시트 이름 (기본값: 첫 번째 시트)", placeholder="Sheet1", key="_gs_sheet_name", value="")
        if st.button("🔗 링크로 데이터 가져오기", key="_gs_fetch_btn"):
            if not _gs_url.strip():
                st.warning("구글 시트 링크를 입력해주세요.")
            else:
                try:
                    import re as _re
                    _gid_match = _re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', _gs_url)
                    if not _gid_match:
                        st.error("❌ 올바른 구글 시트 링크가 아닙니다.")
                    else:
                        _sheet_id = _gid_match.group(1)
                        _tab_match = _re.search(r'[#&?]gid=(\d+)', _gs_url)
                        _tab_gid = _tab_match.group(1) if _tab_match else "0"
                        _export_url = f"https://docs.google.com/spreadsheets/d/{_sheet_id}/export?format=csv&gid={_tab_gid}"
                        if _gs_sheet_name.strip():
                            import urllib.parse as _up
                            _export_url += f"&sheet={_up.quote(_gs_sheet_name.strip())}"
                        with st.spinner("구글 시트에서 데이터를 불러오는 중..."):
                            _gs_resp = requests.get(_export_url, timeout=15)
                        if _gs_resp.status_code == 200:
                            _csv_df2 = None
                            for _enc in ["utf-8-sig","utf-8","cp949","euc-kr"]:
                                try:
                                    _csv_df2 = pd.read_csv(io.BytesIO(_gs_resp.content), encoding=_enc)
                                    break
                                except: continue
                            if _csv_df2 is None:
                                st.error("데이터를 읽을 수 없습니다. 인코딩 문제일 수 있습니다.")
                            else:
                                st.session_state["_gs_fetched_df"] = _csv_df2
                                st.success(f"✅ {len(_csv_df2):,}행 로드 완료!")
                                st.rerun()
                        elif _gs_resp.status_code == 403:
                            st.error("❌ 접근 권한 없음 — 시트 공유 설정을 '링크가 있는 모든 사용자 → 뷰어'로 바꿔주세요.")
                        else:
                            st.error(f"❌ 데이터 가져오기 실패 (HTTP {_gs_resp.status_code})")
                except Exception as _gs_err:
                    st.error(f"❌ 오류: {_gs_err}")

        _uploaded_csv_df = st.session_state.get("_gs_fetched_df", None)
        st.markdown("---")
        st.markdown("**방법 2** — CSV 파일 직접 업로드")
        _uploaded_csv = st.file_uploader("CSV 파일 선택", type=["csv"], key="_csv_uploader")
        if _uploaded_csv is not None:
            _csv_df2b = None
            for _enc in ["utf-8-sig","utf-8","cp949","euc-kr"]:
                try:
                    _csv_df2b = pd.read_csv(io.BytesIO(_uploaded_csv.read()), encoding=_enc)
                    break
                except: continue
            if _csv_df2b is not None:
                _uploaded_csv_df = _csv_df2b
            else:
                st.error("파일 인코딩을 인식할 수 없습니다.")

        if _uploaded_csv_df is not None:
            try:
                _csv_df = _uploaded_csv_df
                st.success(f"✅ {len(_csv_df):,}행 로드됨 | 컬럼: {list(_csv_df.columns)}")
                st.dataframe(_csv_df.head(3), use_container_width=True)
                st.markdown("#### 컬럼 매핑")
                _col_opts = ["(없음)"] + list(_csv_df.columns)
                def _auto_detect(candidates):
                    for _c in candidates:
                        if _c in _csv_df.columns: return _c
                    for _c in _csv_df.columns:
                        if _c.lower().replace(" ","") in [x.lower().replace(" ","") for x in candidates]: return _c
                    return "(없음)"
                _cm1, _cm2 = st.columns(2)
                with _cm1:
                    _map_date    = st.selectbox("📅 날짜",    _col_opts, index=_col_opts.index(_auto_detect(["date","날짜","일자","Date","수집일"])), key="_map_date")
                    _map_keyword = st.selectbox("🔑 키워드",  _col_opts, index=_col_opts.index(_auto_detect(["keyword","키워드","Keyword","검색어"])), key="_map_kw")
                    _map_rank    = st.selectbox("🏆 순위",    _col_opts, index=_col_opts.index(_auto_detect(["rank","순위","Rank","노출순위"])), key="_map_rank")
                    _map_mall    = st.selectbox("🏪 쇼핑몰",  _col_opts, index=_col_opts.index(_auto_detect(["mall","쇼핑몰","Mall","seller","판매자"])), key="_map_mall")
                with _cm2:
                    _map_vol     = st.selectbox("📊 검색량",  _col_opts, index=_col_opts.index(_auto_detect(["vol","검색량","volume","Vol","월검색량"])), key="_map_vol")
                    _map_title   = st.selectbox("📦 상품명",  _col_opts, index=_col_opts.index(_auto_detect(["title","상품명","제목","Title","product"])), key="_map_title")
                    _map_price   = st.selectbox("💰 가격",    _col_opts, index=_col_opts.index(_auto_detect(["price","가격","Price","판매가"])), key="_map_price")
                    _map_ctr     = st.selectbox("🖱️ 클릭률", _col_opts, index=_col_opts.index(_auto_detect(["ctr","클릭률","CTR","클릭율"])), key="_map_ctr")
                _fallback_date = st.date_input("날짜 컬럼이 없을 경우 기준 날짜", value=dt.date.today(), key="_csv_fallback_date")
                _sync_to_notion = st.checkbox("✅ 업로드 후 Notion에도 저장", value=bool(notion_token and notion_db_id), key="_csv_notion_sync")
                if st.button("📤 데이터 불러오기", type="primary", key="_csv_import_btn"):
                    def _mapcol(col_name, default):
                        if col_name and col_name != "(없음)" and col_name in _csv_df.columns: return _csv_df[col_name]
                        return default
                    _norm = pd.DataFrame()
                    _norm["date"]    = _mapcol(_map_date, str(_fallback_date))
                    _norm["keyword"] = _mapcol(_map_keyword, "").astype(str).str.strip()
                    _norm["rank"]    = pd.to_numeric(_mapcol(_map_rank, 999), errors="coerce").fillna(999).astype(int)
                    _norm["mall"]    = _mapcol(_map_mall, "").astype(str).str.strip()
                    _norm["vol"]     = pd.to_numeric(_mapcol(_map_vol, 0), errors="coerce").fillna(0).astype(int)
                    _norm["title"]   = _mapcol(_map_title, "").astype(str).str.strip()
                    _norm["price"]   = pd.to_numeric(_mapcol(_map_price, 0), errors="coerce").fillna(0).astype(int)
                    _norm["ctr"]     = pd.to_numeric(_mapcol(_map_ctr, 0), errors="coerce").fillna(0.0)
                    _norm["is_mine"] = False
                    _norm["is_comp"] = False
                    _norm["date"] = pd.to_datetime(_norm["date"], errors="coerce").dt.strftime("%Y-%m-%d").fillna(str(_fallback_date))
                    _norm = _norm[_norm["keyword"].str.len() > 0].reset_index(drop=True)
                    if _norm.empty:
                        st.error("❌ 유효한 데이터가 없습니다. 키워드 컬럼 매핑을 확인해주세요.")
                    else:
                        if not st.session_state.history_df.empty:
                            st.session_state.history_df = pd.concat([st.session_state.history_df, _norm], ignore_index=True).drop_duplicates(subset=["date","keyword","rank","mall"])
                        else:
                            st.session_state.history_df = _norm
                        st.success(f"✅ {len(_norm):,}건 데이터가 로드되었습니다!")
                        if _sync_to_notion and notion_token and notion_db_id:
                            with st.spinner("Notion에 저장 중..."):
                                _total_ok, _total_fail = 0, 0
                                for _d in _norm["date"].unique():
                                    _day_df = _norm[_norm["date"] == _d].copy()
                                    _n_ok, _n_msg = save_to_notion(_day_df, str(_d), notion_token, notion_db_id)
                                    if _n_ok: _total_ok += len(_day_df)
                                    else: _total_fail += len(_day_df)
                                if _total_fail == 0: st.success(f"✅ Notion 저장 완료: {_total_ok:,}건")
                                else: st.warning(f"⚠️ Notion 저장: {_total_ok:,}건 성공 / {_total_fail:,}건 실패")
                        st.rerun()
            except Exception as _csv_err:
                st.error(f"❌ 오류: {_csv_err}")

    st.markdown("---")

    _KW_FILE = _os.path.join(_AUTH_DIR, "keywords.txt")
    if 'save_kws_text' not in st.session_state:
        if _os.path.exists(_KW_FILE):
            with open(_KW_FILE, "r", encoding="utf-8") as _f:
                st.session_state.save_kws_text = _f.read().strip()
        else:
            st.session_state.save_kws_text = get_secret("DEFAULT_KEYWORDS", "")

    _kw_col1, _kw_col2 = st.columns([5, 1])
    with _kw_col1:
        kws_text = st.text_area("키워드 입력 (줄바꿈 구분)", height=200, value=st.session_state.save_kws_text)
    with _kw_col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("📂 불러오기", use_container_width=True, key="_load_kw_file"):
            if _os.path.exists(_KW_FILE):
                with open(_KW_FILE, "r", encoding="utf-8") as _f:
                    st.session_state.save_kws_text = _f.read().strip()
                st.success("✅ keywords.txt 로드!")
                st.rerun()
            else:
                st.warning("keywords.txt 파일이 없습니다.")
        if st.button("💾 txt 저장", use_container_width=True, key="_save_kw_file"):
            with open(_KW_FILE, "w", encoding="utf-8") as _f:
                _f.write(kws_text)
            st.success("✅ keywords.txt 저장!")
    st.session_state.save_kws_text = kws_text

    if st.button("🚀 분석 시작 및 Notion 저장", type="primary"):
        keywords = [k.strip() for k in kws_text.split('\n') if k.strip()]
        if not keywords:
            st.warning("키워드를 입력하세요.")
        else:
            prog = st.progress(0)
            status = st.empty()
            results = []
            completed_count = [0]
            t_db   = [x.strip() for x in my_brand_1.split(',')]
            t_bit  = [x.strip() for x in my_brand_2.split(',')]
            t_comp = [x.strip() for x in competitors.split(',')]

            from concurrent.futures import ThreadPoolExecutor, as_completed
            import threading
            results_lock = threading.Lock()

            def fetch_single_kw(kw):
                vol, clk, ctr = get_vol(kw, ad_api_key, ad_sec_key, ad_cus_id)
                items = get_rank(kw, naver_cid, naver_csec)
                return kw, vol, clk, ctr, items

            def process_kw_result(kw, vol, clk, ctr, items):
                r_db = r_bit = 999
                local_rows = []
                if items:
                    for r, item in enumerate(items, 1):
                        mn = item['mallName'].replace(" ","").lower()
                        if any(x.lower().replace(" ","") in mn for x in t_db): r_db = min(r_db, r)
                        if any(x.lower().replace(" ","") in mn for x in t_bit): r_bit = min(r_bit, r)
                        if r <= 3 or any(x.lower().replace(" ","") in mn for x in t_db+t_bit+t_comp):
                            local_rows.append({
                                "date": TODAY_ISO, "keyword": kw, "vol": vol, "click": clk, "ctr": ctr,
                                "rank": r, "mall": item['mallName'],
                                "title": item['title'].replace("<b>","").replace("</b>",""),
                                "price": item['lprice'], "link": item['link'],
                                "is_db":  any(x.lower().replace(" ","") in mn for x in t_db),
                                "is_bit": any(x.lower().replace(" ","") in mn for x in t_bit),
                                "is_da":  "다다사" in mn,
                                "is_hr":  "효로로" in mn,
                                "is_dv":  "드론뷰" in mn,
                            })
                else:
                    # 순위 결과 없어도 검색량 저장 (미노출 키워드 vol 표시용)
                    local_rows.append({
                        "date": TODAY_ISO, "keyword": kw, "vol": vol, "click": clk, "ctr": ctr,
                        "rank": 999, "mall": "", "title": "", "price": 0, "link": "",
                        "is_db": False, "is_bit": False, "is_da": False, "is_hr": False, "is_dv": False,
                    })
                best_rank = min(r_db, r_bit)
                ai_line = f"- 키워드: {kw} | 자사 최고 순위: {'순위 밖' if best_rank==999 else str(best_rank)+'위'} | 월간 검색수: {vol}회 | 클릭률: {ctr}%\n"
                with results_lock:
                    results.extend(local_rows)
                return ai_line

            status.text(f"🔍 병렬 수집 시작... (총 {len(keywords)}개 키워드)")
            ai_raw_parts = []
            with ThreadPoolExecutor(max_workers=4) as executor:
                future_to_kw = {executor.submit(fetch_single_kw, kw): kw for kw in keywords}
                for future in as_completed(future_to_kw):
                    kw = future_to_kw[future]
                    try:
                        kw_r, vol, clk, ctr, items = future.result()
                        ai_raw_parts.append(process_kw_result(kw_r, vol, clk, ctr, items))
                    except Exception as e:
                        import logging as _log
                        _log.warning(f"[P4] '{kw}' 오류: {e}")
                    completed_count[0] += 1
                    prog.progress(completed_count[0] / len(keywords))
                    status.text(f"🔍 수집 중... ({completed_count[0]}/{len(keywords)}) 완료")

            ai_raw = "".join(ai_raw_parts)
            df = pd.DataFrame(results)
            st.session_state.crawled_df = df
            import threading as _threading
            _sync_status = {"done": False, "success": False, "msg": ""}
            _history_df_copy = st.session_state.history_df.copy() if not st.session_state.history_df.empty else pd.DataFrame()

            def _bg_notion_slack():
                import logging as _log
                import requests as _req

                # ── Google Sheets: 전체 데이터 저장 ──────────────────────────
                if apps_script_url and not df.empty:
                    try:
                        _log.warning(f"[SEND] df 행수={len(df)}, 고유키워드={df['keyword'].nunique()}, 컬럼={list(df.columns)}")
                        _csv = df.to_csv(index=False).encode("utf-8")
                        _req.post(
                            apps_script_url,
                            params={"token": apps_script_token, "type": "auto_daily"},
                            data=_csv,
                            headers={"Content-Type": "text/plain; charset=utf-8"},
                            timeout=30,
                        )
                        _log.info(f"[GSheets] 전체 {len(df)}건 전송 완료")
                    except Exception as _e:
                        _log.warning(f"[GSheets] 전송 실패: {_e}")

                # ── Notion: 자사 상품(is_mine)만 저장 ───────────────────────
                if notion_token and notion_db_id:
                    _df_mine = df[df["is_db"].fillna(False) | df["is_bit"].fillna(False)].copy()
                    if _df_mine.empty:
                        _sync_status.update({"done": True, "success": False, "msg": "자사 데이터 없음 (Notion 저장 건너뜀)"})
                        _log.info("[Notion] 자사 데이터 없음 — 저장 건너뜀")
                    else:
                        # 전체 df 전달 → notion_sync 내부에서 is_mine 키워드만 저장하되 Top1Mall은 전체 기준
                        ok, m = save_to_notion(df, TODAY_ISO, notion_token, notion_db_id)
                        _sync_status.update({"done": True, "success": ok, "msg": f"자사 {len(_df_mine)}건: {m}"})
                        _log.info(f"[Notion] {m}")
                else:
                    _sync_status.update({"done": True, "success": False, "msg": "Notion 미설정"})
                if slack_webhook_url:
                    s_ok, s_msg = send_slack(slack_webhook_url, df.copy(), _history_df_copy, TODAY_ISO, notion_db_id=notion_db_id, only_on_big_change=False)
                    _log.info(f"[Slack] {s_msg}")
                    send_slack(slack_webhook_url, df.copy(), _history_df_copy, TODAY_ISO, notion_db_id=notion_db_id, only_on_big_change=True)

            _threading.Thread(target=_bg_notion_slack, daemon=True).start()
            status.empty()
            gsheet_status = "📊 GSheets 저장 중..." if apps_script_url else ""
            notion_status = "🗂 Notion 자사만 저장 중..." if (notion_token and notion_db_id) else "⚠️ Notion 미설정"
            slack_status  = "Slack 알림 전송 중..." if slack_webhook_url else ""
            st.success(f"✅ 수집 완료! ({len(results)}건)  {gsheet_status}  {notion_status}  {slack_status}")
            _obs_log_change(f"크롤링 완료 ({len(keywords)}개 키워드, {len(results)}건)", f"- 키워드: {', '.join(keywords[:5])}{'...' if len(keywords)>5 else ''}")

            if not df.empty and 'keyword' in df.columns:
                st.markdown("---")
                st.markdown("### 📊 키워드별 광고 ROI 추정")
                _roi_c1, _roi_c2, _roi_c3 = st.columns(3)
                with _roi_c1: _aov = st.number_input("평균 주문 금액 (원)", min_value=1000, value=80000, step=1000, key="_roi_aov")
                with _roi_c2: _cvr = st.number_input("전환율 (%)", min_value=0.1, max_value=100.0, value=2.0, step=0.1, key="_roi_cvr")
                with _roi_c3: _cpc = st.number_input("평균 CPC (원/클릭)", min_value=10, value=500, step=10, key="_roi_cpc")
                _roi_rows = []
                for _, _kr in df.groupby('keyword').agg(vol=('vol','max'), click=('click','max'), ctr=('ctr','max'), rank=('rank','min')).reset_index().iterrows():
                    _mc = float(_kr['click']) if _kr['click'] else (float(_kr['vol'])*float(_kr['ctr'])/100 if _kr['ctr'] else 0)
                    _rev = _mc * (_cvr/100) * _aov
                    _cost = _mc * _cpc
                    _roi = ((_rev-_cost)/_cost*100) if _cost > 0 else 0
                    _roas = (_rev/_cost) if _cost > 0 else 0
                    _roi_rows.append({"키워드": _kr['keyword'], "현재 최고순위": f"{int(_kr['rank'])}위" if _kr['rank']<999 else "순위 밖", "월 검색량": f"{int(_kr['vol']):,}", "예상 월 클릭": f"{int(_mc):,}", "예상 월 매출": f"₩{int(_rev):,}", "예상 광고비": f"₩{int(_cost):,}", "ROAS": f"{_roas:.1f}x", "ROI": f"{_roi:+.0f}%", "_roi_raw": _roi})
                _roi_df = pd.DataFrame(_roi_rows).sort_values("_roi_raw", ascending=False)
                def _color_roi(val):
                    if isinstance(val, str) and "%" in val:
                        n = float(val.replace("%","").replace("+",""))
                        return "color: #1A7A2A; font-weight:700" if n > 0 else "color: #C0392B; font-weight:700"
                    return ""
                st.dataframe(_roi_df.drop(columns=["_roi_raw"]).style.applymap(_color_roi, subset=["ROI"]), use_container_width=True, hide_index=True)
                st.caption("💡 ROAS > 1이면 광고비 이상 회수.")

            if gemini_key:
                status.text("🤖 AI 리포트 생성 중...")
                ai_prompt = f"""[오늘 날짜] {TODAY_KOR}
네이버 쇼핑 당사(드론박스/빛드론) 키워드별 순위 데이터입니다.
실무자가 즉시 실행할 수 있는 '구체적인 액션 플랜' 위주로 SEO 전략 보고서를 작성해주세요.

[수집 데이터]
{ai_raw}

[필수 항목]
1. 📊 오늘 순위 현황 요약
2. 🚨 긴급 조치 타겟 키워드 TOP 3
3. 🛠️ 즉시 실행 액션 플랜 (상품명/태그 수정, 광고 입찰가, 리뷰 유도)
4. 🛡️ 상위권 안착 및 방어 전략
5. ✅ 이번 주 액션 3가지 — 담당자가 바로 체크리스트로 옮길 수 있게 '한 줄 = 한 작업' 형식, 각 항목에 대상 키워드와 기대 효과 명시"""
                try:
                    st.session_state.ai_report_text = "\n" + _gemini_generate(gemini_key, ai_prompt)
                except Exception as e:
                    import logging as _log
                    _log.warning(f"[Gemini] 실패: {e}")
                status.empty()

# ── 7. AI Report ───────────────────────────────────────────────────────────────
elif selected_menu == "AI Report":
    st.markdown("<div style='font-size:1.5rem;font-weight:800;color:#111;letter-spacing:-0.03em;margin-bottom:0.2rem;'>AI Report</div><div style='font-size:0.82rem;color:#AAA;margin-bottom:1.4rem;'>일자별 SEO 전략 & AI 액션 플랜 자동 생성</div>", unsafe_allow_html=True)
    if 'ai_reports_cache' not in st.session_state:
        st.session_state.ai_reports_cache = {}
        if st.session_state.ai_report_text:
            st.session_state.ai_reports_cache[TODAY_ISO] = st.session_state.ai_report_text
    hist_df = st.session_state.history_df
    if hist_df.empty:
        st.warning("과거 데이터가 없습니다. [Run & Sync] 메뉴에서 순위 수집 후 Notion에 저장하거나, [Dashboard]에서 새로고침 해주세요.")
    else:
        available_dates = sorted(hist_df['date'].dropna().unique().tolist(), reverse=True)
        if not available_dates:
            st.error("[Error] 동기화된 데이터에 유효한 날짜 값이 없습니다.")
        else:
            col1, _ = st.columns([1, 3])
            with col1:
                selected_date = st.selectbox("📅 보고서 기준일 선택", available_dates)
            st.markdown("---")
            if selected_date in st.session_state.ai_reports_cache:
                st.success(f"✅ {selected_date} 기준 캐싱된 SEO 리포트")
                st.markdown(st.session_state.ai_reports_cache[selected_date])
            else:
                if gemini_key:
                    if st.button("📝 AI 리포트 생성", type="primary", key="_ai_report_gen"):
                        _date_df = hist_df[hist_df['date'] == selected_date].copy()
                        if _date_df.empty:
                            st.warning("해당 날짜의 데이터가 없습니다.")
                        else:
                            _ai_raw2 = _date_df[['keyword','rank','vol','ctr','mall']].to_csv(index=False)
                            _prompt2 = f"""[날짜] {selected_date}
네이버 쇼핑 당사(드론박스/빛드론) 키워드별 순위 데이터입니다.
실무자가 즉시 실행할 수 있는 '구체적인 액션 플랜' 위주로 SEO 전략 보고서를 작성해주세요.

[수집 데이터]
{_ai_raw2}

[필수 항목]
1. 📊 오늘 순위 현황 요약
2. 🚨 긴급 조치 타겟 키워드 TOP 3
3. 🛠️ 즉시 실행 액션 플랜 (상품명/태그 수정, 광고 입찰가, 리뷰 유도)
4. 🛡️ 상위권 안착 및 방어 전략
5. ✅ 이번 주 액션 3가지 — 담당자가 바로 체크리스트로 옮길 수 있게 '한 줄 = 한 작업' 형식, 각 항목에 대상 키워드와 기대 효과 명시"""
                            try:
                                with st.spinner("🤖 AI 리포트 생성 중..."):
                                    _report_text = _gemini_generate(gemini_key, _prompt2)
                                st.session_state.ai_reports_cache[selected_date] = _report_text
                                st.rerun()
                            except Exception as _e:
                                st.error(f"AI 생성 실패: {_e}")
                else:
                    st.info("💡 AI 리포트 생성을 위해 사이드바에서 Gemini API 키를 설정해주세요.")

# ── ⚙️ 설정 ────────────────────────────────────────────────────────────────────
elif selected_menu == "⚙️ 설정":
    _u2 = st.session_state.current_user or {}
    st.markdown(f"""
    <div class="km-page-header">
      <div>
        <div class="km-page-title">설정</div>
        <div class="km-page-sub">{_u2.get('display_name') or _u2.get('email','')} · API 키 및 브랜드 설정</div>
      </div>
    </div>""", unsafe_allow_html=True)

    # API 키 미설정 경고
    if not bool(_k.get("naver_client_id")):
        st.markdown("""<div style='background:#FFF0E8;border:2px solid #FF6B2B;border-radius:6px;padding:12px 16px;box-shadow:3px 3px 0 #FF6B2B;margin-bottom:16px;font-size:13px;color:#C03800;font-weight:600;'>
        ⚠️ Naver API 키가 설정되지 않았습니다. 아래에서 입력 후 저장해주세요.</div>""", unsafe_allow_html=True)

    _sc1, _sc2 = st.columns(2)

    with _sc1:
        st.markdown('<div class="km-block"><div class="km-block-head"><span class="km-block-title">🔑 네이버 API 키</span></div>', unsafe_allow_html=True)
        _s_naver_cid   = st.text_input("Naver Client ID",    value=_k.get("naver_client_id", ""),     type="password", key="s_naver_cid")
        _s_naver_csec  = st.text_input("Naver Secret",       value=_k.get("naver_client_secret", ""), type="password", key="s_naver_csec")
        _s_ad_api      = st.text_input("Ad API Key",         value=_k.get("naver_ad_api_key", ""),    type="password", key="s_ad_api")
        _s_ad_sec      = st.text_input("Ad Secret Key",      value=_k.get("naver_ad_secret_key", ""), type="password", key="s_ad_sec")
        _s_ad_cid      = st.text_input("Ad Customer ID",     value=_k.get("naver_customer_id", ""),   type="password", key="s_ad_cid")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="km-block" style="margin-top:14px;"><div class="km-block-head"><span class="km-block-title">🤖 AI 키</span></div>', unsafe_allow_html=True)
        _s_gemini      = st.text_input("Gemini API Key",     value=_k.get("gemini_key", ""),          type="password", key="s_gemini")
        st.markdown('</div>', unsafe_allow_html=True)

    with _sc2:
        st.markdown('<div class="km-block"><div class="km-block-head"><span class="km-block-title">🔗 연동 설정</span></div>', unsafe_allow_html=True)
        _s_notion_tok  = st.text_input("Notion Token",       value=_k.get("notion_token", ""),        type="password", key="s_notion_tok")
        _s_notion_db   = st.text_input("Notion Database ID", value=_k.get("notion_database_id", ""),  type="password", key="s_notion_db")
        _s_slack       = st.text_input("Slack Webhook URL",  value=_k.get("slack_webhook_url", ""),   type="password", key="s_slack")
        _s_gas_url     = st.text_input("GAS URL (레거시)",   value=_k.get("apps_script_url", ""),     type="password", key="s_gas_url")
        _s_gas_tok     = st.text_input("GAS Token (레거시)", value=_k.get("apps_script_token", ""),   type="password", key="s_gas_tok")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="km-block" style="margin-top:14px;"><div class="km-block-head"><span class="km-block-title">🏪 브랜드 설정</span></div>', unsafe_allow_html=True)
        _s_brand1      = st.text_area("내 브랜드 1 (쉼표 구분)", value=_k.get("my_brand_1", "드론박스, DroneBox"), key="s_brand1")
        _s_brand2      = st.text_area("내 브랜드 2 (쉼표 구분)", value=_k.get("my_brand_2", "빛드론, BitDrone"),   key="s_brand2")
        _s_comp        = st.text_area("경쟁사 (쉼표 구분)",       value=_k.get("competitors", "다다사, 효로로, 드론뷰"), key="s_comp")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    _btn_c1, _btn_c2, _ = st.columns([1, 1, 3])
    with _btn_c1:
        if st.button("💾 저장", type="primary", use_container_width=True, key="s_save"):
            _ok, _msg = _auth_save_keys(st.session_state.current_user["id"], {
                "gemini_key": _s_gemini, "naver_client_id": _s_naver_cid,
                "naver_client_secret": _s_naver_csec, "naver_ad_api_key": _s_ad_api,
                "naver_ad_secret_key": _s_ad_sec, "naver_customer_id": _s_ad_cid,
                "apps_script_url": _s_gas_url, "apps_script_token": _s_gas_tok,
                "my_brand_1": _s_brand1, "my_brand_2": _s_brand2, "competitors": _s_comp,
                "notion_token": _s_notion_tok, "notion_database_id": _s_notion_db,
                "slack_webhook_url": _s_slack,
            })
            if _ok:
                st.session_state.user_keys = _auth_load_keys(st.session_state.current_user["id"])
                st.success("✅ 설정이 저장되었습니다.")
                _obs_log_change("API 키 저장", "Notion/Slack 설정 업데이트")
            else:
                st.error(f"저장 실패: {_msg}")
    with _btn_c2:
        if st.button("🚪 로그아웃", type="secondary", use_container_width=True, key="s_logout"):
            if _COOKIE_OK and _cookie_manager:
                try:
                    _tok = _cookie_manager.get("km_auto_token")
                    if _tok: _delete_token(_tok)
                    _cookie_manager.delete("km_auto_token")
                except Exception: pass
            st.session_state.authenticated = False
            st.session_state.current_user  = None
            st.session_state.user_keys     = {}
            st.rerun()

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    with st.expander("🔐 비밀번호 변경"):
        _cp_cur  = st.text_input("현재 비밀번호", type="password", key="cp_cur")
        _cp_new  = st.text_input("새 비밀번호 (8자 이상)", type="password", key="cp_new")
        _cp_new2 = st.text_input("새 비밀번호 확인", type="password", key="cp_new2")
        if st.button("비밀번호 변경", type="primary", key="cp_btn"):
            if not _cp_cur or not _cp_new:
                st.error("모든 항목을 입력해주세요.")
            elif _cp_new != _cp_new2:
                st.error("새 비밀번호가 일치하지 않습니다.")
            elif len(_cp_new) < 8:
                st.error("비밀번호는 8자 이상이어야 합니다.")
            else:
                try:
                    from auth.users import change_password as _auth_change_pw
                    _cp_ok, _cp_msg = _auth_change_pw(
                        st.session_state.current_user["email"], _cp_cur, _cp_new
                    )
                    if _cp_ok:
                        st.success("✅ 비밀번호가 변경됐습니다.")
                    else:
                        st.error(_cp_msg)
                except Exception as _e:
                    st.error(f"변경 중 오류: {_e}")

# ── 8. GEO/AEO 가이드 ──────────────────────────────────────────────────────────
elif selected_menu == "GEO/AEO 가이드":
    st.markdown("""
    <div style='font-size:1.5rem;font-weight:800;color:#111;letter-spacing:-0.03em;margin-bottom:0.2rem;'>GEO/AEO 가이드</div>
    <div style='font-size:0.82rem;color:#AAA;margin-bottom:1.4rem;'>Generative Engine Optimization · Answer Engine Optimization 공식 문서 기반 참고자료</div>
    """, unsafe_allow_html=True)

    st.info("📌 **핵심 주장**: Google 공식 문서에 따르면 GEO/AEO는 별도의 최적화 시스템이 아니라 새로운 답변 서비스에 적용된 **기초 SEO**입니다. 모든 주장은 1차 출처(공식 문서)에 링크됩니다.")

    # ── 용어 맵 ──
    with st.expander("📖 용어 맵 (Terminology Map)", expanded=True):
        _term_data = {
            "용어": ["SEO", "AEO", "GEO", "LLMO / AI SEO / AIO"],
            "풀네임": ["Search Engine Optimization", "Answer Engine Optimization", "Generative Engine Optimization", "LLM Optimization 등"],
            "성격": [
                "기본 시스템: 검색엔진이 콘텐츠를 이해하고 사용자가 찾을 수 있도록 지원",
                "AI/직접/음성 답변에서 인용되기 위한 업계 용어",
                "생성형 답변에서 가시성 및 귀속을 위한 업계/학문 용어",
                "마케팅 신조어"
            ],
            "Google 공식 입장": [
                "공식. Google Search Central 문서의 핵심",
                "'온라인에서 흔한' 용어로 언급. 별도의 Google 시스템 아님",
                "'온라인에서 흔한' 용어로 언급. Google Search에서는 SEO 기반으로 처리",
                "Google 공식 프레임워크 아님 — 각 출처별로 확인 필요"
            ]
        }
        st.dataframe(pd.DataFrame(_term_data), use_container_width=True, hide_index=True)

    # ── Google 공식 문서 ──
    with st.expander("🔵 Google 공식 문서", expanded=True):
        _google_docs = [
            ("Optimizing for generative AI features on Google Search",
             "https://developers.google.com/search/docs/fundamentals/ai-optimization-guide",
             "GEO/AEO 질문에 대한 Google의 공식 답변. Google Search의 생성형 AI 최적화 = SEO. llms.txt, 청킹, 특별 AI 마크업 불필요"),
            ("AI features and your website",
             "https://developers.google.com/search/docs/appearance/ai-features",
             "AI Overviews / AI Mode 작동 방식. 추가 기술 요구사항 없음 — 색인 가능 + 스니펫 대상이면 충분"),
            ("SEO Starter Guide",
             "https://developers.google.com/search/docs/fundamentals/seo-starter-guide",
             "기본 원칙: 구조, 콘텐츠, 링크, 제목, 스니펫, 이미지/동영상, 홍보"),
            ("Google Search Essentials",
             "https://developers.google.com/search/docs/essentials",
             "Google Search 등장을 위한 최소 기준: 기술 요건, 스팸 정책, 주요 모범 사례"),
            ("Structured data intro",
             "https://developers.google.com/search/docs/appearance/structured-data/intro-structured-data",
             "구조화된 데이터의 공식 역할: 리치 결과 적격성 — 특별한 'AI 검색' 스키마 아님"),
            ("Google-Extended",
             "https://developers.google.com/crawling/docs/crawlers-fetchers/google-common-crawlers#google-extended",
             "Gemini/Vertex AI 학습 및 그라운딩 제어 토큰. Google Search 포함/순위에 영향 없음"),
        ]
        for _title, _url, _why in _google_docs:
            _c1, _c2 = st.columns([2, 3])
            with _c1:
                st.markdown(f"**[{_title}]({_url})**")
            with _c2:
                st.caption(_why)
            st.divider()

    # ── 엔진별 공식 입장 ──
    with st.expander("🌐 AI 검색엔진별 공식 입장 비교"):
        _engine_data = {
            "엔진/제품": ["Google AI Overviews / AI Mode", "ChatGPT search (OpenAI)", "Perplexity", "Claude web search (Anthropic)", "Microsoft Bing / Copilot"],
            "검색 백엔드": ["Google 인덱스", "OAI-SearchBot + 서드파티", "PerplexityBot + Perplexity-User", "서드파티 검색(Brave 등)", "Bing 인덱스"],
            "공식 퍼블리셔 가이드": [
                "Search Essentials + SEO 기본. llms.txt 불필요",
                "OAI-SearchBot robots.txt 허용; noindex로 거부. 별도 콘텐츠 최적화 가이드 없음",
                "PerplexityBot + IP 허용. 기술 접근만, 콘텐츠 전략 없음",
                "퍼블리셔 최적화 문서 없음. 검색 공급자 인덱스의 신뢰할 수 있는 1차 출처 권장",
                "스키마가 LLM에 도움 + IndexNow 최신성 + 명확한 헤딩/표/FAQ 공식 권장"
            ],
            "Google 'SEO로 충분' 대비": ["기준선", "사실상 동일", "사실상 동일", "사실상 동일", "⚠️ 다름 — 생성형 특화 가이드 발행"]
        }
        st.dataframe(pd.DataFrame(_engine_data), use_container_width=True, hide_index=True)
        st.caption("출처: OpenAI Publishers FAQ, Perplexity crawlers docs, Anthropic web search tool docs, Bing Webmaster Blog")

    # ── llms.txt ──
    with st.expander("📄 llms.txt — 실제 정체"):
        st.markdown("""
**출처**: 2024-09-03 Jeremy Howard(fast.ai / Answer.AI)가 제안. 사이트 루트 `/llms.txt`에 LLM이 추론 시 사이트를 활용할 수 있도록 정리된 마크다운 인덱스.

**지원 현황 (2026 Q1 기준)**:
- 🔴 **Google** — 공식 미지원. John Mueller & Gary Illyes: "현재 어떤 AI 시스템도 llms.txt를 사용하지 않으며, 지원 계획 없음"
- 🟡 **OpenAI / 기타** — GPTBot/ChatGPT가 llms.txt를 파싱한다는 공식 발표 없음
- ⚠️ **"Anthropic/Perplexity 지원 확인"** — 일부 SEO 블로그 주장이나, 주요 플랫폼이 무시한다는 보고도 있음. **1차 확인 안됨 → 사실로 승격 안함**

**결론**: llms.txt는 커뮤니티 관례이지, 공식 표준이 아닙니다.
        """)

    # ── 무시할 것들 ──
    with st.expander("🚫 무시해야 할 과대 주장들"):
        _ignore_list = [
            "Google Search를 위해 llms.txt가 필요하다",
            "AI 검색에는 특별/비밀 스키마가 필요하다",
            "AI를 위해 콘텐츠를 작은 청크로 나눠야 한다",
            "AI 시스템만을 위한 어색한 재작성",
            "인위적인 언급 파밍",
            "'AI Overview 1위 보장' 영업 멘트",
        ]
        for _item in _ignore_list:
            st.markdown(f"❌ {_item}")

        st.success("✅ **AI 검색 공통 안전 기준**: 공개 접근 가능한 소스 텍스트 · 명확한 작성자/조직/날짜/근거 · 정규 비중복 URL · 신뢰할 수 있는 외부 인용 · 최신 제품/가격/정책/FAQ")

    # ── 학술/업계 참고 ──
    with st.expander("📚 업계 & 학술 참고 자료 (Secondary)"):
        _ref_data = {
            "출처": [
                "arXiv — GEO: Generative Engine Optimization",
                "Semrush — Answer Engine Optimization",
                "Ahrefs — Answer Engine Optimization",
                "Search Engine Journal — Google 가이드",
            ],
            "링크": [
                "https://arxiv.org/abs/2311.09735",
                "https://www.semrush.com/blog/answer-engine-optimization/",
                "https://ahrefs.com/blog/answer-engine-optimization/",
                "https://www.searchenginejournal.com/googles-new-ai-search-guide-calls-aeo-and-geo-still-seo/575026/",
            ],
            "활용": [
                "'GEO' 용어를 공식화한 논문. KDD 2024 채택",
                "AI 답변에서 브랜드 가시성을 위한 마케팅 관행으로 AEO 설명",
                "직접 답변 서비스의 SEO 보완으로 AEO 설명",
                "Google 공식 가이드의 업계 해석. Google 문서를 1차 출처로 유지",
            ]
        }
        _ref_df = pd.DataFrame(_ref_data)
        for _, _row in _ref_df.iterrows():
            st.markdown(f"**[{_row['출처']}]({_row['링크']})** — {_row['활용']}")

    st.caption("데이터 출처: [awesome-geo](https://github.com/aldegad/awesome-geo) (CC0-1.0)")

# ── 9. 상세페이지 제작기 ────────────────────────────────────────────────────────
elif selected_menu == "상세페이지 제작기":
    st.markdown("""
    <div style='font-size:1.5rem;font-weight:800;color:#111;letter-spacing:-0.03em;margin-bottom:0.2rem;'>상세페이지 제작기</div>
    <div style='font-size:0.82rem;color:#AAA;margin-bottom:1.4rem;'>네이버 쇼핑 최적화 상품 상세페이지 콘텐츠 자동 생성</div>
    """, unsafe_allow_html=True)

    if not gemini_key:
        st.warning("⚠️ 상세페이지 생성을 위해 사이드바에서 Gemini API 키를 먼저 설정해주세요.")
    else:
        _dp_tab1, _dp_tab2, _dp_tab3 = st.tabs(["✏️ 상품 정보 입력", "📄 생성된 상세페이지", "🎯 GEO 준비도 평가"])

        with _dp_tab1:
            _dp_c1, _dp_c2 = st.columns(2)
            with _dp_c1:
                _dp_name = st.text_input("상품명 *", placeholder="예: DJI 매빅3 프로 드론 (플라이모어 콤보)")
                _dp_category = st.text_input("카테고리", placeholder="예: 촬영용 드론 / 소비자 드론")
                _dp_price = st.text_input("판매가", placeholder="예: 3,890,000원")
                _dp_brand = st.text_input("브랜드", placeholder="예: DJI")
            with _dp_c2:
                _dp_keywords = st.text_area("타겟 키워드 (줄바꿈 구분)", placeholder="드론\n4K드론\n매빅3프로\n촬영드론", height=110)
                _dp_features = st.text_area("주요 특징/스펙 (줄바꿈 구분)", placeholder="1인치 CMOS 센서\n4K/60fps 촬영\n최대 43분 비행\n전방위 장애물 감지", height=110)

            _dp_tone = st.selectbox("글쓰기 톤", ["전문가/신뢰감", "친근/쉬운 설명", "스펙 중심 간결체"])
            _dp_sections = st.multiselect(
                "생성할 섹션 선택",
                ["상품 소개 (Hero 문구)", "주요 특징 상세 설명", "스펙 표", "FAQ", "SEO 메타 태그 (title/description)", "네이버 쇼핑 상품명 최적화 예시"],
                default=["상품 소개 (Hero 문구)", "주요 특징 상세 설명", "스펙 표", "SEO 메타 태그 (title/description)"]
            )

            if st.button("🚀 상세페이지 생성", type="primary", use_container_width=True):
                if not _dp_name:
                    st.error("상품명을 입력해주세요.")
                else:
                    # ── awesome-geo 기반 GEO/AEO 시스템 지식 ──
                    _GEO_KNOWLEDGE = """
[GEO/AEO 최적화 원칙 — awesome-geo 기반]
Google, ChatGPT, Perplexity, Claude, Bing/Copilot 등 AI 검색 엔진에 인용되려면:

핵심 원칙 (엔진 공통):
- 공개적으로 크롤/인덱싱 가능한 콘텐츠
- 명확한 작성자/브랜드/날짜/근거 명시
- 중복 없는 정규 URL
- 신뢰할 수 있는 외부 인용 포함
- 최신 상품정보/가격/정책/FAQ 유지
- 브랜드·핵심 엔티티 명칭 일관성

구조 최적화 (특히 Bing/Copilot에 효과적):
- 명확한 제목 계층(H1→H2→H3) 사용
- 표(Table) 형식으로 스펙/비교 정보 제공
- FAQ 섹션: 질문-답변 쌍으로 직접 답변 제공
- 구조화 데이터(Schema.org) 권장: Product, FAQ, BreadcrumbList

SEO 메타 최적화 (Google AI Overviews / AI Mode 기준):
- title: 60자 이내, 핵심 키워드 앞배치
- meta description: 160자 이내, 스니펫 소환력 있게
- 스니펫 최적화: 핵심 답변을 문단 앞줄에 배치 (position zero 타겟)

피해야 할 것:
- AI만을 위한 어색한 문체 재작성
- 인위적 키워드 반복 (키워드 스터핑)
- 과장·미확인 주장
- "AI 검색 보장" 식의 과대 문구
"""
                    _dp_prompt = f"""당신은 네이버 쇼핑 SEO + GEO/AEO 전문가입니다. 아래 GEO/AEO 원칙과 상품 정보를 바탕으로 AI 검색 엔진에도 잘 인용되는 상품 상세페이지 콘텐츠를 작성해주세요.

{_GEO_KNOWLEDGE}

[상품 정보]
- 상품명: {_dp_name}
- 카테고리: {_dp_category or '미입력'}
- 브랜드: {_dp_brand or '미입력'}
- 판매가: {_dp_price or '미입력'}
- 타겟 키워드: {_dp_keywords or '미입력'}
- 주요 특징/스펙: {_dp_features or '미입력'}
- 글쓰기 톤: {_dp_tone}

[생성할 섹션]
{chr(10).join(f'- {s}' for s in _dp_sections)}

[작성 지침]
1. 네이버 쇼핑 SEO + GEO/AEO 원칙을 동시에 적용
2. 타겟 키워드를 자연스럽게 포함 (스터핑 금지)
3. 브랜드명·모델명·핵심 엔티티를 일관되게 사용
4. FAQ 섹션은 실제 구매자 질문 형식으로 작성 (AI 직접 답변 타겟)
5. 스펙 표는 마크다운 표(|col|col|) 형식 사용
6. SEO 메타 태그: title 60자 이내, description 160자 이내
7. 각 섹션 첫 문장에 핵심 정보 배치 (스니펫 최적화)
8. 네이버 쇼핑 상품명: [브랜드] + [주요 키워드] + [모델명] + [옵션] 순서

마크다운 형식으로 작성해주세요."""

                    with st.spinner("📝 상세페이지 생성 중..."):
                        try:
                            _dp_result = _gemini_generate(gemini_key, _dp_prompt)
                            st.session_state['_dp_result'] = _dp_result
                            st.session_state['_dp_name_saved'] = _dp_name
                            st.session_state['_dp_brand_saved'] = _dp_brand
                            st.success("✅ 생성 완료! '생성된 상세페이지' 탭에서 확인하세요.")
                        except Exception as _e:
                            st.error(f"생성 실패: {_e}")

        with _dp_tab2:
            if '_dp_result' in st.session_state and st.session_state['_dp_result']:
                _dp_name_saved = st.session_state.get('_dp_name_saved', '상품')
                st.markdown(f"### {_dp_name_saved}")
                st.markdown("---")
                st.markdown(st.session_state['_dp_result'])
                st.markdown("---")
                _dp_col1, _dp_col2 = st.columns(2)
                with _dp_col1:
                    st.download_button(
                        "📥 마크다운 다운로드",
                        data=st.session_state['_dp_result'].encode('utf-8'),
                        file_name=f"상세페이지_{_dp_name_saved[:20]}.md",
                        mime="text/markdown",
                        use_container_width=True
                    )
                with _dp_col2:
                    _dp_html = f"""<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"><title>{_dp_name_saved}</title>
<style>body{{font-family:'Noto Sans KR',sans-serif;max-width:900px;margin:40px auto;padding:20px;line-height:1.7;color:#333;}}
h1,h2,h3{{color:#111;}}table{{border-collapse:collapse;width:100%;}}td,th{{border:1px solid #ddd;padding:8px 12px;}}th{{background:#f5f5f5;}}</style>
</head><body>
<h1>{_dp_name_saved}</h1>
<pre style="white-space:pre-wrap;font-family:inherit;">{st.session_state['_dp_result']}</pre>
</body></html>"""
                    st.download_button(
                        "📥 HTML 다운로드",
                        data=_dp_html.encode('utf-8'),
                        file_name=f"상세페이지_{_dp_name_saved[:20]}.html",
                        mime="text/html",
                        use_container_width=True
                    )
            else:
                st.info("💡 '상품 정보 입력' 탭에서 정보를 입력하고 생성 버튼을 눌러주세요.")

        with _dp_tab3:
            st.markdown("#### 🎯 GEO 준비도 평가 — awesome-geo 기준")
            st.caption("생성된 상세페이지가 AI 검색 엔진(Google AI Overviews, ChatGPT, Perplexity, Bing/Copilot)에 인용될 준비가 됐는지 평가합니다.")

            if '_dp_result' not in st.session_state or not st.session_state['_dp_result']:
                st.info("💡 먼저 상세페이지를 생성하면 자동으로 평가됩니다.")
            else:
                _content = st.session_state['_dp_result']
                _content_lower = _content.lower()

                # ── 체크리스트 항목 정의 ──
                _geo_checks = [
                    # (카테고리, 항목명, 통과조건함수, 실패시 개선안)
                    ("📋 구조", "명확한 헤딩(##) 사용",
                     lambda c: c.count("##") >= 2,
                     "## 헤딩을 2개 이상 사용해 콘텐츠 구조를 명확히 하세요."),
                    ("📋 구조", "스펙/비교 표(Table) 포함",
                     lambda c: "|" in c and "---" in c,
                     "마크다운 표(|컬럼|컬럼|)로 스펙을 정리하면 AI가 구조화 데이터로 인식합니다."),
                    ("📋 구조", "FAQ 섹션 포함",
                     lambda c: "faq" in c.lower() or "자주 묻는" in c or "Q:" in c or "**Q" in c,
                     "FAQ 섹션을 추가하면 AI 직접 답변(Featured Snippet) 노출에 유리합니다."),
                    ("🔍 SEO", "SEO 메타 태그(title/description) 포함",
                     lambda c: "title" in c.lower() and "description" in c.lower(),
                     "SEO 메타 태그(title, meta description)를 포함해주세요."),
                    ("🔍 SEO", "타겟 키워드 포함",
                     lambda c: bool(st.session_state.get('_dp_name_saved','')) and
                               st.session_state.get('_dp_name_saved','').split()[0].lower() in c.lower(),
                     "상품명의 핵심 키워드가 본문에 자연스럽게 포함돼야 합니다."),
                    ("🔍 SEO", "브랜드명 일관 사용",
                     lambda c: (not st.session_state.get('_dp_brand_saved','')) or
                               st.session_state.get('_dp_brand_saved','').lower() in c.lower(),
                     "브랜드명을 일관되게 사용해 AI 엔진이 엔티티를 정확히 인식하게 하세요."),
                    ("🤖 AI 최적화", "첫 문단에 핵심 정보 배치",
                     lambda c: len(c.split('\n')[0]) > 20 or (len(c.split('\n')) > 2 and len(c.split('\n')[2]) > 30),
                     "첫 문단에 상품의 핵심 가치를 배치하면 AI 스니펫 소환 가능성이 높아집니다."),
                    ("🤖 AI 최적화", "구체적 수치/스펙 포함",
                     lambda c: any(ch.isdigit() for ch in c),
                     "구체적인 수치(해상도, 용량, 크기 등)가 있으면 AI가 사실 기반 답변으로 인용합니다."),
                    ("🤖 AI 최적화", "과장 표현 없음 (신뢰도)",
                     lambda c: not any(w in c for w in ["세계 최고", "완벽한", "100% 보장", "무조건"]),
                     "과장 표현을 제거하면 AI 엔진의 신뢰도 평가가 높아집니다."),
                    ("🌐 Bing/Copilot", "명확한 소제목+내용 쌍 구조",
                     lambda c: c.count("##") >= 3,
                     "Bing/Copilot은 ##소제목 + 내용 쌍 구조를 특히 중요시합니다. 섹션을 3개 이상 사용하세요."),
                ]

                # ── 평가 실행 ──
                _passed = []
                _failed = []
                for _cat, _name, _check_fn, _fix in _geo_checks:
                    try:
                        if _check_fn(_content):
                            _passed.append((_cat, _name))
                        else:
                            _failed.append((_cat, _name, _fix))
                    except Exception:
                        _failed.append((_cat, _name, _fix))

                _score = len(_passed)
                _total = len(_geo_checks)
                _pct = int(_score / _total * 100)

                # ── 점수 표시 ──
                if _pct >= 80:
                    _score_color = "#22c55e"
                    _score_label = "우수"
                    _score_emoji = "🏆"
                elif _pct >= 60:
                    _score_color = "#f59e0b"
                    _score_label = "보통"
                    _score_emoji = "⚡"
                else:
                    _score_color = "#ef4444"
                    _score_label = "개선 필요"
                    _score_emoji = "⚠️"

                st.markdown(f"""
<div style='background:linear-gradient(135deg,#f8fafc,#f1f5f9);border-radius:16px;padding:24px;margin-bottom:20px;text-align:center;'>
  <div style='font-size:3rem;font-weight:900;color:{_score_color};'>{_score_emoji} {_pct}점</div>
  <div style='font-size:1.1rem;color:#555;margin-top:4px;'>GEO 준비도 <b style='color:{_score_color};'>{_score_label}</b> &nbsp;|&nbsp; {_score}/{_total} 항목 통과</div>
  <div style='background:#e5e7eb;border-radius:99px;height:10px;margin:14px auto;max-width:320px;'>
    <div style='background:{_score_color};width:{_pct}%;height:10px;border-radius:99px;transition:width 0.5s;'></div>
  </div>
  <div style='font-size:0.78rem;color:#aaa;'>기준: awesome-geo (Google·ChatGPT·Perplexity·Bing/Copilot 공식 문서 기반)</div>
</div>
""", unsafe_allow_html=True)

                # ── 통과 항목 ──
                if _passed:
                    with st.expander(f"✅ 통과 항목 ({len(_passed)}개)", expanded=False):
                        for _cat, _name in _passed:
                            st.markdown(f"✅ **{_cat}** · {_name}")

                # ── 미흡 항목 + 개선안 ──
                if _failed:
                    with st.expander(f"🔧 개선 필요 항목 ({len(_failed)}개)", expanded=True):
                        for _cat, _name, _fix in _failed:
                            st.markdown(f"""
<div style='background:#fff7ed;border-left:4px solid #f59e0b;border-radius:8px;padding:12px 16px;margin-bottom:10px;'>
  <div style='font-size:0.85rem;font-weight:700;color:#92400e;'>{_cat} · {_name}</div>
  <div style='font-size:0.82rem;color:#78350f;margin-top:4px;'>💡 {_fix}</div>
</div>
""", unsafe_allow_html=True)

                # ── AI 재생성 버튼 ──
                st.markdown("---")
                if _failed and st.button("🔄 개선안 반영해서 재생성", use_container_width=True):
                    _fix_notes = "\n".join([f"- {n}: {f}" for _, n, f in _failed])
                    _dp_reprompt = f"""아래는 이전에 작성한 상세페이지 콘텐츠입니다. GEO/AEO 평가에서 미흡한 항목이 발견됐습니다. 개선안을 반영해 전체 콘텐츠를 다시 작성해주세요.

[미흡 항목 및 개선 방향]
{_fix_notes}

[기존 콘텐츠]
{_content}

위 개선사항을 모두 반영해 마크다운 형식으로 다시 작성해주세요. 기존 내용은 유지하되 개선안만 적용하세요."""
                    with st.spinner("🔄 개선된 상세페이지 재생성 중..."):
                        try:
                            _dp_improved = _gemini_generate(gemini_key, _dp_reprompt)
                            st.session_state['_dp_result'] = _dp_improved
                            st.success("✅ 재생성 완료! '생성된 상세페이지' 탭에서 확인하세요.")
                            st.rerun()
                        except Exception as _e:
                            st.error(f"재생성 실패: {_e}")

# ── 10. AI 인용 추적 (GEO) ──────────────────────────────────────────────────────
elif selected_menu == "AI 인용 추적":
    from integrations.geo_tracker import (
        run_geo_check, compute_share, save_geo_results, load_geo_history,
        build_brand_groups, DEFAULT_PROMPT_TEMPLATES,
    )

    st.markdown("""
    <div style='font-size:1.5rem;font-weight:800;color:#111;letter-spacing:-0.03em;margin-bottom:0.2rem;'>AI 인용 추적</div>
    <div style='font-size:0.82rem;color:#AAA;margin-bottom:1.4rem;'>네이버 순위 추적의 GEO 버전 — AI에게 구매 추천을 물었을 때 우리 브랜드가 인용되는가</div>
    """, unsafe_allow_html=True)

    st.info("🤖 소비자가 AI에게 물어볼 법한 질의(추천/구매처)를 키워드별로 보내고, "
            "응답에서 **드론박스·빛드론 vs 경쟁사**의 인용 여부와 언급 순서를 기록합니다. "
            "매일 실행하면 '일자별 순위 추이'처럼 **AI 답변 점유율 추이**가 쌓입니다.")

    if not gemini_key:
        st.warning("⚙️ 설정에서 Gemini API 키를 먼저 등록해주세요.")
    else:
        _geo_uid = (_u.get("id") or _u.get("email") or "unknown")

        # ── 키워드 입력 (기존 추적 키워드 재사용) ──
        _geo_default_kws = []
        try:
            if not hist_df.empty and "keyword" in hist_df.columns:
                _geo_default_kws = list(pd.Series(hist_df["keyword"]).dropna().unique())[:8]
        except Exception:
            pass
        if not _geo_default_kws:
            _geo_default_kws = ["입문용 드론", "촬영용 드론", "DJI 미니4 프로"]

        _geo_col1, _geo_col2 = st.columns([3, 2])
        with _geo_col1:
            _geo_kw_text = st.text_area(
                "검사할 키워드 (줄바꿈 구분)",
                value="\n".join(_geo_default_kws),
                height=140,
                help="키워드 1개당 질의 2회(추천/구매처)가 실행됩니다. Gemini 무료 쿼터를 고려해 5~10개 권장."
            )
        with _geo_col2:
            with st.expander("📋 사용되는 질의 시나리오", expanded=True):
                for _pt, _tm in DEFAULT_PROMPT_TEMPLATES:
                    st.caption(f"**[{_pt}]** {_tm.format(kw='〈키워드〉')}")
            _geo_groups_preview = build_brand_groups(my_brand_1, my_brand_2, competitors)
            st.caption("추적 브랜드: " + " · ".join(_geo_groups_preview.keys()))

        _geo_kws = [k.strip() for k in _geo_kw_text.split("\n") if k.strip()]
        _geo_total_calls = len(_geo_kws) * len(DEFAULT_PROMPT_TEMPLATES)

        if st.button(f"🤖 AI 인용 체크 실행 ({_geo_total_calls}회 질의)", type="primary",
                     use_container_width=True, disabled=not _geo_kws):
            _geo_bar = st.progress(0, text="준비 중…")
            def _geo_prog(done, total, msg):
                _geo_bar.progress(min(done / max(total, 1), 1.0), text=f"({done}/{total}) {msg}")

            _geo_rows, _geo_errs = run_geo_check(
                generate_fn=lambda p: _gemini_generate(gemini_key, p),
                keywords=_geo_kws,
                brand1_str=my_brand_1, brand2_str=my_brand_2, competitors_str=competitors,
                progress_cb=_geo_prog,
            )
            _geo_bar.empty()

            if _geo_errs:
                with st.expander(f"⚠️ 질의 실패 {len(_geo_errs)}건"):
                    for _ek, _ep, _em in _geo_errs:
                        st.caption(f"- {_ek} [{_ep}]: {_em}")

            if _geo_rows:
                st.session_state["_geo_today_df"] = pd.DataFrame(_geo_rows)
                if save_geo_results(_geo_uid, _geo_rows):
                    st.success(f"✅ {len(_geo_rows)}행 기록 완료 — Google Sheets `geo_results` 시트에 저장됐습니다.")
                else:
                    st.warning("결과는 화면에 표시되지만 시트 저장에 실패했습니다 (GSHEET 설정 확인). 아래 CSV로 백업하세요.")
            else:
                st.error("수집된 결과가 없습니다. Gemini 키와 쿼터를 확인해주세요.")

        # ── 오늘 결과 표시 ──
        _geo_today = st.session_state.get("_geo_today_df", pd.DataFrame())
        if not _geo_today.empty:
            st.markdown("#### 📊 이번 실행 결과")
            _geo_share_now = compute_share(_geo_today)
            _geo_mcols = st.columns(min(len(_geo_share_now), 5) or 1)
            for _i, (_idx, _r) in enumerate(_geo_share_now.sort_values("share", ascending=False).iterrows()):
                if _i >= len(_geo_mcols):
                    break
                _is_mine = _r["brand"] in list(_geo_groups_preview.keys())[:2]
                _geo_mcols[_i].metric(
                    ("🏠 " if _is_mine else "") + str(_r["brand"]),
                    f"{_r['share']}%",
                    f"{int(_r['mentions'])}/{int(_r['queries'])} 질의 인용",
                    delta_color="off",
                )

            # 키워드 × 브랜드 매트릭스 (언급 순서 표시)
            _geo_mat = _geo_today[_geo_today["mentioned"] == 1].copy()
            if not _geo_mat.empty:
                _geo_mat["표시"] = _geo_mat["mention_order"].apply(lambda o: f"✓ {o}번째")
                _geo_pivot = _geo_mat.pivot_table(
                    index=["keyword", "prompt_type"], columns="brand",
                    values="표시", aggfunc="first", fill_value="—",
                )
                st.dataframe(_geo_pivot, use_container_width=True)
            else:
                st.caption("이번 실행에서 인용된 브랜드가 없습니다.")

            # 인용 문맥 스니펫
            _geo_snip = _geo_today[(_geo_today["mentioned"] == 1) & (_geo_today["snippet"] != "")]
            if not _geo_snip.empty:
                with st.expander(f"💬 인용 문맥 보기 ({len(_geo_snip)}건)"):
                    for _idx, _r in _geo_snip.iterrows():
                        st.markdown(f"**{_r['brand']}** · {_r['keyword']} [{_r['prompt_type']}]")
                        st.caption(_r["snippet"])

            st.download_button(
                "📥 이번 실행 결과 CSV",
                _geo_today.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"geo_check_{dt.date.today().isoformat()}.csv",
                mime="text/csv", use_container_width=True,
            )

        # ── 일자별 인용률 추이 ──
        st.markdown("#### 📈 일자별 AI 인용률 추이")
        try:
            _geo_hist = load_geo_history(_geo_uid, days=90)
        except Exception:
            _geo_hist = pd.DataFrame()
        if _geo_hist.empty:
            st.caption("아직 누적 이력이 없습니다. 매일(또는 주 2~3회) 실행하면 추이 그래프가 그려집니다.")
        else:
            _geo_share_hist = compute_share(_geo_hist)
            _geo_chart = (
                alt.Chart(_geo_share_hist)
                .mark_line(point=True)
                .encode(
                    x=alt.X("date:O", title="날짜"),
                    y=alt.Y("share:Q", title="인용률 (%)", scale=alt.Scale(domain=[0, 100])),
                    color=alt.Color("brand:N", title="브랜드"),
                    tooltip=["date", "brand", "share", "mentions", "queries"],
                )
                .properties(height=320)
            )
            st.altair_chart(_geo_chart, use_container_width=True)
            with st.expander("📄 이력 원본 데이터"):
                st.dataframe(_geo_hist.drop(columns=["user_id"], errors="ignore"),
                             use_container_width=True, height=260)

# ── 11. 스키마·FAQ 생성기 (GEO/AEO) ─────────────────────────────────────────────
elif selected_menu == "스키마·FAQ 생성기":
    from integrations.schema_gen import (
        build_product_schema, build_faq_schema, build_howto_schema,
        build_breadcrumb_schema, to_script_tag, validate_schema,
        faq_to_html, reviews_to_faq,
    )
    import json as _sg_json

    st.markdown("""
    <div style='font-size:1.5rem;font-weight:800;color:#111;letter-spacing:-0.03em;margin-bottom:0.2rem;'>스키마·FAQ 생성기</div>
    <div style='font-size:0.82rem;color:#AAA;margin-bottom:1.4rem;'>Schema.org JSON-LD 자동 생성 + 리뷰 기반 FAQ 변환 — 자사몰·블로그의 GEO/AEO 기술 토대</div>
    """, unsafe_allow_html=True)

    _sg_tab1, _sg_tab2 = st.tabs(["🧩 JSON-LD 스키마 생성", "💬 리뷰 → FAQ 변환 (AEO)"])

    # ════════ 탭 1: JSON-LD 스키마 생성 ════════
    with _sg_tab1:
        st.caption("스키마 구조는 AI 없이 규격대로 생성됩니다(환각 없음). 완성된 `<script>` 태그를 자사몰/블로그 `<head>` 또는 본문에 붙여넣으세요.")
        _sg_type = st.selectbox("스키마 유형", ["Product (상품)", "FAQPage (자주 묻는 질문)", "HowTo (사용법/가이드)", "BreadcrumbList (탐색 경로)"])

        _sg_schema = None
        if _sg_type.startswith("Product"):
            _pc1, _pc2 = st.columns(2)
            with _pc1:
                _p_name  = st.text_input("상품명 *", placeholder="DJI Mini 4 Pro 플라이 모어 콤보")
                _p_brand = st.text_input("브랜드", value="DJI")
                _p_price = st.text_input("판매가 (숫자만)", placeholder="1139000")
                _p_sku   = st.text_input("SKU/모델번호", placeholder="CP.MA.00000735.01")
            with _pc2:
                _p_url   = st.text_input("상품 페이지 URL", placeholder="https://dronebox.co.kr/...")
                _p_img   = st.text_input("이미지 URL (쉼표로 여러 개)", placeholder="https://.../main.jpg")
                _p_rat   = st.text_input("평점 (선택, 예: 4.8)")
                _p_cnt   = st.text_input("리뷰 수 (선택, 예: 127)")
            _p_desc = st.text_area("상품 설명", height=90, placeholder="249g 초경량 4K 촬영 드론…")
            if st.button("스키마 생성", type="primary", key="_sg_btn_p"):
                if not _p_name.strip():
                    st.error("상품명은 필수입니다.")
                else:
                    _sg_schema = build_product_schema(
                        _p_name, _p_desc, _p_brand, _p_price, "KRW",
                        _p_url, _p_img, _p_sku, "InStock", _p_rat, _p_cnt)

        elif _sg_type.startswith("FAQPage"):
            st.caption("질문|답변 형식으로 한 줄에 하나씩 입력 (리뷰에서 자동 생성하려면 옆 탭 이용)")
            _f_text = st.text_area("Q&A 목록", height=180,
                placeholder="드론 자격증이 필요한가요?|250g 미만 드론은 4종 온라인 교육만 이수하면 됩니다. 자세한 기준은…\n배송은 얼마나 걸리나요?|평일 오후 2시 이전 주문 시 당일 출고됩니다.")
            if st.button("스키마 생성", type="primary", key="_sg_btn_f"):
                _f_qa = []
                for _ln in _f_text.split("\n"):
                    if "|" in _ln:
                        _q, _a = _ln.split("|", 1)
                        _f_qa.append({"q": _q, "a": _a})
                if not _f_qa:
                    st.error("'질문|답변' 형식의 줄이 없습니다.")
                else:
                    _sg_schema = build_faq_schema(_f_qa)

        elif _sg_type.startswith("HowTo"):
            _h_name = st.text_input("가이드 제목", placeholder="DJI Mini 4 Pro 첫 비행 준비 방법")
            _h_steps = st.text_area("단계 (한 줄에 하나)", height=150,
                placeholder="기체와 조종기를 완충합니다.\nDJI Fly 앱을 설치하고 계정에 로그인합니다.\n…")
            _h_time = st.number_input("총 소요 시간 (분, 선택)", min_value=0, value=0)
            if st.button("스키마 생성", type="primary", key="_sg_btn_h"):
                _h_list = [s for s in _h_steps.split("\n") if s.strip()]
                if not _h_name.strip() or len(_h_list) < 2:
                    st.error("제목과 2개 이상의 단계를 입력해주세요.")
                else:
                    _sg_schema = build_howto_schema(_h_name, _h_list, _h_time or "")

        else:  # BreadcrumbList
            st.caption("이름|URL 형식, 상위 → 하위 순서로 입력 (URL 생략 가능)")
            _b_text = st.text_area("경로", height=120,
                placeholder="홈|https://dronebox.co.kr\n드론|https://dronebox.co.kr/drone\nDJI Mini 4 Pro|")
            if st.button("스키마 생성", type="primary", key="_sg_btn_b"):
                _b_items = []
                for _ln in _b_text.split("\n"):
                    if _ln.strip():
                        _parts = _ln.split("|", 1)
                        _b_items.append((_parts[0], _parts[1] if len(_parts) > 1 else ""))
                if len(_b_items) < 2:
                    st.error("2개 이상의 경로 항목을 입력해주세요.")
                else:
                    _sg_schema = build_breadcrumb_schema(_b_items)

        if _sg_schema:
            _sg_issues = validate_schema(_sg_schema)
            if _sg_issues:
                for _is in _sg_issues:
                    st.warning(f"⚠️ {_is}")
            else:
                st.success("✅ 필수 항목 검증 통과")
            _sg_tag = to_script_tag(_sg_schema)
            st.code(_sg_tag, language="html")
            st.download_button("📥 스키마 파일 다운로드", _sg_tag.encode("utf-8"),
                file_name="schema_jsonld.html", mime="text/html", use_container_width=True)
            st.caption("검증: [Google 리치 결과 테스트](https://search.google.com/test/rich-results)에 붙여넣어 확인하세요.")

    # ════════ 탭 2: 리뷰 → FAQ 변환 ════════
    with _sg_tab2:
        st.caption("고객 리뷰·문의를 붙여넣으면 실제 고객 언어 기반 Q&A를 생성합니다. "
                   "답변은 AEO 적격 형식(질문형 헤딩 + 40~60자 직접 답변 우선)으로 작성됩니다.")
        if not gemini_key:
            st.warning("⚙️ 설정에서 Gemini API 키를 먼저 등록해주세요.")
        else:
            _rf_product = st.text_input("상품명", placeholder="DJI Mini 4 Pro", key="_rf_p")
            _rf_reviews = st.text_area("고객 리뷰/문의 붙여넣기 (최대 8,000자)", height=220,
                placeholder="배터리가 생각보다 오래가요. 35분은 너무하고 한 28분?\n초보인데 조작이 쉬워요. 근데 자격증 필요한가요?\n…")
            _rf_n = st.slider("생성할 Q&A 개수", 5, 15, 10)

            if st.button("💬 FAQ 생성", type="primary", use_container_width=True, key="_rf_btn"):
                with st.spinner("리뷰 분석 및 FAQ 생성 중…"):
                    _rf_qa, _rf_err = reviews_to_faq(
                        lambda p: _gemini_generate(gemini_key, p),
                        _rf_product, _rf_reviews, _rf_n)
                if _rf_err:
                    st.error(_rf_err)
                else:
                    st.session_state["_rf_qa"] = _rf_qa
                    st.success(f"✅ Q&A {len(_rf_qa)}개 생성 완료 — 아래에서 수정 후 내보내세요.")

            _rf_qa_state = st.session_state.get("_rf_qa")
            if _rf_qa_state:
                _rf_df = pd.DataFrame(_rf_qa_state)
                _rf_edited = st.data_editor(
                    _rf_df, use_container_width=True, num_rows="dynamic",
                    column_config={"q": st.column_config.TextColumn("질문", width="medium"),
                                   "a": st.column_config.TextColumn("답변", width="large")},
                    key="_rf_editor")
                _rf_final = _rf_edited.to_dict("records")

                _rf_schema = build_faq_schema(_rf_final)
                _rf_issues = validate_schema(_rf_schema)
                for _is in _rf_issues:
                    st.warning(f"⚠️ {_is}")

                _rf_c1, _rf_c2 = st.columns(2)
                with _rf_c1:
                    st.markdown("**FAQPage 스키마 (head 삽입)**")
                    _rf_tag = to_script_tag(_rf_schema)
                    st.code(_rf_tag, language="html")
                    st.download_button("📥 스키마 다운로드", _rf_tag.encode("utf-8"),
                        file_name="faq_schema.html", mime="text/html",
                        use_container_width=True, key="_rf_dl1")
                with _rf_c2:
                    st.markdown("**HTML FAQ 블록 (본문 삽입)**")
                    _rf_html = faq_to_html(_rf_final, title=f"{_rf_product or '상품'} 자주 묻는 질문")
                    st.code(_rf_html, language="html")
                    st.download_button("📥 HTML 다운로드", _rf_html.encode("utf-8"),
                        file_name="faq_block.html", mime="text/html",
                        use_container_width=True, key="_rf_dl2")
                st.caption("💡 두 파일을 함께 사용하세요: 스키마는 `<head>`, FAQ 블록은 상세페이지 본문에. "
                           "상세페이지 제작기로 만든 페이지에도 그대로 삽입할 수 있습니다.")

# ── 12. GEO 진단 (자사 vs 경쟁사 + AI 크롤러 점검) ──────────────────────────────
elif selected_menu == "GEO 진단":
    from integrations.geo_audit import audit_url, check_ai_crawlers, AI_CRAWLERS

    st.markdown("""
    <div style='font-size:1.5rem;font-weight:800;color:#111;letter-spacing:-0.03em;margin-bottom:0.2rem;'>GEO 진단</div>
    <div style='font-size:0.82rem;color:#AAA;margin-bottom:1.4rem;'>자사 vs 경쟁사 상세페이지 상대 평가 + AI 크롤러 접근성 점검</div>
    """, unsafe_allow_html=True)

    _ga_tab1, _ga_tab2 = st.tabs(["⚖️ 페이지 비교 진단", "🕷️ AI 크롤러 점검"])

    with _ga_tab1:
        st.caption("같은 6개 기준(사실 밀도·구조화 데이터·FAQ 구조·메타/OG·이미지 alt·콘텐츠 분량)으로 "
                   "두 페이지를 채점해 비교합니다. AI를 쓰지 않는 결정적 측정입니다.")
        _ga_c1, _ga_c2 = st.columns(2)
        with _ga_c1:
            _ga_mine = st.text_input("🏠 자사 페이지 URL", placeholder="https://dronebox.co.kr/product/...")
        with _ga_c2:
            _ga_comp = st.text_input("👀 경쟁사 페이지 URL (선택)", placeholder="https://...")

        if st.button("⚖️ 진단 실행", type="primary", use_container_width=True, key="_ga_btn"):
            _ga_results = []
            for _label, _u_in in [("자사", _ga_mine), ("경쟁사", _ga_comp)]:
                if not _u_in.strip():
                    continue
                with st.spinner(f"{_label} 페이지 분석 중…"):
                    _a, _err = audit_url(_u_in.strip())
                if _err:
                    st.error(f"{_label} 페이지 로드 실패: {_err} — 로그인 필요/봇 차단 페이지일 수 있습니다.")
                elif _a:
                    _ga_results.append((_label, _a))
            st.session_state["_ga_results"] = _ga_results

        _ga_results = st.session_state.get("_ga_results", [])
        if _ga_results:
            _ga_mcols = st.columns(len(_ga_results))
            for _i, (_label, _a) in enumerate(_ga_results):
                _ga_mcols[_i].metric(f"{'🏠' if _label=='자사' else '👀'} {_label} 종합", f"{_a['total']}점")

            # 영역별 점수 비교 표
            _ga_rows = []
            for _area in next(iter(_ga_results))[1]["scores"].keys():
                _row = {"진단 영역": _area}
                for _label, _a in _ga_results:
                    _row[_label] = _a["scores"][_area]
                if len(_ga_results) == 2:
                    _row["격차"] = _ga_rows_diff = _ga_results[0][1]["scores"][_area] - _ga_results[1][1]["scores"][_area]
                _ga_rows.append(_row)
            st.dataframe(pd.DataFrame(_ga_rows), use_container_width=True, hide_index=True)

            if len(_ga_results) == 2:
                _ga_chart_df = pd.DataFrame([
                    {"영역": a, "페이지": lbl, "점수": res["scores"][a]}
                    for lbl, res in _ga_results for a in res["scores"]
                ])
                st.altair_chart(
                    alt.Chart(_ga_chart_df).mark_bar().encode(
                        x=alt.X("점수:Q", scale=alt.Scale(domain=[0, 100])),
                        y=alt.Y("영역:N", title=None),
                        color=alt.Color("페이지:N"),
                        yOffset="페이지:N",
                        tooltip=["영역", "페이지", "점수"],
                    ).properties(height=260),
                    use_container_width=True)
                # 열세 영역 안내
                _weak = [r["진단 영역"] for r in _ga_rows if r.get("격차", 0) < 0]
                if _weak:
                    st.warning("📌 경쟁사 대비 열세 영역: " + ", ".join(_weak) +
                               " — 스키마·FAQ 생성기와 상세페이지 제작기로 보강하세요.")
                else:
                    st.success("✅ 전 영역에서 경쟁사 이상입니다.")

            for _label, _a in _ga_results:
                with st.expander(f"📄 {_label} 상세 측정값 — {_a['url']}"):
                    st.table(pd.DataFrame(list(_a["detail"].items()), columns=["항목", "값"]))
            st.caption("⚠️ 네이버 스마트스토어 등 JS 렌더링/봇 차단 페이지는 측정값이 실제보다 낮게 나올 수 있습니다. "
                       "자사몰·블로그 페이지 비교에 가장 정확합니다.")

    with _ga_tab2:
        st.caption("robots.txt에서 주요 AI 크롤러(GPTBot, ClaudeBot, PerplexityBot 등) 허용 여부와 "
                   "llms.txt 존재를 점검합니다. AI 검색에 인용되려면 크롤러가 들어올 수 있어야 합니다.")
        _cr_url = st.text_input("사이트 주소", placeholder="dronebox.co.kr", key="_cr_url")
        if st.button("🕷️ 점검 실행", type="primary", use_container_width=True, key="_cr_btn") and _cr_url.strip():
            with st.spinner("robots.txt / llms.txt 점검 중…"):
                _cr = check_ai_crawlers(_cr_url.strip())
            if _cr.get("error"):
                st.warning(_cr["error"])
            _cr_df = pd.DataFrame(_cr["crawlers"])
            def _cr_color(v):
                if "전체 차단" in str(v): return "color:#C0392B;font-weight:700"
                if "부분" in str(v): return "color:#C07A00;font-weight:700"
                return "color:#1A7A2A;font-weight:700"
            st.dataframe(_cr_df.style.applymap(_cr_color, subset=["상태"]),
                         use_container_width=True, hide_index=True)
            _cc1, _cc2 = st.columns(2)
            _cc1.metric("robots.txt", "있음" if _cr["robots_found"] else "없음(전체 허용)")
            _cc2.metric("llms.txt", "있음 ✅" if _cr["llms_txt"] else "없음")
            if not _cr["llms_txt"]:
                st.info("💡 llms.txt는 AI 엔진에게 사이트 핵심 정보를 알려주는 신생 표준입니다. "
                        "사이트 소개·주요 페이지·연락처를 마크다운으로 정리해 루트에 올려두면 GEO에 유리합니다.")

# ── 13. 키워드 인텐트 분류 ──────────────────────────────────────────────────────
elif selected_menu == "키워드 인텐트":
    from integrations.intent_classify import classify_keywords, INTENT_LABELS

    st.markdown("""
    <div style='font-size:1.5rem;font-weight:800;color:#111;letter-spacing:-0.03em;margin-bottom:0.2rem;'>키워드 인텐트 분류</div>
    <div style='font-size:0.82rem;color:#AAA;margin-bottom:1.4rem;'>검색 의도(정보형/비교형/거래형) 분류 → 콘텐츠 기획으로 연결</div>
    """, unsafe_allow_html=True)

    if not gemini_key:
        st.warning("⚙️ 설정에서 Gemini API 키를 먼저 등록해주세요.")
    else:
        _ic_default = []
        try:
            if not hist_df.empty and "keyword" in hist_df.columns:
                _ic_default = list(pd.Series(hist_df["keyword"]).dropna().unique())[:30]
        except Exception:
            pass
        _ic_text = st.text_area("분류할 키워드 (줄바꿈 구분, 최대 60개)",
                                value="\n".join(_ic_default), height=160)
        if st.button("🧭 인텐트 분류 실행", type="primary", use_container_width=True, key="_ic_btn"):
            _ic_kws = [k for k in _ic_text.split("\n") if k.strip()]
            with st.spinner(f"{len(_ic_kws)}개 키워드 분류 중…"):
                _ic_res, _ic_err = classify_keywords(
                    lambda p: _gemini_generate(gemini_key, p), _ic_kws)
            if _ic_err:
                st.error(_ic_err)
            else:
                st.session_state["_ic_res"] = _ic_res

        _ic_res = st.session_state.get("_ic_res")
        if _ic_res:
            _ic_df = pd.DataFrame(_ic_res)
            _ic_counts = _ic_df["intent"].value_counts()
            _ic_cols = st.columns(3)
            for _i, _lb in enumerate(INTENT_LABELS):
                _ic_cols[_i].metric(_lb, f"{int(_ic_counts.get(_lb, 0))}개")

            _ic_filter = st.multiselect("의도 필터", INTENT_LABELS, default=INTENT_LABELS)
            st.dataframe(
                _ic_df[_ic_df["intent"].isin(_ic_filter)].rename(columns={
                    "keyword": "키워드", "intent": "의도",
                    "suggestion": "제안 (콘텐츠/액션)", "confidence": "확신도"}),
                use_container_width=True, hide_index=True)

            # 콘텐츠 캘린더 초안: 정보형+비교형 → 주차 배정
            _ic_content = _ic_df[_ic_df["intent"].isin(["정보형", "비교형"])].reset_index(drop=True)
            if not _ic_content.empty:
                st.markdown("#### 🗓️ 콘텐츠 캘린더 초안 (주 2건 기준)")
                _ic_content["주차"] = [f"{_w // 2 + 1}주차" for _w in range(len(_ic_content))]
                st.dataframe(_ic_content.rename(columns={
                    "keyword": "타겟 키워드", "suggestion": "콘텐츠 주제", "intent": "유형"})[
                    ["주차", "타겟 키워드", "유형", "콘텐츠 주제"]],
                    use_container_width=True, hide_index=True)
                st.download_button("📥 캘린더 CSV",
                    _ic_content.to_csv(index=False).encode("utf-8-sig"),
                    file_name="content_calendar.csv", mime="text/csv", use_container_width=True)

# ── 14. 시즌성 분석 (데이터랩) ──────────────────────────────────────────────────
elif selected_menu == "시즌성 분석":
    from integrations.seasonality import (
        fetch_trend, analyze_seasonality, recommend_timing, MONTH_NAMES)

    st.markdown("""
    <div style='font-size:1.5rem;font-weight:800;color:#111;letter-spacing:-0.03em;margin-bottom:0.2rem;'>시즌성 분석</div>
    <div style='font-size:0.82rem;color:#AAA;margin-bottom:1.4rem;'>네이버 데이터랩 검색 추이로 성수기·비수기 파악 → 캠페인 타이밍 추천</div>
    """, unsafe_allow_html=True)

    if not naver_cid or not naver_csec:
        st.warning("⚙️ 설정에서 Naver Client ID/Secret을 먼저 등록해주세요. (데이터랩은 검색 API와 동일한 키 사용)")
    else:
        st.caption("드론처럼 계절을 타는 카테고리에서 특히 유용합니다. 값은 데이터랩 상대지수(기간 내 최댓값=100)입니다.")
        _sn_default = []
        try:
            if not hist_df.empty and "keyword" in hist_df.columns:
                _sn_default = list(pd.Series(hist_df["keyword"]).dropna().unique())[:5]
        except Exception:
            pass
        if not _sn_default:
            _sn_default = ["입문용 드론"]
        _sn_text = st.text_area("분석할 키워드 (최대 5개, 줄바꿈 구분)",
                                value="\n".join(_sn_default[:5]), height=120)

        if st.button("📅 시즌성 분석 실행", type="primary", use_container_width=True, key="_sn_btn"):
            _sn_kws = [k for k in _sn_text.split("\n") if k.strip()][:5]
            with st.spinner("데이터랩 검색 추이 수집 중…"):
                _sn_res, _sn_err = fetch_trend(naver_cid, naver_csec, _sn_kws)
            if _sn_err:
                st.error(_sn_err)
            else:
                st.session_state["_sn_res"] = _sn_res

        _sn_res = st.session_state.get("_sn_res")
        if _sn_res:
            # 월별 지수 차트 (전체 키워드)
            _sn_chart_rows = []
            for _kw, _series in _sn_res.items():
                _an = analyze_seasonality(_series)
                for _m, _v in _an.get("monthly_index", {}).items():
                    _sn_chart_rows.append({"월": MONTH_NAMES[_m - 1], "_mo": _m, "키워드": _kw, "검색지수": _v})
            if _sn_chart_rows:
                _sn_cdf = pd.DataFrame(_sn_chart_rows).sort_values("_mo")
                st.altair_chart(
                    alt.Chart(_sn_cdf).mark_line(point=True).encode(
                        x=alt.X("월:N", sort=MONTH_NAMES, title="월"),
                        y=alt.Y("검색지수:Q", title="평균 검색지수 (최댓월=100)"),
                        color=alt.Color("키워드:N"),
                        tooltip=["키워드", "월", "검색지수"],
                    ).properties(height=320),
                    use_container_width=True)

            # 키워드별 타이밍 추천
            st.markdown("#### 🎯 키워드별 캠페인 타이밍")
            for _kw, _series in _sn_res.items():
                _an = analyze_seasonality(_series)
                if not _an:
                    st.caption(f"**{_kw}**: 데이터 부족")
                    continue
                _peaks = ", ".join(MONTH_NAMES[m - 1] for m in _an["peak_months"]) or "뚜렷하지 않음"
                _lows = ", ".join(MONTH_NAMES[m - 1] for m in _an["low_months"]) or "뚜렷하지 않음"
                with st.container():
                    st.markdown(f"**🔑 {_kw}**")
                    _sc1, _sc2 = st.columns(2)
                    _sc1.metric("성수기", _peaks)
                    _sc2.metric("비수기", _lows)
                    st.info(recommend_timing(_an))
            st.caption("💡 SEO 콘텐츠는 검색 노출까지 4~8주 걸립니다. 성수기 2개월 전 발행이 이상적입니다. "
                       "→ '키워드 인텐트' 메뉴와 함께 쓰면 어떤 콘텐츠를 언제 낼지 계획할 수 있습니다.")

# ── 15. 엔티티 감사 (브랜드 일관성) ─────────────────────────────────────────────
elif selected_menu == "엔티티 감사":
    from integrations.entity_audit import audit_entity, build_organization_schema
    from integrations.schema_gen import to_script_tag
    from utils.brand import parse_brand_list

    st.markdown("""
    <div style='font-size:1.5rem;font-weight:800;color:#111;letter-spacing:-0.03em;margin-bottom:0.2rem;'>엔티티 감사</div>
    <div style='font-size:0.82rem;color:#AAA;margin-bottom:1.4rem;'>채널별 브랜드 정보(NAP·표기) 일관성 점검 → AI 엔진의 엔티티 인식 강화</div>
    """, unsafe_allow_html=True)

    _ea_tab1, _ea_tab2 = st.tabs(["🔍 일관성 점검", "🏢 Organization 스키마 생성"])

    with _ea_tab1:
        st.caption("자사 정보가 노출되는 여러 채널 URL을 입력하면, 전화번호·사업자번호·브랜드 표기가 "
                   "채널마다 일치하는지 점검합니다. AI는 일관된 엔티티를 더 신뢰·인용합니다.")
        _ea_urls_text = st.text_area("채널 URL (줄바꿈 구분)", height=120,
            placeholder="https://dronebox.co.kr\nhttps://blog.naver.com/...\nhttps://smartstore.naver.com/...")
        _ea_alias_default = " ".join(filter(None, [my_brand_1, my_brand_2]))
        _ea_aliases = st.text_input("브랜드 표기 변형 (쉼표 구분)",
            value=_ea_alias_default or "빛드론, 드론박스",
            help="탐지 기준이 되는 브랜드명들. 띄어쓰기/대소문자 변형은 자동 감지됩니다.")

        if st.button("🔍 감사 실행", type="primary", use_container_width=True, key="_ea_btn"):
            _ea_urls = [u for u in _ea_urls_text.split("\n") if u.strip()]
            _ea_alias_list = parse_brand_list(_ea_aliases)
            if not _ea_urls:
                st.error("점검할 URL을 1개 이상 입력해주세요.")
            else:
                with st.spinner(f"{len(_ea_urls)}개 채널 점검 중…"):
                    _ea_res = audit_entity(_ea_urls, _ea_alias_list)
                st.session_state["_ea_res"] = _ea_res

        _ea_res = st.session_state.get("_ea_res")
        if _ea_res:
            _ea_s = _ea_res["summary"]
            _es1, _es2, _es3 = st.columns(3)
            _es1.metric("점검 채널", f"{_ea_s['점검 채널 수']}개")
            _es2.metric("브랜드 표기 변형", f"{_ea_s['브랜드 표기 변형']}종")
            _es3.metric("일관성", _ea_s["일관성"])

            _ea_valid = [c for c in _ea_res["channels"] if "error" not in c]
            if _ea_valid:
                st.dataframe(pd.DataFrame(_ea_valid), use_container_width=True, hide_index=True)
            for _c in _ea_res["channels"]:
                if "error" in _c:
                    st.caption(f"⚠️ {_c['url']} — 로드 실패: {_c['error']}")

            if _ea_res["issues"]:
                for _label, _msg in _ea_res["issues"]:
                    st.warning(f"**{_label}**: {_msg}")
            else:
                st.success("✅ 채널 간 브랜드 정보가 일관됩니다.")

    with _ea_tab2:
        st.caption("모든 채널 URL을 sameAs에 넣은 Organization/LocalBusiness 스키마를 생성합니다. "
                   "자사몰 메인에 삽입하면 AI 엔진이 분산된 채널을 같은 엔티티로 묶어 인식합니다.")
        _oc1, _oc2 = st.columns(2)
        with _oc1:
            _o_name  = st.text_input("브랜드/상호명 *", value=my_brand_1 or "빛드론")
            _o_url   = st.text_input("대표 홈페이지 URL")
            _o_phone = st.text_input("대표 전화번호")
        with _oc2:
            _o_logo  = st.text_input("로고 이미지 URL")
            _o_addr  = st.text_input("주소")
            _o_local = st.checkbox("오프라인 매장 있음 (LocalBusiness)", value=True)
        _o_same = st.text_area("연결할 채널 URL (sameAs, 줄바꿈 구분)", height=100,
            placeholder="https://blog.naver.com/...\nhttps://smartstore.naver.com/...\nhttps://instagram.com/...")
        if st.button("스키마 생성", type="primary", key="_o_btn"):
            if not _o_name.strip():
                st.error("상호명은 필수입니다.")
            else:
                _o_schema = build_organization_schema(
                    _o_name, _o_url, _o_logo, _o_phone, _o_addr,
                    [s for s in _o_same.split("\n") if s.strip()], _o_local)
                _o_tag = to_script_tag(_o_schema)
                st.code(_o_tag, language="html")
                st.download_button("📥 스키마 다운로드", _o_tag.encode("utf-8"),
                    file_name="organization_schema.html", mime="text/html",
                    use_container_width=True, key="_o_dl")
