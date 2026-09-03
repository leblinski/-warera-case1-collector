// (i) schema_version 5 with 'selected' renamed to 'chosen' in every roll
const { run, load } = require('./common');
const s = load('summary.json'); s.schema_version = 5;
let n = 0, differ = 0;
for (const code in s.categories) for (const k in s.categories[code].rolls) {
  const r = s.categories[code].rolls[k]; r.chosen = r.selected; delete r.selected; n++;
  if (r.chosen && r.fallback_48h && r.chosen.median !== r.fallback_48h.median) differ++;
}
console.error('rolls renamed', n, 'rolls where selected.median != fallback_48h.median', differ);
run('case_i_schema5_chosen', { overrides: { 'summary.json': s } }).catch((e) => { console.error(e); process.exit(1); });
