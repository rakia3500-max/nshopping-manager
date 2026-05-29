# -*- coding: utf-8 -*-
import requests
import pandas as pd
import datetime as dt
import time
import base64
import hmac
import hashlib
import os
import random
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

NAVER_CLIENT_ID    = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET= os.getenv("NAVER_CLIENT_SECRET")
NAVER_AD_API_KEY   = os.getenv("NAVER_AD_API_KEY")
NAVER_AD_SECRET_KEY= os.getenv("NAVER_AD_SECRET_KEY")
NAVER_CUSTOMER_ID  = os.getenv("NAVER_CUSTOMER_ID")
APPS_SCRIPT_URL    = os.getenv("APPS_SCRIPT_URL")
APPS_SCRIPT_TOKEN  = os.getenv("APPS_SCRIPT_TOKEN")

# Load brands/competitors from env vars (MY_BRAND_1, MY_BRAND_2, COMPETITORS)
T_DB   = [x.strip() for x in os.getenv("MY_BRAND_1",  "").split(',') if x.strip()]
T_BIT  = [x.strip() for x in os.getenv("MY_BRAND_2",  "").split(',') if x.strip()]
T_COMP = [x.strip() for x in os.getenv("COMPETITORS", "").split(',') if x.strip()]


def load_keywords(file_path="keywords.txt"):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                kw_list = [line.strip() for line in f if line.strip()]
                if kw_list:
                    return kw_list
        except Exception as e:
            logging.error("keyword file read error: %s", e)
    return []


def get_vol(kw):
    if not (NAVER_AD_SECRET_KEY and NAVER_AD_API_KEY and NAVER_CUSTOMER_ID):
        return 0, 0, 0
    try:
        ts = str(int(time.time() * 1000))
        sig = base64.b64encode(
            hmac.new(NAVER_AD_SECRET_KEY.encode(),
                     ("%s.GET./keywordstool" % ts).encode(),
                     hashlib.sha256).digest()
        ).decode()
        headers = {
            "X-Timestamp": ts, "X-API-KEY": NAVER_AD_API_KEY,
            "X-Customer": NAVER_CUSTOMER_ID, "X-Signature": sig
        }
        res = requests.get(
            "https://api.naver.com/keywordstool?hintKeywords=%s&showDetail=1" % kw.replace(' ', ''),
            headers=headers, timeout=10
        )
        res.raise_for_status()
        for i in res.json().get('keywordList', []):
            if i.get('relKeyword', '').replace(" ", "") == kw.replace(" ", ""):
                v = (int(str(i.get('monthlyPcQcCnt', 0)).replace("<", "0")) +
                     int(str(i.get('monthlyMobileQcCnt', 0)).replace("<", "0")))
                c = (float(str(i.get('monthlyAvePcClkCnt', 0)).replace("<", "0")) +
                     float(str(i.get('monthlyAveMobileClkCnt', 0)).replace("<", "0")))
                return v, round(c, 1), round(c / v * 100, 2) if v else 0
    except Exception:
        pass
    return 0, 0, 0


def get_rank(kw):
    time.sleep(random.uniform(0.8, 1.8))
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
        "User-Agent": "Mozilla/5.0"
    }
    try:
        res = requests.get(
            "https://openapi.naver.com/v1/search/shop.json",
            headers=headers,
            params={"query": kw, "display": 100, "sort": "sim"},
            timeout=10
        )
        res.raise_for_status()
        return res.json().get('items', [])
    except Exception as e:
        logging.warning("search error [%s]: %s", kw, e)
        return []


def run_automation():
    import datetime as dt
    today_iso = (dt.datetime.utcnow() + dt.timedelta(hours=9)).strftime("%Y-%m-%d")
    keywords = load_keywords("keywords.txt")

    t_db_clean   = [x.replace(" ", "").lower() for x in T_DB]
    t_bit_clean  = [x.replace(" ", "").lower() for x in T_BIT]
    t_comp_clean = [x.replace(" ", "").lower() for x in T_COMP]

    results = []

    for kw in keywords:
        vol, clk, ctr = get_vol(kw)
        items = get_rank(kw)
        if not items:
            continue

        for r, item in enumerate(items, 1):
            raw_mall = item.get('mallName', '')
            cm = raw_mall.replace(" ", "").lower()

            is_mine = any(x in cm for x in t_db_clean + t_bit_clean)
            is_comp = any(x in cm for x in t_comp_clean)

            if r > 3 and not is_mine and not is_comp:
                continue

            sm = raw_mall
            if any(x in cm for x in t_db_clean):
                sm = T_DB[0] if T_DB else raw_mall
            elif any(x in cm for x in t_bit_clean):
                sm = T_BIT[0] if T_BIT else raw_mall
            else:
                for comp in T_COMP:
                    if comp.replace(" ", "").lower() in cm:
                        sm = comp
                        break

            comp_flags = {
                ("is_comp_%d" % (i+1)): comp.replace(" ", "").lower() in cm
                for i, comp in enumerate(T_COMP)
            }

            ptype = str(item.get('productType', '1'))
            is_catalog = ptype in ['2', '3', '5', '6', '8', '9']

            row = {
                "date": today_iso, "keyword": kw,
                "vol": vol, "click": clk, "ctr": ctr,
                "rank": r, "mall": sm,
                "title": item.get('title', '').replace("<b>", "").replace("</b>", ""),
                "price": item.get('lprice', 0),
                "link":  item.get('link', ''),
                "is_db":  any(x in cm for x in t_db_clean),
                "is_bit": any(x in cm for x in t_bit_clean),
                "product_type": ptype,
                "is_catalog": is_catalog,
            }
            row.update(comp_flags)
            results.append(row)

    if results and APPS_SCRIPT_URL:
        import pandas as pd, io as _io
        df = pd.DataFrame(results)
        csv_bytes = df.to_csv(index=False).encode('utf-8')
        try:
            requests.post(
                APPS_SCRIPT_URL,
                params={"token": APPS_SCRIPT_TOKEN, "type": "auto_daily"},
                data=csv_bytes,
                headers={"Content-Type": "text/plain; charset=utf-8"},
                timeout=30
            )
            logging.info("GAS upload complete")
        except Exception as e:
            logging.error("GAS upload failed: %s", e)


if __name__ == "__main__":
    run_automation()
