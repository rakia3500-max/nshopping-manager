# -*- coding: utf-8 -*-
"""
[최종 통합 완성본 v7] BitDrone_Manager_Web.py
- Update: AI 프롬프트 고도화 (검색량/클릭률 기반 실무자 맞춤형 '액션 플랜' 제안 기능 추가)
- Update: 차트 렌더링 랙 해결 (기본 14일 조회 + 달력 필터)
- Update: Gemini API 404 에러 방지를 위한 다중 모델 Fallback 로직 적용 (2.5 -> 2.0 -> 1.5 -> pro)
"""

import streamlit as st
from streamlit_option_menu import option_menu
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
import google.generativeai as genai
import sys

# 인코딩 및 페이지 설정
sys.stdout.reconfigure(encoding='utf-8')
st.set_page_config(page_title="쇼핑 통합 관제", layout="wide")

# --- UI Custom CSS (Modern Floating Card Style) ---
st.markdown("""
<style>
/* 폰트 및 배경화면 (Modern SaaS 스타일) */
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');
@font-face {
    font-family: 'NanumSquareRound';
    src: url('https://fastly.jsdelivr.net/gh/projectnoonnu/noonfonts_twelve@1.0/NanumSquareRound.woff') format('woff');
    font-weight: normal;
    font-style: normal;
}

/* 전체 느낌 (다크 테마 배경) */
div[data-testid="stAppViewContainer"] {
    background-color: transparent;
    font-family: 'Poppins', 'NanumSquareRound', sans-serif;
}

/* 사이드바 스타일 (투명하게 두어 config.toml의 테마를 따르게 함) */
section[data-testid="stSidebar"] {
    border-right: none;
}
/* 사이드바 텍스트 기본 톤 */
section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] div {
    color: #9ca3af;
}
section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 {
    color: #ffffff !important;
    font-weight: 700;
}

/* 상단 헤더 숨기기 */
header[data-testid="stHeader"] {
    background-color: transparent !important;
}

/* 메인 여백 */
.block-container {
    padding-top: 3rem;
}

/* Metric (상단 요약 박스 - 둥근 다크 카드 느낌) */
[data-testid="stMetric"] {
    background-color: #222432;
    border-radius: 16px;
    padding: 1.5rem;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
    border: none;
    margin-bottom: 1rem;
}
[data-testid="stMetricValue"] {
    font-size: 1.8rem;
    font-weight: 700;
    color: #ffffff;
}
[data-testid="stMetricLabel"] {
    font-size: 0.9rem;
    font-weight: 600;
    color: #9ca3af;
    text-transform: none;
}

/* 컨텐츠 내 소제목(H1, H2, H3 등) 스타일 */
h1, h2, h3, h4, h5 {
    color: #ffffff;
    font-family: 'Poppins', 'NanumSquareRound', sans-serif;
    font-weight: 700;
}

/* 버튼 스타일 (둥근 파란색 캡슐 Button) */
div.stButton > button {
    background-color: #3b82f6; /* 파란색 */
    color: #ffffff !important; /* 흰색 텍스트 */
    border-radius: 20px;
    font-weight: 700;
    border: none;
    box-shadow: 0 4px 6px -1px rgba(59, 130, 246, 0.3);
    transition: all 0.2s;
}
div.stButton > button:hover {
    background-color: #2563eb;
    color: #ffffff !important;
    transform: translateY(-2px);
    box-shadow: 0 6px 8px -1px rgba(59, 130, 246, 0.4);
}

/* Expander(아코디언) 제목 */
.streamlit-expanderHeader {
    font-weight: 600;
    color: #d1d5db;
}

/* 경고창/안내창(stAlert) 다크 테마 커스텀 */
[data-testid="stAlert"] {
    background-color: #222432 !important; 
    border: 1px solid #374151 !important;
    color: #ffffff !important;
    border-radius: 12px;
}
[data-testid="stAlert"] p {
    color: #ffffff !important;
}
</style>
""", unsafe_allow_html=True)

# --- KST 시간 설정 ---
NOW_KST = dt.datetime.utcnow() + dt.timedelta(hours=9)
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

# --- 세션 상태 초기화 ---
if 'crawled_df' not in st.session_state: st.session_state.crawled_df = pd.DataFrame()
if 'history_df' not in st.session_state: st.session_state.history_df = pd.DataFrame()
if 'ai_report_text' not in st.session_state: st.session_state.ai_report_text = ""

# --- API 엔진 (네이버 검색 & 광고) ---
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
    except: pass
    return 0, 0, 0

def get_rank(kw, cid, sec):
    if not (cid and sec): return []
    try:
        headers = {**HTTP_HEADERS, "X-Naver-Client-Id": cid, "X-Naver-Client-Secret": sec}
        time.sleep(random.uniform(0.8, 1.5))
        res = requests.get("https://openapi.naver.com/v1/search/shop.json", headers=headers, params={"query": kw, "display": 100, "sort": "sim"}, timeout=10)
        res.raise_for_status()
        return res.json().get('items', [])
    except: return []

# --- GAS 연동 (POST/GET) ---
def send_to_gas(df, url, token):
    if not url: return False, "GAS URL 누락"
    try:
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_bytes = csv_buffer.getvalue().encode('utf-8')
        headers = {'Content-Type': 'text/plain; charset=utf-8'}
        res = requests.post(url, params={"token": token, "type": "auto_daily"}, data=csv_bytes, headers=headers, timeout=120)
        res.raise_for_status()
        return True, "성공"
    except requests.exceptions.ReadTimeout:
        return True, "성공 (지연 처리 중)"
    except Exception as e:
        return False, str(e)

def fetch_history_from_gas(url):
    if not url: return pd.DataFrame(), "URL 누락"
    try:
        res = requests.get(url, timeout=120)
        res.raise_for_status()
        df = pd.DataFrame(res.json())
        if not df.empty:
            if 'date' in df.columns: 
                df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            if 'rank' in df.columns: 
                df['rank'] = pd.to_numeric(df['rank'], errors='coerce').fillna(999)
        return df, ""
    except Exception as e: return pd.DataFrame(), str(e)

# --- 사이드바 메뉴 ---
with st.sidebar:
    st.markdown("### 🚁 Shopping Control")
    selected_menu = option_menu(
        None, 
        ["Dashboard", "일자별 순위 추이", "경쟁사 집중 분석", "틈새 키워드 발굴기", "SEO태그 생성기", "Run & Sync", "AI Report"], 
        icons=['speedometer2', 'graph-up', 'bar-chart-line', 'search', 'tags', 'cloud-upload', 'robot'], 
        default_index=0,
        styles={
            "container": {"background-color": "transparent !important", "padding": "0!important", "border": "none"},
            "icon": {"font-size": "1.2rem"}, 
            "nav-link": {
                "background-color": "transparent",
                "color": "#9ca3af",
                "font-size": "0.95rem", 
                "text-align": "left", 
                "margin": "10px 0", 
                "padding": "12px 18px",
                "border-radius": "30px",
                "box-shadow": "none",
                "--hover-color": "rgba(255,255,255,0.05)"
            },
            "nav-link-selected": {
                "background-color": "#3b82f6", 
                "color": "#ffffff", 
                "font-weight": "700",
                "box-shadow": "0 4px 8px rgba(59, 130, 246, 0.3)"
            },
        }
    )
    
    with st.expander("🔑 환경 변수 설정", expanded=False):
        gemini_key = st.text_input("Gemini API Key", value=get_secret("GEMINI_API_KEY"), type="password")
        naver_cid = st.text_input("Naver ID", value=get_secret("NAVER_CLIENT_ID"))
        naver_csec = st.text_input("Naver Secret", value=get_secret("NAVER_CLIENT_SECRET"), type="password")
        ad_api_key = st.text_input("Ad API Key", value=get_secret("NAVER_AD_API_KEY"))
        ad_sec_key = st.text_input("Ad Secret Key", value=get_secret("NAVER_AD_SECRET_KEY"), type="password")
        ad_cus_id = st.text_input("Ad Customer ID", value=get_secret("NAVER_CUSTOMER_ID"))
        apps_script_url = st.text_input("GAS URL", value=get_secret("APPS_SCRIPT_URL"))
        apps_script_token = st.text_input("GAS Token", value=get_secret("APPS_SCRIPT_TOKEN"))
        my_brand_1 = st.text_area("내 브랜드 1", value=get_secret("MY_BRAND_1", "드론박스, DroneBox"))
        my_brand_2 = st.text_area("내 브랜드 2", value=get_secret("MY_BRAND_2", "빛드론, BitDrone"))
        competitors = st.text_area("경쟁사", value=get_secret("COMPETITORS", "다다사, 효로로, 드론뷰"))

