/* 빛드론(bit-drone.shop) 첫 화면 다듬기 (2026-11-10, unslop 점검 → 사장님 승인 항목만)
 * 카페24 스크립트태그로 전 페이지에 붙는다. 디자인 파일 권한이 없어 스크립트로 넣는다.
 * 1) 상단 메뉴: PC 1440px에서 'DJI 매/빅'처럼 두 줄로 쪼개지던 것 → 한 줄
 * 2) 메인 섹션 제목 앞 이모지 16개 제거(✈️🎇🪂🚁 …) + 제목 굵기 한 단계 낮춤
 * 3) 메인 '카메라·임무장비' 진열에서 0원으로 보이던 견적 상품 → '가격 상담 필요'(다른 진열과 같은 문구)
 * 4) 메인 상품 후기: 제목 뒤 '(… 에 등록된 네이버 페이 구매평)' 기록 문구 제거,
 *    '이미지가 없는 리뷰입니다' 빈 그림 → 해당 상품 사진
 * 되돌리기: 이 스크립트태그만 지우면 원래대로.
 */
(function () {
  if (window.__bdMainTidy) return;
  window.__bdMainTidy = true;

  var css = [
    /* 1 메뉴 */
    '#mh_nav_box .mh_sec02{gap:24px}',
    '#mh_nav_box .mh_mypage{flex:none!important}',
    '#mh_nav_box .mh_category{display:flex;flex:1 1 auto!important;min-width:0;width:auto!important;justify-content:flex-start}',
    '#mh_nav_box .mh_category ul{margin:0!important;padding:0!important;width:auto!important;display:flex;flex-wrap:nowrap;align-items:center}',
    '#mh_nav_box .mh_category ul:first-child{display:none}',
    '#mh_nav_box .mh_category ul li{flex:none!important;width:auto!important;margin:0!important;padding:0!important}',
    '#mh_nav_box .mh_category ul li a{white-space:nowrap!important;font-size:15px!important;padding:0 10px!important;margin:0!important;width:auto!important;letter-spacing:0}',
    '#mh_nav_box .mh_mypage a{white-space:nowrap!important}',
    /* 2 제목 굵기 */
    '.title_area .t01{font-weight:600!important}',
    /* 3 가격 상담 필요 */
    '.bd-consult{font-size:14px!important;color:#555!important;font-weight:500}',
    /* 4 빈 사진 후기 */
    '.bd-noimg .thumb{background:#f4f4f2;display:flex!important;align-items:center;justify-content:center}',
    '.bd-noimg .thumb img{width:55%!important;height:auto!important;object-fit:contain}'
  ].join('\n');
  var st = document.createElement('style');
  st.id = 'bd-main-tidy';
  st.appendChild(document.createTextNode(css));
  (document.head || document.documentElement).appendChild(st);

  var EMOJI = /(?![©®™])\p{Extended_Pictographic}️?\s?/gu;
  var REVIEW_META = /\(\s*\d{4}-\d{2}-\d{2}[^)]*구매평\s*\)/;

  function tidy() {
    // 2 제목 이모지 (섹션 제목만 — 상품명·후기 글은 건드리지 않음)
    document.querySelectorAll('.title_area .t01').forEach(function (el) {
      var w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT), n;
      while ((n = w.nextNode())) {
        if (EMOJI.test(n.nodeValue)) { EMOJI.lastIndex = 0; n.nodeValue = n.nodeValue.replace(EMOJI, ''); }
        EMOJI.lastIndex = 0;
      }
    });
    // 3 0원 → 가격 상담 필요 (메인 프로모션 진열의 판매가 칸만)
    document.querySelectorAll('.morenvy-product .price .m_item').forEach(function (el) {
      if (/^\s*0원\s*$/.test(el.textContent)) { el.textContent = '가격 상담 필요'; el.className += ' bd-consult'; }
    });
    // 4 후기
    document.querySelectorAll('.xans-board-list-4 li').forEach(function (li) {
      var t = li.querySelector('.t01');
      if (t && REVIEW_META.test(t.textContent)) {
        var w = document.createTreeWalker(t, NodeFilter.SHOW_TEXT), n;
        while ((n = w.nextNode())) n.nodeValue = n.nodeValue.replace(REVIEW_META, '');
      }
      var th = li.querySelector('.thumb img'), prd = li.querySelector('.bottom .img img');
      if (th && prd && prd.src && /no_image/.test(th.src) && !li.classList.contains('bd-noimg')) {
        th.removeAttribute('onerror');
        th.src = prd.src;
        li.classList.add('bd-noimg');
      }
    });
  }

  function run() {
    try { tidy(); } catch (e) {}
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run); else run();
  window.addEventListener('load', run);
  // 슬라이드 복제·늦게 붙는 후기 사진(onerror)까지 잡기 위해 처음 15초만 한 번 더씩
  var tries = 0, iv = setInterval(function () { run(); if (++tries >= 15) clearInterval(iv); }, 1000);
})();
