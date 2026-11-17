// 탭·영역별 화면 캡처 (이 스킬의 references/screens/*.png 를 만든 스크립트)
//   node capture_screens.js <정적 대시보드 index.html 절대경로> <출력 폴더>
// 정적 페이지는 scripts/export_static.py 로 만든다 (DASHBOARD_PASSWORD 를 비워 암호화 없이). Playwright 필요.
const { chromium } = require('playwright');
const [site, out] = process.argv.slice(2);
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  const p = await ctx.newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('file://' + site); await p.waitForTimeout(2500);
  // 화면에 보이는 요소들의 합집합 영역을 잘라 저장. sels: CSS 선택자 또는 'h3:제목시작' (그 제목의 최상위 패널)
  const shot = async (name, sels, maxH) => {
    const box = await p.evaluate((sels) => {
      const vis = (e) => e && e.offsetParent !== null;
      const find = (s) => {
        if (s.startsWith('h3:')) { const t = s.slice(3); return [...document.querySelectorAll('.panel')].filter(vis).filter(e => !e.parentElement.closest('.panel')).filter(e => (e.querySelector('h3')?.textContent || e.textContent).trim().replace(/\s+/g, ' ').startsWith(t)); }
        return [...document.querySelectorAll(s)].filter(vis);
      };
      const els = sels.flatMap(find); if (!els.length) return null;
      let x0 = 1e9, y0 = 1e9, x1 = 0, y1 = 0;
      for (const e of els) { const r = e.getBoundingClientRect(); x0 = Math.min(x0, r.left + scrollX); y0 = Math.min(y0, r.top + scrollY); x1 = Math.max(x1, r.right + scrollX); y1 = Math.max(y1, r.bottom + scrollY); }
      return { x: Math.max(0, x0 - 8), y: Math.max(0, y0 - 8), width: x1 - x0 + 16, height: y1 - y0 + 16 };
    }, sels);
    if (!box) { console.log('MISSING', name, sels); return; }
    if (maxH && box.height > maxH) box.height = maxH;
    await p.screenshot({ path: `${out}/${name}.png`, fullPage: true, clip: box });
    console.log('ok', name, Math.round(box.width) + 'x' + Math.round(box.height));
  };
  const tab = async (t) => { await p.click(`[data-tab=${t}]`); await p.waitForTimeout(1500); };
  const full = async (name) => { await p.screenshot({ path: `${out}/${name}.png`, fullPage: true }); console.log('ok', name, 'full'); };

  // ── 공통 + 카페24 어드민
  await tab('ops');
  await shot('00-common-header-briefing-range', ['.hero', 'nav', '#brief', '#range']);
  await full('ops-00-full');
  await shot('ops-01-kpi-cards', ['#cards']);
  await shot('ops-02-period-compare', ['h3:핵심 지표 기간 비교']);
  await shot('ops-03-daily-sales_new-vs-returning', ['h3:일별 매출 추이', 'h3:신규 vs 재구매 매출']);
  await shot('ops-04-ad-vs-organic_device', ['h3:일별 광고비 vs 비광고 매출', 'h3:디바이스별 매출 비율', 'h3:디바이스별 매출·주문 상세']);
  await shot('ops-05-visitors_first-purchase', ['h3:방문자 상세', 'h3:신규 방문 · 첫 구매 추이']);
  await shot('ops-06-visitor-trend', ['h3:방문자 추이']);
  await shot('ops-07-category_best-products', ['h3:카테고리 매출', 'h3:베스트 상품 TOP 10']);
  await shot('ops-08-product-funnel', ['h3:상품별 조회 → 담기 → 주문']);
  await shot('ops-09-keywords_low-cart', ['h3:자연 검색 유입 검색어', 'h3:담기율 낮은 상품 경고']);
  await shot('ops-10-domains_ad-paths', ['h3:유입 도메인', 'h3:광고 채널별 방문']);
  await shot('ops-11-members_pageviews', ['h3:회원 · 비회원 매출', 'h3:페이지뷰 TOP']);
  await shot('ops-12-daily-table_composition', ['h3:일별 운영 데이터 (최근 14일)', 'h3:일별 운영 데이터 · 세부 구성']);
  // ── 광고
  await tab('ads');
  await full('ads-00-full');
  await shot('ads-01-kpi-cards', ['#adCards']);
  await shot('ads-02-budget_summary', ['h3:채널별 예산 비율', 'h3:채널별 성과 요약']);
  await shot('ads-03-channel-detail-flow', ['h3:Meta']);
  await shot('ads-04-unlinked-channels', ['h3:미연동 광고 채널 안내']);
  // ── 광고 히스토리 (채널 서브탭)
  await tab('history');
  const sub = async (h) => { await p.click(`[data-h=${h}]`); await p.waitForTimeout(1500); };
  await sub('meta'); await shot('hist-01-meta-creatives', ['#tab-history > .sub-nav', '#hist-meta'], 1500);
  await shot('hist-00-campaign-table', ['#hist-meta .campBox']);
  await sub('google'); await shot('hist-02-google-creatives', ['#tab-history > .sub-nav', '#hist-meta'], 1500);
  await sub('kakao'); await shot('hist-03-kakao-creatives', ['#tab-history > .sub-nav', '#hist-meta'], 1500);
  await sub('naver_powerlink'); await shot('hist-04-naver-keywords', ['#tab-history > .sub-nav', '#hist-naver_powerlink'], 1300);
  await sub('naver_place'); await shot('hist-05-naver-place', ['#tab-history > .sub-nav', '#hist-naver_place']);
  // ── GA4
  await tab('ga4');
  await shot('ga4-01-kpi-cards', ['#ga4Cards']);
  await shot('ga4-02-funnel_new-vs-returning', ['h3:구매 퍼널 · 단계별 이탈', 'h3:신규 vs 재방문']);
  await shot('ga4-03-channels_pages', ['h3:매체별 유입·전환', 'h3:인기 페이지 TOP']);
  // ── 경쟁사
  await tab('comp');
  await shot('comp-01-directory_trend', ['#tab-comp']);
  // ── 주간/월간 리포트
  await tab('weekly');
  await full('weekly-00-full');
  await shot('weekly-01-header_summary', ['#repW .panel:nth-of-type(1)', 'h3:01', 'h3:02']);
  await shot('weekly-02-channels', ['h3:03']);
  await shot('weekly-03-funnels', ['h3:04', 'h3:05']);
  await shot('weekly-04-category_best', ['h3:06', 'h3:07']);
  await shot('weekly-05-customers_keywords', ['h3:08', 'h3:09']);
  await shot('weekly-06-naver-keywords', ['h3:10']);
  await shot('weekly-07-insights', ['h3:11']);
  await tab('monthly');
  await shot('monthly-01-header_summary', ['#repM .panel:nth-of-type(1)', 'h3:01', 'h3:02']);
  // ── 채널 연결
  await tab('channels');
  await shot('channels-01-cards', ['#tab-channels .brief', '#channels']);
  await shot('channels-02-collect-log', ['h3:최근 수집 로그'], 520);
  console.log('errors', errs);
  // ── 다크 모드 · 모바일
  const d = await b.newContext({ viewport: { width: 1440, height: 1000 }, colorScheme: 'dark' }); const dp = await d.newPage();
  await dp.goto('file://' + site); await dp.waitForTimeout(2500); await dp.screenshot({ path: `${out}/extra-dark-mode.png`, clip: { x: 0, y: 0, width: 1440, height: 1000 } });
  const m = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 }); const mp = await m.newPage();
  await mp.goto('file://' + site); await mp.waitForTimeout(2500); await mp.screenshot({ path: `${out}/extra-mobile.png` });
  await mp.click('[data-tab=ads]'); await mp.waitForTimeout(1200); await mp.screenshot({ path: `${out}/extra-mobile-ads.png` });
  console.log('mobile scrollWidth', await mp.evaluate(() => document.documentElement.scrollWidth));
  await b.close();
})();
