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

# --- 메인 로직 ---
def run_daily_routine():
    print("🚑 [긴급 진단] 왜 0이 나오는지 확인합니다.")
    
    # 1. 시크릿(키)가 잘 들어왔는지 확인
    N_CID = get_secret("NAVER_CLIENT_ID")
    N_SEC = get_secret("NAVER_CLIENT_SECRET")
    
    if not N_CID:
        print("❌ [치명적 오류] NAVER_CLIENT_ID가 텅 비어있습니다! Secrets 설정을 확인하세요.")
        return
    else:
        # 보안을 위해 앞 3글자만 보여줌
        print(f"✅ Client ID 로드됨: {N_CID[:3]}***")

    # 2. 키워드 확인
    raw_kws = get_secret("DEFAULT_KEYWORDS")
    if not raw_kws:
        print("❌ [치명적 오류] 키워드가 없습니다.")
        return
    
    # 테스트를 위해 딱 1개 키워드만 검색해봅니다.
    test_keyword = "DJI 매트리스"
    print(f"🔍 테스트 검색 시작: '{test_keyword}'")

    # 3. 네이버 쇼핑 API 호출 (에러 확인용)
    try:
        headers = {"X-Naver-Client-Id": N_CID, "X-Naver-Client-Secret": N_SEC}
        url = "https://openapi.naver.com/v1/search/shop.json"
        params = {"query": test_keyword, "display": 10, "sort": "sim"}
        
        res = requests.get(url, headers=headers, params=params, timeout=10)
        
        # ★★★ 여기가 제일 중요합니다 ★★★
        print(f"📡 API 응답 코드: {res.status_code}")
        
        if res.status_code == 200:
            items = res.json().get('items', [])
            print(f"📦 검색된 상품 수: {len(items)}개")
            if items:
                print(f"🥇 1위 상품명: {items[0]['title']}")
                print(f"🏪 1위 몰이름: {items[0]['mallName']}")
            else:
                print("⚠️ 검색은 됐는데 상품이 0개입니다. (이상함)")
        else:
            # 400, 401, 403, 429 등의 에러가 뜨면 여기가 범인입니다.
            print(f"🔥 [API 에러 발생] 내용: {res.text}")
            print("👉 401: 키 오류 / 403: 권한 없음 / 429: 하루 사용량 초과 / 500: 네이버 점검중")

    except Exception as e:
        print(f"💥 프로그램 자체가 터졌습니다: {e}")

    # 4. 내 브랜드 설정 확인
    my_brands = ["드론박스", "빛드론"] # 하드코딩 테스트
    print(f"🏢 내 브랜드 설정: {my_brands}")

if __name__ == "__main__":
    run_daily_routine()
