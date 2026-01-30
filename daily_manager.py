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
    print("🚀 [확정 모드] 자동 분석 시작 - 브랜드 직접 지정")
    
    # API 키 로드 (이건 시크릿 써야 함)
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
    
    # ==========================================
    # 👇 [여기만 수정하세요] 내 브랜드와 경쟁사 이름
    # ==========================================
    # 따옴표 안에 정확한 한글 이름을 적으세요. (띄어쓰기 있어도 됩니다)
    
    my_brands = ["드론박스", "빛드론", "DRONEBOX", "BitDrone"] 
    competitors = ["다다사", "효로로", "드론뷰"]
    
    print(f"✅ 내 브랜드(고정): {my_brands}")
    print(f"✅ 경쟁사(고정): {competitors}")
    
    today = dt.date.today().isoformat()
    results = []
    
    # 분석 루프
    for idx, kw in enumerate(keywords):
        # 1. 검색량
        vol, clk, ctr = get_vol(kw, AD_KEY, AD_SEC, AD_CUS)
        
        # 2. 순위
        items = get_rank(kw, N_CID, N_SEC)
        
        found_any = False
        row_data = {
            "date": today, "keyword": kw, "vol": vol, "click": clk, "ctr": ctr,
            "rank": "-", "mall": "-", "price": 0, "title": "-", "link": "-", "type": "NONE"
        }

        if items:
            for r, item in enumerate(items, 1):
                # 비교를 위해 공백 제거
                raw_mall = item['mallName']
                clean_mall = raw_mall.replace(" ", "")
                
                # 내 브랜드 찾기 (직접 입력한 리스트 사용)
                is_mine = False
                for b in my_brands:
                    if b.replace(" ", "") in clean_mall:
                        is_mine = True
                        break
                
                # 경쟁사 찾기
                is_comp = False
                for c in competitors:
                    if c.replace(" ", "") in clean_mall:
                        is_comp = True
                        break

                # 상위권 (1~3위)
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
        
        # 로그 출력
        log_type = f"({row_data['type']})" if found_any else ""
        print(f"[{idx+1}/{len(keywords)}] {kw} {log_type}")
        time.sleep(0.3)

    if results:
        df = pd.DataFrame(results)
        print(f"📊 최종 결과: 자사 {len(df[df['type']=='MY'])}개 발견")
        
        if APPS_URL:
            try:
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)
                csv_data = csv_buffer.getvalue().encode('utf-8')
                requests.post(APPS_URL, params={"token": APPS_TOKEN, "type": "auto_daily"}, data=csv_data)
                print("📤 구글 시트 전송 완료")
            except Exception as e:
                print(f"❌ 전송 실패: {e}")

if __name__ == "__main__":
    run_daily_routine()
