/* 빛드론 상품 상세 구매 도움 — 2026-11-05 사장님 승인(비회원 구매 점검 A·B, 시안 3-나)
   A: 가격 밑 '네이버페이구매' 회색 줄을 숨기고, 같은 안내를 네이버페이 버튼 바로 위에
   B: 산업용(경로에 '산업용' 또는 300만 원 이상) 상품은 구매 버튼 아래 체크 카드 + [카톡으로 견적 요청하기][전화]
      카톡 단추: 빛드론 카카오톡 채널 채팅을 열고 '[견적 요청] 상품·링크·수량' 글을 복사(채팅창에 붙여넣기)
   D: 휴대폰 후기·문의 탭이 상세정보 칸에 갇히던 것 바로잡기(2026-11-05)
   C: 가격 아래 정보 표를 아이콘 타일 4칸으로(정품·무료배송/방문 납품·적립·직영 A/S) — 2026-11-05 사장님 승인
   되돌리기: 카페24 스크립트 태그에서 이 파일만 빼면 원래대로 */
(function () {
  if (window.__bdBuyHelp) return; window.__bdBuyHelp = 1;
  var KAKAO = 'https://pf.kakao.com/_xfExiyd/chat', TEL = '070-5176-7075';

  // 2026-11-05 정보 표 C안: 배송·적립·제조사·방문납품·서류·지원·상담 줄 → 아이콘 타일 4칸(+컨슈머 서류·상담 띠)
  function infoTiles() {
  function rowOf(label) {
    var rs = document.querySelectorAll('tr');
    for (var i = 0; i < rs.length; i++) { var th = rs[i].querySelector('th'); if (th && th.textContent.replace(/\s/g, '') === label) return rs[i]; }
    return null;
  }
  function val(r) { var td = r && r.querySelector('td'); return td ? td.textContent.replace(/\s+/g, ' ').trim() : ''; }
  var rShip = rowOf('배송비'), rPt = rowOf('적립금'), rDoc = rowOf('구매서류'), rTech = rowOf('기술지원'), rCs = rowOf('고객상담'), rMaker = rowOf('제조사');
  var rVisit = null; [].forEach.call(document.querySelectorAll('tr'), function (r) { var td = r.querySelector('td'), th = r.querySelector('th'); if (rVisit || !td || !th) return;
    var img = th.querySelector('img'), key = th.textContent + ' ' + (img ? (img.alt || '') + ' ' + decodeURIComponent(img.getAttribute('src') || '') : '');
    if (/방문\s*납품/.test(key + td.textContent) || (img && /(초기\s*세팅|무료\s*교육)/.test(td.textContent))) rVisit = r; });
  var rModel = rowOf('모델명');
  if (!rShip) return;
  var table = rShip.closest('table');
  var pv = val(rPt), amt = (pv.match(/^[\d,]+원/) || [''])[0], pct = (pv.match(/\(([\d.]+%)\)/) || [])[1] || '';
  var path = (document.querySelector('.xans-product-headcategory, .path, .location') || {}).textContent || '';
  var price = parseInt(window.product_price || '0', 10) || 0;
  var ind = path.indexOf('산업용') >= 0 || price >= 3000000;
  function ic(d) { return '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' + d + '</svg>'; }
  var maker = val(rMaker) || 'DJI', visit = rVisit ? val(rVisit).replace(/방문\s*납품\s*시\s*/, '').replace(/\s*및\s*/, '·') : '';
  var I = {
    badge: ic('<path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>'),
    truck: ic('<path d="M3 6h11v9H3zM14 9h4l3 3v3h-7"/><circle cx="7" cy="17" r="1.8"/><circle cx="17" cy="17" r="1.8"/>'),
    coin: ic('<circle cx="12" cy="12" r="8"/><path d="M9.5 9.5h4a1.8 1.8 0 0 1 0 3.6h-3a1.8 1.8 0 0 0 0 3.6h4M12 8v1.5M12 16.7v1.3"/>'),
    tool: ic('<path d="M14.5 6.5a4 4 0 0 0-5 5L4 17l3 3 5.5-5.5a4 4 0 0 0 5-5l-2.5 2.5-2.5-.5-.5-2.5z"/>'),
    doc: ic('<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/>'),
    van: ic('<path d="M2 7h12v8H2zM14 10h4l3 3v2h-7"/><circle cx="6" cy="17" r="1.8"/><circle cx="17" cy="17" r="1.8"/><path d="M5 10.5h5"/>'),
    cap: ic('<path d="M2 9l10-5 10 5-10 5z"/><path d="M6 11v5c2 2 10 2 12 0v-5M22 9v5"/>'),
    phone: ic('<path d="M6 3h3l2 5-2.5 1.5a11 11 0 0 0 6 6L16 13l5 2v3a2 2 0 0 1-2 2A16 16 0 0 1 4 5a2 2 0 0 1 2-2z"/>')
  };
  var css = document.createElement('style');
  css.textContent =
    '.ivc-m{display:flex;align-items:baseline;gap:12px;margin:4px 0 10px;font-size:14px}.ivc-m span{flex:0 0 auto;min-width:120px;color:#191F28;font-weight:600}.ivc-m b{font-weight:500;color:#4E5968}' +
    '.ivc-t.n5{grid-template-columns:repeat(5,minmax(0,1fr));gap:6px}.ivc-t.n5 div{padding:11px 4px 10px}.ivc-t.n5 b{font-size:13px}.ivc-t.n5 .pt b{font-size:14px}.ivc-t.n5 em{font-size:11.5px}' +
    '.ivc{margin:8px 0 14px}.ivc-t{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.ivc-t.n3{grid-template-columns:repeat(3,minmax(0,1fr))}' +
    '.ivc-t div{border:1.5px solid #E5E8EB;border-radius:10px;padding:12px 8px 11px;text-align:center;background:#fff}' +
    '.ivc-t i{display:inline-flex;align-items:center;justify-content:center;width:40px;height:40px;border-radius:50%;background:#F2F4F6;color:#191F28;margin-bottom:6px}' +
    '.ivc-t b{display:block;font-size:14px;color:#191F28;line-height:1.3}.ivc-t em{display:block;font-style:normal;font-size:12px;color:#6B7684;margin-top:2px;line-height:1.35}' +
    '.ivc-t .pt{border-color:#7BD4A0;background:#F0FBF4}.ivc-t .pt i{background:#D3F5DF;color:#0B7A3B}.ivc-t .pt b{color:#0B7A3B;font-size:15px}' +
    '.ivc-s{display:flex;flex-wrap:wrap;gap:6px 16px;margin-top:10px;padding:10px 12px;background:#F9FAFB;border-radius:8px;font-size:12.5px;color:#333D4B}' +
    '.ivc-s span{display:inline-flex;align-items:center;gap:6px}.ivc-s svg{width:16px;height:16px}.ivc-s a{color:#191F28;font-weight:700}' +
    '@media (max-width:640px){.ivc-t{grid-template-columns:repeat(2,minmax(0,1fr))}.ivc-t.n5{grid-template-columns:repeat(2,minmax(0,1fr))}.ivc-t.n5 .pt{grid-column:1/-1;order:9}.ivc-t.n3{grid-template-columns:repeat(3,minmax(0,1fr))}}';
  document.head.appendChild(css);
  var box = document.createElement('div'); box.className = 'ivc';
  // 2026-11-06 전 상품 점검 반영: 적립 없는 상품·견적 상품(가격 1,000원 미만)은 적립 칸 빼기, DJI 아닌 제조사엔 '공식 딜러' 안 씀,
  //   소프트웨어(S/W 분류)는 무료배송·직영 A/S 대신 정품 라이선스·납품 서류·기술 지원
  var hasPt = !!(amt && pct && !/^0(\.0+)?%$/.test(pct)) && price >= 1000;
  var isSw = /S\/W|소프트웨어/.test(path);
  var mk = maker.trim(), isDji = /^dji$/i.test(mk), plain = /자체|^$/.test(mk);
  var T = [];
  if (isSw) T.push('<div><i>' + I.badge + '</i><b>정품 라이선스</b><em>' + (isDji ? 'DJI 공식 딜러' : plain ? '정품만 판매' : '제조사 ' + mk) + '</em></div>');
  else T.push('<div><i>' + I.badge + '</i>' + (isDji ? '<b>DJI 정품</b><em>제조사 DJI 공식 딜러</em>' : plain ? '<b>정품 보증</b><em>정품만 판매합니다</em>' : '<b>' + mk + ' 정품</b><em>제조사 ' + mk + '</em>') + '</div>');
  if (isSw) T.push('<div><i>' + I.doc + '</i><b>납품 서류</b><em>공공기관·학교·기업</em></div>');
  else T.push('<div><i>' + I.truck + '</i><b>무료배송</b><em>5만 원 이상 구매 시</em></div>');
  if (rVisit) T.push('<div class="edu"><i>' + I.cap + '</i><b>무료 교육·세팅</b><em>방문 납품 시 제공</em></div>');   // 2026-11-06 사장님: 방문납품은 무료 교육·초기 세팅 때문
  if (hasPt) T.push('<div class="pt"><i>' + I.coin + '</i><b>' + amt + '</b><em>회원 적립 ' + pct + '</em></div>');
  T.push(isSw ? '<div><i>' + I.phone + '</i><b>기술 지원</b><em>빛드론 고객센터 상담</em></div>' : '<div><i>' + I.tool + '</i><b>직영 A/S</b><em>전주 수리센터</em></div>');
  var n = T.length;
  box.innerHTML = '<div class="ivc-t n' + n + '">' + T.join('') + '</div>' +
    (ind || isSw ? '' : '<div class="ivc-s"><span>' + I.doc + '공공기관·학교·기업 납품 서류 가능</span><span>' + I.phone + '상담 <a href="tel:070-5176-7075">070-5176-7075</a></span></div>');
  if (rModel && val(rModel)) {                         // 2026-11-06 사장님: 모델명 → 타일 순서
    var mdl = document.createElement('div'); mdl.className = 'ivc-m';
    mdl.innerHTML = '<span>모델명</span><b></b>'; mdl.querySelector('b').textContent = val(rModel);
    table.parentNode.insertBefore(mdl, table);
  }
  table.parentNode.insertBefore(box, table);
  [rShip, rPt, rDoc, rTech, rCs, rMaker, rVisit, rModel].forEach(function (r) { if (r) r.style.display = 'none'; });
  }

  // 2026-11-05 휴대폰 '상품후기·상품문의·구매안내' 탭이 안 열리던 문제: 공통 하단(구매시 유의사항 그림)의 <center><div>가 안 닫혀
  //   후기·문의 칸이 상세정보 칸 안으로 들어감 → 상세정보 칸 밖(바로 뒤)으로 꺼내 제자리에 둔다. 스킨을 고치면 이 부분은 할 일이 없어짐.
  function fixTabs() {
    var dt = document.getElementById('detail');
    if (!dt || !dt.parentNode) return;
    var ref = dt;
    [].slice.call(dt.querySelectorAll('div[class*="prd_tab0"]')).forEach(function (s) { ref.parentNode.insertBefore(s, ref.nextSibling); ref = s; });
  }
  function run() {
    try { fixTabs(); } catch (e) {}
    try { infoTiles(); } catch (e) {}
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