# --- [NEW] 전역 쇼핑몰 이름 통합(정규화) 함수 ---
def get_clean_df(df_target):
    if df_target.empty or 'mall' not in df_target.columns: return df_target
    df_clean = df_target.copy()
    
    t_db = [x.strip() for x in my_brand_1.split(',') if x.strip()]
    t_bit = [x.strip() for x in my_brand_2.split(',') if x.strip()]
    t_comp = [x.strip() for x in competitors.split(',') if x.strip()]
    core_malls = t_db + t_bit + t_comp
    
    def map_mall_name(name):
        if not isinstance(name, str): return name
        for core in core_malls:
            if core in name: return core # "DJI온라인다다사" -> "다다사" (이름 완전 정제)
        return name
        
    df_clean['mall'] = df_clean['mall'].apply(map_mall_name)
    return df_clean

# 앱 접속 시 구글 시트 데이터 최초 1회 자동 로드
if st.session_state.history_df.empty and apps_script_url:
    with st.spinner("최신 데이터를 구글 시트에서 불러오는 중... (앱 최초 접속 시에만 약 5~10초 소요됩니다)"):
        df_auto, err_auto = fetch_history_from_gas(apps_script_url)
        if not df_auto.empty:
            st.session_state.history_df = df_auto

# 모든 메뉴에서 공통으로 사용할 정제된 데이터프레임 사전 생성
hist_df = get_clean_df(st.session_state.history_df)
crawled_df = get_clean_df(st.session_state.crawled_df)
metric_df = crawled_df.copy() if not crawled_df.empty else (hist_df[hist_df['date'] == hist_df['date'].max()] if not hist_df.empty else pd.DataFrame())

# --- 1. Dashboard ---
if selected_menu == "Dashboard":
    st.title("📊 Dashboard")
    
    if st.button("🔄 최신 랭킹 수동 새로고침 (클릭)"):
        with st.spinner("DB_Archive 최신 데이터를 새로고침 하는 중..."):
            df, err = fetch_history_from_gas(apps_script_url)
            if not df.empty:
                st.session_state.history_df = df
                # 동기화 직후 hist_df 강제 갱신
                hist_df = get_clean_df(st.session_state.history_df)
                metric_df = hist_df[hist_df['date'] == hist_df['date'].max()] if not hist_df.empty else pd.DataFrame()
                st.success("데이터 새로고침 완료! 최신 순위가 반영되었습니다.")
            else: st.error(f"동기화 실패: {err}")
    
    if not metric_df.empty:
        # [1, 5] Delta를 위한 이전 날짜 데이터 추출 및 축하 이펙트
        prev_df = pd.DataFrame()
        if not hist_df.empty:
            dates = sorted(hist_df['date'].dropna().unique().tolist(), reverse=True)
            today_date = dates[0] if dates else TODAY_ISO
            if len(dates) > 1:
                prev_date = dates[1]
                prev_df = hist_df[hist_df['date'] == prev_date]
        
        top_df = metric_df[metric_df['rank'] <= 3]
        
        # 축하 이펙트 (1-3위에 자사 브랜드가 있으면)
        if not top_df.empty and ('is_db' in top_df.columns or 'is_bit' in top_df.columns):
            if any(top_df['mall'].str.contains('빛드론|드론박스', na=False)):
                st.balloons()
        
        total_kws = metric_df['keyword'].nunique()
        # 단순히 줄(row) 수를 세지 않고, 1~3위에 노출된 '고유 키워드 개수'를 세도록 수정하여 다중 상품/중복 수집으로 인한 수치 뻥튀기 방지
        total_db = top_df[top_df['mall'].str.contains('드론박스', na=False)]['keyword'].nunique()
        total_bit = top_df[top_df['mall'].str.contains('빛드론', na=False)]['keyword'].nunique()
        
        db_delta = 0
        bit_delta = 0
        if not prev_df.empty:
            prev_top = prev_df[prev_df['rank'] <= 3]
            db_delta = total_db - prev_top[prev_top['mall'].str.contains('드론박스', na=False)]['keyword'].nunique()
            bit_delta = total_bit - prev_top[prev_top['mall'].str.contains('빛드론', na=False)]['keyword'].nunique()
            
        c1, c2, c3 = st.columns(3)
        c1.metric("전체 모니터링 키워드", f"{total_kws:,}", "모니터링 중")
        c2.metric("드론박스 (1-3위 노출)", f"{total_db:,}", f"{abs(db_delta)}건 상승" if db_delta >= 0 else f"{abs(db_delta)}건 하락", delta_color="normal" if db_delta >= 0 else "inverse")
        c3.metric("빛드론 (1-3위 노출)", f"{total_bit:,}", f"{abs(bit_delta)}건 상승" if bit_delta >= 0 else f"{abs(bit_delta)}건 하락", delta_color="normal" if bit_delta >= 0 else "inverse")
        
        st.markdown("---")
        st.subheader("🏆 현재 1-3위 노출 키워드 상세")
            
        if not top_df.empty:
            # 1. 자사 브랜드(내 브랜드 1, 2)만 식별하기 위해 정규식 패턴 생성
            t_db = [x.strip() for x in my_brand_1.split(',') if x.strip()]
            t_bit = [x.strip() for x in my_brand_2.split(',') if x.strip()]
            brand_pattern = "|".join(t_db + t_bit)
            
            # 2. 내 브랜드만 추출
            my_brands = top_df[top_df['mall'].str.contains(brand_pattern, na=False, regex=True)]
            
            if not my_brands.empty:
                # 3. 중복 데이터 중복 방지: 동일 키워드 및 쇼핑몰에서는 가장 순위가 높은(min) 데이터 1점만 고르기
                show_df = my_brands.sort_values('rank').drop_duplicates(['keyword', 'mall'])
                
                if not prev_df.empty and 'mall' in prev_df.columns and 'keyword' in prev_df.columns:
                    prev_subset = prev_df[prev_df['mall'].str.contains(brand_pattern, na=False, regex=True)]
                    prev_subset = prev_subset.sort_values('rank').drop_duplicates(['keyword', 'mall'])
                    prev_subset = prev_subset[['keyword', 'mall', 'rank']].rename(columns={'rank': 'prev_rank'})
                    
                    show_df = pd.merge(show_df, prev_subset, on=['keyword', 'mall'], how='left')
                    show_df['순위변동'] = show_df['prev_rank'] - show_df['rank']
                    
                    def format_delta(delta):
                        if pd.isna(delta): return "신규 진입"
                        d = int(delta)
                        if d > 0: return f"🔺{d} 계단 상승"
                        elif d < 0: return f"🔻{abs(d)} 계단 하락"
                        return "-"
                    
                    show_df['순위변동'] = show_df['순위변동'].apply(format_delta)
                    
                    show_df = show_df.sort_values(['keyword', 'mall'])
                    st.dataframe(show_df[['keyword', 'rank', '순위변동', 'mall', 'title', 'price']], use_container_width=True)
                else:
                    show_df = show_df.sort_values(['keyword', 'mall'])
                    st.dataframe(show_df[['keyword', 'rank', 'mall', 'title', 'price']], use_container_width=True)
                
                st.markdown("<br>", unsafe_allow_html=True)
                # --- 리포트/Export 영역 (표의 직관성 집중 후 하단 배치) ---
                csv = metric_df.to_csv(index=False).encode('utf-8-sig')
                
                html_report = f"""
                <html><head><meta charset="utf-8"><style>
                    body {{ font-family: 'Malgun Gothic', 'Noto Sans KR', sans-serif; padding: 25px; color: #e2e8f0; background-color: #1e1e2d; border-radius: 12px; margin: 0; }}
                    h1 {{ color: #60a5fa; border-bottom: 2px solid #334155; padding-bottom: 10px; font-size: 24px; margin-top: 0; }}
                    .box {{ background: #2a2a3e; padding: 15px 20px; border-radius: 8px; margin: 12px 0; border-left: 5px solid #3b82f6; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }}
                    .title {{ font-size: 14px; color: #94a3b8; margin-bottom: 5px; font-weight: bold; }}
                    .val {{ font-size: 26px; font-weight: 800; color: #f8fafc; }}
                    .delta {{ font-size: 16px; font-weight: 600; color: {'#f87171' if db_delta < 0 else '#34d399'}; }}
                    .delta-bit {{ font-size: 16px; font-weight: 600; color: {'#f87171' if bit_delta < 0 else '#34d399'}; }}
                </style></head><body>
                    <h1>📈 요약 리포트</h1>
                    <p style="color: #94a3b8; font-size: 13px;"><strong>생성 기준일:</strong> {TODAY_KOR}</p>
                    <div class="box">
                        <div class="title">🎯 전체 모니터링 고유 키워드</div>
                        <div class="val">{total_kws} 개 시장 감시 중</div>
                    </div>
                    <div class="box" style="border-left-color: #60a5fa;">
                        <div class="title">🚁 드론박스 1~3위 장악 성과</div>
                        <div class="val">{total_db} 건 <span class="delta">(전일대비 {db_delta:+}건)</span></div>
                    </div>
                    <div class="box" style="border-left-color: #22d3ee;">
                        <div class="title">💡 빛드론 1~3위 장악 성과</div>
                        <div class="val">{total_bit} 건 <span class="delta-bit">(전일대비 {bit_delta:+}건)</span></div>
                    </div>
                    <p style="margin-top:20px; color: #64748b; font-size: 12px; border-top: 1px solid #334155; padding-top: 10px;">
                        상세 순위 지표 및 경쟁사 단가 분석 데이터는 통합 관제 웹 시스템 본문에서 직접 확인하실 수 있습니다.
                    </p>
                </body></html>
                """
                
                # 리포트 본문을 웹 화면(대시보드)에 그대로 시각화하여 삽입 (Iframe)
                import streamlit.components.v1 as components
                components.html(html_report, height=450, scrolling=True)
                
                c_btn1, c_btn2, c_btn3 = st.columns([1, 1, 1])
                c_btn1.download_button(label="📑 위 리포트 원본 다운로드 (.html)", data=html_report.encode('utf-8-sig'), file_name=f"Smart_Report_{TODAY_ISO}.html", mime="text/html", use_container_width=True)
                c_btn2.download_button(label="📥 당일 전체 데이터 (.csv)", data=csv, file_name=f"Rank_Data_{TODAY_ISO}.csv", mime="text/csv", use_container_width=True)
                
            else:
                st.info("현재 자사 브랜드(드론박스/빛드론) 중 3위 이내에 진출한 상품이 없습니다.")
    else: st.info("동기화 또는 수집을 먼저 진행해주세요.")

