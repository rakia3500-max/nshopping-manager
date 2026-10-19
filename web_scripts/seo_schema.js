/* 구글용 구조화 데이터(JSON-LD) 주입 (2026-10-19)
 * - 빛드론(카페24 스크립트태그) + 드론박스(고도몰 외부 스크립트) 공용. 호스트로 몰을 구분한다.
 * - 홈: Organization + WebSite(사이트 검색 SearchAction)
 * - 드론박스 상품 상세: Product(이름·이미지·설명·브랜드·SKU·가격·재고). 빛드론은 카페24가 이미 Product를 내보내므로 건너뜀.
 * - 값은 페이지에 이미 있는 것만 쓴다(og 메타, 고도몰 setGoodsPrice/setStockFl). 없으면 넣지 않는다.
 * - 같은 종류의 JSON-LD가 이미 있으면 중복 주입하지 않는다.
 */
(function () {
  var host = location.hostname, path = location.pathname;
  var isBit = /(^|\.)bit-drone\.shop$/.test(host);
  var isBox = /(^|\.)drone-box\.co\.kr$/.test(host);
  if (!isBit && !isBox) return;

  var SITE = isBit ? {
    name: '빛드론',
    url: 'https://bit-drone.shop/',
    desc: 'DJI 드론 전문 판매점 — 촬영용·산업용·측량용·농업용 드론과 오즈모 카메라',
    search: 'https://bit-drone.shop/product/search.html?keyword={search_term_string}'
  } : {
    name: '드론박스',
    url: 'https://www.drone-box.co.kr/',
    desc: 'DJI 정품 드론·오즈모 카메라와 농업·산업용 드론 부품 쇼핑몰 (전주)',
    search: 'https://www.drone-box.co.kr/goods/goods_search.php?keyword={search_term_string}'
  };

  function meta(sel) {
    var m = document.querySelector(sel);
    return m ? (m.getAttribute('content') || '').trim() : '';
  }
  function hasType(type) {
    var list = document.querySelectorAll('script[type="application/ld+json"]');
    for (var i = 0; i < list.length; i++) {
      try {
        var d = JSON.parse(list[i].text || list[i].textContent || '');
        var arr = Array.isArray(d) ? d : [d];
        for (var j = 0; j < arr.length; j++) if (arr[j] && arr[j]['@type'] === type) return true;
      } catch (e) { /* 무시 */ }
    }
    return false;
  }
  function add(obj) {
    if (hasType(obj['@type'])) return;
    var s = document.createElement('script');
    s.type = 'application/ld+json';
    s.setAttribute('data-seo-schema', obj['@type']);
    s.text = JSON.stringify(obj);
    (document.head || document.documentElement).appendChild(s);
  }
  function absUrl(u) {
    if (!u) return '';
    if (/^\/\//.test(u)) return 'https:' + u;
    if (/^https?:/.test(u)) return u;
    return location.origin + (u.charAt(0) === '/' ? '' : '/') + u;
  }

  function run() {
    var isHome = isBit ? (path === '/' || path === '/index.html')
                       : (path === '/' || path === '/index.php' || /^\/main\/index\.php$/.test(path));
    if (isHome) {
      var org = { '@context': 'https://schema.org', '@type': 'Organization', name: SITE.name, url: SITE.url, description: SITE.desc };
      var logo = document.querySelector('img[alt*="로고"], img[alt*="logo" i], .logo img, #logo img, h1 img');
      if (logo && logo.src) org.logo = absUrl(logo.getAttribute('src'));
      add(org);
      add({
        '@context': 'https://schema.org', '@type': 'WebSite', name: SITE.name, url: SITE.url,
        potentialAction: { '@type': 'SearchAction', target: { '@type': 'EntryPoint', urlTemplate: SITE.search }, 'query-input': 'required name=search_term_string' }
      });
    }

    if (isBox && /\/goods\/goods_view\.php/.test(path)) {
      var js = '';
      for (var i = 0; i < document.scripts.length; i++) if (!document.scripts[i].src) js += (document.scripts[i].text || '') + '\n';
      var price = (js.match(/['"]setGoodsPrice['"]\s*:\s*['"]([\d.]+)['"]/) || [])[1];
      var stock = (js.match(/['"]setStockFl['"]\s*:\s*['"](\w)['"]/) || [])[1];
      var no = (js.match(/['"]setGoodsNo['"]\s*:\s*['"](\d+)['"]/) || [])[1] || (location.search.match(/goodsNo=(\d+)/) || [])[1];
      var name = meta('meta[property="og:title"]') || (document.title || '').trim();
      var img = absUrl(meta('meta[property="og:image"]'));
      var desc = meta('meta[name="description"]');
      var canon = document.querySelector('link[rel="canonical"]');
      var soldout = !!document.querySelector('.btn_soldout, .soldout, .btn_soldOut, [class*="soldout" i]');
      if (!soldout) {
        var btns = document.querySelectorAll('.btn_goods_action button, .btn_goods_action a, .goods_btn button, .btn_choice button');
        for (var b = 0; b < btns.length; b++) if (/품절/.test(btns[b].textContent || '')) { soldout = true; break; }
      }
      if (name && price && parseFloat(price) > 0) {
        var p = {
          '@context': 'https://schema.org', '@type': 'Product', name: name,
          offers: {
            '@type': 'Offer', price: String(Math.round(parseFloat(price))), priceCurrency: 'KRW',
            availability: soldout ? 'https://schema.org/SoldOut' : 'https://schema.org/InStock',
            itemCondition: 'https://schema.org/NewCondition',
            url: canon ? canon.href : location.href,
            seller: { '@type': 'Organization', name: SITE.name }
          }
        };
        if (img) p.image = [img];
        if (desc) p.description = desc;
        if (no) p.sku = no;
        if (/^DJI\b/i.test(name)) p.brand = { '@type': 'Brand', name: 'DJI' };
        add(p);
      }
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run);
  else run();
})();
