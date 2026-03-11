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
    st.markdown("### 🚁 Shopping Control")
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

# --- 2. 일자별 순위 추이 ---
elif selected_menu == "일자별 순위 추이":
    st.title("📈 일자별 키워드 순위 추이")
    
    hist_df = st.session_state.history_df
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
            selected_kws = st.multiselect("차트에 표시할 키워드 선택/제외", options=all_kws, default=all_kws)

        if len(selected_dates) == 2:
            start_date, end_date = selected_dates
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
