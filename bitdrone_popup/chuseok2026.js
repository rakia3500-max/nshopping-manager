/* 빛드론(bit-drone.shop) 2026 추석 연휴 배송 안내 팝업
 * 카페24 스크립트태그로 전 페이지에 붙지만, 메인에서 기간 안에만 뜬다.
 * 기간: 2026-09-22 00:00 ~ 2026-09-28 23:59 (KST). 지나면 스스로 아무것도 하지 않는다.
 */
(function () {
  var START = Date.parse('2026-09-22T00:00:00+09:00');
  var END = Date.parse('2026-09-28T23:59:59+09:00');
  var KEY = 'bd_chuseok2026_hide';
  var now = Date.now();
  if (now < START || now > END) return;

  var p = location.pathname.replace(/\/+$/, '');
  if (!(p === '' || p === '/index.html' || p === '/index.php')) return;

  var today = new Date(now + 9 * 3600 * 1000).toISOString().slice(0, 10);
  try { if (localStorage.getItem(KEY) === today) return; } catch (e) {}

  function row(k, v, c, last) {
    return '<tr><td style="padding:11px 4px;' + (last ? '' : 'border-bottom:1px solid #edf0f3;') +
      'font-size:14px;color:#5b6673;text-align:left;">' + k + '</td><td style="padding:11px 4px;' +
      (last ? '' : 'border-bottom:1px solid #edf0f3;') + 'font-size:16px;font-weight:bold;color:' + c +
      ';text-align:right;white-space:nowrap;">' + v + '</td></tr>';
  }

  function show() {
    if (document.getElementById('bd-chuseok-pop')) return;
    var wrap = document.createElement('div');
    wrap.id = 'bd-chuseok-pop';
    wrap.setAttribute('role', 'dialog');
    wrap.setAttribute('aria-label', '추석 연휴 배송 안내');
    wrap.style.cssText = 'position:fixed;inset:0;z-index:2147483000;background:rgba(0,0,0,.45);' +
      'display:flex;align-items:center;justify-content:center;padding:16px;box-sizing:border-box;';
    wrap.innerHTML =
      '<div style="width:400px;max-width:100%;background:#fff;border-radius:14px;overflow:hidden;' +
      'box-shadow:0 12px 32px rgba(0,0,0,.25);font-family:\'Noto Sans KR\',\'Malgun Gothic\',sans-serif;' +
      'color:#1d2733;text-align:center;color-scheme:light;">' +
        '<div style="background:#198acb;background:linear-gradient(135deg,#198acb,#0f6fa6);color:#fff;padding:24px 16px 20px;position:relative;">' +
          '<button type="button" data-bd-close aria-label="닫기" style="position:absolute;top:8px;right:10px;background:none;border:0;color:#fff;font-size:26px;line-height:1;cursor:pointer;">×</button>' +
          '<p style="margin:0;font-size:12px;letter-spacing:2px;color:#fff;">BITDRONE NOTICE</p>' +
          '<p style="margin:6px 0 0;font-size:23px;font-weight:bold;color:#fff;">추석 연휴 배송 안내</p>' +
          '<p style="margin:8px 0 0;font-size:13px;color:#fff;">풍성하고 행복한 한가위 보내세요</p>' +
        '</div>' +
        '<div style="padding:12px 18px 4px;"><table style="width:100%;border-collapse:collapse;">' +
          row('택배 마감', '9월 22일(화)', '#e5484d') +
          row('배송 휴무', '9/23(수) ~ 27(일)', '#1d2733') +
          row('출고 재개', '9월 28일(월)부터', '#198acb', true) +
        '</table></div>' +
        '<div style="background:#f5f8fb;margin:4px 18px 14px;border-radius:10px;padding:12px 13px;font-size:13px;line-height:1.7;color:#3d4753;text-align:left;">' +
          '· 연휴 중에도 <b>주문은 가능</b>하며, 9월 28일(월)부터 주문 순서대로 출고됩니다.<br>' +
          '· 연휴 동안 남겨주신 문의는 연휴가 끝난 뒤 순서대로 답변드립니다.' +
        '</div>' +
        '<p style="margin:0;padding:0 0 12px;font-size:12px;color:#8a94a0;">빛드론 · 070-5176-7075</p>' +
        '<div style="display:flex;border-top:1px solid #edf0f3;">' +
          '<button type="button" data-bd-today style="flex:1;padding:13px 0;background:#fff;border:0;border-right:1px solid #edf0f3;font-size:13px;color:#5b6673;cursor:pointer;">오늘 하루 보지 않기</button>' +
          '<button type="button" data-bd-close style="flex:1;padding:13px 0;background:#fff;border:0;font-size:13px;font-weight:bold;color:#198acb;cursor:pointer;">닫기</button>' +
        '</div>' +
      '</div>';
    function close() { if (wrap.parentNode) wrap.parentNode.removeChild(wrap); }
    wrap.addEventListener('click', function (e) {
      if (e.target === wrap || e.target.hasAttribute('data-bd-close')) close();
      if (e.target.hasAttribute('data-bd-today')) {
        try { localStorage.setItem(KEY, today); } catch (err) {}
        close();
      }
    });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
    document.body.appendChild(wrap);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', show);
  else show();
})();
