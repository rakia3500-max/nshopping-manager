/* 빛드론 상품 상세 유튜브 영상 잘림 수정 (2026-09-22)
 * 에디봇 상세가 영상 칸을 width:1000px; height:562px !important 로 고정해,
 * 화면이 좁으면(휴대폰·좁은 창) 영상이 세로로 길어지며 좌우가 잘린다 → 16:9 비율로 높이 자동.
 */
(function () {
  function fix() {
    var list = document.querySelectorAll('iframe[src*="youtube.com"], iframe[src*="youtu.be"], iframe[src*="youtube-nocookie.com"]');
    Array.prototype.forEach.call(list, function (f) {
      if (f.getAttribute('data-bd-yt') || /\/shorts\//.test(f.src)) return;
      f.setAttribute('data-bd-yt', '1');
      var p = f.parentElement;
      if (p && /height/.test(p.getAttribute('style') || '') && f.getAttribute('height') === '100%') {
        /* 에디봇 방식: 감싼 div 높이 고정 */
        p.style.setProperty('height', 'auto', 'important');
        p.style.setProperty('max-height', 'none', 'important');
        p.style.setProperty('aspect-ratio', '16 / 9');
        p.style.setProperty('vertical-align', 'top');
        f.style.display = 'block';
      } else if (/^\d+$/.test(f.getAttribute('height') || '')) {
        /* 일반 방식: iframe 자체에 width/height 숫자 */
        var w = parseInt(f.getAttribute('width'), 10) || 16, h = parseInt(f.getAttribute('height'), 10) || 9;
        f.style.setProperty('max-width', '100%', 'important');
        f.style.setProperty('height', 'auto', 'important');
        f.style.setProperty('aspect-ratio', w + ' / ' + h);
      }
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fix); else fix();
  window.addEventListener('load', fix);
})();
