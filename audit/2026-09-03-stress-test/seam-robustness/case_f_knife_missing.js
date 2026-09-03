// (f) a category missing from summary: delete knife
const { run, load } = require('./common');
const s = load('summary.json'); delete s.categories.knife;
run('case_f_knife_missing', { overrides: { 'summary.json': s } }).catch((e) => { console.error(e); process.exit(1); });
