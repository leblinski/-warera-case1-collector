/* Drives the Price tab of test60.html through the audit harness for a list of cases and
   prints what the user sees. Date.now is frozen at the shard's generated_at so the figures
   are reproducible and comparable with model.py (which defaults to the same instant).
   Usage: node run_cases.js [cases.json]   (default: the three cases from the brief)
*/
const { withPage, text } = require('../harness');
const fs = require('fs');
const PUBLIC = '/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/public';
const gen = JSON.parse(fs.readFileSync(PUBLIC + '/summary.json', 'utf8')).generated_at;
const NOW = new Date(gen).getTime();

const DEFAULT_CASES = [
  { name: 'common knife 40/5, floor below median', price: '4.200', tier: 1, slot: 'weapon', rolls: { attack: 40, criticalChance: 5 } },
  { name: 'epic boots 25, floor above median', price: '68.000', tier: 4, slot: 'boots', rolls: { dodge: 25 } },
  { name: 'legendary tank 141/34, floor 150, age 2d', price: '150.000', tier: 5, slot: 'weapon', rolls: { attack: 141, criticalChance: 34 }, age: '2d' },
  { name: 'legendary tank 141/34, floor 150, no age', price: '150.000', tier: 5, slot: 'weapon', rolls: { attack: 141, criticalChance: 34 } },
];
const cases = process.argv[2] ? JSON.parse(fs.readFileSync(process.argv[2], 'utf8')) : DEFAULT_CASES;

(async () => {
  const results = [];
  for (const c of cases) {
    await withPage({ publicDir: PUBLIC, now: NOW }, async (page, { log }) => {
      await page.waitForFunction(() => document.getElementById('dataStamp') && document.getElementById('dataStamp').textContent.trim() !== '', null, { timeout: 15000 }).catch(() => {});
      await page.fill('#price', c.price);
      const inferred = await page.evaluate(() => Array.from(document.querySelectorAll('#rarityBtns [data-tier]')).filter(b => b.getAttribute('aria-pressed') === 'true').map(b => b.getAttribute('data-tier')));
      const maybes = await page.evaluate(() => Array.from(document.querySelectorAll('#rarityBtns .maybe')).map(b => b.getAttribute('data-tier')));
      const rarityNote = await text(page, '#rarityNote');
      if (c.tier) await page.click('#rarityBtns [data-tier="' + c.tier + '"]');
      await page.click('#slotGrid [data-slot="' + c.slot + '"]');
      for (const k in c.rolls) {
        const btn = await page.$('#rollGrid [data-rollkey="' + k + '"][data-roll="' + c.rolls[k] + '"]');
        if (btn) await btn.click();
        else await page.fill('#rollGrid [data-rollinput="' + k + '"]', String(c.rolls[k]));
      }
      if (!Object.keys(c.rolls).length) {
        results.push({ name: c.name, inferredTierFromPrice: inferred, alsoLegal: maybes, rarityNote, salesHead: await text(page, '#salesHead'),
          rollGrid: await text(page, '#rollGrid'), scrapVerdict: await text(page, '#scrapVerdict'), figure: await text(page, '#figure') });
        return;
      }
      if (c.age) await page.$eval('#ageHours', (el, v) => { el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); }, c.age);
      if (c.mode === 'patient') { await page.$eval('[data-mode="patient"]', el => el.click()); }
      if (c.modeHack === 'patient') { await page.evaluate(() => { document.querySelector('[data-mode="patient"]').click(); }); }
      await page.waitForFunction(() => !document.getElementById('analyseBtn').disabled, null, { timeout: 5000 });
      await page.click('#analyseBtn');
      await page.waitForFunction(() => /direct price/.test(document.getElementById('debug').textContent), null, { timeout: 20000 });
      const r = {
        name: c.name, inferredTierFromPrice: inferred, alsoLegal: maybes, rarityNote,
        salesHead: await text(page, '#salesHead'), salesStatus: await text(page, '#salesStatus'),
        resultText: await text(page, '#resultText'), miniTarget: await text(page, '#miniTarget'),
        miniVelocity: await text(page, '#miniVelocity'), miniCoverage: await text(page, '#miniCoverage'),
        trendMiniKicker: await text(page, '#trendMiniKicker'), trendMiniPrice: await text(page, '#trendMiniPrice'),
        trendMiniReason: await text(page, '#trendMiniReason'),
        confidence: await text(page, '#confidence'), floorSignal: await text(page, '#floorSignal'),
        docketLabel: await text(page, '#docketLabel'), docketHint: await text(page, '#docketHint'),
        figure: await text(page, '#figure'), trendHeroPrice: await text(page, '#trendHeroPrice'), trendHeroType: await text(page, '#trendHeroType'),
        trendHeroKicker: await text(page, '#trendHeroKicker'),
        scrapVerdict: await text(page, '#scrapVerdict'), rollFacts: await text(page, '#rollFacts'),
        opp: (await page.$('#opportunityDepth')) && !(await page.$eval('#opportunityDepth', e => e.hidden)) ? {
          range: await text(page, '#oppRange'), profit: await text(page, '#oppProfit'), safe: await text(page, '#oppSafeRange'),
          caution: await text(page, '#oppCautionRange'), risk: await text(page, '#oppRiskRange'), velocity: await text(page, '#oppVelocity') } : null,
        debug: await text(page, '#debug'),
        errors: log.filter(l => l.type === 'pageerror').map(l => l.text),
      };
      if (r.opp && c.oppCount != null) {
        await page.fill('#oppCount', String(c.oppCount));
        await page.dispatchEvent('#oppCount', 'input');
        r.opp.withCount = { text: await text(page, '#oppDepthText'), velocity: await text(page, '#oppVelocity') };
      }
      results.push(r);
    });
  }
  console.log(JSON.stringify({ now: gen, results }, null, 1));
})().catch(e => { console.error('FAIL', e); process.exit(1); });
