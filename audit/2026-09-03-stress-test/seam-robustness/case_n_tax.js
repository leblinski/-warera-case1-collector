// (n) tax input 0, blank, -5, 100 ; price 1.400 typed so the Price tab figure is visible
const { run } = require('./common');
(async () => {
  for (const t of ['0', '', '-5', '100']) await run('case_n_tax_' + (t === '' ? 'blank' : t), { tax: t, price: '1.400' });
})().catch((e) => { console.error(e); process.exit(1); });
