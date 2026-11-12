/* 빛드론: 카페24 기본 주소(dronebox2.cafe24.com)로 들어온 손님을 대표 주소(bit-drone.shop) 같은 페이지로 (2026-11-12 사장님 "켜줘")
   카페24 관리자에 '기본 도메인 → 대표 도메인 이동' 설정이 없어 스크립트로 대신함. 관리자(/disp)에는 스크립트가 안 붙음.
   주문서·로그인·마이쇼핑·처리 주소·디자인 미리보기는 넘기지 않음(진행 중인 주문·로그인이 끊기지 않게). */
(function () {
  var h = location.hostname, p = location.pathname, q = location.search;
  if (!/^(m\.|www\.)?dronebox2\.cafe24\.com$/i.test(h)) return;
  if (/^\/(order|member|myshop|exec|disp|api|skin-|admin|board\/.*write)/i.test(p) || /preview|skin_no|layout_preview/i.test(q)) return;
  location.replace('https://bit-drone.shop' + p + q + location.hash);
})();
