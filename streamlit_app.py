# -*- coding: utf-8 -*-
import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
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
if 'crawled_df' not in st.session_state: st.session_state.crawled_df = None
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

# --- GAS 웹훅 전송 함수 (최적화) ---
def send_to_gas(df, url, token):
    if not url: return False, "GAS URL이 설정되지 않았습니다."
    try:
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_bytes = csv_buffer.getvalue().encode('utf-8')
        headers = {'Content-Type': 'text/plain; charset=utf-8'}
        
        # timeout을 15초로 설정하여 GAS 스크립트 실행 지연 방어
        res = requests.post(url, params={"token": token, "type": "auto_daily"}, data=csv_bytes, headers=headers, timeout=15)
        res.raise_for_status()
        return True, "전송 성공"
    except Exception as e:
        return False, str(e)

# --- 사이드바 ---
with st.sidebar:
    st.markdown("### ⚙️ 시스템 설정")
    selected_menu = option_menu(
        "Navigation", 
        ["Run & Sync", "Dashboard", "Charts", "AI Report"], 
        icons=['play-circle', 'house', 'bar-chart', 'robot'], 
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

# --- 1. Run & Sync (실행 및 구글시트 전송) ---
if selected_menu == "Run & Sync":
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
            status_text.text("✅ 크롤링 완료. 데이터 정제 중...")
            
            # GAS 발송
            if not df.empty and apps_script_url:
                status_text.text("🚀 구글 시트(GAS)로 데이터 전송 중...")
                success, msg = send_to_gas(df, apps_script_url, apps_script_token)
                if success:
                    st.toast("✅ 구글 시트 전송 완료 -> Slack 알림 대기중", icon="🚀")
                else:
                    st.error(f"GAS 전송 실패: {msg}")
            
            # AI 리포트 생성 백그라운드 처리
            if gemini_key:
                status_text.text("🤖 AI 리포트 생성 중...")
                genai.configure(api_key=gemini_key)
                prompt = f"[오늘 날짜] **{TODAY_KOR}**\n아래 데이터를 분석하여 일일 SEO 전략 보고서를 작성하세요.\n\n{ai_raw_text}"
                try:
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    st.session_state.ai_report_text = model.generate_content(prompt).text
                except Exception as e:
                    st.session_state.ai_report_text = f"AI 분석 실패: {e}"
            
            status_text.empty()
            st.success("🎉 모든 작업이 완료되었습니다. Dashboard에서 결과를 확인하세요.")

# --- 2. Dashboard ---
elif selected_menu == "Dashboard":
    st.title("📊 시스템 대시보드")
    df = st.session_state.crawled_df
    
    if df is not None and not df.empty:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("분석 대상 키워드", f"{df['keyword'].nunique()} 개")
        col2.metric("자사 노출(1~3위)", f"{len(df[(df['rank'] <= 3) & (df['is_db'] | df['is_bit'])])} 건")
        col3.metric("평균 검색량", f"{int(df['vol'].mean())}")
        col4.metric("데이터 동기화", "완료")
        
        st.markdown("---")
        st.subheader("🗂️ 핵심 데이터 테이블")
        st.dataframe(df[['keyword', 'rank', 'mall', 'vol', 'title', 'price']], use_container_width=True)
    else:
        st.info("데이터가 없습니다. 'Run & Sync' 메뉴에서 분석을 먼저 실행하세요.")

# --- 3. Charts ---
elif selected_menu == "Charts":
    st.title("📈 키워드 및 몰별 차트")
    df = st.session_state.crawled_df
    
    if df is not None and not df.empty:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("몰별 노출 점유율")
            st.bar_chart(df['mall'].value_counts())
        with col2:
            st.subheader("키워드별 평균 검색량")
            st.area_chart(df.groupby('keyword')['vol'].mean())
    else:
        st.info("데이터가 없습니다.")

# --- 4. AI Report ---
elif selected_menu == "AI Report":
    st.title("📝 AI 전략 리포트")
    if st.session_state.ai_report_text:
        st.markdown(st.session_state.ai_report_text)
    else:
        st.info("생성된 AI 리포트가 없습니다. 실행 메뉴에서 분석을 완료해주세요.")
