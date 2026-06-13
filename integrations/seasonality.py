# -*- coding: utf-8 -*-
"""
[SEASON] 네이버 데이터랩 검색어 트렌드 기반 시즌성 분석
========================================================
데이터랩 통합검색어 트렌드 API로 키워드의 월별 검색 추이를 수집하고,
- 성수기/비수기 월 식별
- 다음 성수기까지 남은 기간 → 콘텐츠·광고 준비 타이밍 추천
드론은 계절성이 강한 카테고리(봄·가을 비행 성수기)라 캠페인 타이밍 최적화에 유용.

데이터랩 API는 네이버 검색 API와 동일한 client_id/secret 사용.
값은 0~100 상대지수(기간 내 최댓값=100)로 반환됨에 유의.
"""
from __future__ import annotations

import logging
import datetime as dt

import requests

log = logging.getLogger(__name__)

DATALAB_URL = "https://openapi.naver.com/v1/datalab/search"
MONTH_NAMES = ["1월", "2월", "3월", "4월", "5월", "6월",
               "7월", "8월", "9월", "10월", "11월", "12월"]


def fetch_trend(client_id: str, client_secret: str, keywords: list[str],
                months_back: int = 25, time_unit: str = "month"):
    """
    키워드별 검색 트렌드 수집.
    Returns: (results, error)
      results: {키워드: [(period, ratio), ...]}  -- period는 "YYYY-MM-DD"
    한 번에 최대 5개 키워드 그룹. 25개월이면 작년 동월과 비교 가능.
    """
    kws = [k.strip() for k in keywords if k.strip()][:5]
    if not kws:
        return None, "키워드가 비어 있습니다."

    end = dt.date.today()
    start = end - dt.timedelta(days=months_back * 31)
    payload = {
        "startDate": start.strftime("%Y-%m-%d"),
        "endDate": end.strftime("%Y-%m-%d"),
        "timeUnit": time_unit,
        "keywordGroups": [{"groupName": k, "keywords": [k]} for k in kws],
    }
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
        "Content-Type": "application/json",
    }
    try:
        r = requests.post(DATALAB_URL, json=payload, headers=headers, timeout=20)
    except Exception as e:
        return None, f"API 호출 실패: {e}"
    if r.status_code != 200:
        return None, f"데이터랩 API 오류 (HTTP {r.status_code}): {r.text[:200]}"

    try:
        data = r.json().get("results", [])
    except Exception as e:
        return None, f"응답 파싱 실패: {e}"

    out = {}
    for grp in data:
        name = grp.get("title", "")
        out[name] = [(d.get("period", ""), float(d.get("ratio", 0))) for d in grp.get("data", [])]
    return out, ""


def analyze_seasonality(series: list[tuple]) -> dict:
    """
    [(period, ratio), ...] → 월별 평균 지수 + 성수기/비수기 분석.
    같은 월이 여러 해에 걸쳐 있으면 평균 내어 계절 패턴 추출.
    """
    if not series:
        return {}
    monthly = {m: [] for m in range(1, 13)}
    for period, ratio in series:
        try:
            mth = int(period.split("-")[1])
            monthly[mth].append(ratio)
        except (IndexError, ValueError):
            continue
    avg = {m: (sum(v) / len(v)) for m, v in monthly.items() if v}
    if not avg:
        return {}

    mx = max(avg.values()) or 1
    norm = {m: round(v / mx * 100, 1) for m, v in avg.items()}  # 최댓월=100 정규화
    mean = sum(norm.values()) / len(norm)
    peak_months = sorted([m for m, v in norm.items() if v >= mean * 1.15])
    low_months = sorted([m for m, v in norm.items() if v <= mean * 0.85])

    # 다음 성수기까지 D-계산 (준비 리드타임 안내)
    this_month = dt.date.today().month
    next_peak = None
    if peak_months:
        ahead = [m for m in peak_months if m > this_month] or peak_months
        next_peak = min(ahead)
    months_to_peak = ((next_peak - this_month) % 12) if next_peak else None

    return {
        "monthly_index": norm,
        "peak_months": peak_months,
        "low_months": low_months,
        "next_peak_month": next_peak,
        "months_to_peak": months_to_peak,
        "is_peak_now": this_month in peak_months,
    }


def recommend_timing(analysis: dict) -> str:
    """시즌성 분석 → 캠페인 타이밍 추천 문구"""
    if not analysis or not analysis.get("peak_months"):
        return "뚜렷한 계절성이 관찰되지 않습니다. 상시 운영 키워드로 보입니다."
    peaks = ", ".join(MONTH_NAMES[m - 1] for m in analysis["peak_months"])
    if analysis.get("is_peak_now"):
        return f"🔥 지금이 성수기입니다({peaks}). 광고 입찰가 상향과 재고 확보를 권장합니다."
    nxt = analysis.get("next_peak_month")
    gap = analysis.get("months_to_peak", 0)
    if nxt is None:
        return f"성수기: {peaks}."
    nxt_name = MONTH_NAMES[nxt - 1]
    if gap <= 1:
        return (f"⏰ 다음 성수기({nxt_name})가 임박했습니다. 지금 콘텐츠 발행과 "
                f"상품페이지 최적화를 완료해야 검색 노출이 성수기에 맞춰 익습니다.")
    if gap <= 2:
        return (f"📝 다음 성수기는 {nxt_name}({gap}개월 후)입니다. SEO 콘텐츠는 노출까지 "
                f"4~8주 걸리므로 지금이 콘텐츠 기획·발행 적기입니다.")
    return (f"다음 성수기는 {nxt_name}({gap}개월 후)입니다. 비수기 동안 "
            f"콘텐츠 자산을 축적해두면 성수기 진입이 수월합니다.")
