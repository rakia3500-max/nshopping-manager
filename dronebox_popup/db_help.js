/* 드론박스 구매 도움 (2026-11-06 사장님 승인, 고객 행동 녹화 점검 후속)
   B: 상세 구매 칸에 "로그인 없이 바로구매·네이버페이" 안내 (쿠폰적용이 회원 전용이라 로그인하러 가는 손님 막기)
   C: 주문하러 온 로그인 화면에서 '비회원 주문하기'를 로그인 단추 바로 밑으로
   D: 휴대폰 상세·장바구니·주문·로그인 화면에서 '상담하기' 단추를 작은 동그라미로, 구매 단추 위쪽으로
   E: 장바구니 5만 원 미만이면 "○원 더 담으면 무료배송" 안내
   X: 비어 있는 '검수상품보기' 링크, 깨진 옛 쿠폰 그림(210831coupon.jpg) 숨김
   Q(11-12): 비회원이 상품문의 쓰기를 누르면 [카톡 문의][로그인하고 글][전화] 작은 창, 문의 0건 칸에도 단추 (PC·휴대폰)
   R(11-12): 경로 글자 — 상세 'HOME'(#)과 펼쳐지지 않는 분류 이름을 실제 목록 주소로 (PC·휴대폰)
   개인정보·쿠키를 읽거나 밖으로 보내지 않음. 화면 글자·배치만 바꿈. 빼면 원래대로. */
