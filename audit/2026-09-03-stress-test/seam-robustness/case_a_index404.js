// (a) index.json 404, summary/commodities fine
const { run } = require('./common');
run('case_a_index404', { overrides: { 'index.json': { __status: 404 } } }).catch((e) => { console.error(e); process.exit(1); });
