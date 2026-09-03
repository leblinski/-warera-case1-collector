// (g) tier with zero coverage: all six Mythic categories keep their entry but rolls = {}
const { run, load } = require('./common');
const s = load('summary.json');
for (const k of ['jet', 'boots6', 'helmet6', 'gloves6', 'chest6', 'pants6']) s.categories[k].rolls = {};
run('case_g_mythic_zero', { overrides: { 'summary.json': s }, sortTiers: [1, 6] }).catch((e) => { console.error(e); process.exit(1); });
