"""트래픽 메뉴 — 구글 서치콘솔 + GA4 실시간 데이터 (2026-07-21, 로컬 Bit Ops Console에서 이식).

사용자 키(⚙️ 설정):
- gcp_sa_json      : 구글 서비스 계정 JSON 전체 (서치콘솔 사용자 + GA4 뷰어로 추가된 계정)
- gsc_site_url     : 서치콘솔 속성 1 (예: sc-domain:bit-drone.shop)
- gsc_site_url2    : 서치콘솔 속성 2 (예: https://www.drone-box.co.kr/) — 선택
- ga4_property_id  : GA4 속성 ID 숫자 (드론박스) — 선택
"""
import json
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st


def _sa_creds(sa_json: str, scopes: list[str]):
    from google.oauth2 import service_account
    info = json.loads(sa_json)
    return service_account.Credentials.from_service_account_info(info, scopes=scopes)


def _token(creds) -> str:
    from google.auth.transport.requests import Request
    if not creds.valid:
        creds.refresh(Request())
    return creds.token


@st.cache_data(ttl=3600, show_spinner="서치콘솔 조회 중...")
def _sc_query(sa_json: str, site: str, dims: tuple, days: int) -> list[dict]:
    creds = _sa_creds(sa_json, ["https://www.googleapis.com/auth/webmasters.readonly"])
    from datetime import date, timedelta
    end = date.today() - timedelta(days=2)
    start = end - timedelta(days=days)
    r = requests.post(
        f"https://searchconsole.googleapis.com/webmasters/v3/sites/"
        f"{quote(site, safe='')}/searchAnalytics/query",
        headers={"Authorization": f"Bearer {_token(creds)}"},
        json={"startDate": start.isoformat(), "endDate": end.isoformat(),
              "dimensions": list(dims), "rowLimit": 250}, timeout=30)
    r.raise_for_status()
    return r.json().get("rows", [])


@st.cache_data(ttl=3600, show_spinner="GA4 조회 중...")
def _ga4_report(sa_json: str, pid: str, metrics: tuple, dims: tuple, days: int) -> list[dict]:
    creds = _sa_creds(sa_json, ["https://www.googleapis.com/auth/analytics.readonly"])
    body = {"dateRanges": [{"startDate": f"{days}daysAgo", "endDate": "today"}],
            "metrics": [{"name": m} for m in metrics], "limit": 100}
    if dims:
        body["dimensions"] = [{"name": d} for d in dims]
        body["orderBys"] = [{"metric": {"metricName": metrics[0]}, "desc": True}]
    r = requests.post(
        f"https://analyticsdata.googleapis.com/v1beta/properties/{pid}:runReport",
        headers={"Authorization": f"Bearer {_token(creds)}"}, json=body, timeout=30)
    r.raise_for_status()
    return [{"dims": [d["value"] for d in row.get("dimensionValues", [])],
             "metrics": [float(m["value"] or 0) for m in row.get("metricValues", [])]}
            for row in r.json().get("rows", [])]


def _df(rows, key_name):
    return pd.DataFrame([{key_name: r["keys"][0], "클릭": r["clicks"],
                          "노출": r["impressions"],
                          "클릭률": f'{r["ctr"] * 100:.1f}%',
                          "평균 순위": round(r["position"], 1)} for r in rows])


