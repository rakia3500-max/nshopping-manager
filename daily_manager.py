import requests
import pandas as pd
import datetime as dt
import time
import base64
import hmac
import hashlib
import os
import io

# --- 시크릿 로드 ---
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

# --- 메인 로직 ---
def run_daily_routine():
    print("🚀 [정석 모드] 원본 데이터 전송 시작")
    
    # 설정 로드
    GEMINI_KEY = get_secret("GEMINI_API_KEY")
    N_CID = get_secret("NAVER_CLIENT_ID")
    N_SEC = get_secret("NAVER_CLIENT_SECRET")
    AD_KEY = get_secret("NAVER_AD_API_KEY")
    AD_SEC = get_secret("NAVER_AD_SECRET_KEY")
    AD_CUS = get_secret("NAVER_CUSTOMER_ID")
    APPS_URL = get_secret("APPS_SCRIPT_URL")
    APPS_TOKEN = get_secret("APPS_SCRIPT_TOKEN")
    
    # 키워드
    raw_kws = get_secret("DEFAULT_KEYWORDS")
    if not raw_kws:
        print("❌ 키워드 없음")
        return
    keywords = [k.strip() for k in raw_kws.replace('\n', ',').split(',') if k.strip()]
    
    # 브랜드 설정 (찾기용)
    MY_BRANDS = ["드론박스", "빛드론", "DRONEBOX", "BitDrone"]
    COMPETITORS = ["다다사", "효로로", "드론뷰", "dadasa", "hyororo", "droneview"]
    
    today = dt.date.today().isoformat()
    results = []
    
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
                raw_mall = item['mallName'] # 원본 이름 유지!
                clean_mall = raw_mall.replace(" ", "").lower()
                
                # 브랜드 판별
                is_mine = any(b.replace(" ", "").lower() in clean_mall for b in MY_BRANDS)
                is_comp = any(c.replace(" ", "").lower() in clean_mall for c in COMPETITORS)
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
        
        log_txt = f"{kw}"
        if found_any: log_txt += f" -> {row_data['mall']} ({row_data['type']})"
        print(f"[{idx+1}/{len(keywords)}] {log_txt}")
        time.sleep(0.3)

    if results and APPS_URL:
        try:
            df = pd.DataFrame(results)
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_data = csv_buffer.getvalue().encode('utf-8')
            
            # [중요] UTF-8 헤더를 추가해서 한글 깨짐 방지
            headers = {'Content-Type': 'text/csv; charset=utf-8'}
            res = requests.post(APPS_URL, params={"token": APPS_TOKEN, "type": "auto_daily"}, data=csv_data, headers=headers)
            print(f"📤 전송 완료: {res.status_code}")
        except Exception as e:
            print(f"❌ 전송 실패: {e}")

if __name__ == "__main__":
    run_daily_routine()
