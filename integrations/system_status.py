# -*- coding: utf-8 -*-
"""
[STATUS] 시스템 상태 신호등
============================
앱이 의존하는 핵심 요소들의 상태를 신호등으로 표시.
- check_config(): 빠른 점검 — 키/설정 존재 여부만 (네트워크 X, 항상 실행)
- live_*(): 실제 연결 테스트 — 버튼 클릭 시에만 (네트워크 O)

상태 등급: "green"(정상) / "yellow"(선택/주의) / "red"(필수 누락) / "gray"(미설정·선택)
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

DOT = {"green": "🟢", "yellow": "🟡", "red": "🔴", "gray": "⚪"}


def _item(name, level, detail, required=False):
    return {"name": name, "level": level, "detail": detail, "required": required}


def check_config(keys: dict, encrypt_ok: bool) -> list[dict]:
    """네트워크 없이 설정 상태만 빠르게 점검 (대시보드 상시 표시용)"""
    k = keys or {}
    items = []

    # 1) 암호화 (필수) — API 키 보안의 전제
    items.append(_item(
        "암호화 (ENCRYPT_KEY)",
        "green" if encrypt_ok else "red",
        "정상 — API 키가 암호화 저장됩니다." if encrypt_ok
        else "ENCRYPT_KEY 미설정 — Secrets에 추가하세요.",
        required=True))

    # 2) 네이버 검색 API (필수) — 순위/검색량 수집의 핵심
    has_naver = bool(k.get("naver_client_id") and k.get("naver_client_secret"))
    items.append(_item(
        "네이버 검색 API",
        "green" if has_naver else "red",
        "설정됨 — 순위·검색량·시즌성 수집 가능." if has_naver
        else "Client ID/Secret 미설정 — 순위 수집 불가.",
        required=True))

    # 3) 네이버 광고 API (선택) — 검색량/클릭 정밀도
    has_ad = bool(k.get("naver_ad_api_key") and k.get("naver_customer_id"))
    items.append(_item(
        "네이버 광고 API",
        "green" if has_ad else "gray",
        "설정됨 — 검색량·클릭 데이터 정밀." if has_ad
        else "미설정 — 검색량 정밀도가 낮아질 수 있음(선택).",
        required=False))

    # 4) Gemini (선택이지만 AI 기능 다수가 의존)
    has_gem = bool(k.get("gemini_key"))
    items.append(_item(
        "Gemini AI",
        "green" if has_gem else "yellow",
        "설정됨 — AI 리포트·인용 추적·FAQ·인텐트 사용 가능." if has_gem
        else "미설정 — AI 기능(리포트/인용추적/FAQ/인텐트) 비활성.",
        required=False))

    # 5) 데이터 저장소 (Apps Script — 자동 크롤 결과 수집)
    has_gas = bool(k.get("apps_script_url"))
    items.append(_item(
        "데이터 저장소 (GAS)",
        "green" if has_gas else "gray",
        "연결됨 — 자동 크롤 이력 수집." if has_gas
        else "미설정 — 일자별 추이 누적 안 됨(선택).",
        required=False))

    # 6) Slack 알림 (선택)
    has_slack = bool(k.get("slack_webhook_url"))
    items.append(_item(
        "Slack 알림",
        "green" if has_slack else "gray",
        "연결됨 — 순위 변동 이벤트 알림." if has_slack
        else "미설정 — 알림 비활성(선택).",
        required=False))

    # 7) Notion 연동 (선택)
    has_notion = bool(k.get("notion_token") and k.get("notion_database_id"))
    items.append(_item(
        "Notion 연동",
        "green" if has_notion else "gray",
        "연결됨." if has_notion else "미설정(선택).",
        required=False))

    return items


def overall_level(items: list[dict]) -> str:
    """전체 종합 등급: 필수 red 하나라도 → red, 아니면 가장 나쁜 등급"""
    if any(i["level"] == "red" and i["required"] for i in items):
        return "red"
    if any(i["level"] == "red" for i in items):
        return "red"
    if any(i["level"] == "yellow" for i in items):
        return "yellow"
    return "green"


def overall_summary(items: list[dict]) -> str:
    lv = overall_level(items)
    reds = [i["name"] for i in items if i["level"] == "red"]
    if lv == "green":
        return "모든 핵심 기능 정상 작동 중입니다."
    if lv == "yellow":
        return "필수 기능은 정상이며, 일부 선택 기능이 비활성 상태입니다."
    return f"필수 설정 누락: {', '.join(reds)} — 설정에서 확인하세요."


# ── 실제 연결 테스트 (버튼 클릭 시) ──────────────────────────────────────────
def live_naver(client_id: str, client_secret: str) -> tuple[str, str]:
    """네이버 검색 API 실제 호출 테스트"""
    if not (client_id and client_secret):
        return "gray", "키 미설정"
    import requests
    try:
        r = requests.get(
            "https://openapi.naver.com/v1/search/shop.json",
            headers={"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret},
            params={"query": "드론", "display": 1}, timeout=10)
        if r.status_code == 200:
            return "green", "연결 정상 (HTTP 200)"
        if r.status_code in (401, 403):
            return "red", f"인증 실패 (HTTP {r.status_code}) — 키를 확인하세요."
        return "yellow", f"응답 이상 (HTTP {r.status_code})"
    except Exception as e:
        return "red", f"연결 실패: {type(e).__name__}"


def live_gemini(api_key: str) -> tuple[str, str]:
    """Gemini API 실제 호출 테스트"""
    if not api_key:
        return "gray", "키 미설정"
    import requests
    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
            json={"contents": [{"parts": [{"text": "ping"}]}]}, timeout=15)
        if r.status_code == 200:
            return "green", "연결 정상 (HTTP 200)"
        if r.status_code in (400, 403):
            return "red", f"인증/요청 오류 (HTTP {r.status_code}) — 키를 확인하세요."
        return "yellow", f"응답 이상 (HTTP {r.status_code})"
    except Exception as e:
        return "red", f"연결 실패: {type(e).__name__}"


def live_apps_script(url: str, token: str) -> tuple[str, str]:
    """Apps Script(데이터 저장소) 연결 테스트"""
    if not url:
        return "gray", "미설정"
    import requests
    try:
        r = requests.get(url, params={"token": token}, timeout=15)
        if r.status_code == 200:
            return "green", "연결 정상"
        return "yellow", f"응답 이상 (HTTP {r.status_code})"
    except Exception as e:
        return "red", f"연결 실패: {type(e).__name__}"
