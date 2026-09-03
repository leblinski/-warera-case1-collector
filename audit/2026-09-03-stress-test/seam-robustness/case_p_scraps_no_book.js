// (p) commodities.json present but scraps has only price (no order_book)
const { run, load } = require('./common');
const c = load('commodities.json'); delete c.commodities.scraps.order_book;
run('case_p_scraps_no_book', { overrides: { 'commodities.json': c } }).catch((e) => { console.error(e); process.exit(1); });
