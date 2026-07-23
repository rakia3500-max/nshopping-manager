"""경쟁사 1위 벤치마킹 (nshopping-manager, 2026-07-23).

검색어 1위 경쟁사 상세페이지를 크롤링해, 내 상품이 따라잡으려면 무엇을 고쳐야 하는지
Gemini가 액션 리스트로 알려준다. 다중 사용자용 — 사용자별 네이버 API·Gemini 키 사용.
"""
import re
import requests
import streamlit as st

HDR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0 Safari/537.36"}
_GEMINI_MODELS = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.0-flash"]


def _meta(html, prop):
    m = re.search(rf'<meta[^>]+(?:property|name)=["\']{re.escape(prop)}["\'][^>]+'
                  r'content=["\'](.*?)["\']', html, re.I | re.S)
    if not m:
        m = re.search(rf'<meta[^>]+content=["\'](.*?)["\'][^>]+'
                      rf'(?:property|name)=["\']{re.escape(prop)}["\']', html, re.I | re.S)
    return m.group(1).strip() if m else ""


def fetch_detail(url):
    out = {"url": url, "name": "", "price": "", "text": "", "img": 0, "ok": False}
    if not url or not str(url).startswith("http"):
        return out
    try:
        r = requests.get(url, headers=HDR, timeout=20)
        html = r.text
    except Exception:
        return out
    out["ok"] = r.status_code == 200
    out["name"] = _meta(html, "og:title") or (
        (re.search(r"<title[^>]*>(.*?)</title>", html, re.S) or [None, ""])[1].strip())
    price = _meta(html, "product:price:amount") or _meta(html, "og:price:amount")
    if not price:
        mm = re.search(r'"price"\s*:\s*"?([0-9,]{4,})"?', html)
        price = mm.group(1) if mm else ""
    out["price"] = price
    out["img"] = len(re.findall(r"<img\b", html, re.I))
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.I | re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    out["text"] = re.sub(r"\s+", " ", t).strip()
    return out


def _excerpt(d, n=1800):
    txt = d.get("text", "")
    name0 = re.split(r"[\s|(]", d.get("name", "") or "")[0]
    i = txt.find(name0) if name0 and len(name0) >= 2 else -1
    start = i if i > 0 else 1500
    return txt[start:start + n]


def _gemini(api_key, prompt):
    for model in _GEMINI_MODELS:
        try:
            url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                   f"{model}:generateContent?key={api_key}")
            r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=45)
            if r.status_code == 200:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            continue
    return "AI 분석 실패 — Gemini 키/모델을 확인하세요."


def _prompt(keyword, our_name, comp, our_d, comp_d):
    return (
        f"네이버쇼핑 검색어 '{keyword}'에서 **경쟁사가 상위, 내 상품은 밀려 있습니다.** "
        "1위 경쟁사 상세페이지를 분석해, 내 상품이 따라잡으려면 무엇을 고쳐야 하는지 알려줘.\n\n"
        f"[내 상품] {our_name}\n"
        f"내 상세 요약: {_excerpt(our_d) or '(상세 없음/미노출)'}\n\n"
        f"[1위 경쟁사] {comp.get('title','')} · 가격 {comp.get('price','?')}\n"
        f"1위 상세 요약: {_excerpt(comp_d)}\n\n"
        "아래 형식으로 간결한 한국어로:\n"
        "■ 1위가 잘하는 점 (3~5개)\n■ 내가 부족한 점 (3개)\n"
        "■ 따라잡기 액션 (우선순위 순, 상품명/상세페이지/검색태그/가격 관점별로 구체적으로)")


def _clean(s):
    return re.sub(r"<[^>]+>", "", str(s)).strip()


def render(keys):
    st.subheader("🎯 경쟁사 1위 벤치마킹")
    st.caption("검색어 1위 경쟁사 상세페이지를 크롤링해, 내 상품이 따라잡으려면 뭘 고쳐야 하는지 "
               "AI가 액션 리스트로 알려줍니다. (경쟁 자사몰은 상세까지 분석 가능)")

    cid = keys.get("naver_client_id", "")
    csec = keys.get("naver_client_secret", "")
    gkey = keys.get("gemini_key", "")
    brands = [b.strip().replace(" ", "").lower()
              for b in (keys.get("my_brand_1", "") + "," + keys.get("my_brand_2", "")).split(",")
              if b.strip()]
    if not (cid and csec):
        st.info("네이버 검색 API 키가 필요합니다 (⚙️ 설정).")
        return
    if not gkey:
        st.info("Gemini 키가 필요합니다 (⚙️ 설정).")
        return

    kw = st.text_input("공략할 검색어", placeholder="예: dji 미니 4k")
    if st.button("🎯 벤치마킹 분석", type="primary", disabled=not kw.strip()):
        with st.spinner("네이버쇼핑 조회 + 상세페이지 크롤링 + AI 분석 중... (20~40초)"):
            try:
                r = requests.get("https://openapi.naver.com/v1/search/shop.json",
                                 headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec},
                                 params={"query": kw, "display": 40, "sort": "sim"}, timeout=10)
                items = r.json().get("items", [])
            except Exception as e:
                st.error(f"네이버쇼핑 조회 실패: {e}")
                return

            def _own(m):
                mn = str(m).replace(" ", "").lower()
                return any(b in mn for b in brands) if brands else False

            comp = next((it for it in items if not _own(it.get("mallName", ""))), None)
            ours = next((it for it in items if _own(it.get("mallName", ""))), None)
            if not comp:
                st.warning("경쟁사 상위 상품을 찾지 못했습니다.")
                return
            comp_meta = {"title": _clean(comp.get("title", "")), "price": comp.get("lprice", "")}
            comp_d = fetch_detail(comp.get("link", ""))
            our_name = _clean(ours.get("title", "")) if ours else "(내 상품이 상위 40위 밖 — 미노출)"
            our_d = fetch_detail(ours.get("link", "")) if ours else {"text": "", "name": our_name}
            advice = _gemini(gkey, _prompt(kw, our_name, comp_meta, our_d, comp_d))
            st.session_state["_bm_res"] = {
                "kw": kw, "advice": advice, "our_name": our_name,
                "comp_title": comp_meta["title"], "comp_mall": comp.get("mallName", ""),
                "comp_price": comp_meta["price"], "comp_ok": comp_d["ok"],
                "comp_link": comp.get("link", ""), "our_link": ours.get("link", "") if ours else ""}

    res = st.session_state.get("_bm_res")
    if res:
        c1, c2 = st.columns(2)
        c1.markdown(f"**🛒 내 상품**  \n{res['our_name']}")
        c2.markdown(f"**🥇 1위 · {res['comp_mall']}**  \n{res['comp_title'][:55]} · {res['comp_price']}원")
        if not res["comp_ok"]:
            st.warning("1위 경쟁사 페이지 크롤링 실패 — 링크가 막혔거나 스마트스토어(JS)일 수 있습니다.")
        st.markdown(res["advice"])
        with st.expander("원본 링크"):
            st.caption(f"내 상품: {res['our_link'] or '(미노출)'}")
            st.caption(f"1위: {res['comp_link']}")
