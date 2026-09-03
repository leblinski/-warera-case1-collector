/* Shared probe for the seam-robustness cases. Loads the page through ../harness.js with the
   given collector overrides and reads every figure a user acts on from all four tabs. */
const fs = require('fs'); const path = require('path');
const { withPage, text, DEFAULT_PUBLIC } = require('../harness');
const PUB = DEFAULT_PUBLIC;
const load = (n) => JSON.parse(fs.readFileSync(path.join(PUB, n), 'utf8'));
const NOW = Date.parse('2026-09-03T15:35:00Z'); // ~4 min after generated_at, so the strip reads fresh

async function probe(page, o) {
  o = o || {};
  const out = {};
  await page.waitForTimeout(1500);
  if (o.tax !== undefined) { await page.fill('#tax', String(o.tax)); await page.dispatchEvent('#tax', 'input'); await page.waitForTimeout(300); }
  // Price tab: pin Common, pick boots, roll 3 -> rollFacts + scrap floor card
  await page.click('#tabBar [data-tab="price"]');
  await page.click('#rarityBtns [data-tier="' + (o.tier || 1) + '"]');
  await page.click('#slotGrid [data-slot="' + (o.slot || 'boots') + '"]');
  const rb = await page.$('#rollGrid [data-roll="' + (o.roll || 3) + '"]');
  if (rb) await rb.click();
  await page.waitForTimeout(300);
  if (o.price !== undefined) { await page.fill('#price', String(o.price)); await page.dispatchEvent('#price', 'input'); await page.waitForTimeout(300); }
  out.dataStamp = await text(page, '#dataStamp');
  out.price = {
    taxChip: await text(page, '#taxChip'), taxIn: await page.inputValue('#tax'),
    figure: await text(page, '#figure'), docketHint: await text(page, '#docketHint'), docketLabel: await text(page, '#docketLabel'),
    flipFigure: await text(page, '#flipFigure'), flipDetail: await text(page, '#flipDetail'), scrapDetail: await text(page, '#scrapDetail'),
    scrapNote: await text(page, '#scrapNote'), scrapPrice: await page.inputValue('#scrapPrice'),
    scrapVerdict: await text(page, '#scrapVerdict'), scrapRows: await text(page, '#scrapRows'),
    quickScrap: await text(page, '#quickScrapVal'), cutCard: await text(page, '#cutCardText'),
    cutCardHidden: await page.$eval('#cutCard', (e) => e.hidden).catch(() => null),
    rollFacts: await text(page, '#rollFacts'), rollNbrs: await text(page, '#rollNbrs'),
  };
  await page.click('#tabBar [data-tab="cases"]'); await page.waitForTimeout(200);
  out.cases = { verdict: await text(page, '#caseVerdict'), detail: await text(page, '#caseDetail'), rows: await text(page, '#caseRows'), foot: await text(page, '#caseFoot'), swing: await text(page, '#caseSwing'), tab: await text(page, '#tabCaseVal') };
  await page.click('#tabBar [data-tab="craft"]'); await page.waitForTimeout(200);
  out.craft = { verdict: await text(page, '#craftVerdict'), detail: await text(page, '#craftDetail'), rows: await text(page, '#craftRows'), foot: await text(page, '#craftFoot'), note: await text(page, '#craftNote'), scrapIn: await page.inputValue('#craftScrap'), steelIn: await page.inputValue('#craftSteel'), books: await text(page, '#craftBooks') };
  await page.click('#tabBar [data-tab="sort"]'); await page.waitForTimeout(200);
  out.sort = {};
  for (const t of (o.sortTiers || [1, 2, 6])) {
    const b = await page.$('#sortPick [data-sorttier="' + t + '"]');
    if (b) { await b.click(); await page.waitForTimeout(150); }
    const head = await text(page, '#sortRows .cut-head');
    const rows = await text(page, '#sortRows');
    const tap = await page.$('#sortRows .cut-row.tap[data-cut="' + t + '-' + (o.slot || 'boots') + '"]');
    let detail = null;
    if (tap) { await tap.click(); await page.waitForTimeout(150); detail = await text(page, '#cutd-' + t + '-' + (o.slot || 'boots')); }
    out.sort['tier' + t] = { head, rows, detail };
  }
  out.sort.gate = await text(page, '#sortGateNote'); out.sort.foot = await text(page, '#sortFoot'); out.sort.detail = await text(page, '#sortDetail');
  return out;
}

async function run(name, opts, extraFn) {
  opts = opts || {};
  const res = await withPage({ overrides: opts.overrides || {}, localStorage: opts.localStorage, now: opts.now === null ? undefined : (opts.now || NOW) }, async (page, x) => {
    const out = await probe(page, opts);
    if (extraFn) out.extra = await extraFn(page, x);
    out._requests = x.requests.filter((r) => !r.startsWith('BLOCKED'));
    out._errors = x.log.filter((l) => l.type === 'pageerror' || (l.type === 'error' && !/403/.test(l.text))).map((l) => l.text);
    return out;
  });
  const f = path.join(__dirname, name + '.out.json');
  fs.writeFileSync(f, JSON.stringify(res, null, 1));
  console.log(JSON.stringify(res, null, 1));
  return res;
}
module.exports = { run, probe, load, NOW, PUB };
