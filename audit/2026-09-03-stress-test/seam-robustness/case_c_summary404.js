// (c) summary.json 404
const { run } = require('./common');
run('case_c_summary404', { overrides: { 'summary.json': { __status: 404 } } }).catch((e) => { console.error(e); process.exit(1); });
