# -*- coding: utf-8 -*-
"""
[최종 릴리즈] BitDrone_Manager_Web_UI.py
- Fix: Gemini 2.5 Flash 모델 우선 적용
- Fix: GAS 누적 데이터(DB_Archive) Fetch 예외 처리 및 디버깅 강화
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
import logging

sys.stdout.reconfigure(encoding='utf-8')
st.set_page_config(page_title="쇼핑 통합 관제 (Web)", layout="wide")

# --- 전역 변수 ---
NOW_KST = dt.datetime.utcnow() + dt.timedelta(hours=9)
TODAY_ISO = NOW_KST.strftime("%Y-%m-%d")
TODAY_KOR = NOW_KST.strftime("%Y년 %m월 %d일")

def get_secret(key, default=""):
    return st.secrets.get(key, default)

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
}

# --- 세션 상태 초기화 ---
if 'crawled_df' not in st.session_state: st.session_state.crawled_df = pd.DataFrame()
if 'history_df' not in st.session_state: st.session_state.history_df = pd.DataFrame()
if 'ai_report_text' not in st.session_state: st.session_state.ai_report_text = ""

# --- API 엔진 ---
def get_vol(kw, ak, sk, cid):
    if not (ak and sk and cid): return 0, 0, 0
    try:
        ts = str(int(time.time() * 1000))
        sig = base64.b64encode(hmac.new(sk.encode(), f"{ts}.GET./keywordstool".encode(), hashlib.sha256).digest()).decode()
        headers = {**HTTP_HEADERS, "X-Timestamp": ts, "X-API-KEY": ak, "X-Customer": cid, "X-Signature": sig}
        time.sleep(random.uniform(1.5, 3.5)) 
        res = requests.get(f"https://api.naver.com/keywordstool?hintKeywords={kw.replace(' ', '')}&showDetail=1", headers=headers, timeout=10)
        res.raise_for_status()
        for i in res.json().get('keywordList', []):
            if i['relKeyword'].replace(" ", "") == kw.replace(" ", ""):
                v = int(str(i['monthlyPcQcCnt']).replace("<", "")) + int(str(i['monthlyMobileQcCnt']).replace("<", ""))
                c = float(str(i['monthlyAvePcClkCnt']).replace("<", "")) + float(str(i['monthlyAveMobileClkCnt']).replace("<", ""))
                return v, round(c, 1), round(c / v * 100, 2) if v else 0
    except Exception as e: logging.error(f"Keyword API Error: {e}")
    return 0, 0, 0

def get_rank(kw, cid, sec):
    if not (cid and sec): return []
    try:
        headers = {**HTTP_HEADERS, "X-Naver-Client-Id": cid, "X-Naver-Client-Secret": sec}
        time.sleep(random.uniform(1.0, 2.0))
        res = requests.get("https://openapi.naver.com/v1/search/shop.json", headers=headers, params={"query": kw, "display": 100, "sort": "sim"}, timeout=10)
        res.raise_for_status()
        return res.json().get('items', [])
    except Exception as e: logging.error(f"Search API Error: {e}")
    return []

# --- GAS 웹훅 (POST & GET) ---
def send_to_gas(df, url, token):
    if not url: return False, "GAS URL 누락"
    try:
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_bytes = csv_buffer.getvalue().encode('utf-8')
        headers = {'Content-Type': 'text/plain; charset=utf-8'}
        res = requests.post(url, params={"token": token, "type": "auto_daily"}, data=csv_bytes, headers=headers, timeout=30)
        res.raise_for_status()
        return True, "성공"
    except Exception as e:
        return False, str(e)

def fetch_history_from_gas(url):
    if not url: return pd.DataFrame(), "GAS URL이 설정되지 않았습니다."
    try:
        res = requests.get(url, timeout=20)
        res.raise_for_status()
        try:
            data = res.json()
        except ValueError:
            return pd.DataFrame(), f"JSON 파싱 실패. 배포 권한이 '모든 사용자'인지 확인하세요.\n(응답: {res.text[:100]})"
        
        if not data or len(data) == 0:
            return pd.DataFrame(), "DB_Archive 시트에 데이터가 없습니다. 먼저 'Run & Sync'를 실행하여 데이터를 누적하세요."

        df = pd.DataFrame(data)
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        if 'rank' in df.columns:
            df['rank'] = pd.to_numeric(df['rank'], errors='coerce').fillna(999)
        return df, ""
    except Exception as e:
        return pd.DataFrame(), f"요청 실패: {str(e)}"

# --- 사이드바 ---
with st.sidebar:
    st.markdown("### ⚙️ 시스템 설정")
    selected_menu = option_menu(
        "Navigation", 
        ["Dashboard", "Run & Sync", "AI Report"], 
        icons=['house', 'play-circle', 'robot'], 
        menu_icon="cast", default_index=0
    )
    
    with st.expander("🔑 환경 변수 설정", expanded=False):
        gemini_key = st.text_input("Gemini API Key", value=get_secret("GEMINI_API_KEY"), type="password")
        naver_cid = st.text_input("Naver Client ID", value=get_secret("NAVER_CLIENT_ID"))
        naver_csec = st.text_input("Naver Client Secret", value=get_secret("NAVER_CLIENT_SECRET"), type="password")
        ad_api_key = st.text_input("Ad API Key", value=get_secret("NAVER_AD_API_KEY"))
        ad_sec_key = st.text_input("Ad Secret Key", value=get_secret("NAVER_AD_SECRET_KEY"), type="password")
        ad_cus_id = st.text_input("Ad Customer ID", value=get_secret("NAVER_CUSTOMER_ID"))
        apps_script_url = st.text_input("Apps Script URL", value=get_secret("APPS_SCRIPT_URL"))
        apps_script_token = st.text_input("Apps Script Token", value=get_secret("APPS_SCRIPT_TOKEN"))
        
        my_brand_1 = st.text_area("내 브랜드 1", value=get_secret("MY_BRAND_1", "드론박스, DroneBox, DRONEBOX, DJI 정품판매점 드론박스"))
        my_brand_2 = st.text_area("내 브랜드 2", value=get_secret("MY_BRAND_2", "빛드론, Bit-Drone, Bit Drone, BITDRONE, BIT-DRONE"))
        competitors = st.text_area("경쟁사", value=get_secret("COMPETITORS", "다다사, dadasa, 효로로, Hyororo, 드론뷰, DroneView"))

# --- 1. Dashboard (메인 화면) ---
if selected_menu == "Dashboard":
    st.title("📊 통합 관제 대시보드")
    
    if st.button("🔄 구글 시트 과거 데이터 동기화"):
        with st.spinner("누적 데이터를 가져오는 중입니다..."):
            df, err_msg = fetch_history_from_gas(apps_script_url)
            if not df.empty:
                st.session_state.history_df = df
                st.success("데이터 동기화 완료!")
            else:
                st.error(f"동기화 실패: {err_msg}")

    hist_df = st.session_state.history_df
    curr_df = st.session_state.crawled_df

    metric_df = curr_df if not curr_df.empty else (hist_df[hist_df['date'] == hist_df['date'].max()] if not hist_df.empty else pd.DataFrame())
    
    if not metric_df.empty:
        col1, col2, col3, col4 = st.columns(4)
        db_top = len(metric_df[(metric_df['rank'] <= 3) & metric_df['mall'].str.contains('드론박스', na=False)])
        bit_top = len(metric_df[(metric_df['rank'] <= 3) & metric_df['mall'].str.contains('빛드론', na=False)])
        
        col1.metric("분석 대상 키워드", f"{metric_df['keyword'].nunique()} 개")
        col2.metric("드론박스 상위(1~3위)", f"{db_top} 건")
        col3.metric("빛드론 상위(1~3위)", f"{bit_top} 건")
        vol_col = 'vol' if 'vol' in metric_df.columns else 'search_vol'
        avg_vol = int(pd.to_numeric(metric_df[vol_col], errors='coerce').mean()) if vol_col in metric_df.columns else 0
        col4.metric("평균 검색량", f"{avg_vol}")
    
    st.markdown("---")

    st.subheader("📈 일자별 키워드 순위 추이")
    if not hist_df.empty:
        target_malls = ["드론박스", "빛드론"]
        chart_data = hist_df[hist_df['mall'].isin(target_malls)]
        
        if not chart_data.empty:
            line_chart = alt.Chart(chart_data).mark_line(point=True).encode(
                x=alt.X('date:T', title='일자'),
                y=alt.Y('rank:Q', scale=alt.Scale(reverse=True, domain=[10, 1]), title='순위 (1위에 가까울수록 위)'),
                color=alt.Color('keyword:N', title='키워드'),
                strokeDash=alt.StrokeDash('mall:N', title='쇼핑몰'),
                tooltip=['date', 'keyword', 'mall', 'rank']
            ).properties(height=400).interactive()
            st.altair_chart(line_chart, use_container_width=True)
        else:
            st.info("차트를 구성할 '드론박스' 또는 '빛드론' 누적 데이터가 아직 없습니다.")
    else:
        st.warning("상단의 '동기화 버튼'을 눌러 구글 시트 데이터를 불러오세요. (데이터가 없다면 Run & Sync 먼저 실행)")

    st.markdown("---")
    
    col_t, col_a = st.columns([1.5, 1])
    with col_t:
        st.subheader("🗂️ 최신 순위 데이터")
        if not metric_df.empty:
            st.dataframe(metric_df[['keyword', 'rank', 'mall', 'title', 'price']], use_container_width=True)
        else:
            st.write("데이터가 없습니다.")
            
    with col_a:
        st.subheader("🤖 AI 전략 리포트 요약")
        if st.session_state.ai_report_text:
            st.info(st.session_state.ai_report_text[:300] + "...\n\n(상세 내용은 AI Report 메뉴 확인)")
        else:
            st.warning("금일 생성된 AI 리포트가 없습니다.")


# --- 2. Run & Sync (실행) ---
elif selected_menu == "Run & Sync":
    st.title("🎯 데이터 수집 및 GAS 연동")
    kws_text = st.text_area("키워드 입력 (콤마/줄바꿈 구분)", height=200, value=get_secret("DEFAULT_KEYWORDS", ""))
    
    if st.button("🚀 실행 및 구글 시트 전송", type="primary"):
        keywords = [k.strip() for k in kws_text.replace(',', '\n').split('\n') if k.strip()]
        if not keywords: 
            st.warning("키워드를 입력해주세요.")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()
            results, ai_raw_text = [], ""
            
            t_db = [x.strip() for x in my_brand_1.split(',')]
            t_bit = [x.strip() for x in my_brand_2.split(',')]
            t_comp = [x.strip() for x in competitors.split(',')]

            for idx, kw in enumerate(keywords):
                status_text.text(f"🔍 크롤링 진행 중... ({idx+1}/{len(keywords)}) : {kw}")
                progress_bar.progress((idx + 1) / len(keywords))
                
                vol, clk, ctr = get_vol(kw, ad_api_key, ad_sec_key, ad_cus_id)
                items = get_rank(kw, naver_cid, naver_csec)
                
                r_db = r_bit = 999
                top_mall = items[0]['mallName'] if items else "-"
                
                if items:
                    for r, item in enumerate(items, 1):
                        mn = item['mallName'].replace(" ", "")
                        if any(x.replace(" ", "") in mn for x in t_db): r_db = min(r_db, r)
                        if any(x.replace(" ", "") in mn for x in t_bit): r_bit = min(r_bit, r)
                        
                        is_mine = any(x.replace(" ", "") in mn for x in t_db + t_bit)
                        is_comp = any(x.replace(" ", "") in mn for x in t_comp) or "다다사" in mn
                        
                        if r <= 3 or is_mine or is_comp:
                            standard_mall = item['mallName']
                            clean_mall = standard_mall.replace(" ", "").lower()
                            
                            if any(x in clean_mall for x in ["드론박스", "dronebox"]): standard_mall = "드론박스"
                            elif any(x in clean_mall for x in ["빛드론", "bitdrone"]): standard_mall = "빛드론"
                            elif "다다사" in clean_mall: standard_mall = "다다사"
                            elif "효로로" in clean_mall: standard_mall = "효로로"
                            elif "드론뷰" in clean_mall: standard_mall = "드론뷰"
                            
                            results.append({
                                "date": TODAY_ISO, "keyword": kw, "vol": vol, "click": clk, "ctr": ctr,
                                "rank": r, "mall": standard_mall, "title": item['title'].replace("<b>", "").replace("</b>", ""),
                                "price": item['lprice'], "link": item['link'],
                                "is_db": any(x.replace(" ", "") in mn for x in t_db),
                                "is_bit": any(x.replace(" ", "") in mn for x in t_bit),
                                "is_da": "다다사" in mn, "is_hr": "효로로" in mn, "is_dv": "드론뷰" in mn
                            })
                best = min(r_db, r_bit)
                ai_raw_text += f"{kw},{best if best < 999 else '순위밖'},{top_mall}\n"

            df = pd.DataFrame(results)
            st.session_state.crawled_df = df
            status_text.text("✅ 크롤링 완료. GAS 데이터 전송 중...")
            
            if not df.empty and apps_script_url:
                success, msg = send_to_gas(df, apps_script_url, apps_script_token)
                if success:
                    st.toast("✅ 구글 시트 전송 완료", icon="🚀")
                else:
                    st.error(f"GAS 전송 실패: {msg}")
            
            # --- AI 리포트 (요청하신 gemini-2.5-flash 최우선 적용) ---
            if gemini_key:
                status_text.text("🤖 AI 리포트 생성 중...")
                genai.configure(api_key=gemini_key)
                prompt = f"[오늘 날짜] **{TODAY_KOR}**\n아래 데이터를 분석하여 일일 SEO 전략 보고서를 작성하세요.\n\n{ai_raw_text}"
                
                ai_result = ""
                error_logs = []
                
                models = ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-1.5-pro']
                for m in models:
                    try:
                        model = genai.GenerativeModel(m)
                        res = model.generate_content(prompt)
                        if res.text: 
                            ai_result = res.text
                            break
                    except Exception as e:
                        error_logs.append(f"[{m}] {str(e)}")
                        continue
                
                if ai_result:
                    st.session_state.ai_report_text = ai_result
                else:
                    st.session_state.ai_report_text = "⚠️ **AI 분석 실패**\n\n" + "\n".join(error_logs)
            
            status_text.empty()
            st.success("🎉 모든 작업이 완료되었습니다. Dashboard에서 결과를 확인하세요.")

# --- 3. AI Report ---
elif selected_menu == "AI Report":
    st.title("📝 AI 전략 리포트")
    if st.session_state.ai_report_text:
        st.markdown(st.session_state.ai_report_text)
        st.download_button("📜 리포트 다운로드 (TXT)", st.session_state.ai_report_text, file_name=f"Report_{TODAY_ISO}.txt")
    else:
        st.info("생성된 AI 리포트가 없습니다. 실행 메뉴에서 분석을 완료해주세요.")
