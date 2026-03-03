# -*- coding: utf-8 -*-
"""
[최종 통합 완성본 v5] BitDrone_Manager_Web.py
- Update: 차트 렌더링 랙(버벅거림) 해결을 위한 '날짜 기간 필터(Date Picker)' 추가
- Update: 기본 조회 기간을 '최근 14일'로 제한하여 사이트 이동 속도 대폭 향상
- Fix: 슬랙 알림 정상화 및 GAS 타임아웃 120초 유지
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
st.set_page_config(page_title="비트드론 쇼핑 통합 관제", layout="wide")

# --- KST 시간 설정 ---
NOW_KST = dt.datetime.utcnow() + dt.timedelta(hours=9)
TODAY_ISO = NOW_KST.strftime("%Y-%m-%d")
TODAY_KOR = NOW_KST.strftime("%Y년 %m월 %d일")

def get_secret(key, default=""):
    return st.secrets.get(key, default)

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
    st.markdown("### 🚁 BitDrone Control")
    selected_menu = option_menu("메뉴", ["Dashboard", "일자별 순위 추이", "Run & Sync", "AI Report"], 
                               icons=['speedometer2', 'graph-up', 'cloud-upload', 'robot'], default_index=0)
    
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

# --- 1. Dashboard ---
if selected_menu == "Dashboard":
    st.title("📊 통합 관제 대시보드 요약")
    
    if st.button("🔄 구글 시트 데이터 동기화"):
        with st.spinner("DB_Archive 데이터를 불러오는 중... (최초 1회 약 10초 소요)"):
            df, err = fetch_history_from_gas(apps_script_url)
            if not df.empty:
                st.session_state.history_df = df
                st.success("동기화 완료")
            else: st.error(f"동기화 실패: {err}")

    hist_df = st.session_state.history_df
    metric_df = st.session_state.crawled_df if not st.session_state.crawled_df.empty else (hist_df[hist_df['date'] == hist_df['date'].max()] if not hist_df.empty else pd.DataFrame())
    
    if not metric_df.empty:
        top_df = metric_df[metric_df['rank'] <= 3]
        
        c1, c2, c3 = st.columns(3)
        c1.metric("전체 키워드", f"{metric_df['keyword'].nunique()} 개")
        c2.metric("드론박스 (1-3위)", f"{len(top_df[top_df['mall'].str.contains('드론박스', na=False)])} 건")
        c3.metric("빛드론 (1-3위)", f"{len(top_df[top_df['mall'].str.contains('빛드론', na=False)])} 건")
        
        st.markdown("---")
        st.subheader("🏆 현재 1-3위 노출 키워드 상세")
        if not top_df.empty:
            st.dataframe(top_df[['keyword', 'rank', 'mall', 'title', 'price']], use_container_width=True)
        else:
            st.info("현재 3위 이내에 진출한 상품이 없습니다.")
    else: st.info("동기화 또는 수집을 먼저 진행해주세요.")

# --- 2. 일자별 순위 추이 (속도 최적화 적용) ---
elif selected_menu == "일자별 순위 추이":
    st.title("📈 일자별 키워드 순위 추이")
    
    hist_df = st.session_state.history_df
    if not hist_df.empty:
        # [최적화] 날짜 형식 변환 및 기본 기간 설정 (최근 14일)
        hist_df['date_obj'] = pd.to_datetime(hist_df['date']).dt.date
        min_date = hist_df['date_obj'].min()
        max_date = hist_df['date_obj'].max()
        default_start = max_date - dt.timedelta(days=14)
        if default_start < min_date: default_start = min_date

        st.markdown("#### 📅 조회 기간 및 키워드 필터")
        col1, col2 = st.columns([1, 2])
        
        with col1:
            # 날짜 선택 달력 필터 (기본값: 최근 14일)
            selected_dates = st.date_input(
                "조회할 기간을 선택하세요",
                value=(default_start, max_date),
                min_value=min_date,
                max_value=max_date
            )
        with col2:
            # 키워드 멀티 선택 필터
            all_kws = sorted(hist_df['keyword'].unique().tolist())
            selected_kws = st.multiselect("차트에 표시할 키워드 선택/제외", options=all_kws, default=all_kws)

        # 사용자가 날짜를 정상적으로(시작일~종료일) 선택했을 때만 렌더링
        if len(selected_dates) == 2:
            start_date, end_date = selected_dates
            
            # 선택한 날짜와 키워드로 데이터프레임 필터링 (렌더링 데이터 최소화)
            mask = (hist_df['date_obj'] >= start_date) & (hist_df['date_obj'] <= end_date)
            filtered_df = hist_df.loc[mask]
            if selected_kws:
                filtered_df = filtered_df[filtered_df['keyword'].isin(selected_kws)]
            
            if not filtered_df.empty:
                chart = alt.Chart(filtered_df).mark_line(point=True, strokeWidth=2).encode(
                    x=alt.X('date:T', title='날짜'),
                    y=alt.Y('rank:Q', scale=alt.Scale(reverse=True, domain=[10, 1]), title='순위 (1위에 가까울수록 위)'),
                    color='keyword:N',
                    tooltip=['date', 'keyword', 'rank', 'mall']
                ).properties(height=600).interactive()
                st.altair_chart(chart, use_container_width=True)
            else:
                st.warning("선택한 기간/키워드에 해당하는 데이터가 없습니다.")
        else:
            st.info("시작일과 종료일을 모두 선택해주세요.")
            
    else: 
        st.warning("과거 데이터가 없습니다. 대시보드에서 '데이터 동기화'를 먼저 진행해주세요.")

# --- 3. Run & Sync ---
elif selected_menu == "Run & Sync":
    st.title("🎯 실시간 순위 수집")
    kws_text = st.text_area("키워드 입력 (줄바꿈 구분)", height=200, value=get_secret("DEFAULT_KEYWORDS", ""))
    
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
                ai_raw += f"{kw}: {min(r_db, r_bit)}위\n"

            df = pd.DataFrame(results)
            st.session_state.crawled_df = df
            status.text("📤 구글 시트로 전송 중 (최대 120초 소요)...")
            
            success, msg = send_to_gas(df, apps_script_url, apps_script_token)
            if success: st.toast("✅ 전송 완료!"); status.empty()
            else: st.error(f"전송 실패: {msg}")

            # AI 리포트 생성
            if gemini_key:
                genai.configure(api_key=gemini_key)
                models = ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-pro']
                for m in models:
                    try:
                        model = genai.GenerativeModel(m)
                        res = model.generate_content(f"{TODAY_KOR} 쇼핑 순위 분석 보고서 작성:\n{ai_raw}")
                        st.session_state.ai_report_text = res.text
                        break
                    except: continue

# --- 4. AI Report ---
elif selected_menu == "AI Report":
    st.title("🤖 AI SEO 전략 리포트")
    if st.session_state.ai_report_text:
        st.markdown(st.session_state.ai_report_text)
    else: st.info("Run & Sync 메뉴에서 분석을 실행하면 리포트가 생성됩니다.")