# --- 2. 일자별 순위 추이 ---
elif selected_menu == "일자별 순위 추이":
    st.title("📈 일자별 키워드 순위 추이")
    
    if not hist_df.empty:
        hist_df['date_obj'] = pd.to_datetime(hist_df['date']).dt.date
        min_date = hist_df['date_obj'].min()
        max_date = hist_df['date_obj'].max()
        default_start = max_date - dt.timedelta(days=14)
        if default_start < min_date: default_start = min_date

        st.markdown("#### 📅 조회 기간 및 키워드 필터")
        col1, col2 = st.columns([1, 2])
        
        with col1:
            selected_dates = st.date_input(
                "조회할 기간을 선택하세요",
                value=(default_start, max_date),
                min_value=min_date,
                max_value=max_date
            )
        with col2:
            all_kws = sorted(hist_df['keyword'].unique().tolist())
            # 난잡함을 방지하기 위해 기본적으로 5개의 키워드만 선택되도록 처리
            default_kws = all_kws[:5] if len(all_kws) > 5 else all_kws
            selected_kws = st.multiselect("차트에 표시할 키워드 선택/제외", options=all_kws, default=default_kws)

        if len(selected_dates) == 2:
            start_date, end_date = selected_dates
            mask = (hist_df['date_obj'] >= start_date) & (hist_df['date_obj'] <= end_date)
            filtered_df = hist_df.loc[mask]
            if selected_kws:
                filtered_df = filtered_df[filtered_df['keyword'].isin(selected_kws)]
            
            if not filtered_df.empty:
                st.markdown("---")
                chart_type = st.radio("📈 차트 보기 방식", ["선그래프 (일자별 최고 순위 추이)", "🔲 자사몰 성과 히트맵 (한눈에 보는 순위판)"], horizontal=True)
                
                # 오류 방지: 완전히 안전하게 데이터가 정렬된 상태에서 시작
                filtered_df = filtered_df.sort_values(['keyword', 'mall', 'title', 'date_obj'])
                
                if "히트맵" in chart_type:
                    # 히트맵: (사용자 요청) 단순히 전체 최고순위 표시가 아닌, '내 쇼핑몰'이 몇 위인지 직관적으로 보여주기 위해 필터링
                    t_db = [x.strip() for x in my_brand_1.split(',') if x.strip()]
                    t_bit = [x.strip() for x in my_brand_2.split(',') if x.strip()]
                    my_brand_filter = "|".join(t_db + t_bit)
                    
                    my_heatmap_df = filtered_df[filtered_df['mall'].str.contains(my_brand_filter, na=False, regex=True)]
                    if not my_heatmap_df.empty:
                        best_rank_df = my_heatmap_df.groupby(['date', 'keyword'], as_index=False).agg({'rank':'min', 'mall':'first'})
                    else:
                        best_rank_df = filtered_df.groupby(['date', 'keyword'], as_index=False).agg({'rank':'min', 'mall':'first'}) # Fallback

                    best_rank_df['rank_display'] = best_rank_df['rank'].apply(lambda x: str(int(x)) if x <= 10 else "10+")
                    best_rank_df['rank_color'] = best_rank_df['rank'].apply(lambda x: x if x <= 10 else 11)

                if "히트맵" in chart_type:
                    # 히트맵 전용 오류 없는 기본 mark_rect 테마 설정
                    base = alt.Chart(best_rank_df).encode(
                        x=alt.X('date:O', title='날짜', axis=alt.Axis(labelAngle=-45, labelColor="#9ca3af", titleColor="#9ca3af", domainColor="#9ca3af", tickColor="#9ca3af")),
                        y=alt.Y('keyword:N', title='키워드', axis=alt.Axis(labelColor="#9ca3af", titleColor="#9ca3af", domainColor="#9ca3af", tickColor="#9ca3af"))
                    )
                    rects = base.mark_rect().encode(
                        # 1등은 형광 시안, 5등 이내는 파랑, 10등 이내는 네이비, 그 밖은 배경색으로 처리하여 가시성 극대화!
                        color=alt.Color('rank_color:Q', scale=alt.Scale(domain=[1, 3, 5, 10, 11], range=['#00e5ff', '#0ea5e9', '#3b82f6', '#1e3a8a', '#1e1e2d']), legend=None),
                        tooltip=[
                            alt.Tooltip('date:N', title='날짜'),
                            alt.Tooltip('keyword:N', title='키워드'),
                            alt.Tooltip('rank:Q', title='최고 순위'),
                            alt.Tooltip('mall:N', title='쇼핑몰')
                        ]
                    )
                    text = base.mark_text(baseline='middle', color='#ffffff', fontWeight='bold').encode(
                        text='rank_display:N'
                    )
                    chart = (rects + text).properties(height=max(300, len(selected_kws)*50), background="transparent").interactive()
                    st.altair_chart(chart, use_container_width=True, theme="streamlit")
                else:
                    try:
                        selection = alt.selection_point(fields=['keyword'], bind='legend')
                    except AttributeError:
                        selection = alt.selection_multi(fields=['keyword'], bind='legend')
                    
                    # 선그래프: [수정] 스파게티 꼬임 방지를 위해 타사(경쟁사) 배제, 순수 우리 브랜드(드론박스/빛드론)만 필터링하여 선 그래프 추적
                    t_db = [x.strip() for x in my_brand_1.split(',') if x.strip()]
                    t_bit = [x.strip() for x in my_brand_2.split(',') if x.strip()]
                    my_brand_filter = "|".join(t_db + t_bit)
                    line_filtered_df = filtered_df[filtered_df['mall'].str.contains(my_brand_filter, na=False, regex=True)]
                    
                    # 선그래프: 동일 키워드 및 상품 내부에서 중복 수집된 데이터(광고+일반)가 혼재하여 X자로 교차하지 않도록 그룹핑
                    line_df = line_filtered_df.groupby(['date', 'keyword', 'title', 'mall'], as_index=False)['rank'].min()
                    line_df['데이터_유형'] = '실제 수집 데이터'
                    
                    st.markdown("---")
                    st.caption("※ 너무 많은 키워드를 동시에 선택하시면 선이 뒤엉켜(스파게티) 볼 수 없습니다. 제대로 된 분석, 특히 AI 추세선 파악을 위해서는 상단에서 **핵심 분석 대상 키워드를 1~2개로 좁혀서** 보시는 것이 좋습니다.")
                    
                    use_ai_pred = st.toggle("🤖 AI 추세 분석 (최근 트렌드 기반 향후 5일 예상 순위 흐름 점선 예측)", value=False)
                    if use_ai_pred:
                        import numpy as np
                        future_rows = []
                        # 선의 뒤섞임 방지를 위해 완벽한 시간적/분류적 정렬!!
                        line_df = line_df.sort_values(['keyword', 'title', 'mall', 'date'])
                        
                        for (keyword, title, mall), group in line_df.groupby(['keyword', 'title', 'mall']):
                            if len(group) >= 2:
                                group_recent = group.tail(7) # 최근 7일치 트렌드 집중 반영
                                x = np.arange(len(group_recent))
                                y = group_recent['rank'].values
                                poly = np.polyfit(x, y, 1) # 1차 선형회귀
                                
                                last_date = pd.to_datetime(group_recent['date'].iloc[-1])
                                last_rank = group_recent['rank'].iloc[-1]
                                
                                # 점선 연결을 위한 마지막 실제 데이터 기준점 추가
                                future_rows.append({
                                    'date': last_date.strftime('%Y-%m-%d'),
                                    'keyword': keyword,
                                    'title': title,
                                    'mall': mall,
                                    'rank': last_rank,
                                    '데이터_유형': 'AI 예측 트렌드'
                                })
                                
                                for i in range(1, 6): # 향후 5일
                                    fut_date = last_date + dt.timedelta(days=i)
                                    pred_rank = poly[0] * (len(group_recent) - 1 + i) + poly[1]
                                    future_rows.append({
                                        'date': fut_date.strftime('%Y-%m-%d'),
                                        'keyword': keyword,
                                        'title': title,
                                        'mall': mall,
                                        'rank': max(1, min(100, round(pred_rank))),
                                        '데이터_유형': 'AI 예측 트렌드'
                                    })
                        if future_rows:
                            pred_df = pd.DataFrame(future_rows)
                            # 다시 한번 시간순 정렬하여 Altair에서 선이 좌우로 튀는 '스파게티 현상' 원천 봉쇄
                            line_df = pd.concat([line_df, pred_df], ignore_index=True)
                            line_df = line_df.sort_values(['keyword', 'title', 'mall', 'date'])
                            
                    # 1위 위인 0, -2, -4 등 불필요한 마이너스 y축 패딩이 생기지 않도록 엄격한 domain 설정
                    max_rank = int(line_df['rank'].max() + 2) if not line_df.empty else 10
                    if max_rank < 5: max_rank = 5
                    
                    base_chart = alt.Chart(line_df).encode(
                        x=alt.X('date:O', title='날짜', axis=alt.Axis(labelAngle=-45, labelColor="#9ca3af", titleColor="#9ca3af", domainColor="#9ca3af", tickColor="#9ca3af")),
                        y=alt.Y('rank:Q', scale=alt.Scale(reverse=True, domain=[max_rank, 1], nice=False), title='상품별 순위 (1위에 가까울수록 위)', axis=alt.Axis(labelColor="#9ca3af", titleColor="#9ca3af", domainColor="#9ca3af", tickColor="#9ca3af")),
                        color=alt.Color('keyword:N', legend=alt.Legend(title="키워드 (선택된 항목)", orient="right", titleColor="#9ca3af", labelColor="#d1d5db")),
                        detail='title:N', # 상품 고유 구분자로 선을 분리
                        opacity=alt.condition(selection, alt.value(1), alt.value(0.1)),
                        tooltip=[
                            alt.Tooltip('date:N', title='날짜'), 
                            alt.Tooltip('데이터_유형:N', title='분석 상태'), 
                            alt.Tooltip('keyword:N', title='키워드'), 
                            alt.Tooltip('rank:Q', title='해당일 순위'), 
                            alt.Tooltip('mall:N', title='쇼핑몰'), 
                            alt.Tooltip('title:N', title='상품명')
                        ]
                    )
                    
                    chart = base_chart.mark_line(point=alt.OverlayMarkDef(filled=False, fill='white', size=80, strokeWidth=2), strokeWidth=3).encode(
                        strokeDash=alt.condition(alt.datum['데이터_유형'] == 'AI 예측 트렌드', alt.value([5, 5]), alt.value([1, 0]))
                    ).properties(
                        height=500,
                        background="transparent"
                    ).add_params(
                        selection
                    ).interactive()
                    
                    st.altair_chart(chart, use_container_width=True, theme="streamlit")
            else:
                st.warning("선택한 기간/키워드에 해당하는 데이터가 없습니다.")
        else:
            st.info("시작일과 종료일을 모두 선택해주세요.")
            
    else: 
        st.warning("과거 데이터가 없습니다. 대시보드에서 '데이터 동기화'를 먼저 진행해주세요.")

