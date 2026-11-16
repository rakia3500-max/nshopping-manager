/* 두 몰 상품 상세 폭 맞춤 (2026-11-16 사장님 ⑤ '상세페이지 사이즈 안 맞음')
   - 그 상품 상세에서 큰 그림이 가장 많이 쓴 폭(W)을 기준으로, 영상(유튜브 iframe)·표·색 상자처럼 단독으로 놓인 큰 덩어리를 W에 맞추고 가운데 정렬
   - 상세 칸보다 넓은 덩어리(예: DJI 페이지에서 가져온 1260px 글 상자)는 칸 폭으로 줄임
   - 그림은 원본보다 크게 늘리지 않음(늘어난 그림은 원본 크기로)
   - 두 칸·세 칸 카드처럼 W의 60% 미만인 것, 그림 여러 장 묶음 상자는 건드리지 않음
   - PC 화면(가로 900px 이상)에서 전부 동작. 휴대폰은 '칸보다 넓은 덩어리 줄이기'(1·1-1)만 — 독3 계열 휴대폰 가로 넘침(1270px) 해결(11-16 사장님 '같이 고치기')
   빛드론: #prdDetail .cont / 드론박스 PC: .detail_explain_box .txt-manual / 드론박스 휴대폰(m.drone-box.co.kr): .js_goods_description
   되돌리기: 이 파일을 불러오는 스크립트 태그(빛드론)·외부 스크립트(드론박스)에서 빼면 원래대로 */
