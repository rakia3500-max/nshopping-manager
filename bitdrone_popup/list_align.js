/* 빛드론(bit-drone.shop) 상품 목록 줄맞춤 (2026-09-22)
 * 카페24 스크립트태그로 전 페이지에 붙는다. 디자인 파일 권한이 없어 스타일을 스크립트로 넣는다.
 * 1) 사진 칸 정사각형 고정 (가로로 긴 사진 때문에 이름이 위로 올라가던 문제)
 * 2) 상품명 2줄 높이 고정
 * 3) 가격을 이름 바로 아래로 (모델명·요약 문구 유무에 따라 가격이 밀리던 문제)
 */
(function () {
  if (document.getElementById('bd-list-align')) return;
  var css = [
    '.prdList__item .thumbnail{aspect-ratio:1/1;display:flex!important;align-items:center;justify-content:center;overflow:hidden}',
    '.prdList__item .thumbnail>a{display:flex!important;align-items:center;justify-content:center;width:100%;height:100%}',
    '.prdList__item .thumbnail>a>img{max-width:100%!important;max-height:100%!important;width:auto!important;height:auto!important;object-fit:contain}',
    '.prdList__item .description .name{min-height:48px;box-sizing:border-box}',
    '.prdList__item .description .name>a{display:-webkit-box!important;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden}',
    '.prdList__item .spec{display:flex!important;flex-direction:column}',
    '.prdList__item .spec li[rel="소비자가"]{order:-3}',          /* 소비자가 */
    '.prdList__item .spec li[rel="판매가"]{order:-2}',                /* 판매가 */
    '.prdList__item .spec li[rel="할인판매가"]{order:-1}',    /* 할인판매가 */
    '.prdList__item .spec li[rel="상품요약정보"] .m_item{display:-webkit-box!important;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden}' /* 상품요약정보 */
  ].join('\n');
  var st = document.createElement('style');
  st.id = 'bd-list-align';
  st.appendChild(document.createTextNode(css));
  (document.head || document.documentElement).appendChild(st);
})();