# --- 3. 경쟁사 집중 분석 ---
elif selected_menu == "경쟁사 집중 분석":
    st.title("⚔️ 경쟁사 점유율 정밀 분석")
    if hist_df.empty:
        st.warning("과거 데이터가 없습니다. 대시보드에서 '구글 시트 데이터 동기화'를 먼저 진행해주세요.")
    else:
        latest_date = sorted(hist_df['date'].dropna().unique().tolist(), reverse=True)[0]
        st.markdown(f"**기준일:** {latest_date} (최근 수집일 기준 상위 10위권 진입 노출 횟수 집중 분석)")
        
        target_df = hist_df[hist_df['date'] == latest_date]
        t_db = [x.strip() for x in my_brand_1.split(',') if x.strip()]
        t_bit = [x.strip() for x in my_brand_2.split(',') if x.strip()]
        t_comp = [x.strip() for x in competitors.split(',') if x.strip()]
        
        # 브랜드별 10위 내 진입 횟수 (부분 일치)
        comp_count = {}
        for brand in t_db + t_bit + t_comp:
            # 중복 데이터 방지를 위해 고유 키워드 갯수(nunique)로 카운트
            count = target_df[(target_df['mall'].str.contains(brand, na=False)) & (target_df['rank'] <= 10)]['keyword'].nunique()
            comp_count[brand] = count
            
        chart_df = pd.DataFrame(list(comp_count.items()), columns=["추적 대상 브랜드", "10위 이내 노출 수"])
        chart_df = chart_df[chart_df["10위 이내 노출 수"] > 0].sort_values("10위 이내 노출 수", ascending=False)
        
        if not chart_df.empty:
            bar_chart = alt.Chart(chart_df).mark_bar(cornerRadiusTopLeft=8, cornerRadiusTopRight=8, color="#3b82f6").encode(
                x=alt.X('추적 대상 브랜드:N', sort='-y', axis=alt.Axis(labelAngle=0, title='브랜드')),
                y=alt.Y('10위 이내 노출 수:Q', title='노출된 키워드 개수 (10위 이내)'),
                tooltip=['추적 대상 브랜드', '10위 이내 노출 수']
            ).properties(height=500)
            st.altair_chart(bar_chart, use_container_width=True)
            
            # 표 다운로드
            csv = chart_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(label="📥 차트 요약 데이터 다운로드 (CSV)", data=csv, file_name=f"Competitor_Data_{latest_date}.csv", mime="text/csv")
        else:
            st.info("현재 분석 대상 브랜드 중 10위 안에 진입한 상품이 없습니다.")
            
        # --- 3.5 경쟁사 특화 분석 멀티 탭 ---
        st.markdown("---")
        st.subheader("🕵️ 타사 브랜드 X-Ray 정밀 타격")
        st.markdown("가격이 고정된 DJI 시장에서 경쟁사가 어떤 무기를 쥐고 점유율을 뺏어가고 있는지 핵심 지표를 스캔합니다.")
        
        all_comp_kws = sorted(hist_df['keyword'].dropna().unique().tolist())
        target_kw = st.selectbox("전략을 분석할 핵심 타겟 키워드를 먼저 하나 선택하세요", all_comp_kws)
        
        tab1, tab2, tab3 = st.tabs(["🥊 1:1 라이벌 데스매치 (순위 비교)", "🍰 1페이지 매대 점유율 (1~40위)", "🥷 1등 경쟁사 '마법 단어(Title)' 해킹기"])
        
        with tab1:
            st.markdown("###### 우리 브랜드와 지정한 **타겟 타사 단 1곳만 남겨두고**, 두 경쟁자의 피말리는 순위 혈투(추세)를 선그래프로 직관적으로 비교합니다.")
            
            # 사용자에게 1:1 매칭 선택권을 주기 위한 타사 목록 구성
            comp_options = [c for c in t_comp if hist_df[(hist_df['keyword'] == target_kw) & (hist_df['mall'].str.contains(c, na=False))].shape[0] > 0]
            if not comp_options:
                comp_options = t_comp
                
            rival = st.selectbox("비교할 타겟 경쟁사 선택", comp_options)
            
            my_malls_pattern = "|".join(t_db + t_bit)
            deathmatch_mask = (hist_df['keyword'] == target_kw) & (hist_df['mall'].str.contains(f"{my_malls_pattern}|{rival}", na=False, regex=True))
            dm_df = hist_df[deathmatch_mask].copy()
            
            if not dm_df.empty:
                dm_trend = dm_df.groupby(['date', 'mall'], as_index=False)['rank'].min().sort_values('date')
                
                max_rank_dm = int(dm_trend['rank'].max() + 2)
                if max_rank_dm < 5: max_rank_dm = 5
                
                dm_chart = alt.Chart(dm_trend).mark_line(point=True, strokeWidth=4).encode(
                    x=alt.X('date:O', title='날짜', axis=alt.Axis(labelAngle=-45, labelColor="#9ca3af", titleColor="#9ca3af", tickColor="#9ca3af")),
                    y=alt.Y('rank:Q', title='최고 노출 순위 (1위에 가까울수록 위)', scale=alt.Scale(reverse=True, domain=[max_rank_dm, 1], nice=False), axis=alt.Axis(labelColor="#9ca3af", titleColor="#9ca3af", tickColor="#9ca3af")),
                    color=alt.Color('mall:N', title='쇼핑몰', legend=alt.Legend(orient="bottom", labelColor="#d1d5db", titleColor="#9ca3af")),
                    tooltip=[
                        alt.Tooltip('date:N', title='날짜'),
                        alt.Tooltip('mall:N', title='쇼핑몰'),
                        alt.Tooltip('rank:Q', title='최고 랭킹')
                    ]
                ).properties(height=450, background="transparent").interactive()
                st.altair_chart(dm_chart, use_container_width=True, theme="streamlit")
            else:
                st.info(f"해당 키워드에 대한 타사({rival})의 최근 비교 데이터가 부족하여 분석할 수 없습니다.")
                
        with tab2:
            st.markdown(f"###### **{latest_date}** 기준, 네이버 쇼핑 1페이지(1~40위) 검색 결과 내에 각 쇼핑몰이 고유 상품을 몇 개나 심어버렸는지(매대 장악력) 파악합니다.")
            share_df = hist_df[(hist_df['date'] == latest_date) & (hist_df['keyword'] == target_kw) & (hist_df['rank'] <= 40)].copy()
            
            # 자사 및 추적 타사(다다사/효로로/드론뷰 등)만 엄격히 걸러내어 비중 계산
            all_brands_pattern = "|".join(t_db + t_bit + t_comp)
            share_df = share_df[share_df['mall'].str.contains(all_brands_pattern, na=False, regex=True)]
            
            if not share_df.empty:
                share_counts = share_df.groupby('mall').size().reset_index(name='1페이지 노출 상품 개수(파이)')
                share_counts = share_counts.sort_values(by='1페이지 노출 상품 개수(파이)', ascending=False)
                
                pie_chart = alt.Chart(share_counts).mark_arc(innerRadius=60, cornerRadius=4, stroke="#1e1e2d", strokeWidth=2).encode(
                    theta=alt.Theta(field="1페이지 노출 상품 개수(파이)", type="quantitative"),
                    color=alt.Color(field="mall", type="nominal", title="쇼핑몰", legend=alt.Legend(orient="right", labelColor="#d1d5db", titleColor="#9ca3af")),
                    tooltip=['mall:N', '1페이지 노출 상품 개수(파이):Q']
                ).properties(height=400, background="transparent")
                
                col1, col2 = st.columns([1, 1])
                with col1:
                    st.altair_chart(pie_chart, use_container_width=True, theme="streamlit")
                with col2:
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    st.dataframe(share_counts.reset_index(drop=True), use_container_width=True)
            else:
                st.info("해당 키워드의 최근 시간대에 1페이지(40위 이내)에 진입한 브랜드의 누적 상품 데이터가 없습니다.")
                
        with tab3:
            st.markdown(f"###### 검색량 전쟁터에서 최상위 **20위(Top 20)** 안에 안착한 경쟁사들이 상품명(`title`)에 어떤 후킹 단어를 우선 배치하고 있는지, 마법의 단어를 탈탈 털어냅니다.")
            title_df = hist_df[(hist_df['date'] == latest_date) & (hist_df['keyword'] == target_kw) & (hist_df['rank'] <= 20)].copy()
            
            if not title_df.empty:
                import re
                from collections import Counter
                words = []
                for title in title_df['title'].dropna():
                    clean_title = re.sub(r'[^가-힣a-zA-Z0-9\s]', ' ', title)
                    words.extend([w for w in clean_title.split() if w])
                    
                target_word = target_kw.split()[0].lower() # 기준 단어
                stop_words = ["dji", "및", "등", "용", "수", "할", "정품", "드론", "전용", "dji온라인판매점", "dji공식판매점", target_word]
                filtered_words = [w for w in words if len(w) > 1 and w.lower() not in stop_words]
                
                word_counts = Counter(filtered_words).most_common(15)
                word_df = pd.DataFrame(word_counts, columns=["경쟁사들이 선택한 '마법 단어'", '최상위권 등장 횟수(Top20 내)'])
                
                if len(word_counts) > 0:
                    bar_w = alt.Chart(word_df).mark_bar(color="#60a5fa", cornerRadiusTopRight=4, cornerRadiusBottomRight=4).encode(
                        x=alt.X('최상위권 등장 횟수(Top20 내):Q', axis=alt.Axis(labelColor="#9ca3af", titleColor="#9ca3af", tickColor="#9ca3af")),
                        y=alt.Y("경쟁사들이 선택한 '마법 단어':N", sort='-x', axis=alt.Axis(title='추출된 단어', labelColor="#d1d5db", titleColor="#9ca3af", tickColor="#9ca3af")),
                        tooltip=["경쟁사들이 선택한 '마법 단어'", '최상위권 등장 횟수(Top20 내)']
                    ).properties(height=400, background="transparent")
                    st.altair_chart(bar_w, use_container_width=True, theme="streamlit")
                else:
                    st.info("유의미한 단어 추출 결과가 없습니다.")
            else:
                st.info("해당 키워드는 현재 추적 가능한 상위 20위 경쟁사 데이터가 존재하지 않습니다.")

