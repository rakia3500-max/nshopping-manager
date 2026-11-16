/* 빛드론 PC 상단 메가메뉴 (시안 2) — 2026-11-16 사장님 선택("시안 2 메가메뉴").
   메뉴에 마우스를 올리면 가로 판: 왼쪽 하위 분류 + 오른쪽 대표 상품 사진 + 아래 고객지원 줄.
   PC(가로 1024px 이상, 마우스 사용)에서만 동작. 휴대폰·태블릿은 원래 메뉴 그대로.
   스킨의 원래 펼침 상자(.sub-category-box, .top_board)는 PC에서만 숨김.
   자료(하위 분류 순서·대표 상품)는 이 파일 안 CATS·PRD — 분류·대표 상품이 바뀌면 시안 HTML을 고치고 build_mega_js.py 로 다시 만듦.
   시안: 08_쇼핑몰/빛드론_메뉴시안_2026-11-16/빛드론_메뉴시안.html
   되돌리기: 카페24 스크립트 태그에서 이 파일만 빼면 원래대로 */
(function () {
  if (window.__bdMega) return; window.__bdMega = 1;
  var mq = window.matchMedia ? window.matchMedia('(min-width:1024px) and (hover:hover)') : null;
  if (!mq || !mq.matches) return;
  var IMG = 'https://ecimg.cafe24img.com/pg724b63244550007/dronebox2/web/product/medium/';
  function L(no) { return '/product/list.html?cate_no=' + no; }
  function P(no) { return '/product/detail.html?product_no=' + no; }
  var PRD = {
    543:['DJI 매빅4 프로 단품 (DJI RC 2)','20250513/8fb349920e8cf31f2593dbbc51bf42b5.jpg'],
    541:['DJI 매빅4 프로 플라이모어 콤보 (DJI RC 2)','20250513/1a03119566443fd4d6b6f62b9ad679bd.jpg'],
    542:['DJI 매빅4 프로 512GB 크리에이터 콤보','20250513/ae88053e7a54b6141d7eca444d3efc18.jpg'],
    281:['DJI 매빅3 클래식 플라이모어 콤보','20240116/6be526690d57af19c8145b21ec25880c.jpg'],
    479:['DJI 에어3S 플라이모어 콤보 (DJI RC 2)','20241126/2337ce12b61ab40e97af6ae69b665676.jpg'],
    480:['DJI 에어3S 플라이모어 콤보 (RC-N3)','20241126/b2bf12262fb1acf0074b18304b243ef0.jpg'],
    784:['DJI 에어3S 플라이모어 콤보 + 케어 리프레시 1년','20260929/83243fd1184d30f72dc4391a2e2241c5.jpg'],
    293:['DJI 에어3/에어3S 인텔리전트 플라이트 배터리','20240117/0bfa36f163f75cda0cc4efe98c10b768.jpg'],
    612:['DJI 미니5 프로 단품','20250919/6bb925e70053a4ba3f47f880d1034bd5.jpg'],
    611:['DJI 미니5 프로 플라이모어 콤보 (RC-N3)','20251230/68db3ae9c07a5b8e9924bec98ffaec0a.jpg'],
    616:['DJI 미니5 프로 배터리','20250917/917c403b0cd5734b34a0e733ad061d18.jpg'],
    635:['DJI 네오2 플라이모어 콤보','20251114/4e996f2f3e2a95dbb823ae866237783d.jpg'],
    501:['DJI 네오 모션 플라이모어 콤보','20241122/c9869f5613216de7726654b9d010b1f0.jpg'],
    665:['DJI 리토 X1 단품','20260423/0b325c37ff11faab55d6066e0936e659.jpg'],
    664:['DJI 리토 X1 플라이모어 콤보 (RC-N3)','20260423/c62637a0fcc36f094a0be7c7749601ba.jpg'],
    663:['DJI 리토 X1 플라이모어 콤보 (DJI RC 2)','20260423/48dcc5ca17cf48664a06aa23c4bc0ce6.jpg'],
    357:['DJI 팬텀4 배터리','20240116/d19f562afa919a8c230f1a2c17a809fd.jpg'],
    358:['DJI 팬텀4 저소음 프로펠러','20240116/b164b230f74a20fafd5748c556eb35cd.jpg'],
    654:['DJI 아바타 360 플라이모어 콤보 (DJI RC 2)','20260327/9c61635c4fb8555ab4a81d41443af4a9.jpg'],
    655:['DJI 아바타 360 모션 플라이모어 콤보','20260327/3c32986d0d6c7188160d12d5af10e83d.jpg'],
    403:['DJI 아바타2 단품','20240412/1ed6d010f169ea2db8299871760d422b.jpg'],
    339:['DJI 오즈모포켓3 단품','20240116/c5333d1a585f94ca4e0b1f45e565d08c.jpg'],
    795:['DJI 오즈모 포켓 4P 화이트 스탠다드 콤보','20261026/591a971009642d126c83e5ca1b2f6284.jpg'],
    637:['DJI 오즈모 액션 6 스탠다드 콤보','20251119/8d4d46769824758f25966417faf62173.jpg'],
    622:['DJI 오즈모 나노 스탠다드 콤보 128GB','20250923/0b69bfcfe22a3c2c33266b2b8b973044.jpg'],
    794:['DJI 오즈모 360 II 볼텍스 콤보','20261006/8c0b3b7bdd578afcf191c973367e03cc.jpg'],
    628:['DJI 오즈모 모바일 8','20251105/eb305be1b3c9a49f385f695c5596feb0.jpg'],
    755:['DJI Mic Mini 2S 송신기','20261102/83cd2ee7a765b0aa4a6a5ddc83a75775.jpg'],
    646:['DJI RS 5 콤보','20260130/44c9f95e5834b84d54763d52ff988d42.jpg'],
    647:['DJI RS 5','20260130/f0da3b705c1d30cba2bc0b72979f9329.jpg'],
    533:['DJI RS 4 Mini','20250221/17f17c0e7d50f3d0072eb0d91b4b7314.jpg'],
    343:['DJI 로닌 RS3 프로 콤보','20240116/dbbef89c09fc3037d55aeefab5c605c0.jpg'],
    345:['DJI 로닌 RS3 콤보','20240116/9e479f4b0a97259f1bc4ad46c0635b0c.jpg'],
    347:['DJI 로닌 RS3 미니','20240116/d7189d1667f73f31e46f993545b3ff55.jpg'],
    804:['DJI 매트리스 5T','20261109/ecf053029d8f911b4f6c05bf2399aa01.jpg'],
    797:['DJI 매트리스 5TD 콤보','20261026/325fb385510dac8ff8e23a1589a4dfce.jpg'],
    796:['DJI 독4 드론 스테이션','20261026/119c2f08f5c408745883965b18450882.jpg'],
    550:['DJI 매트리스 400 RTK','20250617/2fc0477f3c9fd74bb7ea7f662752e104.jpg'],
    514:['DJI 매트리스 4T 워리프리 Plus 콤보','20250109/83750dd73e4c4a85f17c7bfb652fa9be.jpg'],
    534:['DJI 독3 + 매트리스 4TD 세트','20250305/f45d025159c1fa41de2f88c589d21c57.jpg'],
    309:['DJI 매빅3 엔터프라이즈 멀티스펙트럴','20240119/3e04537c9c92d9b9e3a7c321127f61d3.png'],
    413:['DJI 젠뮤즈 H30T 열화상 카메라','20261103/715f56ba8342fe0a09c086601acaa602.jpg'],
    507:['DJI 플라이카트 30','20241209/e05abd1178a8d5447640c2ccdfbb823b.jpg'],
    565:['DJI 테라 스탠다드 1년','20250724/5f333c62596237a73adb9e47f8e44a65.jpg'],
    568:['DJI 테라 스탠다드 영구판','20250724/933057e335c4f7868ed690db7fdd0bd1.jpg'],
    672:['PIX4D Matic Analyst','20260506/000782490058d23f9bf93e8aa12825bf.png']
  };
  var CATS = [
    {no:24, name:'DJI 매빅', short:'매빅', img:543, subs:[[125,'DJI 매빅4 프로',543],[46,'DJI 매빅3 프로',0,'MAVIC 3 PRO'],[48,'DJI 매빅3 클래식',0,'MAVIC 3 CLASSIC'],[66,'DJI 매빅2 시리즈',0,'MAVIC 2'],[67,'DJI 매빅1 시리즈',0,'MAVIC']], picks:[543,541,542]},
    {no:25, name:'DJI 에어', short:'에어', img:479, subs:[[102,'DJI 에어3S',479],[49,'DJI 에어3',0,'AIR 3'],[68,'DJI 에어2/2S',0,'AIR 2S'],[70,'DJI 에어1',0,'AIR']], picks:[479,480,293]},
    {no:23, name:'DJI 미니', short:'미니', img:611, subs:[[132,'DJI 미니5 프로',611],[50,'DJI 미니4 프로',0,'MINI 4 PRO'],[69,'DJI 미니3 시리즈',0,'MINI 3'],[107,'DJI 미니 4K',0,'MINI 4K'],[71,'DJI 미니2',0,'MINI 2'],[72,'DJI 미니1',0,'MINI'],[167,'DJI LITO / LITO X1',665]], picks:[611,616]},
    {no:84, name:'DJI 네오', short:'네오', img:635, subs:[], picks:[635,501]},
    {no:118, name:'DJI 리토', short:'리토', img:665, subs:[], picks:[665,664,663]},
    {no:76, name:'DJI 팬텀', short:'팬텀', img:0, ph:'PHANTOM', subs:[], picks:[357,358]},
    {no:26, name:'DJI AVATA / FPV', short:'아바타·FPV', img:654, subs:[[51,'DJI 아바타',403]], picks:[654,655,403]},
    {no:27, name:'DJI 핸드헬드', short:'핸드헬드', img:339, subs:[[34,'DJI 오즈모포켓',795],[164,'DJI 오즈모 액션',637],[88,'DJI 오즈모 나노',622],[54,'DJI Mic',755],[56,'DJI 오즈모 모바일',628],[130,'DJI 오즈모 360',0,'OSMO 360']], picks:[795,637,622,755]},
    {no:42, name:'DJI 로닌', short:'로닌', img:646, subs:[[80,'DJI RS 4 PRO',0,'RS 4 PRO'],[105,'DJI RS 4',0,'RS 4'],[121,'DJI RS 4 MINI',533],[57,'RS 3 PRO',0,'RS 3 PRO'],[58,'RS 3',0,'RS 3'],[59,'RS 3 MINI',0,'RS 3 MINI'],[166,'DJI RS 5',647]], picks:[646,647,533]},
    {no:43, name:'DJI 산업용드론', short:'산업용 드론', img:804, subs:[[170,'DJI 매트리스 5 시리즈',804],[117,'DJI 매트리스 4 시리즈',514],[122,'드론 스테이션',534],[129,'DJI 매트리스 400 RTK',550],[60,'DJI 매빅3 엔터프라이즈',309],[61,'DJI 매트리스 350 RTK',0,'M350 RTK'],[62,'DJI 매트리스 30 시리즈',0,'M30'],[74,'페이로드',413],[112,'운송용 드론',0,'FLYCART 30'],[82,'인스파이어3',0,'INSPIRE 3']], picks:[804,514,550,534]},
    {no:92, name:'S/W', short:'소프트웨어', img:565, subs:[[94,'DJI S/W',565],[95,'PIX4D',672]], picks:[565,568,672]}
  ];
  var SUPPORT = {name:'고객지원', href:'/board/free/list.html?board_no=1', subs:[['수리접수','/board/%EC%88%98%EB%A6%AC%EC%A0%91%EC%88%98/1/'],['공공기관 구매안내','/board/%EA%B3%B5%EA%B3%B5%EA%B8%B0%EA%B4%80-%EA%B5%AC%EB%A7%A4%EC%95%88%EB%82%B4/2/'],['리뷰','/board/%EB%A6%AC%EB%B7%B0/4/'],['공지사항','/board/%EA%B3%B5%EC%A7%80%EC%82%AC%ED%95%AD/5/']]};
  function CAT(no) { for (var i = 0; i < CATS.length; i++) if (CATS[i].no === no) return CATS[i]; }
  function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;'); }
  function ph(no, label) {
    var p = PRD[no];
    return '<div class="bm-ph">' + (p ? '<img src="' + IMG + p[1] + '" alt="' + esc(label) + '" loading="lazy">' : '<span>' + esc(label) + '</span>') + '</div>';
  }
  var CSS = [
    '#mh_nav_box .sub-category-box,#mh_nav_box .top_board{display:none !important}',
    '#bdMega{position:absolute;left:0;right:0;top:100%;background:#fff;border-top:1px solid #E6E8EC;border-bottom:1px solid #E6E8EC;box-shadow:0 18px 30px rgba(17,24,39,.07);display:none;z-index:9990;text-align:left;letter-spacing:-0.01em}',
    '#bdMega.on{display:block}',
    '#bdMega *{box-sizing:border-box}',
    '#bdMega a{text-decoration:none;color:inherit}',
    '#bdMega ul{list-style:none;margin:0;padding:0}',
    '#bdMega .bm-in{display:grid;grid-template-columns:300px 1fr;gap:40px;padding:30px 40px 28px;max-width:1400px;margin:0 auto}',
    '#bdMega h3{font-size:20px;font-weight:700;letter-spacing:-0.02em;margin:0;color:#16181D}',
    '#bdMega .bm-all{display:inline-block;margin-top:6px;font-size:13.5px;color:#2F7DF6;font-weight:600}',
    '#bdMega .bm-left ul{margin-top:18px;display:grid;grid-template-columns:1fr;gap:2px}',
    '#bdMega .bm-left ul.two{grid-template-columns:1fr 1fr;column-gap:8px}',
    '#bdMega .bm-left li a{display:block;padding:8px 10px;margin-left:-10px;border-radius:6px;font-size:14.5px;color:#3A3F47;line-height:1.4}',
    '#bdMega .bm-left li a:hover{background:#EEF4FF;color:#2F7DF6}',
    '#bdMega .bm-empty{margin-top:18px;font-size:14px;color:#6B7280;line-height:1.6}',
    '#bdMega .bm-lbl{font-size:13px;font-weight:600;color:#6B7280;margin-bottom:12px}',
    '#bdMega .bm-cards{display:grid;grid-template-columns:repeat(4,1fr);gap:18px}',
    '#bdMega .bm-ph{aspect-ratio:1/1;background:#F5F6F8;border-radius:10px;display:flex;align-items:center;justify-content:center;overflow:hidden}',
    '#bdMega .bm-ph img{width:100%;height:100%;object-fit:contain;mix-blend-mode:multiply;display:block}',
    '#bdMega .bm-ph span{font-size:15px;font-weight:700;color:#A3AAB5;text-align:center;padding:0 8px}',
    '#bdMega .bm-card p{margin:10px 0 0;font-size:14px;line-height:1.45;color:#3A3F47;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}',
    '#bdMega .bm-card:hover p{color:#2F7DF6}',
    '#bdMega .bm-card:hover .bm-ph{outline:1px solid #D5DEEE}',
    '#bdMega .bm-foot{background:#F5F6F8}',
    '#bdMega .bm-foot-in{display:flex;gap:24px;padding:13px 40px;max-width:1400px;margin:0 auto;font-size:13.5px;color:#6B7280}',
    '#bdMega .bm-foot a:hover{color:#2F7DF6}',
    '#bdMega .bm-foot b{color:#3A3F47;font-weight:600;margin-right:4px}',
    '#mh_nav_box .bm-open > a{color:#2F7DF6 !important;box-shadow:inset 0 -2px 0 #F39800}'
  ].join('\n');

  function hoverCtl(openFn, closeFn) {
    var tOpen = null, tClose = null, cur = null;
    return {
      enter: function (k) { clearTimeout(tClose); clearTimeout(tOpen);
        if (cur !== null) { cur = k; openFn(k); return; }
        tOpen = setTimeout(function () { cur = k; openFn(k); }, 120); },
      leave: function () { clearTimeout(tOpen); tClose = setTimeout(function () { cur = null; closeFn(); }, 180); },
      stay: function () { clearTimeout(tClose); }
    };
  }

  function init() {
    var box = document.getElementById('mh_nav_box');
    var cat = box && box.querySelector('.xans-layout-category');
    if (!cat || document.getElementById('bdMega')) return;
    var st = document.createElement('style'); st.id = 'bdMegaCss'; st.textContent = CSS; document.head.appendChild(st);
    if (getComputedStyle(box).position === 'static') box.style.position = 'relative';
    var mega = document.createElement('div'); mega.id = 'bdMega'; box.appendChild(mega);
    var foot = '<div class="bm-foot"><div class="bm-foot-in"><span><b>고객지원</b></span>' +
      SUPPORT.subs.map(function (s) { return '<a href="' + s[1] + '">' + s[0] + '</a>'; }).join('') + '</div></div>';
    function render(k) {
      if (k === 'sup') {
        mega.innerHTML = '<div class="bm-in"><div class="bm-left"><h3>고객지원</h3><ul>' +
          SUPPORT.subs.map(function (s) { return '<li><a href="' + s[1] + '">' + s[0] + '</a></li>'; }).join('') + '</ul></div>' +
          '<div class="bm-right"><div class="bm-lbl">자주 찾는 곳</div><div class="bm-cards">' +
          SUPPORT.subs.slice(0, 2).map(function (s) { return '<a class="bm-card" href="' + s[1] + '"><div class="bm-ph" style="aspect-ratio:2/1"><span>' + s[0] + '</span></div></a>'; }).join('') +
          '</div></div></div>';
        return;
      }
      var c = CAT(+k); if (!c) return;
      var left = '<h3>' + esc(c.name) + '</h3><a class="bm-all" href="' + L(c.no) + '">전체 상품 보기 →</a>';
      left += c.subs.length ? '<ul class="' + (c.subs.length > 6 ? 'two' : '') + '">' + c.subs.map(function (s) { return '<li><a href="' + L(s[0]) + '">' + esc(s[1]) + '</a></li>'; }).join('') + '</ul>'
                            : '<p class="bm-empty">하위 분류 없이 한 목록으로 보여 드립니다.</p>';
      var cards = c.picks.filter(function (p) { return PRD[p]; }).map(function (p) { return '<a class="bm-card" href="' + P(p) + '">' + ph(p, PRD[p][0]) + '<p>' + esc(PRD[p][0]) + '</p></a>'; }).join('');
      mega.innerHTML = '<div class="bm-in"><div class="bm-left">' + left + '</div><div class="bm-right"><div class="bm-lbl">대표 상품</div><div class="bm-cards">' + cards + '</div></div></div>' + foot;
    }
    var items = [];
    [].forEach.call(cat.querySelectorAll('li'), function (li) {
      if (li.parentElement.closest('li')) return;
      var a = li.querySelector('a'); if (!a || !a.textContent.trim()) return;
      var m = (a.getAttribute('href') || '').match(/cate_no=(\d+)/);
      var k = m ? m[1] : (li.closest('.xans-layout-boardinfo') ? 'sup' : null);
      if (!k || (k !== 'sup' && !CAT(+k))) return;
      li.setAttribute('data-bm', k); items.push(li);
    });
    if (!items.length) return;
    function closeAll() { mega.classList.remove('on'); items.forEach(function (x) { x.classList.remove('bm-open'); }); }
    var h = hoverCtl(function (k) { render(k); mega.classList.add('on'); items.forEach(function (x) { x.classList.toggle('bm-open', x.getAttribute('data-bm') === String(k)); }); }, closeAll);
    items.forEach(function (x) { x.addEventListener('mouseenter', function () { h.enter(x.getAttribute('data-bm')); }); x.addEventListener('mouseleave', h.leave); });
    mega.addEventListener('mouseenter', h.stay); mega.addEventListener('mouseleave', h.leave);
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeAll(); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