(function () {
  var FREE = 50000;
  var mob = /^m\./.test(location.hostname);
  var path = location.pathname;

  function txt(e) { return ((e && (e.innerText || e.textContent)) || '').replace(/\s+/g, ' ').trim(); }
  function num(s) { var m = String(s).replace(/,/g, '').match(/(\d+)\s*원/); return m ? +m[1] : 0; }

  function css() {
    if (document.getElementById('dbh-css')) return;
    var c = document.createElement('style'); c.id = 'dbh-css';
    c.textContent =
      '.secondhand_goods_mobile{display:none!important}img[src*="210831coupon"]{display:none!important}' +
      'a.kakaoChatPc.dbh-d{width:46px!important;height:46px!important;overflow:hidden!important;right:8px!important;bottom:178px!important;border-radius:50%!important}' +
      'a.kakaoChatPc.dbh-d img{width:108px!important;max-width:none!important;margin:0!important}' +
      '.dbh-b{margin:8px 0;padding:8px 12px;font-size:13px;line-height:1.5;color:#333D4B;background:#F2FBF5;border:1px solid #C3E6CB;border-radius:6px;text-align:left}.dbh-b b{color:#03A94D}' +
      '.dbh-c{display:block;margin:10px 0 0;padding:13px 0;border:1.5px solid #1C88CB;color:#1C88CB!important;background:#fff;text-align:center;font-size:16px;font-weight:700;text-decoration:none}' +
      '.dbh-c small{display:block;font-size:12.5px;font-weight:400;color:#6B7684;margin-top:2px}' +
      '.dbh-e{margin:12px 20px 4px;padding:10px 12px;background:#EAF6FC;border-radius:8px;font-size:14px;color:#191F28}.dbh-e b{color:#1C88CB}' +
      '.dbh-e .bar{height:6px;background:#D3E8F5;border-radius:3px;margin-top:7px;overflow:hidden}.dbh-e .bar i{display:block;height:100%;background:#1C88CB;border-radius:3px}';
    (document.head || document.documentElement).appendChild(c);
  }

  // D
  function smallChat() {
    if (!/goods_view|\/order\/|\/member\/login/.test(path)) return;
    var k = document.querySelector('a.kakaoChatPc'); if (k) k.classList.add('dbh-d');
  }

  // B: 상세 구매 칸(펼침 칸) 단추 위
  function buyNote() {
    if (path.indexOf('goods_view') < 0 || document.querySelector('.dbh-b')) return;
    var pb = document.querySelector('.price_box');                // 견적·가격 문의 상품(가격 칸에 'n원'이 없음)은 안내 안 함
    if (!pb || !/\d\s*원/.test(txt(pb)) || /견적|문의/.test(txt(pb))) return;
    var bar = document.querySelector('.ly_buy_dn .detail_prd_btn, .ly_buy_dn.js_goods_view_buy_btn .detail_prd_btn');
    var outer = [].filter.call(document.querySelectorAll('.detail_prd_btn.st_btn_buy_outer'), function (e) { return !e.closest('.detail_buy_top_btn'); })[0] || bar;
    if (!outer || !outer.parentNode) return;
    var cp = !!document.querySelector('.coupon_apply_btn');
    var n = document.createElement('div'); n.className = 'dbh-b';
    n.innerHTML = '<b>로그인 없이</b> 바로구매·네이버페이로 살 수 있어요.' + (cp ? '<br><span style="color:#6B7684">(쿠폰적용은 회원 전용이에요)</span>' : '');
    outer.parentNode.insertBefore(n, outer);
  }

  // C: 주문하러 온 로그인 화면
  function guestUp() {
    if (path.indexOf('/member/login') < 0 || document.querySelector('.dbh-c')) return;
    var g = [].filter.call(document.querySelectorAll('a,button'), function (b) { return txt(b).replace(/\s/g, '') === '비회원주문하기'; })[0];
    var sub = document.querySelector('.member_login_btn');
    if (!g || !sub) return;
    var a = document.createElement('a'); a.className = 'dbh-c'; a.href = '#';
    a.innerHTML = '비회원으로 바로 주문하기<small>가입·로그인 없이 주문할 수 있어요</small>';
    a.addEventListener('click', function (e) { e.preventDefault(); g.click(); });   // 원래 단추 동작 그대로
    var box = sub.closest('.submit') || sub; box.parentNode.insertBefore(a, box.nextSibling);
    var old = g.closest('div') || g; old.style.display = 'none';
    [].forEach.call(document.querySelectorAll('h3,h4,strong,p'), function (e) { if (txt(e) === '비회원 주문') e.style.display = 'none'; });
  }

  // E: 장바구니 무료배송까지 남은 금액
  function freeShip() {
    if (path.indexOf('/order/cart') < 0 || document.querySelector('.dbh-e')) return;
    var row = null, tot = 0, ship = 0;
    [].forEach.call(document.querySelectorAll('dt,th,span,div,p,strong'), function (e) {
      var t = txt(e);
      if (!row && t === '총 상품금액') { row = e.parentElement; tot = num(txt(row)); }
      if (!ship && t === '배송비') ship = num(txt(e.parentElement));
    });
    if (!row || !tot || tot >= FREE || !ship) return;
    var left = FREE - tot, el = document.createElement('div'); el.className = 'dbh-e';
    el.innerHTML = '<b>' + left.toLocaleString() + '원</b> 더 담으면 <b>무료배송</b>이에요 (5만 원 이상)<div class="bar"><i style="width:' + Math.round(tot * 100 / FREE) + '%"></i></div>';
    var anchor = row; while (anchor.parentElement && txt(anchor.parentElement).indexOf('총 합계금액') < 0) anchor = anchor.parentElement;
    var wrap = anchor.parentElement || row.parentElement; wrap.parentNode.insertBefore(el, wrap);
  }

  // 2026-11-12 Q: 상품문의 — 쓰기는 회원 전용이라 비회원은 '로그인이 필요한 서비스' 경고만 보고 막힘(녹화 27분 손님)
  //   → 비회원이 쓰기·문의하기를 누르면 [카톡으로 바로 문의][로그인하고 쓰기] 작은 창. 문의 0건 칸에도 같은 단추.
  var TEL = '0507-1337-7089';
  function guest() { return !!document.querySelector('a[href*="member/login.php"]') && !document.querySelector('a[href*="logout"]'); }
  function css2() {
    if (document.getElementById('dbh-css2')) return;
    var c = document.createElement('style'); c.id = 'dbh-css2';
    c.textContent =
      '.dbh-qa{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;align-items:center;padding:6px 0}.dbh-qa p{width:100%;margin:0 0 4px;color:#4E5968;font-size:14px}' +
      '.dbh-qb{display:inline-flex;align-items:center;gap:6px;padding:10px 16px;border-radius:6px;font-size:14px;font-weight:700;text-decoration:none;cursor:pointer;border:1.5px solid #1C88CB;background:#fff;color:#1C88CB!important}' +
      '.dbh-qb.k{background:#FEE500;border-color:#FEE500;color:#191F28!important}' +
      '.dbh-ly{position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:100000;display:flex;align-items:center;justify-content:center;padding:16px}' +
      '.dbh-ly .in{background:#fff;border-radius:12px;max-width:340px;width:100%;padding:20px 18px 16px;text-align:center;box-shadow:0 8px 24px rgba(0,0,0,.2)}' +
      '.dbh-ly h4{margin:0 0 6px;font-size:17px;color:#191F28}.dbh-ly p{margin:0 0 14px;font-size:13.5px;color:#4E5968;line-height:1.5}' +
      '.dbh-ly .dbh-qb{display:flex;justify-content:center;width:100%;box-sizing:border-box;margin-top:8px}.dbh-ly .x{margin-top:10px;font-size:13px;color:#8B95A1;background:none;border:0;cursor:pointer}';
    (document.head || document.documentElement).appendChild(c);
  }
  function kakao() { try { if (typeof kakaoChatStart === 'function') { kakaoChatStart(); return; } } catch (e) {} location.href = 'tel:' + TEL; }
  function qaLayer(goWrite) {
    var ly = document.createElement('div'); ly.className = 'dbh-ly';
    ly.innerHTML = '<div class="in"><h4>상품 문의하기</h4><p>글로 남기는 상품문의는 회원만 쓸 수 있어요.<br>로그인 없이 카톡으로 바로 물어보세요.</p>' +
      '<a class="dbh-qb k" data-a="k">카톡으로 바로 문의</a><a class="dbh-qb" data-a="w">로그인하고 글 남기기</a>' +
      '<a class="dbh-qb" href="tel:' + TEL + '">전화 ' + TEL + '</a><button type="button" class="x" data-a="x">닫기</button></div>';
    ly.addEventListener('click', function (e) {
      var a = e.target.closest('[data-a]'); if (!a && e.target !== ly) return;
      var k = a ? a.getAttribute('data-a') : 'x';
      if (k === 'k') { e.preventDefault(); ly.remove(); kakao(); }
      else if (k === 'w') { e.preventDefault(); ly.remove(); goWrite(); }
      else if (k === 'x') { ly.remove(); }
    });
    document.body.appendChild(ly);
  }
  function qaHelp() {
    if (path.indexOf('goods_view') < 0) return;
    css2();
    if (!window.__dbhQa) {
      window.__dbhQa = 1;
      document.addEventListener('click', function (e) {          // 비회원만 가로챔(회원은 원래대로 글쓰기)
        var b = e.target.closest && e.target.closest('a.btn_qna_write, a[href*="bdId=goodsqa"], .dbh-qw');
        if (!b || !guest()) return;
        e.preventDefault(); e.stopPropagation();
        var nx = encodeURIComponent(location.pathname + location.search);
        qaLayer(function () { location.href = (mob ? '/member/login.php?returnUrl=' : '../member/login.php?returnUrl=') + nx; });
      }, true);
    }
    var fill = function () {                                       // 문의 0건 칸 — 글자만 있던 자리에 단추
      var nd = document.querySelector('#ajax-goods-goodsqa-list .no_data');
      if (!nd || nd.querySelector('.dbh-qa')) return;
      nd.innerHTML = '<div class="dbh-qa"><p>아직 문의가 없어요. 궁금한 점을 편하게 물어보세요.</p>' +
        '<a class="dbh-qb k" href="#" data-k="1">카톡으로 바로 문의</a><a class="dbh-qb dbh-qw" href="#">문의 글 남기기</a></div>';
      nd.querySelector('[data-k]').addEventListener('click', function (e) { e.preventDefault(); kakao(); });
      nd.querySelector('.dbh-qw').addEventListener('click', function (e) {
        if (guest()) return;                                        // 비회원은 위 가로채기가 작은 창을 띄움
        e.preventDefault(); var w = document.querySelector('a.btn_qna_write'); if (w) w.click();
      });
    };
    fill(); setTimeout(fill, 1500); setTimeout(fill, 4000);
  }

  // 2026-11-12 R: 경로 글자 — 상세의 'HOME'(주소 '#')과 펼쳐지지 않는 분류 이름을 실제 주소로
  function crumbFix() {
    [].forEach.call(document.querySelectorAll('a.local_home'), function (a) { if (a.getAttribute('href') === '#') a.setAttribute('href', '/'); });
    [].forEach.call(document.querySelectorAll('.location_select'), function (s) {
      var t = s.querySelector('.location_tit a'), items = s.querySelectorAll('ul a[href]');
      if (!t || items.length !== 1) return;                         // 고를 분류가 하나뿐일 때만(여러 개면 원래 펼침 그대로)
      var m = (items[0].getAttribute('href') || '').match(/(?:cateCd|Cd)=(\w+)/);   // 상세에선 '?Cd=002'가 상세 주소에 붙어 틀림 → 목록 주소로
      var to = m ? '/goods/goods_list.php?cateCd=' + m[1] : items[0].href;
      t.setAttribute('href', to);
      t.addEventListener('click', function (e) { e.preventDefault(); e.stopPropagation(); location.href = to; }, true);
    });
  }

  function run() {
    css();
    [qaHelp, crumbFix].forEach(function (f) { try { f(); } catch (e) {} });   // PC·휴대폰 모두
    if (!mob) return;                         // B·C·D·E는 휴대폰 화면만 (X는 CSS로 PC도)
    [smallChat, buyNote, guestUp, freeShip].forEach(function (f) { try { f(); } catch (e) {} });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run); else run();
})();