# --- 4. 틈새 키워드 발굴기 ---
elif selected_menu == "틈새 키워드 발굴기":
    st.title("💎 틈새 꿀 키워드 발굴기")
    st.markdown("네이버 광고 API를 활용하여, 기준 키워드와 연관성 높으면서 검색량이 빵빵한 **숨은 잠재 수익 키워드**를 탐색합니다.")
    
    if 'save_base_kw' not in st.session_state: st.session_state.save_base_kw = "미니드론"
    
    col1, col2 = st.columns([3, 1])
    with col1:
        base_kw = st.text_input("💡 탐색 기준 장난감/단어 입력 (예: 드론, 미니드론 등)", value=st.session_state.save_base_kw)
        st.session_state.save_base_kw = base_kw
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        search_btn = st.button("🚀 추천 키워드 탐색 발사", use_container_width=True)
        
    if search_btn:
        if not (ad_api_key and ad_sec_key and ad_cus_id):
            st.error("좌측 사이드바 '환경 변수 설정'을 열고 네이버 광고 API 정보를 정확히 3개 모두 입력해주세요.")
        else:
            with st.spinner(f"'{base_kw}' 중심 연관 키워드 AI 파싱 중... (약 2~4초 소요)"):
                try:
                    ts = str(int(time.time() * 1000))
                    sig = base64.b64encode(hmac.new(ad_sec_key.encode(), f"{ts}.GET./keywordstool".encode(), hashlib.sha256).digest()).decode()
                    headers = {**HTTP_HEADERS, "X-Timestamp": ts, "X-API-KEY": ad_api_key, "X-Customer": ad_cus_id, "X-Signature": sig}
                    
                    res = requests.get(f"https://api.naver.com/keywordstool?hintKeywords={base_kw.replace(' ', '')}&showDetail=1", headers=headers, timeout=10)
                    res.raise_for_status()
                    
                    kw_list = res.json().get('keywordList', [])
                    results = []
                    for i in kw_list[:300]: # 최대 300개 연관 분석
                        # 네이버 API에서 '< 10' 등으로 문자열이 넘어올 때 처리하는 오류 해결식
                        v_pc_val = str(i['monthlyPcQcCnt']).replace("< 10", "10")
                        v_mo_val = str(i['monthlyMobileQcCnt']).replace("< 10", "10")
                        
                        click_pc_val = str(i['monthlyAvePcClkCnt']).replace("< 10", "10")
                        click_mo_val = str(i['monthlyAveMobileClkCnt']).replace("< 10", "10")
                        
                        sum_v = int(v_pc_val) + int(v_mo_val)
                        
                        if sum_v > 50: # 월 50건 이상 짜리만 선별
                            results.append({
                                "연관 추천 타겟 키워드": i['relKeyword'],
                                "월별 통합 잠재 고객 수 (검색량)": sum_v,
                                "기존 평균 클릭률": float(click_pc_val) + float(click_mo_val)
                            })
                            
                    if results:
                        kw_df = pd.DataFrame(results).sort_values("월별 통합 잠재 고객 수 (검색량)", ascending=False).head(100)
                        st.success(f"탐색 완료! 네이버 데이터베이스 기준 잠재 키워드 TOP 100개를 발굴했습니다. (조회 높은 순 정렬)")
                        st.dataframe(kw_df, use_container_width=True)
                        
                        # 표 다운로드
                        csv2 = kw_df.to_csv(index=False).encode('utf-8-sig')
                        st.download_button(label="📥 발굴 키워드 전체 리스트 다운로드 (CSV)", data=csv2, file_name=f"{base_kw}_SecretKeywords.csv", mime="text/csv")
                    else:
                        st.warning("유의미한 연관 키워드를 네이버에서 찾지 못했습니다. 다른 단어를 입력해보세요.")
                except Exception as e:
                    st.error(f"API 권한/통신 오류: {str(e)}\n\nAPI 키를 설정했는지, IP차단을 당했는지 확인해주세요.")

