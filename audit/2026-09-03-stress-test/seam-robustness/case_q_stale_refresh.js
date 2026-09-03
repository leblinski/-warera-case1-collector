// (q) stale-data path: first load fine; on Refresh, index.json returns a NEW generated_at but
// summary.json and commodities.json fail (404). What does the strip say, and which numbers show?
const { run, load, NOW } = require('./common');
const { text } = require('../harness');
const later = new Date(NOW + 20 * 60000).toISOString();
run('case_q_stale_refresh', { now: NOW + 21 * 60000 }, async (page) => {
  const i = load('index.json'); i.generated_at = later; i.updated_at = later;
  await page.route('**/index.json*', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(i) }));
  await page.route('**/summary.json*', (r) => r.fulfill({ status: 404, body: '' }));
  await page.route('**/commodities.json*', (r) => r.fulfill({ status: 404, body: '' }));
  await page.click('#tabBar [data-tab="cases"]');
  const before = { stamp: await text(page, '#dataStamp'), verdict: await text(page, '#caseVerdict'), detail: await text(page, '#caseDetail') };
  await page.click('#dataRefresh'); await page.waitForTimeout(2500);
  const after = { stamp: await text(page, '#dataStamp'), verdict: await text(page, '#caseVerdict'), detail: await text(page, '#caseDetail'), foot: await text(page, '#caseFoot') };
  await page.waitForTimeout(9000);
  after.stampLater = await text(page, '#dataStamp');
  return { before, after };
}).catch((e) => { console.error(e); process.exit(1); });
