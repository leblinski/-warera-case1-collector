"""(e) velocity ('sales / hour') vs the true sales/hour of the exact roll and of the band; plus
opportunityDepthBands. Run: python3 e_velocity.py"""
import json, math, glob, os, statistics
from model import load_shard, State, Model, robustFilter, median, PUBLIC, soldHours, qnum

codes = sorted(os.path.basename(p)[:-5] for p in glob.glob(f'{PUBLIC}/prices/*.json'))


def pct(a, q):
    a = sorted(a); pos = (len(a) - 1) * q; lo = math.floor(pos); hi = math.ceil(pos)
    return a[lo] if lo == hi else a[lo] + (a[hi] - a[lo]) * (pos - lo)


ratios_exact, ratios_band, weapon_ratios = [], [], []
print('code roll | page velocity | exact sales/h (window) | band(|d|<=5 or all comps) sales/h | coverage h | n_exact')
for code in codes:
    shard = load_shard(code)
    # the top-count roll for this item = a typical roll
    counts = {}
    for it in shard['_sales']: counts[json.dumps(it['skills'], sort_keys=True)] = counts.get(json.dumps(it['skills'], sort_keys=True), 0) + 1
    top = json.loads(max(counts, key=counts.get))
    st = State(shard, top, 1.0); M = Model(st)
    sales, meta = M.analyse_sales(shard)
    m = M.build(sales, meta)
    cov = max(.25, meta['coverageHours'])
    n_exact = sum(1 for it in sales if M.exactMatch(it))
    true_exact = n_exact / cov
    if st.slot == 'weapon':
        band = len(sales) / cov
        weapon_ratios.append(m['velocity'] / true_exact if true_exact else float('nan'))
    else:
        t = M.singleStatTarget()
        band = sum(1 for it in sales if M.statValue(it) is not None and abs(M.statValue(it) - t) <= 5) / cov
    if true_exact: ratios_exact.append(m['velocity'] / true_exact)
    if band: ratios_band.append(m['velocity'] / band)
    print(f'{code:8} {json.dumps(top):45} | {m["velocity"]:7.2f} | {true_exact:7.2f} | {band:7.2f} | {cov:5.1f} | {n_exact}')

print('\nvelocity / true exact sales-per-hour: median %.2f p10 %.2f p90 %.2f' % (pct(ratios_exact, .5), pct(ratios_exact, .1), pct(ratios_exact, .9)))
print('velocity / band sales-per-hour:       median %.2f p10 %.2f p90 %.2f' % (pct(ratios_band, .5), pct(ratios_band, .1), pct(ratios_band, .9)))
print('weapons only, velocity / exact:       ', [round(x, 2) for x in weapon_ratios])

# Across every roll with >=5 exact sales in the window (armour), the ratio velocity/(exact/h)
allr = []
for code in codes:
    shard = load_shard(code)
    if shard['slot'] == 'weapon': continue
    for roll in shard['rolls']:
        st = State(shard, roll['skills'], 1.0); M = Model(st)
        sales, meta = M.analyse_sales(shard)
        n_exact = sum(1 for it in sales if M.exactMatch(it))
        if n_exact < 5: continue
        cov = max(.25, meta['coverageHours'])
        v = M.velocityForSingle(sales, cov)
        allr.append((v / (n_exact / cov), st.tier, code, roll['skills'], v, n_exact / cov))
xs = [r[0] for r in allr]
print(f'\narmour rolls n_exact>=5: {len(allr)}; velocity/(exact per h): median {pct(xs,.5):.2f} p10 {pct(xs,.1):.2f} p90 {pct(xs,.9):.2f} min {min(xs):.2f} max {max(xs):.2f}')
for t in range(1, 7):
    ys = [r[0] for r in allr if r[1] == t]
    if ys: print(f'  tier {t}: n={len(ys)} median {pct(ys,.5):.2f} p10 {pct(ys,.1):.2f} p90 {pct(ys,.9):.2f}')

# weapons: velocity is a sum over at most 12 comparables -> hard cap 12*1.12/coverage
print('\nweapon velocity hard cap = 12*1.12/coverage:')
for code in ['knife', 'gun', 'rifle', 'sniper', 'tank', 'jet']:
    shard = load_shard(code)
    st = State(shard, shard['rolls'][0]['skills'], 1.0); M = Model(st)
    sales, meta = M.analyse_sales(shard)
    cov = max(.25, meta['coverageHours'])
    print(f'  {code}: coverage {cov:.2f}h -> cap {12*1.12/cov:.2f}/h ; actual item sales/h in window {len(sales)/cov:.2f}')

# opportunityDepthBands for the two 'higher' cases
print('\nopportunityDepthBands:')
for code, roll, floor in [('boots4', {'dodge': 25}, 60.0), ('tank', {'attack': 141, 'criticalChance': 34}, 140.0), ('knife', {'attack': 40, 'criticalChance': 5}, 1.8)]:
    shard = load_shard(code); st = State(shard, roll, floor); M = Model(st)
    sales, meta = M.analyse_sales(shard); m = M.build(sales, meta)
    b = M.opportunityDepthBands(m)
    cov = max(.25, meta['coverageHours'])
    n_exact = sum(1 for it in sales if M.exactMatch(it))
    exact_rows = [it for it in sales if M.exactMatch(it)]
    durs = [soldHours(it) for it in exact_rows if soldHours(it) is not None]
    med_sold = qnum(durs, .5) if durs else None
    true_rate = n_exact / cov
    # competitors that matter: exact-or-better rolls sold at >= floor within the window
    print(f'  {code} {roll} floor {floor}: higher={m["higher"]} hist={m["histTarget"]} velocity={b["velocity"]:.2f}/h cycle={b["cycleHours"]:.2f}h (durations n={b["durationCount"]}) '
          f'-> SAFE 0-{b["safeMax"]}, LESS SAFE {b["safeMax"]+1}-{b["cautionMax"]}, RISKY {b["cautionMax"]+1}+')
    print(f'     true exact-roll rate {true_rate:.2f}/h, exact median sold-in {med_sold if med_sold is None else round(med_sold,2)}h -> exact sales per median sold-in {"-" if med_sold is None else round(true_rate*max(.25,med_sold),1)}; '
          f'queue hours for 12 blockers: page {12/b["velocity"]:.2f}h vs exact-rate {12/true_rate if true_rate else float("inf"):.2f}h')