# --- 5. SEO & GEO 태그 생성기 ---
elif selected_menu == "SEO태그 생성기":
    st.title("🚀 제품 SEO & GEO 메타태그 생성기")
    st.markdown("네이버 쇼핑 1위 제품을 벤치마킹하고, 최신 AI 검색 엔진(GEO) 및 SEO 알고리즘에 맞춘 완벽한 상품 메타태그를 원클릭으로 구워냅니다.")
    
    if 'save_target_kw' not in st.session_state: st.session_state.save_target_kw = ""
    if 'save_target_product' not in st.session_state: st.session_state.save_target_product = ""
    if 'save_mall_name' not in st.session_state: st.session_state.save_mall_name = "드론박스"
    if 'save_usps' not in st.session_state: st.session_state.save_usps = ""
    
    col1, col2 = st.columns([1, 1])
    with col1:
        kw_options = sorted(hist_df['keyword'].dropna().unique().tolist()) if not hist_df.empty else ["기본키워드"]
        idx = kw_options.index(st.session_state.save_target_kw) if st.session_state.save_target_kw in kw_options else 0
        target_kw = st.selectbox("🎯 타겟 키워드 (1위 벤치마킹 대상)", options=kw_options, index=idx)
        st.session_state.save_target_kw = target_kw
        
        target_product = st.text_input("📦 내 상품명 (선택)", placeholder="예: DJI 네오 2 플라이모어 콤보", value=st.session_state.save_target_product)
        st.session_state.save_target_product = target_product
        
        mall_name = st.text_input("🏢 우리 쇼핑몰명 (Author)", value=st.session_state.save_mall_name)
        st.session_state.save_mall_name = mall_name
        
    with col2:
        usps = st.text_area("✨ 특장점 필살기 (USPs)", placeholder="가벼운 무게, 전방 LiDAR 센서 등 어필할 특징을 적어주세요.", height=110, value=st.session_state.save_usps)
        st.session_state.save_usps = usps
        
    if st.button("🌟 1등 벤치마킹 SEO & GEO 문구 자동 생성", use_container_width=True, type="primary"):
        if not gemini_key:
            st.error("좌측 사이드바 '환경 변수 설정'에서 Gemini API Key를 입력해주세요.")
        else:
            with st.spinner("최고의 성과를 위한 SEO & GEO 데이터를 생성하는 중... (약 5~10초)"):
                # 1. 1위 데이터 벤치마킹
                top1_title = "조회된 1위 데이터 없음"
                if not hist_df.empty:
                    top1_df = hist_df[(hist_df['keyword'] == target_kw) & (hist_df['rank'] == 1)]
                    if not top1_df.empty:
                        latest_top1 = top1_df.sort_values('date', ascending=False).iloc[0]
                        top1_title = f"{latest_top1['mall']}: {latest_top1['title']}"
                        
                # 2. 제미나이 프롬프트 생성
                prompt = f"""
당신은 네이버 쇼핑 및 구글 SEO/GEO(Generative Engine Optimization) 최고 등급의 마케터입니다.
사용자의 상품이 검색엔진(네이버/구글)과 AI 챗봇(ChatGPT, Gemini 등)에서 최상단에 노출되도록 아래 정해진 스마트스토어 양식에 맞춰 메타태그 데이터를 생성하세요.

[입력 데이터]
- 타겟 검색 키워드: {target_kw}
- 내 상품명: {target_product if target_product else '(입력안됨. 키워드를 바탕으로 최적화된 상품명 생성할 것)'}
- 우리 쇼핑몰명: {mall_name}
- 핵심 특장점: {usps if usps else '없음'}
- 🎯 현재 이 키워드의 실제 1등 상품 제목 (벤치마킹 필수): {top1_title}

[요청 사항]
1. 1등 상품의 제목을 철저히 분석/벤치마킹하여, 이길 수 있는 시선을 끄는 강력한 제목(Title)을 제안하세요. (내 상품명이 주어졌다면 다듬고, 안 주어졌다면 새로 지어주세요)
2. Description은 1~2문장의 매력적이고 자연스러운 세일즈/소개글이어야 합니다. AI 챗봇이 사용자 문답에서 상품을 추천해줄 때 쓰기 가장 완벽한 구어체/설명형 형태(GEO 특화)로 작성하세요.
3. Keywords (메타태그 키워드)는 특수기호 없이 콤마(,)로만 구분된 15개의 핫한 키워드 + GEO용 일상 언어 연관 단어.
4. 속성 정보: 짧은 스펙이나 특성을 캐럿(^) 기호로 이어붙이세요. 시작과 끝에는 캐럿이 절대 없어야 합니다. 꼭 500자 이하로 제한하세요. (ex: 135g초경량^전방LiDAR^빠른배송)
5. 검색 태그: 가장 클릭률을 높일 타겟팅 키워드를 수직선(|)으로 이어붙이세요. 시작/끝에 수직선이 없어야 합니다. 반드시 **최대 10개**만 작성. 공백 지양. (ex: {target_kw.replace(' ', '')}|입문용드론|가성비촬영장비)

결과는 다음 형식을 **정확하고 완벽하게** 지켜서 출력하세요. 다른 잡담이나 마크다운(```) 블록은 절대 금지합니다.

Title: (추천 타이틀 내용)
Author: {mall_name}
Description: (상품 설명문 내용)
Keywords: (콤마로 구분된 15개 키워드)
Attributes: (캐럿으로 구분된 속성들)
SearchTags: (수직선으로 구분된 10개 태그)
"""
                try:
                    genai.configure(api_key=gemini_key)
                    models_to_try = ['gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-pro']
                    response_text = ""
                    for m_name in models_to_try:
                        try:
                            model = genai.GenerativeModel(m_name)
                            response = model.generate_content(prompt)
                            response_text = response.text
                            if response_text: break
                        except Exception:
                            continue
                            
                    if not response_text:
                        st.error("API 응답이 없거나 모델 로드에 실패했습니다. 키를 확인하세요.")
                    else:
                        st.success("✨ 1위 벤치마킹 완벽 반영! 압도적인 SEO & GEO 태그 생성이 완료되었습니다!")
                        
                        # 파싱
                        lines = response_text.strip().split('\n')
                        res_dict = {}
                        for line in lines:
                            if ":" in line:
                                k, v = line.split(":", 1)
                                res_dict[k.strip()] = v.strip()
                                
                        # UI 렌더링
                        st.markdown("<br>", unsafe_allow_html=True)
                        st.markdown("### 📋 상품 개별 SEO 태그 입력용 결과")
                        
                        def render_row(label, value):
                            c1, c2 = st.columns([1, 4])
                            c1.markdown(f"**{label}**")
                            c2.code(value, language='text')
                            st.divider()
                            
                        render_row("타이틀 (Title)", res_dict.get('Title', '생성 실패'))
                        render_row("메타태그 작성자 (Author)", res_dict.get('Author', mall_name))
                        render_row("메타태그 설명 (Description)", res_dict.get('Description', '생성 실패'))
                        render_row("메타태그 키워드 (Keywords)", res_dict.get('Keywords', '생성 실패'))
                        render_row("속성 정보 (기호: ^)", res_dict.get('Attributes', '생성 실패'))
                        render_row("검색 태그 (기호: |)", res_dict.get('SearchTags', '생성 실패'))
                        
                        st.info("💡 위 결과 우측 상단의 [복사] 아이콘을 클릭하여, 쇼핑몰의 [SEO 태그 설정] 및 [쇼핑 정보 등록] 항목에 바로 붙여넣으세요.")
                except Exception as e:
                    st.error(f"생성 중 오류: {e}")

