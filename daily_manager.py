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
    print("🚀 [강력 매칭 모드] 분석 시작")
    
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
        print("❌ [오류] DEFAULT_KEYWORDS 없음")
        return
    keywords = [k.strip() for k in raw_kws.replace('\n', ',').split(',') if k.strip()]
    
    # --- [핵심] 브랜드/경쟁사 정제 (따옴표 제거 + 소문자화 + 공백제거) ---
    def clean_brand_list(secret_val):
        if not secret_val: return []
        # 콤마로 나누고 -> 앞뒤 공백 제거 -> 따옴표 제거 -> 소문자 변환 -> 내부 공백 제거
        return [x.strip().replace('"', '').replace("'", "").lower().replace(" ", "") 
                for x in secret_val.split(',') if x.strip()]

    my_brands = clean_brand_list(get_secret("MY_BRAND_1")) + clean_brand_list(get_secret("MY_BRAND_2"))
    competitors = clean_brand_list(get_secret("COMPETITORS"))
    
    print(f"✅ [설정] 내 브랜드(정제됨): {my_brands}")
    print(f"✅ [설정] 경쟁사(정제됨): {competitors}")
    
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
                # 비교를 위해 몰 이름도 정제 (소문자 + 공백제거)
                raw_mall = item['mallName']
                clean_mall = raw_mall.replace(" ", "").lower()
                
                # 디버깅: 첫 번째 키워드의 1위 업체가 뭔지 로그로 확인
                if idx == 0 and r == 1:
                    print(f"🔎 [디버깅] '{kw}' 1위 몰이름: 실제='{raw_mall}' vs 변환='{clean_mall}'")

                # 1. 내 브랜드 체크
                is_mine = any(b in clean_mall for b in my_brands)
                # 2. 경쟁사 체크
                is_comp = any(c in clean_mall for c in competitors)
                # 3. 상위권(1~3위)
                is_top = r <= 3
                
                if is_mine or is_comp or is_top:
                    brand_type = "TOP"
                    if is_comp: brand_type = "COMP" # 경쟁사가 상위권일 수도 있으니 순서 중요
                    if is_mine: brand_type = "MY"   # 내 브랜드가 최우선
                    
                    row_data.update({
                        "rank": r, "mall": raw_mall, "price": item['lprice'],
                        "title": item['title'].replace("<b>", "").replace("</b>", ""),
                        "link": item['link'],
                        "type": brand_type
                    })
                    found_any = True
                    break

        results.append(row_data)
        
        log_type = f"({row_data['type']})" if found_any else ""
        if idx % 10 == 0: # 로그 너무 많으면 보기 힘드니 10개마다 출력
            print(f"[{idx+1}/{len(keywords)}] {kw} {log_type}")
        time.sleep(0.3)

    if results:
        df = pd.DataFrame(results)
        print(f"📊 최종 수집: {len(df)}개 (내 브랜드 발견: {len(df[df['type']=='MY'])})")
        
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
