/* 빛드론 상품 상세 구매 도움 — 2026-11-05 사장님 승인(비회원 구매 점검 A·B, 시안 3-나)
   A: 가격 밑 '네이버페이구매' 회색 줄을 숨기고, 같은 안내를 네이버페이 버튼 바로 위에
   B: 산업용(경로에 '산업용' 또는 300만 원 이상) 상품은 구매 버튼 아래 체크 카드 + [카톡으로 견적 요청하기][전화]
      카톡 단추: 빛드론 카카오톡 채널 채팅을 열고 '[견적 요청] 상품·링크·수량' 글을 복사(채팅창에 붙여넣기)
   되돌리기: 카페24 스크립트 태그에서 이 파일만 빼면 원래대로 */
(function () {
  if (window.__bdBuyHelp) return; window.__bdBuyHelp = 1;
  var KAKAO = 'https://pf.kakao.com/_xfExiyd/chat', TEL = '070-5176-7075';
  function run() {
    var npay = document.getElementById('NaverChk_Button');
    if (!npay || !npay.parentNode) return;              // 상품 상세가 아니면 아무것도 안 함
    var css = document.createElement('style');
    css.textContent =
      '.bdh-np{margin:10px 0 6px;font-size:13px;line-height:1.5;color:#333D4B;background:#F2FBF5;border:1px solid #C3E6CB;padding:8px 12px;border-radius:6px}.bdh-np b{color:#03A94D}' +
      '.bdh-q{margin:12px 0 4px;border:1.5px solid #191F28;border-radius:10px;overflow:hidden;background:#fff}' +
      '.bdh-q h4{margin:0;padding:10px 14px;background:#F2F4F6;color:#191F28;font-size:14.5px;font-weight:700}' +
      '.bdh-q ul{margin:0;padding:10px 14px 4px;list-style:none;display:grid;grid-template-columns:1fr 1fr;gap:4px 10px;font-size:13px;color:#333D4B}' +
      '.bdh-q li{margin:0}.bdh-q li:before{content:"\\2714  ";color:#191F28;font-weight:700}' +
      '.bdh-q .r{display:flex;gap:8px;padding:8px 14px 12px}' +
      '.bdh-q .r a{flex:1;display:flex;align-items:center;justify-content:center;flex-wrap:wrap;text-align:center;padding:11px 8px;font-weight:700;font-size:14px;text-decoration:none;border-radius:6px;box-sizing:border-box}' +
      '.bdh-q .q{background:#191F28;color:#fff!important}.bdh-q .t{background:#fff;color:#191F28!important;border:1.5px solid #191F28}' +
      '.bdh-kk{display:inline-block;width:16px;height:16px;border-radius:50%;background:#FEE500;margin-right:6px;position:relative;flex:0 0 16px}' +
      '.bdh-kk:after{content:"";position:absolute;left:4px;top:4px;width:8px;height:6px;border-radius:50%;background:#3C1E1E}' +
      '.bdh-mbr{display:none}' +
      '.bdh-toast{position:fixed;left:50%;bottom:90px;transform:translateX(-50%);background:#191F28;color:#fff;padding:12px 16px;border-radius:8px;font-size:13.5px;z-index:99999;box-shadow:0 6px 16px rgba(0,0,0,.25);max-width:90vw;line-height:1.5}' +
      '@media (max-width:640px){.bdh-mbr{display:block;width:100%;height:0}.bdh-q .r a{line-height:1.35}}';
    document.head.appendChild(css);

    // A. 회색 줄 숨기고 네이버페이 버튼 위 안내
    var rows = document.querySelectorAll('tr');
    for (var i = 0; i < rows.length; i++) {
      var th = rows[i].querySelector('th');
      if (th && th.textContent.replace(/\s/g, '') === '네이버페이구매') rows[i].style.display = 'none';
    }
    var note = document.createElement('div');
    note.className = 'bdh-np';
    note.innerHTML = '<b>로그인 없이</b> 아래 네이버페이로 바로 구매할 수 있어요.<br><span style="color:#6B7684">(회원 로그인 상태에서는 일반결제 · 적립금 적립)</span>';
    npay.parentNode.insertBefore(note, npay);

    // B. 산업용·고가 상품
    var path = (document.querySelector('.xans-product-headcategory, .path, .location') || {}).textContent || '';
    var price = parseInt(window.product_price || '0', 10) || 0;
    if (path.indexOf('산업용') < 0 && price < 3000000) return;
    var no = window.iProductNo || '';
    var mob = /Mobi|Android|iPhone/i.test(navigator.userAgent);
    var q = document.createElement('div');
    q.className = 'bdh-q';
    q.innerHTML = '<h4>기관·법인 담당자님, 이렇게 도와드려요</h4>' +
      '<ul><li>견적서·세금계산서</li><li>방문 납품</li><li>사용 교육</li><li>전주 직영 수리센터 A/S</li></ul>' +
      '<div class="r"><a class="q" href="' + KAKAO + '" target="_blank" rel="noopener"><i class="bdh-kk"></i>카톡으로<span class="bdh-mbr"></span> 견적 요청하기</a>' +
      '<a class="t" href="tel:' + TEL + '">' + (mob ? '전화 걸기' : TEL) + '</a></div>';
    npay.parentNode.insertBefore(q, note);
    q.querySelector('.q').addEventListener('click', function () {
      var name = ((document.querySelector('meta[property="og:title"]') || {}).content || document.title).replace(/\s*\|.*$/, '');
      var qty = (document.querySelector('#quantity') || {}).value || 1;
      var msg = ['[견적 요청]', '상품: ' + name, '링크: ' + location.origin + '/product/detail.html?product_no=' + no,
                 '수량: ' + qty, '기관·회사명: ', '요청 사항: '].join(String.fromCharCode(10));
      try {
        if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(msg);
        else { var t = document.createElement('textarea'); t.value = msg; t.style.position = 'fixed'; t.style.opacity = '0'; document.body.appendChild(t); t.select(); document.execCommand('copy'); t.remove(); }
      } catch (e) {}
      var o = document.createElement('div'); o.className = 'bdh-toast';
      o.innerHTML = '상품 정보를 복사했어요 📋<br>열린 카카오톡 채팅창에 <b>붙여넣기</b>만 하시면 됩니다.';
      document.body.appendChild(o); setTimeout(function () { o.remove(); }, 6000);
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run); else run();
})();
