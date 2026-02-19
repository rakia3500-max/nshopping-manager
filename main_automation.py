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

if not all([NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, NAVER_AD_API_KEY, NAVER_AD_SECRET_KEY, NAVER_CUSTOMER_ID]):
    logging.error("❌ GitHub Secrets 누락")
    sys.exit(1)

T_DB = [x.strip() for x in "드론박스, DroneBox, DJI 정품판매점 드론박스".split(',')]
T_BIT = [x.strip() for x in "빛드론, Bit-Drone, Bit Drone, BITDRONE".split(',')]
T_COMP = [x.strip() for x in "다다사, dadasa, 효로로, 드론뷰".split(',')]

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
    except Exception as e:
        logging.warning(f"⚠️ {kw} 검색량 에러: {e}")
    return 0, 0, 0

def get_rank(kw):
    time.sleep(random.uniform(1.0, 2.0)) 
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
        logging.warning(f"⚠️ {kw} 쇼핑 에러: {e}")
        return []

def run_automation():
    today_iso = (dt.datetime.utcnow() + dt.timedelta(hours=9)).strftime("%Y-%m-%d")
    keywords = ["DJI 드론", "매빅3", "에어3"] 
    results = []
    
    for kw in keywords:
        vol, clk, ctr = get_vol(kw)
        items = get_rank(kw)
        if items:
            for r, item in enumerate(items, 1):
                mn = item.get('mallName', '').replace(" ", "")
                if r <= 3 or any(x.replace(" ", "") in mn for x in T_DB + T_BIT + T_COMP):
                    sm = item.get('mallName', '')
                    cm = sm.replace(" ", "").lower()
                    if any(x in cm for x in ["드론박스", "dronebox"]): sm = "드론박스"
                    elif any(x in cm for x in ["빛드론", "bitdrone"]): sm = "빛드론"
                    results.append({"date": today_iso, "keyword": kw, "vol": vol, "rank": r, "mall": sm, "title": item.get('title', '').replace("<b>", "").replace("</b>", ""), "price": item.get('lprice', 0)})

    if results and APPS_SCRIPT_URL:
        df = pd.DataFrame(results)
        csv_bytes = df.to_csv(index=False).encode('utf-8')
        requests.post(APPS_SCRIPT_URL, params={"token": APPS_SCRIPT_TOKEN, "type": "auto_daily"}, data=csv_bytes, headers={'Content-Type': 'text/plain; charset=utf-8'}, timeout=10)
        logging.info("✅ 전송 완료")

if __name__ == "__main__":
    run_automation()
