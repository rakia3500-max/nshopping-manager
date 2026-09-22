/* 상품 상세 깨짐 수정 (2026-09-22) — 빛드론(카페24 스크립트태그) + 드론박스(고도몰 스킨) 공용, youtube_fix.js를 대체
 * 1) 유튜브: 에디봇이 영상 칸을 height:562px !important 로 고정 → 좁은 화면에서 좌우 잘림 → 16:9 자동 높이
 * 2) 넓이 고정 요소: DJI 사이트에서 복사한 글상자(width:1260px)·스펙 표(width:437px) 등이
 *    화면보다 넓어 글자가 잘리고 페이지가 옆으로 밀림 → 화면 폭에 맞추고 줄바꿈
 */
(function () {
  /* 빛드론(카페24) + 드론박스(고도몰 PC .detail_explain_box / 모바일 .js_goods_description) */
  var ROOT = '#prdDetail, .edibot-product-detail, #prdDetailContent, .cont_detail, .detail_explain_box, .js_goods_description';

  function fixVideo() {
    var list = document.querySelectorAll('iframe[src*="youtube.com"], iframe[src*="youtu.be"], iframe[src*="youtube-nocookie.com"]');
    Array.prototype.forEach.call(list, function (f) {
      if (/\/shorts\//.test(f.src)) return;
      var p = f.parentElement, first = !f.getAttribute('data-bd-yt');
      f.setAttribute('data-bd-yt', '1');
      if (!first) {
        /* 이미 처리한 영상은 비율 검사만 (처음엔 화면에 안 그려져 폭이 0이었을 수 있음) */
      } else if (p && /height/.test(p.getAttribute('style') || '') && f.getAttribute('height') === '100%') {
        p.style.setProperty('height', 'auto', 'important');
        p.style.setProperty('max-height', 'none', 'important');
        p.style.setProperty('aspect-ratio', '16 / 9');
        p.style.setProperty('vertical-align', 'top');
        f.style.display = 'block';
      } else if (/^\d+$/.test(f.getAttribute('height') || '')) {
        var w = parseInt(f.getAttribute('width'), 10) || 16, h = parseInt(f.getAttribute('height'), 10) || 9;
        f.style.setProperty('max-width', '100%', 'important');
        f.style.setProperty('height', 'auto', 'important');
        f.style.setProperty('aspect-ratio', w + ' / ' + h);
      }
      /* 스킨이 높이를 auto로 덮어써 150px로 납작해진 경우 (드론박스 모바일) */
      var r = f.getBoundingClientRect();
      if (r.width > 0 && (r.height / r.width < 0.45 || r.height / r.width > 0.75) && p && !/aspect-ratio/.test(p.getAttribute('style') || '')) {
        f.style.setProperty('width', '100%', 'important');
        f.style.setProperty('max-width', '100%', 'important');
        f.style.setProperty('height', 'auto', 'important');
        f.style.setProperty('aspect-ratio', '16 / 9');
      }
    });
  }

  function fixWide(root) {
    var vw = document.documentElement.clientWidth;
    /* 인라인 width:NNNpx 가 부모보다 넓은 요소 */
    Array.prototype.forEach.call(root.querySelectorAll('[style*="width"], table[width], td[width], th[width]'), function (e) {
      if (/^(IMG|IFRAME|VIDEO|SVG)$/i.test(e.tagName) || !e.parentElement) return;
      var st = e.getAttribute('style') || '';
      var m = st.match(/(?:^|;)\s*width:\s*(\d+)px/);
      var w = m ? +m[1] : parseInt(e.getAttribute('width'), 10);
      if (!w || /%/.test(e.getAttribute('width') || '')) return;
      var pw = e.parentElement.getBoundingClientRect().width;
      if (!pw || w <= pw + 2) return;
      e.style.setProperty('width', /^(TABLE)$/.test(e.tagName) ? '100%' : 'auto', 'important');
      e.style.setProperty('max-width', '100%', 'important');
      e.style.setProperty('box-sizing', 'border-box', 'important');
      if (/(?:^|;)\s*min-width:\s*\d+px/.test(st)) e.style.setProperty('min-width', '0', 'important');
      /* 글이 들어 있는 고정 높이 상자는 줄바꿈되면 글이 잘리므로 높이 자동 */
      if (/(?:^|;)\s*height:\s*\d+px/.test(st) && e.textContent.trim() && getComputedStyle(e).position !== 'absolute')
        e.style.setProperty('height', 'auto', 'important');
    });
    /* 스타일 규칙(class)로 폭이 정해진 요소 — DJI 사이트 복사본 등. 가로 스크롤 상자 안은 건드리지 않음 */
    var rw = root.getBoundingClientRect().width;
    Array.prototype.forEach.call(root.querySelectorAll('*'), function (e) {
      if (/^(IMG|IFRAME|VIDEO|SVG|PATH)$/i.test(e.tagName)) return;
      if (e.getBoundingClientRect().width <= rw + 2) return;
      for (var p = e.parentElement; p && p !== root; p = p.parentElement)
        if (getComputedStyle(p).overflowX !== 'visible') return;
      e.style.setProperty('width', 'auto', 'important');
      e.style.setProperty('max-width', '100%', 'important');
      e.style.setProperty('min-width', '0', 'important');
      e.style.setProperty('box-sizing', 'border-box', 'important');
      var cs = getComputedStyle(e);
      if (/flex/.test(cs.display)) e.style.setProperty('flex-wrap', 'wrap', 'important');
    });
    /* 줄바꿈 금지 글줄이 화면보다 넓은 경우 */
    Array.prototype.forEach.call(root.querySelectorAll('span, p, div, td, th, li, strong, b, font, h1, h2, h3, h4'), function (e) {
      if (e.getBoundingClientRect().width > vw && !e.querySelector('img, iframe, table, video') &&
          getComputedStyle(e).whiteSpace !== 'normal') e.style.setProperty('white-space', 'normal', 'important');
    });
  }

  function run() {
    fixVideo();
    Array.prototype.forEach.call(document.querySelectorAll(ROOT), fixWide);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run); else run();
  window.addEventListener('load', run);
})();
