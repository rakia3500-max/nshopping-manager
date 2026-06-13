# -*- coding: utf-8 -*-
"""
[ALERTS] 순위 변동 이벤트 감지 + Slack 알림
============================================
"일일 요약" 알림을 "이벤트 기반" 알림으로 고도화.

감지 이벤트
  🚨 자사 급락      : 전일 대비 N계단 이상 하락 (기본 3)
  ⚠️ 자사 순위권 이탈: 전일 순위권 → 오늘 미노출
  🏆 자사 TOP3 진입 : 전일 4위 이하 → 오늘 1~3위
  👀 경쟁사 1페이지 첫 진입: 전일 1페이지 밖 → 오늘 진입

main_automation.py(GitHub Actions)에서 매일 크롤 직후 호출:
  전일 데이터는 Apps Script GET으로 로드, SLACK_WEBHOOK_URL 설정 시에만 발송.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

MY_MALLS_DEFAULT = ("드론박스", "빛드론")
PAGE1_DEFAULT = 40  # 네이버쇼핑 PC 1페이지 노출 수


def _best_ranks(df, malls):
    """{(keyword, mall): 최고(min) 순위} — 대상 mall만"""
    out = {}
    if df is None or len(df) == 0:
        return out
    for _, r in df.iterrows():
        mall = str(r.get("mall", ""))
        if mall not in malls:
            continue
        key = (str(r.get("keyword", "")), mall)
        try:
            rank = int(float(r.get("rank", 0)))
        except (TypeError, ValueError):
            continue
        if rank > 0 and (key not in out or rank < out[key]):
            out[key] = rank
    return out


def detect_events(
    today_df,
    prev_df,
    my_malls=MY_MALLS_DEFAULT,
    comp_malls=("다다사", "효로로", "드론뷰"),
    drop_threshold: int = 3,
    page1: int = PAGE1_DEFAULT,
) -> list[dict]:
    """오늘/전일 수집 데이터 비교 → 이벤트 목록 (level, icon, msg)"""
    my_malls, comp_malls = tuple(my_malls), tuple(comp_malls)
    t_my, p_my = _best_ranks(today_df, my_malls), _best_ranks(prev_df, my_malls)
    t_cp, p_cp = _best_ranks(today_df, comp_malls), _best_ranks(prev_df, comp_malls)
    events = []

    # 자사: 급락 / 이탈 / TOP3 진입
    for key, prev_rank in p_my.items():
        kw, mall = key
        now = t_my.get(key)
        if now is None:
            # 오늘 해당 키워드 수집 자체가 없으면 이탈 판단 보류
            if today_df is not None and len(today_df) and \
               kw in set(str(x) for x in today_df["keyword"]):
                events.append({"level": "warn", "icon": "⚠️",
                               "msg": f"*{mall}* `{kw}` 순위권 이탈 (전일 {prev_rank}위 → 미노출)"})
            continue
        if now - prev_rank >= drop_threshold:
            events.append({"level": "danger", "icon": "🚨",
                           "msg": f"*{mall}* `{kw}` {prev_rank}위 → {now}위 ({now - prev_rank}계단 하락)"})
    for key, now in t_my.items():
        kw, mall = key
        prev_rank = p_my.get(key)
        if now <= 3 and (prev_rank is None or prev_rank > 3):
            frm = f"{prev_rank}위" if prev_rank else "신규"
            events.append({"level": "good", "icon": "🏆",
                           "msg": f"*{mall}* `{kw}` TOP3 진입! ({frm} → {now}위)"})

    # 경쟁사: 1페이지 첫 진입
    for key, now in t_cp.items():
        kw, mall = key
        prev_rank = p_cp.get(key)
        if now <= page1 and (prev_rank is None or prev_rank > page1):
            events.append({"level": "watch", "icon": "👀",
                           "msg": f"경쟁사 *{mall}* `{kw}` 1페이지 진입 ({now}위)"})

    order = {"danger": 0, "warn": 1, "good": 2, "watch": 3}
    return sorted(events, key=lambda e: order.get(e["level"], 9))


def format_alert_message(events: list[dict], date_str: str = "") -> str:
    """Slack(mrkdwn) 메시지 생성. 이벤트 없으면 빈 문자열."""
    if not events:
        return ""
    head = f"📡 *키워드맵 순위 이벤트 알림*{(' — ' + date_str) if date_str else ''}\n"
    return head + "\n".join(f"{e['icon']} {e['msg']}" for e in events[:20]) + \
        (f"\n… 외 {len(events) - 20}건" if len(events) > 20 else "")


def load_prev_from_apps_script(apps_script_url: str, token: str, today_iso: str):
    """Apps Script 이력(GET)에서 오늘 이전 가장 최근 일자의 데이터프레임 반환"""
    import requests
    import pandas as pd
    try:
        res = requests.get(apps_script_url, params={"token": token}, timeout=25)
        df = pd.DataFrame(res.json())
    except Exception as e:
        log.warning("[alerts] 이력 로드 실패: %s", e)
        return None
    if df.empty or "date" not in df.columns:
        return None
    dates = sorted({str(d) for d in df["date"] if str(d) < today_iso})
    if not dates:
        return None
    return df[df["date"].astype(str) == dates[-1]].copy()


def send_slack_webhook(webhook_url: str, text: str) -> bool:
    import requests
    try:
        r = requests.post(webhook_url, json={"text": text}, timeout=15)
        return r.status_code == 200
    except Exception as e:
        log.warning("[alerts] Slack 발송 실패: %s", e)
        return False