(function () {
  if (window.__bdDetailFit) return; window.__bdDetailFit = 1;
  function root() { return document.querySelector('#prdDetail .cont') || document.querySelector('.detail_explain_box .txt-manual') || document.querySelector('.js_goods_description'); }
  function padX(el) { var cs = getComputedStyle(el); return parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight) + parseFloat(cs.borderLeftWidth) + parseFloat(cs.borderRightWidth); }
  function cw(el) { var cs = getComputedStyle(el); return el.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight); }
  function center(e) { e.style.marginLeft = 'auto'; e.style.marginRight = 'auto'; }
  // e의 조상(상세 칸 전까지) 중 '최대 폭'이 W보다 좁게 묶인 틀을 W(+안쪽 여백)까지 풀어 줌
  function openUp(e, r, W) {
    for (var p = e.parentElement; p && p !== r; p = p.parentElement) {
      var mw = parseFloat(getComputedStyle(p).maxWidth);
      if (!(mw && mw < W + padX(p) - 1 && mw >= 0.6 * W)) continue;
      // 그림이 든 틀은 넓히지 않음(넓히면 그림이 원래보다 커짐 — 11-16 빛드론 552에서 확인)
      var hasImg = [].some.call(p.querySelectorAll('img'), function (im) { return im.getBoundingClientRect().width >= 300; });
      if (hasImg) return false;
      p.style.maxWidth = (W + padX(p)) + 'px';
    }
    return true;
  }
  function run() {
    // 넘치는 상자가 있으면 휴대폰 innerWidth가 1270처럼 커지므로 기기 화면 폭·휴대폰 주소로 판단
    var mob = Math.min(window.innerWidth, screen.width || 9999) < 900 || /^m\./.test(location.hostname);
    var r = root(); if (!r) return;
    var R = cw(r); if (R < (mob ? 200 : 600)) return;
    // 1) 칸보다 넓은 덩어리 → 칸 폭
    [].forEach.call(r.querySelectorAll('div,section,table,figure,p,ul,iframe,img,video'), function (e) {
      if (e.getBoundingClientRect().width > R + 2) { e.style.maxWidth = '100%'; e.style.boxSizing = 'border-box'; if (e.tagName === 'IMG') e.style.height = 'auto'; e.setAttribute('data-bdshrink', '1'); }
    });
    // 1-1) 줄인 글 상자가 높이 고정이라 글이 잘리면 높이를 글에 맞춤
    [].forEach.call(r.querySelectorAll('[data-bdshrink]'), function (e) {
      if (e.tagName === 'IMG' || e.tagName === 'IFRAME') return;
      if (e.scrollHeight > e.clientHeight + 4) { e.style.height = 'auto'; e.style.minHeight = e.clientHeight + 'px'; }
    });
    if (mob) return;   // 휴대폰은 여기까지(넘침만 바로잡음)
    // 2) 늘어난 그림 → 원본 폭까지만
    [].forEach.call(r.querySelectorAll('img'), function (im) {
      var w = im.getBoundingClientRect().width;
      if (im.naturalWidth > 100 && w > im.naturalWidth + 10) { im.style.maxWidth = im.naturalWidth + 'px'; im.style.height = 'auto'; center(im); }
    });
    // 3) 기준 폭 W = 큰 그림이 가장 많이 차지한 폭(면적 기준)
    var area = {};
    [].forEach.call(r.querySelectorAll('img'), function (im) {
      var b = im.getBoundingClientRect(); if (b.width < Math.max(400, 0.55 * R) || b.height < 60) return;   // 작은 그림(두 칸 그림 등)은 기준에서 뺌
      var w = Math.round(b.width); area[w] = (area[w] || 0) + b.height;
    });
    var W = 0, best = 0; for (var k in area) if (area[k] > best) { best = area[k]; W = +k; }
    if (best < 500) return;   // 큰 그림이 덜 떴으면(높이 합 500px 미만) 다음 차례에 — 잘못된 기준 폭 방지(11-16 514 영상 498px 사고)
    if (!W) return;   // 잴 그림이 아직 없으면(늦게 뜨는 그림) 다음 차례에
    W = Math.min(W, R);
    // 4) 영상 → W (16:9 틀 안 영상은 틀이 높이를 맞춤)
    [].forEach.call(r.querySelectorAll('iframe'), function (f) {
      if (!/youtube|youtu\.be|vimeo/.test(f.src || f.getAttribute('data-src') || '')) return;
      if (openUp(f, r, W) === false) return;
      if (getComputedStyle(f).position === 'absolute') {   // 16:9 비율 틀(padding-bottom) 안 영상 → 틀을 W로
        var fp = f.parentElement;
        if (fp && fp !== r && fp.getBoundingClientRect().width > W + 12) { fp.style.maxWidth = W + 'px'; center(fp); }
        return;
      }
      if (cw(f.parentElement) < W - 2) return;
      f.style.width = W + 'px'; f.style.maxWidth = '100%'; f.style.height = Math.round(W * 9 / 16) + 'px'; f.style.display = 'block'; center(f);
    });
    // 5) 단독 표·색 상자 → W
    [].forEach.call(r.querySelectorAll('table,div,section,figure'), function (e) {
      var b = e.getBoundingClientRect(); if (b.height < 40) return;
      var w = Math.round(b.width); if (w < 0.6 * W || Math.abs(w - W) <= 12 || w > W + 12) return;
      var cs = getComputedStyle(e);
      var boxy = e.tagName === 'TABLE' || cs.backgroundColor !== 'rgba(0, 0, 0, 0)' || parseFloat(cs.borderTopWidth) > 0 || cs.boxShadow !== 'none';
      if (!boxy || e.querySelectorAll('img').length > 2) return;
      // 이미 맞춘 상자 안의 표·상자는 건너뜀(바깥 상자만 맞춤)
      for (var q = e.parentElement; q && q !== r; q = q.parentElement) if (q.getAttribute('data-bdfit')) return;
      if (openUp(e, r, W) === false) return;
      var p = e.parentElement; if (!p || cw(p) < W - 2) return;
      e.style.width = W + 'px'; e.style.maxWidth = '100%'; e.style.boxSizing = 'border-box'; center(e); e.setAttribute('data-bdfit', '1');
    });
  }
  var n = 0, t = null;
  function go() { run(); setTimeout(run, 1500); setTimeout(run, 4000); setTimeout(run, 8000);
    // 늦게 뜨는 그림(스크롤해야 뜸) 대비: 스크롤 멈출 때마다 다시 맞춤(최대 15번)
    window.addEventListener('scroll', function () { if (n >= 15) return; clearTimeout(t); t = setTimeout(function () { n++; run(); }, 400); }, {passive: true}); }
  if (document.readyState === 'complete') go(); else window.addEventListener('load', go);
})();
