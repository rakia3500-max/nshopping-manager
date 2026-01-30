import requests
import pandas as pd
import datetime as dt
import time
import base64
import hmac
import hashlib
import os
import io
import sys

# --- 1. 시크릿 로드 함수 ---
def get_secret(key):
    val = os.environ.get(key)
    if val: return val
    try:
        import streamlit as st
        if key in st.secrets: return st.secrets[key]
    except: pass
    return None

# --- API 함수 ---
def get_vol(kw, ak, sk, cid):
    if not (ak and sk and cid): return 0, 0, 0
    try:
        ts = str(int(time.time() * 1000))
        msg = f"{ts}.GET./keywordstool".encode()
        sig = base64.b64encode(hmac.new(sk.encode(), msg, hashlib.sha256).digest()).decode()
        headers = {"X-Timestamp": ts, "X-API-KEY": ak, "X-Customer": cid, "X-Signature": sig}
        res = requests.get(f"https://api.naver.com/keywordstool?hintKeywords={kw.replace(' ', '')}&showDetail=1", headers=headers, timeout=5)
        for i in res.json().get('keywordList', []):
            if i['relKeyword'].replace(" ", "") == kw.replace(" ", ""):
                v = int(str(i['monthlyPcQcCnt']).replace("<", "")) + int(str(i['monthlyMobileQcCnt']).replace("<", ""))
                c = float(str(i['monthlyAvePcClkCnt']).replace("<", "")) + float(str(i['monthlyAveMobileClkCnt']).replace("<", ""))
                return v, round(c, 1), round(c / v * 100, 2) if v else 0
    except: pass
    return 0, 0, 0

def get_rank(kw, cid, sec):
    try:
        headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": sec}
        res = requests.get("https://openapi.naver.com/v1/search/shop.json", 
                           headers=headers, params={"query": kw, "display": 100, "sort": "sim"}, timeout=5)
        return res.json().get('items', [])
    except: return []

# --- 3. 메인 로직 ---
def run_daily_routine():
    print("🔎 [포렌식 모드] 정밀 분석 시작")
    
    # API 키 로드
    GEMINI_KEY = get_secret("GEMINI_API_KEY")
    N_CID = get_secret("NAVER_CLIENT_ID")
    N_SEC = get_secret("NAVER_CLIENT_SECRET")
    AD_KEY = get_secret("NAVER_AD_API_KEY")
    AD_SEC = get_secret("NAVER_AD_SECRET_KEY")
    AD_CUS = get_secret("NAVER_CUSTOMER_ID")
    APPS_URL = get_secret("APPS_SCRIPT_URL")
    APPS_TOKEN = get_secret("APPS_SCRIPT_TOKEN")
    
    # 키워드 로드
    raw_kws = get_secret("DEFAULT_KEYWORDS")
    if not raw_kws:
        print("❌ 키워드 없음")
        return
    keywords = [k.strip() for k in raw_kws.replace('\n', ',').split(',') if k.strip()]
    
    # [하드코딩] 브랜드 설정
    MY_BRANDS = ["드론박스", "빛드론", "DRONEBOX", "BitDrone"]
    COMPETITORS = ["다다사", "효로로", "드론뷰", "dadasa", "hyororo", "droneview"]
    
    print(f"🎯 찾는 내 브랜드: {MY_BRANDS}")
    print(f"🎯 찾는 경쟁사: {COMPETITORS}")
    
    today = dt.date.today().isoformat()
    results = []
    
    total_found_my = 0
    total_found_comp = 0
    
    # 분석 루프
    print("\n--- [실시간 탐지 로그] ---")
    for idx, kw in enumerate(keywords):
        # 1. API 호출
        vol, clk, ctr = get_vol(kw, AD_KEY, AD_SEC, AD_CUS)
        items = get_rank(kw, N_CID, N_SEC)
        
        found_any = False
        row_data = {
            "date": today, "keyword": kw, "vol": vol, "click": clk, "ctr": ctr,
            "rank": "-", "mall": "-", "price": 0, "title": "-", "link": "-", "type": "NONE"
        }

        if items:
            for r, item in enumerate(items, 1):
                raw_mall = item['mallName']
                clean_mall = raw_mall.replace(" ", "").lower()
                
                # 상세 로그: 무엇과 비교했는지 출력 (상위 5개 키워드만)
                if idx < 5 and r == 1:
                    print(f"👁️ '{kw}' 1위: {raw_mall} (변환됨: {clean_mall})")

                # 판별 로직
                is_mine = False
                for b in MY_BRANDS:
                    if b.replace(" ", "").lower() in clean_mall:
                        is_mine = True
                        print(f"🚨 [내꺼 발견!] {kw} -> {raw_mall} ({r}위)")
                        total_found_my += 1
                        break
                
                is_comp = False
                for c in COMPETITORS:
                    if c.replace(" ", "").lower() in clean_mall:
                        is_comp = True
                        print(f"⚠️ [경쟁사 발견] {kw} -> {raw_mall} ({r}위)")
                        total_found_comp += 1
                        break

                is_top = r <= 3
                
                if is_mine or is_comp or is_top:
                    brand_type = "TOP"
                    if is_comp: brand_type = "COMP"
                    if is_mine: brand_type = "MY"
                    
                    row_data.update({
                        "rank": r, "mall": raw_mall, "price": item['lprice'],
                        "title": item['title'].replace("<b>", "").replace("</b>", ""),
                        "link": item['link'],
                        "type": brand_type
                    })
                    found_any = True
                    break

        results.append(row_data)
        time.sleep(0.3)

    print("\n--------------------------------")
    print(f"📊 [파이썬 집계 결과]")
    print(f"▶ 내 브랜드 발견 수: {total_found_my}개")
    print(f"▶ 경쟁사 발견 수: {total_found_comp}개")
    print("--------------------------------")

    if results:
        df = pd.DataFrame(results)
        
        # CSV 내용 미리보기 (데이터가 진짜 들어있는지 확인)
        my_df = df[df['type'] == 'MY']
        if not my_df.empty:
            print("\n[전송할 데이터 미리보기 - 내 브랜드]")
            print(my_df[['keyword', 'rank', 'mall', 'type']].head())
        else:
            print("\n[경고] 전송할 데이터에 'MY' 타입이 하나도 없습니다!")

        if APPS_URL:
            try:
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)
                csv_data = csv_buffer.getvalue().encode('utf-8')
                
                print(f"📤 구글 시트로 데이터 전송 중... ({len(df)}행)")
                res = requests.post(APPS_URL, params={"token": APPS_TOKEN, "type": "auto_daily"}, data=csv_data)
                print(f"📨 전송 응답 코드: {res.status_code}")
            except Exception as e:
                print(f"❌ 전송 실패: {e}")

if __name__ == "__main__":
    run_daily_routine()
