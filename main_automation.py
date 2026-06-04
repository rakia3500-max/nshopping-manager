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

# [P2] 절대 경로 기준점 -- 어떤 디렉토리에서 실행해도 keywords.txt를 정확히 찾음
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
NAVER_AD_API_KEY = os.getenv("NAVER_AD_API_KEY")
NAVER_AD_SECRET_KEY = os.getenv("NAVER_AD_SECRET_KEY")
NAVER_CUSTOMER_ID = os.getenv("NAVER_CUSTOMER_ID")
APPS_SCRIPT_URL = os.getenv("APPS_SCRIPT_URL")
APPS_SCRIPT_TOKEN = os.getenv("APPS_SCRIPT_TOKEN")

_brand1_raw = os.getenv("MY_BRAND_1", "드론박스, DroneBox, DJI 정품판매점 드론박스")
_brand2_raw = os.getenv("MY_BRAND_2", "빛드론, Bit-Drone, Bit Drone, BITDRONE")
_comp_raw   = os.getenv("COMPETITORS", "다다사, dadasa, 효로로, 드론뷰")

T_DB   = [x.strip() for x in _brand1_raw.split(',') if x.strip()]
T_BIT  = [x.strip() for x in _brand2_raw.split(',') if x.strip()]
T_COMP = [x.strip() for x in _comp_raw.split(',')   if x.strip()]

def load_keywords(file_path=None):
    # [P2] 절대 경로 우선 -- GitHub Actions 등 다른 CWD에서도 정상 동작
    if file_path is None:
        file_path = os.path.join(BASE_DIR, "keywords.txt")
    abs_path = os.path.abspath(file_path)
    if os.path.exists(abs_path):
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                kw_list = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                if kw_list:
                    logging.info(f"[P2] keywords.txt 로드 완료: {len(kw_list)}개 키워드 ({abs_path})")
                    return kw_list
        except Exception as e:
            logging.error(f"[P2] keywords.txt 읽기 오류: {e}")
    logging.warning(f"[P2] keywords.txt 미발견 ({abs_path}) -- 기본 키워드 3개로 대체")
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
                def _to_int(val):
                    s = str(val).replace("<", "").strip()
                    return int(s) if s.isdigit() else 0
                def _to_float(val):
                    s = str(val).replace("<", "").strip()
                    try: return float(s)
                    except: return 0.0
                v = _to_int(i.get('monthlyPcQcCnt', 0)) + _to_int(i.get('monthlyMobileQcCnt', 0))
                c = _to_float(i.get('monthlyAvePcClkCnt', 0)) + _to_float(i.get('monthlyAveMobileClkCnt', 0))
                return v, round(c, 1), round(c / v * 100, 2) if v else 0
    except Exception as e:
        logging.warning(f"[P3][get_vol] '{kw}' 검색량 API 오류: {type(e).__name__}: {e}")
    return 0, 0, 0

def get_rank(kw):
    time.sleep(random.uniform(0.8, 1.8)) 
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
    keywords = load_keywords()  # [P2] 인수 없이 호출 -- BASE_DIR 기반 절대 경로 자동 사용
    
    # 띄어쓰기 무시 + 소문자 변환된 비교용 리스트
    t_db_clean = [x.replace(" ", "").lower() for x in T_DB]
    t_bit_clean = [x.replace(" ", "").lower() for x in T_BIT]
    t_comp_clean = [x.replace(" ", "").lower() for x in T_COMP]
    
    results = []
    
    for kw in keywords:
        vol, clk, ctr = get_vol(kw)
        items = get_rank(kw)
        if items:
            for r, item in enumerate(items, 1):
                raw_mall = item.get('mallName', '')
                cm = raw_mall.replace(" ", "").lower()
                
                is_mine = any(x in cm for x in t_db_clean + t_bit_clean)
                is_comp = any(x in cm for x in t_comp_clean)
                
                if r <= 3 or is_mine or is_comp:
                    sm = raw_mall
                    if any(x in cm for x in t_db_clean): sm = "드론박스"
                    elif any(x in cm for x in t_bit_clean): sm = "빛드론"
                    elif "다다사" in cm: sm = "다다사"
                    elif "효로로" in cm: sm = "효로로"
                    elif "드론뷰" in cm: sm = "드론뷰"
                    
                    # [핵심 수정] 원본 스트림릿 코드와 100% 동일한 구조와 컬럼 복원
                    results.append({
                        "date": today_iso, 
                        "keyword": kw, 
                        "vol": vol, 
                        "click": clk, 
                        "ctr": ctr,
                        "rank": r, 
                        "mall": sm, 
                        "title": item.get('title', '').replace("<b>", "").replace("</b>", ""),
                        "price": item.get('lprice', 0), 
                        "link": item.get('link', ''),
                        "is_db": any(x in cm for x in t_db_clean),
                        "is_bit": any(x in cm for x in t_bit_clean),
                        "is_da": "다다사" in cm,
                        "is_hr": "효로로" in cm,
                        "is_dv": "드론뷰" in cm
                    })

    if results and APPS_SCRIPT_URL:
        df = pd.DataFrame(results)
        csv_bytes = df.to_csv(index=False).encode('utf-8')
        try:
            requests.post(
                APPS_SCRIPT_URL,
                params={"token": APPS_SCRIPT_TOKEN, "type": "auto_daily"},
                data=csv_bytes,
                headers={'Content-Type': 'text/plain; charset=utf-8'},
                timeout=30
            )
            logging.info("구글 시트 전송 완료")
        except Exception as e:
            logging.error(f"[P3] 구글 시트 전송 실패: {type(e).__name__}: {e}")
    else:
        logging.warning("[P3] 수집 결과 없음 또는 APPS_SCRIPT_URL 미설정")

if __name__ == "__main__":
    run_automation()
