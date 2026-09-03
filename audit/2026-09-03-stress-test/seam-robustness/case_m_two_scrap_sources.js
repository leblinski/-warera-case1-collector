// (m) index.json scraps best_bid 0.30 while commodities.json best_bid stays 0.225
const { run, load } = require('./common');
const i = load('index.json'); i.commodities.scraps.best_bid = 0.30; i.commodities.scraps.best_ask = 0.301;
run('case_m_two_scrap_sources', { overrides: { 'index.json': i }, price: '1.400' }).catch((e) => { console.error(e); process.exit(1); });
