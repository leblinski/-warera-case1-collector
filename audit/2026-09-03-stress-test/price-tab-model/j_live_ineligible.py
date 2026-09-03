"""(f) Live rows are not condition-filtered: share of snapshot transactions the collector excludes
from comps (state < max_state, quantity != 1, missing roll) that a Gateway page would merge in.
Also: robustFilter effect on the median (filtered vs raw). Run: python3 j_live_ineligible.py"""
import json, glob, os, math, statistics
snap = json.load(open('/home/user/-warera-case1-collector/data/warera_case1_market.json'))
tot = bad_state = bad_qty = no_skill = 0
per = {}
newest100_bad = {}
for code, cat in snap['categories'].items():
    n = b = 0
    rows = sorted(cat['transactions'], key=lambda t: t['sold_at'], reverse=True)
    for i, tx in enumerate(rows):
        tot += 1; n += 1
        st, mx = tx.get('state'), tx.get('max_state')
        ineligible = False
        if st is None or mx is None or st < mx: bad_state += 1; ineligible = True
        if tx.get('quantity') != 1: bad_qty += 1; ineligible = True
        if not tx.get('skills'): no_skill += 1; ineligible = True
        if ineligible:
            b += 1
            if i < 100: newest100_bad[code] = newest100_bad.get(code, 0) + 1
    per[code] = (b, n)
print(f'snapshot transactions {tot}: state<max_state or missing {bad_state} ({bad_state/tot*100:.2f}%), quantity!=1 {bad_qty}, no skills {no_skill}')
print('items with the most ineligible rows among their newest 100 (what one Gateway page returns):', sorted(newest100_bad.items(), key=lambda kv: -kv[1])[:8])
print('per-item ineligible share, top 6:', sorted(((round(b / n * 100, 1), c) for c, (b, n) in per.items()), reverse=True)[:6])

# robustFilter: filtered median vs raw median, page fast window
from model import load_shard, State, Model, robustFilter, median, PUBLIC
codes = sorted(os.path.basename(p)[:-5] for p in glob.glob(f'{PUBLIC}/prices/*.json'))
diffs = []
for code in codes:
    shard = load_shard(code)
    for roll in shard['rolls']:
        st = State(shard, roll['skills'], 1.0); M = Model(st)
        sales, meta = M.analyse_sales(shard)
        raw = [it for it in sales if M.exactMatch(it)]
        if len(raw) < 5: continue
        kept = robustFilter(raw)
        diffs.append((median([it['money'] for it in kept]) - median([it['money'] for it in raw])) / median([it['money'] for it in raw]))
def pct(a, q):
    a = sorted(a); pos = (len(a) - 1) * q; lo = math.floor(pos); hi = math.ceil(pos)
    return a[lo] if lo == hi else a[lo] + (a[hi] - a[lo]) * (pos - lo)
print(f'robustFilter: filtered median vs raw median over {len(diffs)} rolls: mean {statistics.mean(diffs)*100:+.3f}% p10 {pct(diffs,.1)*100:+.3f}% p90 {pct(diffs,.9)*100:+.3f}% max {max(diffs)*100:+.2f}% min {min(diffs)*100:+.2f}%; rolls changed: {sum(1 for d in diffs if abs(d)>1e-9)}')