# --- 6. Run & Sync ---
elif selected_menu == "Run & Sync":
    st.title("🎯 실시간 순위 수집")
    
    if 'save_kws_text' not in st.session_state: st.session_state.save_kws_text = get_secret("DEFAULT_KEYWORDS", "")
    kws_text = st.text_area("키워드 입력 (줄바꿈 구분)", height=200, value=st.session_state.save_kws_text)
    st.session_state.save_kws_text = kws_text
    
    if st.button("🚀 분석 시작 및 구글 시트 전송", type="primary"):
        keywords = [k.strip() for k in kws_text.split('\n') if k.strip()]
        if not keywords: st.warning("키워드를 입력하세요.")
        else:
            prog = st.progress(0)
            status = st.empty()
            results, ai_raw = [], ""
            
            t_db = [x.strip() for x in my_brand_1.split(',')]
            t_bit = [x.strip() for x in my_brand_2.split(',')]
            t_comp = [x.strip() for x in competitors.split(',')]

            for i, kw in enumerate(keywords):
                status.text(f"🔍 수집 중... ({i+1}/{len(keywords)}) : {kw}")
                prog.progress((i + 1) / len(keywords))
                
                vol, clk, ctr = get_vol(kw, ad_api_key, ad_sec_key, ad_cus_id)
                items = get_rank(kw, naver_cid, naver_csec)
                
                r_db = r_bit = 999
                top_mall = items[0]['mallName'] if items else "-"
                
                if items:
                    for r, item in enumerate(items, 1):
                        mn = item['mallName'].replace(" ", "").lower()
                        if any(x.lower().replace(" ","") in mn for x in t_db): r_db = min(r_db, r)
                        if any(x.lower().replace(" ","") in mn for x in t_bit): r_bit = min(r_bit, r)
                        
                        if r <= 3 or any(x.lower().replace(" ","") in mn for x in t_db + t_bit + t_comp):
                            standard_mall = item['mallName']
                            
                            results.append({
                                "date": TODAY_ISO, "keyword": kw, "vol": vol, "click": clk, "ctr": ctr,
                                "rank": r, "mall": standard_mall, "title": item['title'].replace("<b>","").replace("</b>",""),
                                "price": item['lprice'], "link": item['link'],
                                "is_db": any(x.lower().replace(" ", "") in mn for x in t_db),
                                "is_bit": any(x.lower().replace(" ", "") in mn for x in t_bit),
                                "is_da": "다다사" in mn,
                                "is_hr": "효로로" in mn,
                                "is_dv": "드론뷰" in mn
                            })
                
                best_rank = min(r_db, r_bit)
                rank_str = f"{best_rank}위" if best_rank < 999 else "순위 밖"
                ai_raw += f"- 키워드: {kw} | 자사 최고 순위: {rank_str} | 월간 검색수: {vol}회 | 클릭률: {ctr}%\n"

            df = pd.DataFrame(results)
            st.session_state.crawled_df = df
            status.text("📤 구글 시트로 전송 중 (최대 120초 소요)...")
            
            success, msg = send_to_gas(df, apps_script_url, apps_script_token)
            if success: st.toast("✅ 전송 완료!"); status.empty()
            else: st.error(f"전송 실패: {msg}")

            if gemini_key:
                status.text("🤖 실무자 맞춤형 AI 리포트 생성 중...")
                genai.configure(api_key=gemini_key)
                
                ai_prompt = f"""[오늘 날짜] {TODAY_KOR}
아래는 네이버 쇼핑에서 당사(드론박스/빛드론) 브랜드의 키워드별 현재 순위와 주요 지표(월간 검색수, 클릭률) 데이터입니다.
이 데이터를 분석하여, 단순 현황 요약이 아닌 **실무자가 지금 당장 실행할 수 있는 '구체적인 액션 플랜' 위주**로 SEO 전략 보고서를 작성해주세요.

[수집 데이터 요약]
{ai_raw}

[보고서 필수 포함 항목 (마크다운 형식으로 깔끔하게)]
1. 📊 오늘 순위 현황 요약 (긍정적 포인트 / 아쉬운 포인트)
2. 🚨 긴급 조치 타겟 키워드 TOP 3 (검색량은 높은데 순위가 낮거나 밀린 핵심 키워드)
3. 🛠️ 실무자 맞춤형 즉시 실행 액션 플랜
   - 상품명/태그 수정 제안 (어떤 단어를 앞으로 빼야 유리한지 등)
   - 네이버 검색/쇼핑 검색광고 입찰가 조절 제안
   - 이벤트/리뷰 유도 등 상세페이지 보완 제안
4. 🛡️ 상위권(1~3위) 안착 및 방어 전략
"""
                # [수정됨] 모델 Fallback 로직 적용
                models_to_try = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash-latest', 'gemini-1.5-flash', 'gemini-pro']
                for m in models_to_try:
                    try:
                        model = genai.GenerativeModel(m)
                        res = model.generate_content(ai_prompt)
                        st.session_state.ai_report_text = f"\n" + res.text
                        break
                    except: continue
                status.empty()