def render(user_keys: dict):
    sa_json = (user_keys.get("gcp_sa_json") or "").strip()
    site1 = (user_keys.get("gsc_site_url") or "").strip()
    site2 = (user_keys.get("gsc_site_url2") or "").strip()
    ga4_pid = (user_keys.get("ga4_property_id") or "").strip()

    if not sa_json or not (site1 or site2):
        st.info("**트래픽 연동이 아직 설정되지 않았습니다.** ⚙️ 설정에서 아래 3가지를 입력하세요:")
        st.markdown("""
1. **GCP 서비스 계정 JSON** — 서치콘솔 속성에 '사용자', GA4 속성에 '뷰어'로 추가된 서비스 계정의 키 JSON 전체
2. **서치콘솔 속성 URL** — 예: `sc-domain:bit-drone.shop` 또는 `https://www.drone-box.co.kr/`
3. **GA4 속성 ID** (선택) — 드론박스 방문 통계용 숫자 ID
""")
        return

    sites = {}
    if site1:
        sites["사이트 1 (빛드론)" if "bit-drone" in site1 else site1] = site1
    if site2:
        sites["사이트 2 (드론박스)" if "drone-box" in site2 else site2] = site2

    fc1, fc2 = st.columns([1.8, 2.2])
    with fc1:
        sel_label = st.radio("사이트", list(sites), horizontal=True,
                             label_visibility="collapsed")
    with fc2:
        days = {"최근 7일": 7, "최근 28일": 28, "최근 90일": 90}[
            st.radio("기간", ["최근 7일", "최근 28일", "최근 90일"], index=1,
                     horizontal=True, label_visibility="collapsed")]
    site = sites[sel_label]

    try:
        q_rows = _sc_query(sa_json, site, ("query",), days)
    except Exception as e:
        st.error(f"서치콘솔 조회 실패: {e}")
        st.caption("서비스 계정이 해당 속성에 사용자로 추가돼 있는지, URL이 속성과 정확히 "
                   "일치하는지(도메인 속성은 sc-domain: 접두어) 확인하세요.")
        return

    clicks = sum(r["clicks"] for r in q_rows)
    imps = sum(r["impressions"] for r in q_rows)
    strike = sorted([r for r in q_rows if 11 <= r["position"] <= 30],
                    key=lambda r: -r["impressions"])
    page1 = sorted([r for r in q_rows if r["position"] <= 10 and r["impressions"] >= 3],
                   key=lambda r: -r["clicks"])

    if not q_rows:
        st.info("아직 구글 검색 데이터가 없습니다 — 서치콘솔 등록 직후에는 비어 있고 "
                "1~2일 뒤부터 채워집니다.")
    else:
        best = f" 특히 **{strike[0]['keys'][0]}** 가 문 앞에 있어요." if strike else ""
        st.info(f"구글 검색에서 **{imps:,}번 노출, {clicks:,}번 클릭**됐습니다. "
                f"검색어 {len(q_rows)}개 중 **{len(strike)}개가 2~3페이지 대기 중** — "
                f"조금만 밀면 1페이지입니다.{best}")

        k1, k2, k3, k4 = st.columns(4)
        pos = (sum(r["position"] * r["impressions"] for r in q_rows) / imps) if imps else 0
        k1.metric("클릭 (실제 방문)", f"{clicks:,}")
        k2.metric("노출 (보인 횟수)", f"{imps:,}")
        k3.metric("클릭률", f"{clicks / imps * 100:.1f}%" if imps else "-")
        k4.metric("평균 순위", f"{pos:.1f}위" if pos else "-")

        if strike:
            st.markdown("#### 🎯 지금 공략하면 되는 검색어 (2~3페이지 대기 중)")
            st.caption("노출은 되는데 1페이지 밖 — 상품명·설명에 반영하면 효과가 가장 빠른 목록.")
            st.dataframe(_df(strike[:10], "검색어"), use_container_width=True, hide_index=True)
        if page1:
            st.markdown("#### ✅ 이미 1페이지인 검색어")
            st.dataframe(_df(page1[:10], "검색어"), use_container_width=True, hide_index=True)
        with st.expander(f"전체 검색어 {len(q_rows)}개"):
            st.dataframe(_df(q_rows[:100], "검색어"), use_container_width=True, hide_index=True)

    # ── GA4 (드론박스 방문) — 드론박스 사이트를 선택했을 때만 표시 ──
    if ga4_pid and site2 and site == site2:
        st.markdown("### 드론박스 방문 (GA4)")
        try:
            daily = _ga4_report(sa_json, ga4_pid, ("activeUsers", "screenPageViews"),
                                ("date",), days)
            pages = _ga4_report(sa_json, ga4_pid, ("screenPageViews",), ("pageTitle",), days)
            chans = _ga4_report(sa_json, ga4_pid, ("sessions",),
                                ("sessionDefaultChannelGroup",), days)
        except Exception as e:
            st.info(f"GA4 연동 대기 중 — {e}")
            return
        if not daily:
            st.info("GA4 태그 설치 직후라 데이터 수집 중입니다 — 내일부터 표시됩니다.")
            return
        daily.sort(key=lambda r: r["dims"][0])
        users = sum(r["metrics"][0] for r in daily)
        pv = sum(r["metrics"][1] for r in daily)
        import altair as alt
        trend = pd.DataFrame([{"날짜": r["dims"][0][4:6] + "-" + r["dims"][0][6:8],
                               "방문자": r["metrics"][0], "페이지뷰": r["metrics"][1]}
                              for r in daily])
        base = alt.Chart(trend).encode(x=alt.X("날짜:N", sort=None, title=None))
        st.altair_chart(alt.layer(
            base.mark_bar(color="#BFE3D0", size=20).encode(y=alt.Y("방문자:Q", title="방문자")),
            base.mark_line(color="#0E9F5A", point=True).encode(
                y=alt.Y("페이지뷰:Q", title="페이지뷰"))
        ).resolve_scale(y="independent").properties(height=200), use_container_width=True)
        g1, g2, g3 = st.columns(3)
        g1.metric("방문자", f"{users:,.0f}명")
        g2.metric("페이지뷰", f"{pv:,.0f}")
        g3.metric("방문자당 PV", f"{pv / users:.1f}" if users else "-")
        t1, t2 = st.columns(2)
        with t1:
            st.markdown("#### 인기 페이지 Top 10")
            st.dataframe(pd.DataFrame([{"순위": i + 1, "페이지": r["dims"][0][:40],
                                        "조회": int(r["metrics"][0])}
                                       for i, r in enumerate(pages[:10])]),
                         use_container_width=True, hide_index=True)
        with t2:
            st.markdown("#### 유입 채널")
            ch = {"Organic Shopping": "쇼핑 유입 (네이버쇼핑 등)", "Paid Shopping": "쇼핑 광고",
                  "Organic Search": "검색 유입", "Paid Search": "검색 광고",
                  "Organic Video": "영상 유입 (유튜브 등)", "Organic Social": "SNS",
                  "Direct": "직접 방문", "Referral": "링크 타고",
                  "Email": "이메일", "Unassigned": "기타"}
            st.dataframe(pd.DataFrame([{"채널": ch.get(r["dims"][0], r["dims"][0]),
                                        "세션": int(r["metrics"][0])} for r in chans]),
                         use_container_width=True, hide_index=True)
