# -*- coding: utf-8 -*-
"""
[최종 통합 완성본 v7 260327] BitDrone_Manager_Web.py
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

_OBSIDIAN_VAULT = r"C:\Users\binde\Documents\Obsidian Vault\10_Projects\키워드맵"

def _obs_log_change(title: str, detail: str):
    try:
        path = _os.path.join(_OBSIDIAN_VAULT, "변경_이력.md")
        now  = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")
        entry = f"\n### {now} | {title}\n{detail}\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass

def _obs_log_error(title: str, symptom: str, cause: str = "", fix: str = ""):
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
   상단 네비게이션 (horizontal radio)
══════════════════════════════ */
/* 상단 네비 전체 래퍼 */
.km-topnav-wrap { background: #111; margin: -1px calc(-50vw + 50%) 1.5rem; padding: 0 2rem; border-bottom: 2.5px solid #333; }
/* horizontal radio 탭 스타일 */
.km-topnav-wrap [data-testid="stRadio"] > div[role="radiogroup"] {
    display: flex !important; flex-direction: row !important; gap: 0 !important;
    align-items: center !important; height: 48px !important; flex-wrap: nowrap !important; overflow-x: auto !important;
}
.km-topnav-wrap [data-testid="stRadio"] label {
    padding: 0 16px !important; height: 48px !important;
    display: flex !important; align-items: center !important;
    color: rgba(255,255,255,0.42) !important; font-size: 0.82rem !important; font-weight: 400 !important;
    border-radius: 0 !important; border-bottom: 3px solid transparent !important;
    white-space: nowrap !important; cursor: pointer !important; transition: color 0.12s !important;
    border-top: none !important; border-left: none !important; border-right: none !important;
}
.km-topnav-wrap [data-testid="stRadio"] label:hover { color: rgba(255,255,255,0.75) !important; }
.km-topnav-wrap [data-testid="stRadio"] label:has(input:checked) {
    color: #fff !important; border-bottom: 3px solid #FF6B2B !important; font-weight: 600 !important;
}
.km-topnav-wrap [data-testid="stRadio"] label > div:first-child { display: none !important; }
.km-topnav-wrap [data-testid="stRadio"] input { display: none !important; }
.km-topnav-wrap [data-testid="stRadio"] { width: 100% !important; }

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
                    "아이디", placeholder="아이디 입력",
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
                    st.error("아이디와 비밀번호를 입력해주세요.")
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
            _s_email = st.text_input("아이디", placeholder="사용할 아이디 입력", key="_s_email")
            _s_pw  = st.text_input("비밀번호", type="password", key="_s_pw")
            _s_pw2 = st.text_input("비밀번호 확인", type="password", key="_s_pw2")
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            if st.button("회원가입", type="primary", use_container_width=True, key="_s_btn"):
                if not _s_email or not _s_pw:
                    st.error("아이디와 비밀번호를 입력해주세요.")
                elif _s_pw != _s_pw2:
                    st.error("비밀번호가 일치하지 않습니다.")
                else:
                    _ok, _msg = _auth_register(_s_email, _s_pw, _s_name)
                    if _ok:
                        st.success(_msg)
                    else:
                        st.error(_msg)

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
_menu_items = ["Dashboard", "Run & Sync", "경쟁사 집중 분석", "AI Report", "일자별 순위 추이", "SEO태그 생성기", "틈새 키워드 발굴기", "⚙️ 설정"]
st.markdown('<div class="km-topnav-wrap">', unsafe_allow_html=True)
selected_menu = st.radio("메뉴", _menu_items, horizontal=True, label_visibility="collapsed")
st.markdown('</div>', unsafe_allow_html=True)

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
                        return "color: #16A34A; font-weight:700" if n > 0 else "color: #DC2626; font-weight:700"
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
4. 🛡️ 상위권 안착 및 방어 전략"""
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
                _obs_log_change("API 키 저장", f"- Notion: {'있음' if _s_notion_tok else '없음'} / Slack: {'있음' if _s_slack else '없음'}")