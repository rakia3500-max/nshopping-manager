# -*- coding: utf-8 -*-
import requests
import pandas as pd
import datetime as dt
import time
import base64
import hmac
import hashlib
import os
import io
import random
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
NAVER_AD_API_KEY = os.getenv("NAVER_AD_API_KEY")
NAVER_AD_SECRET_KEY = os.getenv("NAVER_AD_SECRET_KEY")
NAVER_CUSTOMER_ID = os.getenv("NAVER_CUSTOMER_ID")
APPS_SCRIPT_URL = os.getenv("APPS_SCRIPT_URL")
APPS_SCRIPT_TOKEN = os.getenv("APPS_SCRIPT_TOKEN")

T_DB = [x.strip() for x in "드론박스, DroneBox, DJI 정품판매점 드론박스".split(',')]
T_BIT = [x.strip() for x in "빛드론, Bit-Drone, Bit Drone, BITDRONE".split(',')]
T_COMP = [x.strip() for x in "다다사, dadasa, 효로로, 드론뷰".split(',')]

def load_keywords(file_path="keywords.txt"):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                kw_list = [line.strip() for line in f if line.strip()]
                if kw_list:
                    logging.info(f"📂 {len(kw_list)}개의 키워드 로드 완료")
                    return kw_list
        except Exception as e:
            logging.error(f"❌ 파일 읽기 에러: {e}")
    return ["입문용 드론", "촬영용 드론", "미니4 프로"]

def get_vol(kw):
    try:
        ts = str(int(time.time() * 1000))
        sig = base64.b64encode(hmac.new(NAVER_AD_SECRET_KEY.encode(), f"{ts}.GET./keywordstool".encode(), hashlib.sha256).digest()).decode()
        headers = {"X-Timestamp": ts, "X-API-KEY": NAVER_AD_API_KEY, "X-Customer": NAVER_CUSTOMER_ID, "X-Signature": sig}
        res = requests.get(f"https://api.naver.com/keywordstool?hintKeywords={kw.replace(' ', '')}&showDetail=1", headers=headers, timeout=10)
        res.raise_for_status()
        for i in res.json().get('keywordList', []):
            if i.get('relKeyword', '').replace(" ", "") == kw.replace(" ", ""):
                v = int(str(i.get('monthlyPcQcCnt', 0)).replace("<", "0")) + int(str(i.get('monthlyMobileQcCnt', 0)).replace("<", "0"))
                c = float(str(i.get('monthlyAvePcClkCnt', 0)).replace("<", "0")) + float(str(i.get('monthlyAveMobileClkCnt', 0)).replace("<", "0"))
                return v, round(c, 1), round(c / v * 100, 2) if v else 0
    except Exception as e: pass
    return 0, 0, 0

def get_rank(kw):
    time.sleep(random.uniform(1.0, 2.5)) # 91개 대량 조회를 위한 딜레이 조정
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID, 
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        res = requests.get("https://openapi.naver.com/v1/search/shop.json", headers=headers, params={"query": kw, "display": 100, "sort": "sim"}, timeout=10)
        res.raise_for_status()
        return res.json().get('items', [])
    except Exception as e:
        logging.warning(f"⚠️ {kw} 검색 에러: {e}")
        return []

def run_automation():
    today_iso = (dt.datetime.utcnow() + dt.timedelta(hours=9)).strftime("%Y-%m-%d")
    keywords = load_keywords("keywords.txt")
    
    # [핵심 로직 개선] 비교를 위한 소문자+공백제거 리스트 사전 구축
    t_db_clean = [x.replace(" ", "").lower() for x in T_DB]
    t_bit_clean = [x.replace(" ", "").lower() for x in T_BIT]
    t_comp_clean = [x.replace(" ", "").lower() for x in T_COMP]
    
    results = []
    
    for kw in keywords:
        logging.info(f"🔍 분석 중: {kw}")
        vol, clk, ctr = get_vol(kw)
        items = get_rank(kw)
        if items:
            for r, item in enumerate(items, 1):
                raw_mall = item.get('mallName', '')
                cm = raw_mall.replace(" ", "").lower() # 추출된 몰 이름을 소문자+공백제거 변환
                
                is_mine = any(x in cm for x in t_db_clean + t_bit_clean)
                is_comp = any(x in cm for x in t_comp_clean)
                
                # 1~3위 무조건 수집 OR 내 업체/경쟁사일 경우 수집
                if r <= 3 or is_mine or is_comp:
                    sm = raw_mall
                    # GAS/Slack 전송을 위한 표준 이름 규격화
                    if any(x in cm for x in t_db_clean): sm = "드론박스"
                    elif any(x in cm for x in t_bit_clean): sm = "빛드론"
                    elif "다다사" in cm: sm = "다다사"
                    elif "효로로" in cm: sm = "효로로"
                    elif "드론뷰" in cm: sm = "드론뷰"
                    
                    results.append({"date": today_iso, "keyword": kw, "vol": vol, "rank": r, "mall": sm, "title": item.get('title', '').replace("<b>", "").replace("</b>", ""), "price": item.get('lprice', 0)})

    if results and APPS_SCRIPT_URL:
        df = pd.DataFrame(results)
        csv_bytes = df.to_csv(index=False).encode('utf-8')
        try:
            requests.post(APPS_SCRIPT_URL, params={"token": APPS_SCRIPT_TOKEN, "type": "auto_daily"}, data=csv_bytes, headers={'Content-Type': 'text/plain; charset=utf-8'}, timeout=30)
            logging.info("✅ 구글 시트 전송 완료")
        except Exception as e:
            logging.error(f"❌ 전송 실패: {e}")

if __name__ == "__main__":
    run_automation()
