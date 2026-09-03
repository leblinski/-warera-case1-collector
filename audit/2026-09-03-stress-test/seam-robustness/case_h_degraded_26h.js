// (h) status 'degraded' + generated_at 26h old (all three files), clock frozen 26h after generated_at
const { run, load } = require('./common');
const i = load('index.json'), s = load('summary.json'), c = load('commodities.json');
const gen = '2026-09-02T13:35:00.000Z';
for (const f of [i, s, c]) { f.status = 'degraded'; f.generated_at = gen; if (f.updated_at) f.updated_at = gen; }
run('case_h_degraded_26h', { overrides: { 'index.json': i, 'summary.json': s, 'commodities.json': c }, now: Date.parse('2026-09-03T15:35:00Z') }).catch((e) => { console.error(e); process.exit(1); });
