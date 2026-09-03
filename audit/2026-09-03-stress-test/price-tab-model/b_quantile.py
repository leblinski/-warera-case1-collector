"""(b) weightedQuantile(exact,0.55/0.70) vs plain median per roll, in the page's own fast window
and in the full 168h shard; plus the step-table recencyWeight vs the collector's 12h half-life.
Run: python3 b_quantile.py"""
import json, math, glob, os, statistics
from model import load_shard, State, Model, robustFilter, weightedQuantileBy, median, recencyWeight, PUBLIC

summary = json.load(open(f'{PUBLIC}/summary.json'))
codes = sorted(os.path.basename(p)[:-5] for p in glob.glob(f'{PUBLIC}/prices/*.json'))


def pct(a, q):
    a = sorted(a); pos = (len(a) - 1) * q; lo = math.floor(pos); hi = math.ceil(pos)
    return a[lo] if lo == hi else a[lo] + (a[hi] - a[lo]) * (pos - lo)


def describe(name, xs):
    if not xs: print(name, 'n=0'); return
    print(f'{name}: n={len(xs)} mean={statistics.mean(xs)*100:+.2f}% median={pct(xs,.5)*100:+.2f}% p10={pct(xs,.1)*100:+.2f}% p90={pct(xs,.9)*100:+.2f}% '
          f'share>0={sum(1 for x in xs if x>1e-9)/len(xs):.2f} share==0={sum(1 for x in xs if abs(x)<=1e-9)/len(xs):.2f} share<0={sum(1 for x in xs if x<-1e-9)/len(xs):.2f}')


rows = []
for code in codes:
    shard = load_shard(code)
    for roll in shard['rolls']:
        sk = roll['skills']
        st = State(shard, sk, 1.0)
        M = Model(st)
        for deep in (False, True):
            sales, meta = M.analyse_sales(shard, deep)
            raw_exact = [it for it in sales if M.exactMatch(it)]
            exact = robustFilter(raw_exact)
            if len(exact) < 5: continue
            q55 = M.weightedQuantile(exact, .55); q70 = M.weightedQuantile(exact, .70); q50 = M.weightedQuantile(exact, .50)
            med = median([it['money'] for it in exact]); med_raw = median([it['money'] for it in raw_exact])
            # collector-style: 12h half-life exponential weights, weighted median (q=.5)
            exp12 = weightedQuantileBy(exact, .5, lambda it: 2 ** (-M.saleAge(it) / 12))
            key = json.dumps({'skills': sk}, separators=(',', ':'))
            sel = summary['categories'][code]['rolls'].get(key, {}).get('selected', {})
            rows.append({'code': code, 'tier': st.tier, 'deep': deep, 'n': len(exact), 'q55': q55, 'q70': q70, 'q50': q50, 'med': med,
                         'med_raw': med_raw, 'exp12': exp12, 'sel_med': sel.get('median'), 'sel_n': sel.get('count')})

for deep in (False, True):
    R = [r for r in rows if r['deep'] == deep]
    print(f'\n=== window: {"full 168h (deep, unreachable in UI)" if deep else "fast window (initialTargetHours per tier)"}; rolls with >=5 filtered exact sales: {len(R)}')
    describe(' q55 vs plain median of same (filtered) set', [(r['q55'] - r['med']) / r['med'] for r in R])
    describe(' q70 vs plain median', [(r['q70'] - r['med']) / r['med'] for r in R])
    describe(' q50(step weights) vs plain median', [(r['q50'] - r['med']) / r['med'] for r in R])
    describe(' q55 vs 12h-half-life weighted median', [(r['q55'] - r['exp12']) / r['exp12'] for r in R])
    describe(' q55 vs collector selected.median (Sort tab figure)', [(r['q55'] - r['sel_med']) / r['sel_med'] for r in R if r['sel_med']])
    describe(' plain filtered median vs collector selected.median', [(r['med'] - r['sel_med']) / r['sel_med'] for r in R if r['sel_med']])
    for t in range(1, 7):
        describe(f'  tier {t} q55 vs median', [(r['q55'] - r['med']) / r['med'] for r in R if r['tier'] == t])
    R10 = [r for r in R if r['n'] >= 10]
    describe(' [n>=10] q55 vs plain median', [(r['q55'] - r['med']) / r['med'] for r in R10])
    describe(' [n>=10] q70 vs plain median', [(r['q70'] - r['med']) / r['med'] for r in R10])
    big = sorted(R, key=lambda r: -abs((r['q55'] - r['med']) / r['med']))[:8]
    print(' largest |q55-med|:', [(r['code'], r['n'], r['q55'], r['med']) for r in big])

print('\n=== recencyWeight step table vs collector 2^(-age/12h): equivalent half-life at each step boundary')
for age in (6, 12, 24, 48, 72, 120, 168):
    w = recencyWeight(age) / 1.12
    h = -age / math.log2(w)
    print(f' age {age:>3}h: page weight ratio to fresh {w:.3f} -> equivalent half-life {h:.1f}h; collector ratio {2**(-age/12):.4f}')
