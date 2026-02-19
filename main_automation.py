# -*- coding: utf-8 -*-
import requests
import pandas as pd
import datetime as dt
import time
import base64
import hmac
import hashlib
import json
import os
import io
import random
import google.generativeai as genai

# --- 환경 변수 로드 (GitHub Secrets) ---
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
NAVER_AD_API_KEY = os.getenv("NAVER_AD_API_KEY")
NAVER_AD_SECRET_KEY = os.getenv("NAVER_AD_SECRET_KEY")
NAVER_CUSTOMER_ID = os.getenv("NAVER_CUSTOMER_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
APPS_SCRIPT_URL = os.getenv("APPS_SCRIPT_URL")
APPS_SCRIPT_TOKEN = os.getenv("APPS_SCRIPT_TOKEN")

# 브랜드 설정 (기본값)
T_DB = [x.strip() for x in "드론박스, DroneBox, DJI 정품판매점 드론박스".split(',')]
T_BIT = [x.strip() for x in "빛드론, Bit-Drone, Bit Drone, BITDRONE".split(',')]
T_COMP = [x.strip() for x in "다다사, dadasa, 효로로, 드론뷰".split(',')]

def get_korea_today():
    return dt.datetime.utcnow() + dt.timedelta(hours=9)

def get_vol(kw):
    try:
        ts = str(int(time.time() * 1000))
        sig = base64.b64encode(hmac.new(NAVER_AD_SECRET_KEY.encode(), f"{ts}.GET./keywordstool".encode(), hashlib.sha256).digest()).decode()
        headers = {"X-Timestamp": ts, "X-API-KEY": NAVER_AD_API_KEY, "X-Customer": NAVER_CUSTOMER_ID, "X-Signature": sig}
        res = requests.get(f"https://api.naver.com/keywordstool?hintKeywords={kw.replace(' ', '')}&showDetail=1", headers=headers, timeout=5)
        for i in res.json().get('keywordList', []):
            if i['relKeyword'].replace(" ", "") == kw.replace(" ", ""):
                v = int(str(i['monthlyPcQcCnt']).replace("<", "")) + int(str(i['monthlyMobileQcCnt']).replace("<", ""))
                c = float(str(i['monthlyAvePcClkCnt']).replace("<", "")) + float(str(i['monthlyAveMobileClkCnt']).replace("<", ""))
                return v, round(c, 1), round(c / v * 100, 2) if v else 0
    except: pass
    return 0, 0, 0

def get_rank(kw):
    time.sleep(random.uniform(0.5, 1.2)) # IP 차단 방지 랜덤 딜레이
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID, 
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        res = requests.get("https://openapi.naver.com/v1/search/shop.json", headers=headers, params={"query": kw, "display": 100, "sort": "sim"})
        return res.json().get('items', [])
    except: return []

def run_automation():
    now = get_korea_today()
    today_iso = now.strftime("%Y-%m-%d")
    
    # 분석 키워드 리스트 (파일이 있다면 읽어오고 없으면 예시 사용)
    keywords = ["DJI 드론", "매빅3", "에어3"] 
    
    results = []
    for kw in keywords:
        vol, clk, ctr = get_vol(kw)
        items = get_rank(kw)
        
        if items:
            for r, item in enumerate(items, 1):
                mn = item['mallName'].replace(" ", "")
                is_mine = any(x.replace(" ", "") in mn for x in T_DB + T_BIT)
                is_comp = any(x.replace(" ", "") in mn for x in T_COMP)
                
                if r <= 3 or is_mine or is_comp:
                    # 이름 표준화 로직 (기본 코드와 동일)
                    standard_mall = item['mallName']
                    clean_mall = standard_mall.replace(" ", "").lower()
                    if any(x in clean_mall for x in ["드론박스", "dronebox"]): standard_mall = "드론박스"
                    elif any(x in clean_mall for x in ["빛드론", "bitdrone"]): standard_mall = "빛드론"
                    
                    results.append({
                        "date": today_iso, "keyword": kw, "vol": vol, "click": clk, "ctr": ctr,
                        "rank": r, "mall": standard_mall, "title": item['title'].replace("<b>", "").replace("</b>", ""),
                        "price": item['lprice'], "link": item['link']
                    })

    # 구글 시트 전송
    if results and APPS_SCRIPT_URL:
        df = pd.DataFrame(results)
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_bytes = csv_buffer.getvalue().encode('utf-8')
        requests.post(APPS_SCRIPT_URL, params={"token": APPS_SCRIPT_TOKEN, "type": "auto_daily"}, 
                      data=csv_bytes, headers={'Content-Type': 'text/plain; charset=utf-8'})
        print(f"[{today_iso}] 전송 완료: {len(results)}건")

if __name__ == "__main__":
    run_automation()
