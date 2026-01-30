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
    print("🚀 [최종] 자동 분석 시작 (브랜드 고정 방식)")
    
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
        print("❌ 키워드가 없습니다.")
        return
    keywords = [k.strip() for k in raw_kws.replace('\n', ',').split(',') if k.strip()]
    
    # ==================================================
    # 👇 [여기에 사장님의 브랜드를 직접 적습니다]
    # (공백이 있든 없든 다 잡아내도록 코드가 알아서 처리합니다)
    # ==================================================
    MY_BRANDS = ["드론박스", "빛드론", "DRONEBOX", "BitDrone"]
    COMPETITORS = ["다다사", "효로로", "드론뷰", "dadasa", "hyororo", "droneview"]
    
    print(f"✅ 추적 브랜드: {MY_BRANDS}")
    
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
                # 1. 몰 이름을 "소문자" + "공백제거" 상태로 변환
                # 예: "DJI 정품판매점 드론박스" -> "dji정품판매점드론박스"
                raw_mall = item['mallName']
                clean_mall = raw_mall.replace(" ", "").lower()
                
                # 2. 내 브랜드 찾기
                is_mine = False
                for brand in MY_BRANDS:
                    # 내 브랜드도 "소문자" + "공백제거" 해서 비교
                    # "드론박스" -> "dji정품판매점드론박스" 안에 있니? (YES!)
                    if brand.replace(" ", "").lower() in clean_mall:
                        is_mine = True
                        break
                
                # 3. 경쟁사 찾기
                is_comp = False
                for comp in COMPETITORS:
                    if comp.replace(" ", "").lower() in clean_mall:
                        is_comp = True
                        break
                
                # 4. 상위권 (1~3위)
                is_top = r <= 3
                
                if is_mine or is_comp or is_top:
                    brand_type = "TOP"
                    if is_comp: brand_type = "COMP"
                    if is_mine: brand_type = "MY" # 내 브랜드가 최우선
                    
                    row_data.update({
                        "rank": r, "mall": raw_mall, "price": item['lprice'],
                        "title": item['title'].replace("<b>", "").replace("</b>", ""),
                        "link": item['link'],
                        "type": brand_type
                    })
                    found_any = True
                    break # 가장 높은 순위 1개만 기록

        results.append(row_data)
        
        # 로그 출력
        log_msg = f"{kw}"
        if found_any: log_msg += f" -> {row_data['rank']}위 ({row_data['type']})"
        print(f"[{idx+1}/{len(keywords)}] {log_msg}")
        time.sleep(0.3)

    if results:
        df = pd.DataFrame(results)
        my_count = len(df[df['type']=='MY'])
        print(f"📊 최종 결과: 총 {len(df)}개 중 내 브랜드 {my_count}개 발견")
        
        if APPS_URL:
            try:
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)
                csv_data = csv_buffer.getvalue().encode('utf-8')
                requests.post(APPS_URL, params={"token": APPS_TOKEN, "type": "auto_daily"}, data=csv_data)
                print("📤 구글 시트/슬랙 전송 완료")
            except Exception as e:
                print(f"❌ 전송 실패: {e}")

if __name__ == "__main__":
    run_daily_routine()
