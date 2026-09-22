/* 빛드론 상품 상세 '공유' 버튼 (2026-09-22)
 * 찜(하트) 버튼 옆에 공유 아이콘을 붙인다. 공유 주소는 카페24 단축 주소 /surl/P/{상품번호}.
 * 휴대폰: 기기 공유창(카톡·문자 등) / PC: 링크 복사 + 안내 문구
 */
(function () {
  if (document.getElementById('bd-share-btn')) return;
  var m = location.search.match(/product_no=(\d+)/) || location.pathname.match(/\/product\/[^\/]*\/(\d+)\//);
  var no = m ? m[1] : (window.iProductNo || (document.querySelector('meta[property="product:productId"]') || {}).content);
  var wishes = document.querySelectorAll('.ec-base-button .sub_wish');
  if (!no || !wishes.length) return;
  var url = location.origin + '/surl/P/' + no;
  var title = document.title;

  var css = '.bd-share{display:inline-flex!important;align-items:center;justify-content:center;cursor:pointer}' +
    '#bd-share-toast{position:fixed;left:50%;bottom:60px;transform:translateX(-50%);background:rgba(26,26,26,.9);color:#fff;font-size:14px;padding:12px 20px;border-radius:24px;z-index:99999;opacity:0;transition:opacity .2s;pointer-events:none;white-space:nowrap}' +
    '#bd-share-toast.on{opacity:1}';
  var st = document.createElement('style');
  st.appendChild(document.createTextNode(css));
  document.head.appendChild(st);

  var icon = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">' +
    '<circle cx="18" cy="5.5" r="2.5" stroke="#1A1A1A" stroke-width="1.5"/><circle cx="6" cy="12" r="2.5" stroke="#1A1A1A" stroke-width="1.5"/>' +
    '<circle cx="18" cy="18.5" r="2.5" stroke="#1A1A1A" stroke-width="1.5"/><path d="M8.2 10.8l7.6-4.1M8.2 13.2l7.6 4.1" stroke="#1A1A1A" stroke-width="1.5"/></svg>';
  /* 하트(찜) 버튼마다 옆에 붙인다 — 본문 버튼 줄 + 하단 고정 버튼 줄 */
  Array.prototype.forEach.call(wishes, function (wish, i) {
    var a = document.createElement('a');
    if (i === 0) a.id = 'bd-share-btn';
    a.className = 'bd-share';
    a.href = '#none';
    a.title = '공유하기';
    a.setAttribute('aria-label', '공유하기');
    a.innerHTML = icon;
    var ws = getComputedStyle(wish), w = wish.getBoundingClientRect().width || 50;
    [['flex', '0 0 ' + w + 'px'], ['width', w + 'px'], ['height', ws.height], ['border', ws.border],
     ['border-radius', ws.borderRadius], ['background', ws.backgroundColor], ['box-sizing', 'border-box'],
     ['padding', '0'], ['margin', '0']].forEach(function (kv) { a.style.setProperty(kv[0], kv[1], 'important'); });
    a.addEventListener('click', onClick);
    wish.parentNode.insertBefore(a, wish.nextSibling);
  });

  function toast(msg) {
    var t = document.getElementById('bd-share-toast');
    if (!t) { t = document.createElement('div'); t.id = 'bd-share-toast'; document.body.appendChild(t); }
    t.textContent = msg; t.className = 'on';
    clearTimeout(t._h); t._h = setTimeout(function () { t.className = ''; }, 2000);
  }
  function copy() {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(url).then(function () { toast('링크가 복사되었습니다'); }, fallback);
    } else fallback();
  }
  function fallback() {
    var ta = document.createElement('textarea');
    ta.value = url; ta.style.cssText = 'position:fixed;top:-100px';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); toast('링크가 복사되었습니다'); } catch (e) { prompt('아래 링크를 복사하세요', url); }
    ta.remove();
  }
  function onClick(e) {
    e.preventDefault();
    var mobile = /Android|iPhone|iPad|Mobile/i.test(navigator.userAgent);
    if (mobile && navigator.share) navigator.share({ title: title, url: url }).catch(function () {});
    else copy();
  }
})();
