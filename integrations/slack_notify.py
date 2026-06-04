# -*- coding: utf-8 -*-
"""
Slack Incoming Webhook 알림 — 스크린샷 스타일 레이아웃

메시지 구조:
  ✅ 네이버 쇼핑 순위 업데이트
  [Results 바로가기]  [Summary 바로가기]
  📅 날짜 / 🔍 키워드 N개
  🏆 자사 노출 / ⚔️ 경쟁사 노출
  (급변 감지 시 추가 섹션)
"""
import logging
import requests

log = logging.getLogger(__name__)


def _notion_url(database_id):
    if not database_id:
        return None
    clean = database_id.replace("-", "")
    return f"https://notion.so/{clean}"


def build_message(df, history_df, date_str, notion_db_id=""):
    """
    DataFrame → Slack Block Kit 배열

    Returns:
        blocks (list)
    """
    # ── 기본 집계 ─────────────────────────────────────────
    kw_count = df["keyword"].nunique() if "keyword" in df.columns else 0

    # 자사 브랜드 노출 키워드 수 (행 수가 아닌 고유 키워드 수)
    db_count  = int(df[df["is_db"].fillna(False)]["keyword"].nunique())  if "is_db"  in df.columns else 0
    bit_count = int(df[df["is_bit"].fillna(False)]["keyword"].nunique()) if "is_bit" in df.columns else 0

    # 경쟁사 노출 키워드 수
    da_count  = int(df[df["is_da"].fillna(False)]["keyword"].nunique()) if "is_da" in df.columns else 0
    hr_count  = int(df[df["is_hr"].fillna(False)]["keyword"].nunique()) if "is_hr" in df.columns else 0
    dv_count  = int(df[df["is_dv"].fillna(False)]["keyword"].nunique()) if "is_dv" in df.columns else 0

    # ── 전일 대비 급변 감지 ───────────────────────────────
    big_changes = []
    if not history_df.empty and "date" in history_df.columns:
        dates = sorted(history_df["date"].dropna().unique().tolist())
        prev_date = None
        if date_str in dates:
            idx = dates.index(date_str)
            prev_date = dates[idx - 1] if idx > 0 else None
        elif dates:
            prev_date = dates[-1]

        if prev_date:
            prev_df   = history_df[history_df["date"] == prev_date]
            mine_now  = df[df.get("is_db", False) | df.get("is_bit", False)] if (
                "is_db" in df.columns or "is_bit" in df.columns) else df

            for kw, grp in mine_now.groupby("keyword"):
                curr_rank = int(grp["rank"].min())
                prev_rows = prev_df[prev_df["keyword"] == kw]
                if not prev_rows.empty:
                    prev_rank = int(prev_rows["rank"].min())
                    diff = prev_rank - curr_rank
                    if abs(diff) >= 5:
                        big_changes.append({
                            "kw": kw, "curr": curr_rank,
                            "prev": prev_rank, "diff": diff
                        })

    big_changes.sort(key=lambda x: abs(x["diff"]), reverse=True)

    # ── Notion 링크 ───────────────────────────────────────
    notion_link = _notion_url(notion_db_id)
    results_link  = f"<{notion_link}|바로가기>" if notion_link else "_미설정_"
    summary_link  = f"<{notion_link}|바로가기>" if notion_link else "_미설정_"

    # ── Block Kit 조립 ────────────────────────────────────
    blocks = []

    # 1. 헤더
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": "✅ 네이버 쇼핑 순위 업데이트",
            "emoji": True,
        }
    })

    # 2. Notion 링크 (2열)
    blocks.append({
        "type": "section",
        "fields": [
            {"type": "mrkdwn", "text": f"📄 *Results 시트*\n{results_link}"},
            {"type": "mrkdwn", "text": f"📊 *Summary 시트*\n{summary_link}"},
        ]
    })

    blocks.append({"type": "divider"})

    # 3. 날짜 / 키워드 수 (2열)
    blocks.append({
        "type": "section",
        "fields": [
            {"type": "mrkdwn", "text": f":calendar: *날짜*\n{date_str}"},
            {"type": "mrkdwn", "text": f":mag: *키워드*\n{kw_count}개"},
        ]
    })

    blocks.append({"type": "divider"})

    # 4. 자사 / 경쟁사 노출 (2열)
    my_brand_text   = f"DB: {db_count} | BI: {bit_count}"
    comp_brand_text = f"DA: {da_count} | HY: {hr_count} | DV: {dv_count}"

    blocks.append({
        "type": "section",
        "fields": [
            {"type": "mrkdwn", "text": f":trophy: *자사 노출*\n{my_brand_text}"},
            {"type": "mrkdwn", "text": f":crossed_swords: *경쟁사 노출*\n{comp_brand_text}"},
        ]
    })

    # 5. 급변 감지 (있을 때만)
    if big_changes:
        blocks.append({"type": "divider"})
        lines = []
        for c in big_changes[:5]:
            arrow = f"▲{c['diff']}" if c["diff"] > 0 else f"▼{abs(c['diff'])}"
            lines.append(f"• *{c['kw']}*  {c['prev']}위 → {c['curr']}위  {arrow}")
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ":rotating_light: *급변 감지 — 즉시 확인 필요!*\n" + "\n".join(lines),
            }
        })

    return blocks


def send_slack(webhook_url, df, history_df, date_str,
               notion_db_id="", only_on_big_change=False):
    """
    Slack Incoming Webhook 전송

    Args:
        only_on_big_change: True 면 급변(5위↑) 있을 때만 전송
    Returns:
        (success: bool, message: str)
    """
    if not webhook_url:
        return False, "Slack Webhook URL이 없습니다."
    if df is None or df.empty:
        return False, "전송할 데이터가 없습니다."

    try:
        blocks = build_message(df, history_df, date_str, notion_db_id)

        if only_on_big_change:
            has_alert = any(":rotating_light:" in str(b) for b in blocks)
            if not has_alert:
                return True, "급변 없음 — Slack 전송 생략"

        resp = requests.post(webhook_url, json={"blocks": blocks}, timeout=15)
        resp.raise_for_status()
        log.info("[slack] 전송 완료")
        return True, "Slack 알림 전송 완료"

    except Exception as e:
        log.error("[slack] 전송 오류: %s", e)
        return False, str(e)
