// (j) selected.median null but count > 0 : (1) on every knife roll; (2) on every roll of every category
const { run, load } = require('./common');
const s1 = load('summary.json');
for (const k in s1.categories.knife.rolls) { const r = s1.categories.knife.rolls[k]; if (r.selected) r.selected.median = null; }
const s2 = load('summary.json');
for (const code in s2.categories) for (const k in s2.categories[code].rolls) { const r = s2.categories[code].rolls[k]; if (r.selected) r.selected.median = null; }
(async () => {
  await run('case_j_median_null_knife', { overrides: { 'summary.json': s1 }, slot: 'weapon' });
  await run('case_j_median_null_all', { overrides: { 'summary.json': s2 } });
})().catch((e) => { console.error(e); process.exit(1); });
