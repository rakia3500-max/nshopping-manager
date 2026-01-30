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

# --- 1. 환경변수/시크릿 로드 헬퍼 ---
def get_secret(key):
    # GitHub Actions 환경변수 우선 확인
    val = os.environ.get(key)
    if val: return val
    # 로컬 테스트용 (streamlit secrets가 있다면)
    try:
        import streamlit as st
        if key in st.secrets: return st.secrets[key]
    except: pass
    return None

# --- 2. API 함수들 (기존 로직 그대로 사용) ---
def get_vol(kw, ak, sk, cid):
    if not (ak and sk and cid): return 0, 0, 0
    try:
        ts = str(int(time.time() * 1000))
        # HMAC 서명 생성
        msg = f"{ts}.GET./keywordstool".encode()
        sig = base64.b64encode(hmac.new(sk.encode(), msg, hashlib.sha256).digest()).decode()
        headers = {"X-Timestamp": ts, "X-API-KEY": ak, "X-Customer": cid, "X-Signature": sig}
        
        # API 호출
        res = requests.get(f"https://api.naver.com/keywordstool?hintKeywords={kw.replace(' ', '')}&showDetail=1", headers=headers, timeout=5)
        
        for i in res.json().get('keywordList', []):
            if i['relKeyword'].replace(" ", "") == kw.replace(" ", ""):
                v = int(str(i['monthlyPcQcCnt']).replace("<", "")) + int(str(i['monthlyMobileQcCnt']).replace("<", ""))
                c = float(str(i['monthlyAvePcClkCnt']).replace("<", "")) + float(str(i['monthlyAveMobileClkCnt']).replace("<", ""))
                return v, round(c, 1), round(c / v * 100, 2) if v else 0
    except Exception as e:
        print(f"광고 API 에러 ({kw}): {e}")
    return 0, 0, 0

def get_rank(kw, cid, sec):
    try:
        headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": sec}
        res = requests.get("https://openapi.naver.com/v1/search/shop.json", 
                           headers=headers, params={"query": kw, "display": 100, "sort": "sim"}, timeout=5)
        return res.json().get('items', [])
    except: return []

def get_ai_report(text, api_key):
    if not api_key: return "API 키 없음"
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        당신은 쇼핑몰 SEO 전문가입니다. 아래 데이터를 요약하여 3줄 핵심 브리핑을 해주세요.
        [데이터]
        {text}
        """
        response = model.generate_content(prompt)
        return response.text if response.text else "분석 실패"
    except Exception as e: return f"AI 에러: {e}"

# --- 3. 메인 실행 로직 ---
def run_daily_routine():
    print("🚀 일일 자동 분석 시작...")
    
    # 시크릿 불러오기
    GEMINI_KEY = get_secret("GEMINI_API_KEY")
    N_CID = get_secret("NAVER_CLIENT_ID")
    N_SEC = get_secret("NAVER_CLIENT_SECRET")
    AD_KEY = get_secret("NAVER_AD_API_KEY")
    AD_SEC = get_secret("NAVER_AD_SECRET_KEY")
    AD_CUS = get_secret("NAVER_CUSTOMER_ID")
    APPS_URL = get_secret("APPS_SCRIPT_URL")
    APPS_TOKEN = get_secret("APPS_SCRIPT_TOKEN")
    
    # 키워드 및 브랜드 설정
    raw_kws = get_secret("DEFAULT_KEYWORDS")
    if not raw_kws:
        print("❌ 키워드(DEFAULT_KEYWORDS)가 설정되지 않았습니다.")
        return
        
    keywords = [k.strip() for k in raw_kws.replace('\n', ',').split(',') if k.strip()]
    
    my_brands = []
    b1 = get_secret("MY_BRAND_1")
    b2 = get_secret("MY_BRAND_2")
    if b1: my_brands += [x.strip() for x in b1.split(',')]
    if b2: my_brands += [x.strip() for x in b2.split(',')]
    
    today = dt.date.today().isoformat()
    results = []
    ai_text = ""

    # 분석 루프
    print(f"📊 총 {len(keywords)}개 키워드 분석 중...")
    for idx, kw in enumerate(keywords):
        # 1. 검색량(Vol) 조회
        vol, clk, ctr = get_vol(kw, AD_KEY, AD_SEC, AD_CUS)
        
        # 2. 순위(Rank) 조회
        items = get_rank(kw, N_CID, N_SEC)
        
        rank_data = "-"
        found = False
        
        if items:
            for r, item in enumerate(items, 1):
                # 내 브랜드 찾기
                mn = item['mallName'].replace(" ", "")
                if any(b.replace(" ", "") in mn for b in my_brands if b):
                    # 찾았다!
                    results.append({
                        "date": today, "keyword": kw, "vol": vol, "click": clk, "ctr": ctr,
                        "rank": r, "mall": item['mallName'], "price": item['lprice'],
                        "title": item['title'].replace("<b>", "").replace("</b>", ""),
                        "link": item['link']
                    })
                    rank_data = f"{r}위"
                    found = True
                    break # 최고 순위 하나만 기록
        
        # 못 찾았어도 검색량 데이터는 남기려면 아래 주석 해제 (선택사항)
        # if not found: results.append({"date": today, "keyword": kw, "vol": vol, ... "rank": 999 ...})

        status = f"{kw}: {vol}건 / {rank_data}"
        print(f"[{idx+1}/{len(keywords)}] {status}")
        ai_text += f"{kw}:{rank_data} "
        time.sleep(0.5) # API 보호

    # 결과 처리
    if results:
        df = pd.DataFrame(results)
        print(f"✅ 분석 완료! 총 {len(df)}개 유효 데이터 발견.")
        
        # (옵션) AI 리포트 생성
        # report = get_ai_report(ai_text, GEMINI_KEY)
        # print(f"📝 AI 요약: {report}")
        
        # 구글 시트/슬랙 전송
        if APPS_URL:
            print("📤 구글 시트로 전송 시도...")
            try:
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)
                csv_data = csv_buffer.getvalue().encode('utf-8')
                
                res = requests.post(APPS_URL, 
                              params={"token": APPS_TOKEN, "type": "auto_daily"}, 
                              data=csv_data)
                print(f"결과 코드: {res.status_code}")
            except Exception as e:
                print(f"전송 실패: {e}")
    else:
        print("⚠️ 발견된 내 상품 순위 데이터가 없습니다.")

if __name__ == "__main__":
    run_daily_routine()
