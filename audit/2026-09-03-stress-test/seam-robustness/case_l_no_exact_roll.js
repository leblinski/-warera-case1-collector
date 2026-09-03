// (l) exact_roll missing on some rolls: every other knife roll and every other boots1 roll
const { run, load } = require('./common');
const s = load('summary.json'); const dropped = {};
for (const code of ['knife', 'boots1']) { let i = 0; dropped[code] = []; for (const k in s.categories[code].rolls) { if (i++ % 2 === 0) { delete s.categories[code].rolls[k].exact_roll; dropped[code].push(k); } } }
console.error('dropped exact_roll on', JSON.stringify(dropped));
run('case_l_no_exact_roll', { overrides: { 'summary.json': s } }).catch((e) => { console.error(e); process.exit(1); });
