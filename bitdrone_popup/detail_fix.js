/* 빛드론 상품 상세 깨짐 수정 (2026-09-22) — youtube_fix.js를 대체
 * 1) 유튜브: 에디봇이 영상 칸을 height:562px !important 로 고정 → 좁은 화면에서 좌우 잘림 → 16:9 자동 높이
 * 2) 넓이 고정 요소: DJI 사이트에서 복사한 글상자(width:1260px)·스펙 표(width:437px) 등이
 *    화면보다 넓어 글자가 잘리고 페이지가 옆으로 밀림 → 화면 폭에 맞추고 줄바꿈
 */
(function () {
  var ROOT = '#prdDetail, .edibot-product-detail, #prdDetailContent, .cont_detail';

  function fixVideo() {
    var list = document.querySelectorAll('iframe[src*="youtube.com"], iframe[src*="youtu.be"], iframe[src*="youtube-nocookie.com"]');
    Array.prototype.forEach.call(list, function (f) {
      if (f.getAttribute('data-bd-yt') || /\/shorts\//.test(f.src)) return;
      f.setAttribute('data-bd-yt', '1');
      var p = f.parentElement;
      if (p && /height/.test(p.getAttribute('style') || '') && f.getAttribute('height') === '100%') {
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
