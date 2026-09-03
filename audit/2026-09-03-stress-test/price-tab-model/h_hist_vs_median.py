"""(a/d) Historical target (the Trends engine) vs the roll's own clearing price, every roll.
For each roll with >=3 exact sales in the page's fast window: page histTarget (floor irrelevant),
the q55 of the exact sales alone, the collector's selected.median, and whether the weapon comps
dropped the exact rows. Run: python3 h_hist_vs_median.py"""
import json, math, glob, os
from model import load_shard, State, Model, robustFilter, median, PUBLIC, WEAPON_STATS

summary = json.load(open(f'{PUBLIC}/summary.json'))
codes = sorted(os.path.basename(p)[:-5] for p in glob.glob(f'{PUBLIC}/prices/*.json'))


def pct(a, q):
    a = sorted(a); pos = (len(a) - 1) * q; lo = math.floor(pos); hi = math.ceil(pos)
    return a[lo] if lo == hi else a[lo] + (a[hi] - a[lo]) * (pos - lo)


def describe(name, xs):
    if not xs: print(f'{name}: n=0'); return
    print(f'{name}: n={len(xs)} median={pct(xs,.5)*100:+.2f}% p10={pct(xs,.1)*100:+.2f}% p90={pct(xs,.9)*100:+.2f}% min={min(xs)*100:+.1f}% max={max(xs)*100:+.1f}% '
          f'|err|>5%: {sum(1 for x in xs if abs(x)>.05)}  |err|>10%: {sum(1 for x in xs if abs(x)>.10)}  |err|>25%: {sum(1 for x in xs if abs(x)>.25)}')


out = []
for code in codes:
    shard = load_shard(code)
    for roll in shard['rolls']:
        sk = roll['skills']
        st = State(shard, sk, 1000.0); M = Model(st)   # floor far above: 'higher' never; hist unaffected
        sales, meta = M.analyse_sales(shard)
        exact_raw = [it for it in sales if M.exactMatch(it)]
        if len(exact_raw) < 3: continue
        m = M.build(sales, meta)
        exact_q55 = M.weightedQuantile(robustFilter(exact_raw), .55)
        key = json.dumps({'skills': sk}, separators=(',', ':'))
        sel = summary['categories'][code]['rolls'].get(key, {}).get('selected', {})
        rec = {'code': code, 'slot': shard['slot'], 'tier': st.tier, 'roll': sk, 'n_exact': len(exact_raw), 'hist': m['histTarget'],
               'exact_q55': exact_q55, 'sel_med': sel.get('median'), 'score': m['confidenceScore'], 'source': m['source']}
        if shard['slot'] == 'weapon':
            comp = m['selected']
            rec['n_comp'] = len(comp); rec['exact_in_comp'] = sum(1 for it in comp if M.exactMatch(it))
            rec['max_attack'] = sk['attack'] == WEAPON_STATS[st.tier - 1][0][1]
        out.append(rec)

print('=== hist vs q55 of the exact roll alone (same window, same weights):')
for slot in ('weapon', 'armour'):
    R = [r for r in out if (r['slot'] == 'weapon') == (slot == 'weapon')]
    describe(f' {slot}', [(r['hist'] - r['exact_q55']) / r['exact_q55'] for r in R])
print('=== hist vs collector selected.median (what the Sort tab / rollFacts "LIST AT" shows):')
for code in codes:
    R = [r for r in out if r['code'] == code and r['sel_med']]
    if R: describe(f' {code:8}', [(r['hist'] - r['sel_med']) / r['sel_med'] for r in R])
print('\n=== weapons: comparables vs exact rows')
for code in ['knife', 'gun', 'rifle', 'sniper', 'tank', 'jet']:
    R = [r for r in out if r['code'] == code]
    if not R: print(f' {code}: no roll with >=3 exact sales in window'); continue
    lost = [r for r in R if r['exact_in_comp'] < min(r['n_exact'], 12)]
    zero = [r for r in R if r['exact_in_comp'] == 0]
    print(f' {code}: rolls={len(R)} rolls where comps hold fewer exact rows than available={len(lost)} rolls with NO exact row in comps={len(zero)}')
    worst = sorted(R, key=lambda r: abs((r['hist'] - r['exact_q55']) / r['exact_q55']))[-5:]
    for r in worst:
        print(f'    {r["roll"]} n_exact={r["n_exact"]} exact_in_comp={r["exact_in_comp"]}/{r["n_comp"]} hist={r["hist"]} exact_q55={r["exact_q55"]} sel_med={r["sel_med"]} score={r["score"]} max_attack={r["max_attack"]}')
print('\n=== max-attack weapon rolls (the non-broken cliff): hist vs exact q55')
describe(' max-attack rolls', [(r['hist'] - r['exact_q55']) / r['exact_q55'] for r in out if r['slot'] == 'weapon' and r['max_attack']])
describe(' other weapon rolls', [(r['hist'] - r['exact_q55']) / r['exact_q55'] for r in out if r['slot'] == 'weapon' and not r['max_attack']])
print('\n=== armour rolls: source of hist and worst cases')
from collections import Counter
print(' sources:', Counter(r['source'] for r in out if r['slot'] != 'weapon'))
worst = sorted([r for r in out if r['slot'] != 'weapon'], key=lambda r: abs((r['hist'] - r['exact_q55']) / r['exact_q55']))[-5:]
for r in worst: print('   ', r)
json.dump(out, open('h_rows.json', 'w'))
