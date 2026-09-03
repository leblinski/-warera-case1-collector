// (o) index.json fails -> Price tab's hard-coded 0.218 fallback; commodities.json (Sort/Craft/Cases) still 0.225
const { run } = require('./common');
(async () => {
  await run('case_o_scrap_fallback_404', { overrides: { 'index.json': { __status: 404 } }, price: '1.400' });
  // same but index.json is valid JSON with no commodities block
  await run('case_o_scrap_fallback_nocomm', { overrides: { 'index.json': { schema_version: 4, generated_at: '2026-09-03T15:30:50.113Z', status: 'ok' } }, price: '1.400' });
})().catch((e) => { console.error(e); process.exit(1); });
