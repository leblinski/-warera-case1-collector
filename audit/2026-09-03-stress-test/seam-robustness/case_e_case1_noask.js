// (e) case1 sell_orders empty, best_ask null
const { run, load } = require('./common');
const c = load('commodities.json');
c.commodities.case1.order_book.sell_orders = []; c.commodities.case1.order_book.best_ask = null;
run('case_e_case1_noask', { overrides: { 'commodities.json': c } }).catch((e) => { console.error(e); process.exit(1); });
