import requests
import pandas as pd
import datetime as dt
import time
import base64
import hmac
import hashlib
import google.generativeai as genai
import os
import io

# --- 1. 환경변수/시크릿 로드 ---
def get_secret(key):
    val = os.environ.get(key)
    if val: return val
    try:
        import streamlit as st
        if key in st.secrets: return st.secrets[key]
    except: pass
    return None

# --- 2. API 함수 ---
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
    print("🚀 일일 자동 분석 시작 (경쟁사 포함)...")
    
    # 시크릿 로드
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
        print("❌ 키워드가 없습니다.")
        return
    keywords = [k.strip() for k in raw_kws.replace('\n', ',').split(',') if k.strip()]
    
    # 브랜드 & 경쟁사 로드 (핵심 수정 부분)
    my_brands = []
    if get_secret("MY_BRAND_1"): my_brands += [x.strip() for x in get_secret("MY_BRAND_1").split(',')]
    if get_secret("MY_BRAND_2"): my_brands += [x.strip() for x in get_secret("MY_BRAND_2").split(',')]
    
    competitors = []
    if get_secret("COMPETITORS"): competitors += [x.strip() for x in get_secret("COMPETITORS").split(',')]
    
    today = dt.date.today().isoformat()
    results = []

    print(f"📊 분석 대상: 키워드 {len(keywords)}개 | 경쟁사 {len(competitors)}개")

    for idx, kw in enumerate(keywords):
        vol, clk, ctr = get_vol(kw, AD_KEY, AD_SEC, AD_CUS)
        items = get_rank(kw, N_CID, N_SEC)
        
        found_any = False
        
        if items:
            for r, item in enumerate(items, 1):
                mn = item['mallName'].replace(" ", "")
                title = item['title'].replace("<b>", "").replace("</b>", "")
                
                # 1. 내 브랜드 체크
                is_mine = any(b.replace(" ", "") in mn for b in my_brands if b)
                # 2. 경쟁사 체크 (다다사 등)
                is_comp = any(c.replace(" ", "") in mn for c in competitors if c)
                # 3. 상위권(1~3위) 체크
                is_top = r <= 3
                
                # 셋 중 하나라도 해당되면 저장
                if is_mine or is_comp or is_top:
                    results.append({
                        "date": today, "keyword": kw, "vol": vol, "click": clk, "ctr": ctr,
                        "rank": r, "mall": item['mallName'], "price": item['lprice'],
                        "title": title, "link": item['link'],
                        # 구글 시트에서 브랜드 판별을 위해 플래그 추가
                        "type": "MY" if is_mine else ("COMP" if is_comp else "TOP")
                    })
                    found_any = True
        
        # 아무것도 못 찾았어도 검색량 데이터는 중요하므로 '순위 밖'으로라도 저장 (선택)
        if not found_any:
             results.append({
                "date": today, "keyword": kw, "vol": vol, "click": clk, "ctr": ctr,
                "rank": "-", "mall": "-", "price": 0, "title": "-", "link": "-", "type": "NONE"
            })

        print(f"[{idx+1}/{len(keywords)}] {kw}: 처리 완료")
        time.sleep(0.3)

    if results:
        df = pd.DataFrame(results)
        print(f"✅ 데이터 생성 완료: {len(df)}행")
        
        if APPS_URL:
            try:
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)
                csv_data = csv_buffer.getvalue().encode('utf-8')
                requests.post(APPS_URL, params={"token": APPS_TOKEN, "type": "auto_daily"}, data=csv_data)
                print("📤 구글 시트 전송 성공")
            except Exception as e:
                print(f"전송 실패: {e}")

if __name__ == "__main__":
    run_daily_routine()
