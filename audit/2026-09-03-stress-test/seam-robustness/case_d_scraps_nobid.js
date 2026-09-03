// (d) scraps order_book with empty buy_orders and best_bid null (commodities.json); index.json untouched
const { run, load } = require('./common');
const c = load('commodities.json');
c.commodities.scraps.order_book.buy_orders = []; c.commodities.scraps.order_book.best_bid = null;
run('case_d_scraps_nobid', { overrides: { 'commodities.json': c } }).catch((e) => { console.error(e); process.exit(1); });
