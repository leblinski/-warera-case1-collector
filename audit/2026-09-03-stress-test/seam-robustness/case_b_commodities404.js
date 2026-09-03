// (b) commodities.json 404
const { run } = require('./common');
run('case_b_commodities404', { overrides: { 'commodities.json': { __status: 404 } } }).catch((e) => { console.error(e); process.exit(1); });
