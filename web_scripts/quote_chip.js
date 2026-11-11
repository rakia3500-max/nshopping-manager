/* 견적 상품 가격 자리 칩 (2026-11-11)
   판매가 대체 문구가 정확히 '견적 상담'인 자리를 연파랑 둥근 사각형 칩으로 감싼다.
   목록은 13px, 상품 상세 판매가는 16px. 다른 문구('견적 문의'·'가격 상담 필요'·실제 가격)는 건드리지 않는다.
   두 쇼핑몰 공용 — 실제가로 바뀌면 글자가 달라져 칩은 저절로 사라진다. */
(function () {
  var TXT = '견적 상담';
  var CSS =
    '.bdq-chip{display:inline-block!important;font-size:13px!important;font-weight:700!important;line-height:1.35!important;' +
    'color:#1B64DA!important;background:#EEF4FF!important;border:1px solid #D3E2FF!important;border-radius:6px!important;' +
    'padding:3px 9px!important;white-space:nowrap!important;letter-spacing:-0.2px;vertical-align:middle;text-decoration:none!important}' +
    '.bdq-chip.bdq-big{font-size:16px!important;padding:4px 12px!important;border-radius:7px!important}';
  var BIG = '.item_detail_list,.detail_info_top,.price_box,.infoArea,#span_product_price_text';
  var SKIP = 'script,style,title,option,select,textarea,button,.bdq-chip';

  function addCss() {
    if (document.getElementById('bdq-chip-css')) return;
    var s = document.createElement('style');
    s.id = 'bdq-chip-css';
    s.textContent = CSS;
    (document.head || document.documentElement).appendChild(s);
  }

  function run() {
    if (!document.body) return;
    var w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
    var hits = [], t;
    while ((t = w.nextNode())) {
      if (t.nodeValue.trim() !== TXT) continue;
      var p = t.parentElement;
      if (!p || p.closest(SKIP)) continue;
      hits.push(t);
    }
    hits.forEach(function (n) {
      var s = document.createElement('span');
      s.className = 'bdq-chip' + (n.parentElement.closest(BIG) ? ' bdq-big' : '');
      s.textContent = TXT;
      n.parentNode.replaceChild(s, n);
    });
  }

  var timer = null;
  function later() {
    if (timer) return;
    timer = setTimeout(function () { timer = null; run(); }, 120);
  }

  function start() {
    addCss();
    run();
    try { new MutationObserver(later).observe(document.body, { childList: true, subtree: true }); } catch (e) {}
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
