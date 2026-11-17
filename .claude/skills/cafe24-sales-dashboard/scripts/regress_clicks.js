// 버튼 전수 클릭 회귀 검사 — 기간 4종 × 비교 4종, 8탭, 광고 히스토리 5개 채널을 눌러 오류 배너·콘솔 오류가 없는지 본다.
//   node regress_clicks.js <정적 대시보드 index.html 절대경로>
// 반드시 '실제와 비슷한 빈 데이터'로도 돌린다: 경쟁사·GA4·Meta 가 없는 DB (operations.md '화면을 고친 뒤 확인하는 법').
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1440, height: 1000 } });
  const errs = []; p.on('pageerror', e => errs.push('pageerror: ' + e.message)); p.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text()); });
  await p.goto('file://' + process.argv[2]); await p.waitForTimeout(2500);
  const banner = async (tag) => { const t = await p.evaluate(() => { const e = document.querySelector('#error'); return e && !e.classList.contains('hidden') ? e.textContent.trim() : ''; }); if (t) errs.push(`${tag}: ${t.slice(0, 120)}`); };
  await banner('first load');
  for (const pp of ['1', '14', '30', '7']) for (const c of ['week', 'month', 'year', 'prev']) { await p.click(`#range [data-p="${pp}"]`); await p.waitForTimeout(250); await p.click(`#range [data-c="${c}"]`); await p.waitForTimeout(450); await banner(`p=${pp} c=${c}`); }
  const tabs = await p.$$eval('nav button', bs => bs.map(x => x.dataset.tab));   // 숨긴 탭(hidden_tabs)은 메뉴에 없다
  for (const t of [...tabs.filter(x => x !== 'ops'), 'ops']) { await p.click(`[data-tab=${t}]`); await p.waitForTimeout(500); await banner('tab ' + t); }
  for (const h of ['meta', 'google', 'kakao', 'naver_powerlink', 'naver_place']) { await p.click('[data-tab=history]'); await p.click(`[data-h=${h}]`); await p.waitForTimeout(400); await banner('hist ' + h); }
  if (tabs.includes('comp')) { await p.click('[data-tab=comp]'); await p.waitForTimeout(300);
    console.log('comp empty msg visible:', await p.evaluate(() => { const e = document.querySelector('#chComp').parentElement.querySelector('.empty'); return !!e && e.offsetParent !== null; })); }
  console.log('tabs:', tabs.join(','));
  console.log('errors:', errs.length ? errs : 'none'); await b.close();
})();
