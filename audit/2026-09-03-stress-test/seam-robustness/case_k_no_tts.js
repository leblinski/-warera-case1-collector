// (k) median_time_to_sell_seconds missing from every window
const { run, load } = require('./common');
const s = load('summary.json');
for (const code in s.categories) for (const k in s.categories[code].rolls) {
  const r = s.categories[code].rolls[k];
  for (const w of ['primary_24h', 'fallback_48h', 'retained_window', 'selected']) if (r[w]) delete r[w].median_time_to_sell_seconds;
}
run('case_k_no_tts', { overrides: { 'summary.json': s } }).catch((e) => { console.error(e); process.exit(1); });