# --- 4. AI Report ---
elif selected_menu == "AI Report":
    st.title("🤖 일자별 AI SEO 전략 및 액션 플랜")
    
    # [예외 처리 1] 이전 버전 세션 상태 충돌 방지 및 마이그레이션
    if 'ai_reports_cache' not in st.session_state:
        st.session_state.ai_reports_cache = {}
        if 'ai_report_text' in st.session_state and st.session_state.ai_report_text:
            st.session_state.ai_reports_cache[TODAY_ISO] = st.session_state.ai_report_text

    # [예외 처리 2] GAS 과거 데이터 로드 확인
    hist_df = st.session_state.history_df
    if hist_df.empty:
        st.warning("과거 데이터가 없습니다. 좌측 메뉴 [Dashboard]에서 '구글 시트 데이터 동기화'를 먼저 진행해주세요.")
    else:
        # 1. 일자 추출 및 필터 UI 생성
        available_dates = sorted(hist_df['date'].dropna().unique().tolist(), reverse=True)
        
        if not available_dates:
            st.error("[Error] 동기화된 데이터에 유효한 날짜(date) 값이 존재하지 않습니다.")
        else:
            col1, col2 = st.columns([1, 3])
            with col1:
                selected_date = st.selectbox("📅 보고서 기준일 선택", available_dates)
            
            st.markdown("---")

            # 2. 메모리에 캐싱된 리포트가 있으면 즉시 출력 (API 절약)
            if selected_date in st.session_state.ai_reports_cache:
                st.success(f"✅ {selected_date} 기준 캐싱된 SEO 리포트")
                st.markdown(st.session_state.ai_reports_cache[selected_date])
                st.download_button(
                    label="📜 리포트 다운로드 (TXT)", 
                    data=st.session_state.ai_reports_cache[selected_date], 
                    file_name=f"Action_Plan_{selected_date}.txt"
                )
            
            # 3. 캐싱된 데이터가 없으면 새로 생성하는 UI 노출
            else:
                st.info(f"선택한 날짜({selected_date})의 AI 리포트가 아직 생성되지 않았습니다.")
                if st.button(f"🚀 {selected_date} 데이터로 AI 리포트 생성", type="primary"):
                    if not gemini_key:
                        st.error("[Error] 좌측 사이드바 '환경 변수 설정'에서 Gemini API Key를 입력해주세요.")
                    else:
                        with st.spinner(f"{selected_date} 데이터를 분석하여 액션 플랜을 생성 중입니다..."):
                            try:
                                # 해당 날짜 데이터 필터링
                                target_df = hist_df[hist_df['date'] == selected_date]
                                ai_raw = ""
                                
                                # 키워드별 지표 재조립
                                for kw in target_df['keyword'].unique():
                                    kw_df = target_df[target_df['keyword'] == kw]
                                    vol = kw_df['vol'].iloc[0] if 'vol' in kw_df.columns else 0
                                    ctr = kw_df['ctr'].iloc[0] if 'ctr' in kw_df.columns else 0
                                    
                                    best_rank = 999
                                    if 'is_db' in kw_df.columns and not kw_df[kw_df['is_db'] == True].empty:
                                        best_rank = min(best_rank, kw_df[kw_df['is_db'] == True]['rank'].min())
                                    if 'is_bit' in kw_df.columns and not kw_df[kw_df['is_bit'] == True].empty:
                                        best_rank = min(best_rank, kw_df[kw_df['is_bit'] == True]['rank'].min())
                                        
                                    rank_str = f"{int(best_rank)}위" if best_rank < 999 else "순위 밖"
                                    ai_raw += f"- 키워드: {kw} | 자사 최고 순위: {rank_str} | 월간 검색수: {vol}회 | 클릭률: {ctr}%\n"

                                # API 호출 설정
                                genai.configure(api_key=gemini_key)
                                ai_prompt = f"""[기준일] {selected_date}
아래는 네이버 쇼핑에서 당사 브랜드의 키워드별 순위와 지표입니다.
단순 현황 요약이 아닌 실무자가 즉시 실행할 '구체적인 액션 플랜' 위주로 SEO 전략 보고서를 마크다운 형식으로 작성해주세요.

[수집 데이터]
{ai_raw}

[필수 포함 항목]
1. 📊 {selected_date} 순위 현황 요약 (긍/부정 포인트)
2. 🚨 긴급 조치 타겟 키워드 TOP 3
3. 🛠️ 실무자 맞춤형 즉시 실행 액션 플랜 (입찰가, 상품명 등)
4. 🛡️ 상위권 방어 전략
"""
                                # [수정됨] 2.5부터 구형 Pro까지 순차적 Fallback (에러 방어 로직)
                                models_to_try = [
                                    'gemini-2.5-flash',
                                    'gemini-2.0-flash',
                                    'gemini-1.5-flash-latest',
                                    'gemini-1.5-flash',
                                    'gemini-pro'
                                ]
                                
                                res_text = ""
                                last_error = ""
                                successful_model = ""
                                
                                for model_name in models_to_try:
                                    try:
                                        model = genai.GenerativeModel(model_name)
                                        res = model.generate_content(ai_prompt)
                                        res_text = res.text
                                        successful_model = model_name
                                        break  # 성공 시 즉시 루프 탈출
                                    except Exception as e:
                                        last_error = str(e)
                                        continue  # 실패 시 다음 하위 모델로 재시도
                                
                                if res_text:
                                    st.session_state.ai_reports_cache[selected_date] = f"\n" + res_text
                                    st.rerun() 
                                else:
                                    st.error(f"[Error] 모든 API 모델 호출 실패. 최신 패키지 업데이트가 필요합니다.\n마지막 에러: {last_error}")
                                
                            except Exception as e:
                                st.error(f"[Error] AI 리포트 생성 중 예외 발생: {str(e)}")
