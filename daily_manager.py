import requests
import pandas as pd
import datetime as dt
import time
import base64
import hmac
import hashlib
import os
import io

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
    print("🚀 [진단 모드] 일일 자동 분석 시작")
    
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
        print("❌ [오류] DEFAULT_KEYWORDS 시크릿이 로드되지 않았습니다.")
        return
    keywords = [k.strip() for k in raw_kws.replace('\n', ',').split(',') if k.strip()]
    
    # 브랜드 & 경쟁사 로드
    my_brands = []
    if get_secret("MY_BRAND_1"): my_brands += [x.strip() for x in get_secret("MY_BRAND_1").split(',')]
    if get_secret("MY_BRAND_2"): my_brands += [x.strip() for x in get_secret("MY_BRAND_2").split(',')]
    
    competitors = []
    if get_secret("COMPETITORS"): competitors += [x.strip() for x in get_secret("COMPETITORS").split(',')]
    
    print(f"✅ [설정 확인] 키워드: {len(keywords)}개 로드됨")
    print(f"✅ [설정 확인] 내 브랜드: {len(my_brands)}개 로드됨")
    print(f"✅ [설정 확인] 경쟁사: {len(competitors)}개 로드됨")
    
    today = dt.date.today().isoformat()
    results = []
    
    # 분석 루프
    for idx, kw in enumerate(keywords):
        vol, clk, ctr = get_vol(kw, AD_KEY, AD_SEC, AD_CUS)
        items = get_rank(kw, N_CID, N_SEC)
        
        found_any = False
        row_data = {
            "date": today, "keyword": kw, "vol": vol, "click": clk, "ctr": ctr,
            "rank": "-", "mall": "-", "price": 0, "title": "-", "link": "-", "type": "NONE"
        }

        if items:
            for r, item in enumerate(items, 1):
                mn = item['mallName'].replace(" ", "")
                # 내 브랜드 찾기
                is_mine = any(b.replace(" ", "") in mn for b in my_brands if b)
                # 경쟁사 찾기
                is_comp = any(c.replace(" ", "") in mn for c in competitors if c)
                # 상위권(1~3위)
                is_top = r <= 3
                
                if is_mine or is_comp or is_top:
                    row_data.update({
                        "rank": r, "mall": item['mallName'], "price": item['lprice'],
                        "title": item['title'].replace("<b>", "").replace("</b>", ""),
                        "link": item['link'],
                        "type": "MY" if is_mine else ("COMP" if is_comp else "TOP")
                    })
                    found_any = True
                    break # 가장 높은 순위 1개만 기록

        results.append(row_data)
        
        log_msg = f"{kw}: {vol}건"
        if found_any: log_msg += f" / {row_data['rank']}위 ({row_data['type']})"
        else: log_msg += " / 발견 못함"
        print(f"[{idx+1}/{len(keywords)}] {log_msg}")
        
        time.sleep(0.3)

    if results:
        df = pd.DataFrame(results)
        print(f"📊 최종 데이터: {len(df)}행 생성됨.")
        
        if APPS_URL:
            try:
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)
                csv_data = csv_buffer.getvalue().encode('utf-8')
                res = requests.post(APPS_URL, params={"token": APPS_TOKEN, "type": "auto_daily"}, data=csv_data)
                print(f"📤 전송 결과: {res.status_code}")
            except Exception as e:
                print(f"❌ 전송 실패: {e}")

if __name__ == "__main__":
    run_daily_routine()
