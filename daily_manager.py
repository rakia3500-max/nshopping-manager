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
    print("🚀 [최종 수정] 데이터 '이름 세탁' 후 전송 모드")
    
    # 시크릿 로드
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
    
    # [하드코딩] 브랜드 설정
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
                raw_mall = item['mallName']
                clean_mall = raw_mall.replace(" ", "").lower()
                
                # --- [핵심 수정] 이름 세탁기 가동 ---
                # 복잡한 몰 이름을 구글 시트가 좋아하는 단순한 이름으로 변경
                
                final_mall_name = raw_mall # 기본값은 원래 이름
                brand_type = "NONE"
                
                # 1. 내 브랜드 확인
                is_mine = False
                for b in MY_BRANDS:
                    if b.replace(" ", "").lower() in clean_mall:
                        is_mine = True
                        break
                
                if is_mine:
                    brand_type = "MY"
                    # ★★★ 여기가 해결책입니다 ★★★
                    # 긴 이름을 '드론박스'나 '빛드론'으로 딱 잘라서 저장합니다.
                    if "드론박스" in clean_mall or "dronebox" in clean_mall:
                        final_mall_name = "드론박스"
                    elif "빛드론" in clean_mall or "bitdrone" in clean_mall:
                        final_mall_name = "빛드론"
                
                # 2. 경쟁사 확인
                is_comp = False
                if not is_mine: # 내께 아니면 경쟁사 확인
                    for c in COMPETITORS:
                        if c.replace(" ", "").lower() in clean_mall:
                            is_comp = True
                            break
                    if is_comp:
                        brand_type = "COMP"
                        # 경쟁사 이름도 깔끔하게 통일 (선택사항)
                        if "다다사" in clean_mall: final_mall_name = "다다사"
                        elif "효로로" in clean_mall: final_mall_name = "효로로"
                        elif "드론뷰" in clean_mall: final_mall_name = "드론뷰"

                # 3. 상위권 확인
                is_top = r <= 3
                if brand_type == "NONE" and is_top:
                    brand_type = "TOP"

                # 저장 조건 충족 시
                if brand_type != "NONE":
                    row_data.update({
                        "rank": r, 
                        "mall": final_mall_name,  # <--- 세탁된 이름 저장
                        "price": item['lprice'],
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

    # --- 구글 시트로 전송 ---
    if results and APPS_URL:
        try:
            df = pd.DataFrame(results)
            print(f"📊 최종 데이터: {len(df)}개 (내 브랜드: {len(df[df['type']=='MY'])})")
            
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_data = csv_buffer.getvalue().encode('utf-8')
            
            # 구글 시트로 전송 (알림은 구글 시트가 보냄)
            res = requests.post(APPS_URL, params={"token": APPS_TOKEN, "type": "auto_daily"}, data=csv_data)
            print(f"📤 구글 시트 전송 완료: {res.status_code}")
            
        except Exception as e:
            print(f"❌ 전송 실패: {e}")

if __name__ == "__main__":
    run_daily_routine()
