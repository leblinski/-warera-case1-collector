"""(b)(c)(e) Out-of-sample estimator comparison with rolling origins.
For each roll and origin T (every ORIGIN_STEP_H hours from first_sale+48h to now-24h), estimate
from non-stale sales with sold_at <= T and score against non-stale sales in (T, T+24h].
Losses per (roll, T): relMAE = mean_i |est-p_i|/p_i ; bias = mean_i (est-p_i)/p_i ;
sold = share of p_i >= est ; rev = est*sold / median(future p) (revenue proxy vs 'listing at the
realised median').  Aggregates are equal-weight per roll-origin; noise = cluster (by roll)
bootstrap of the paired difference vs the plain 48h median."""
import sys, os, statistics, random, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

random.seed(1)
ORIGIN_STEP_H = int(sys.argv[1]) if len(sys.argv) > 1 else 6
HOR = int(sys.argv[2]) if len(sys.argv) > 2 else 24
NOW = now_epoch()
rolls, meta = load()
first = min(v[0][0] for v in rolls.values())
origins = list(range(first + 48 * H, NOW - HOR * H + 1, ORIGIN_STEP_H * H))
print('now', NOW, 'first sale', first, 'origins', len(origins), 'step h', ORIGIN_STEP_H)

EST = ['med48', 'selected', 'med24', 'rwmed', 'rwmean', 'trim20', 'last3', 'q25', 'q75', 'ret7', 'wmean_all']

def estimates(hist, T):
    """hist: list of (t, p, tts) with t <= T, sorted by t."""
    w48 = [(t, p) for t, p, _ in hist if t > T - 48 * H]
    w24 = [p for t, p in w48 if t > T - 24 * H]
    w7 = [p for t, p, _ in hist if t > T - 168 * H]
    if not w48:
        return None, 0, len(w24), len(w7)
    p48 = [p for _, p in w48]
    weights = [2 ** (-(T - t) / (12 * H)) for t, _ in w48]
    out = {
        'med48': median(p48),
        'selected': median(w24) if len(w24) >= 3 else median(p48),
        'med24': median(w24) if w24 else None,
        'rwmed': weighted_median(p48, weights),
        'rwmean': sum(p * w for p, w in zip(p48, weights)) / sum(weights),
        'trim20': trimmed_mean(p48, 0.2),
        'last3': median(p48[-3:]),
        'q25': quantile(p48, .25),
        'q75': quantile(p48, .75),
        'ret7': median(w7) if w7 else None,
        'wmean_all': sum(p48) / len(p48),
    }
    return out, len(p48), len(w24), len(w7)

records = []  # dict per roll-origin
for key, v in rolls.items():
    ts = [t for t, _, _ in v]
    import bisect
    for T in origins:
        i = bisect.bisect_right(ts, T)
        j = bisect.bisect_right(ts, T + HOR * H)
        hist = v[:i]; fut = [p for _, p, _ in v[i:j]]
        if not fut:
            continue
        est, n48, n24, n7 = estimates(hist, T)
        rec = {'key': key, 'T': T, 'n48': n48, 'n24': n24, 'n7': n7, 'nfut': len(fut),
               'fut_med': median(fut), 'tier': meta[key[0]]['tier'], 'est': est, 'losses': {}}
        if est is None:
            # quiet roll: only ret7 may exist
            w7 = [p for t, p, _ in hist if t > T - 168 * H]
            rec['est'] = {'ret7': median(w7) if w7 else None}
        for name, e in rec['est'].items():
            if e is None: continue
            rel = [(e - p) / p for p in fut]
            rec['losses'][name] = (statistics.mean(abs(r) for r in rel), statistics.mean(rel),
                                   sum(1 for p in fut if p >= e) / len(fut),
                                   e * sum(1 for p in fut if p >= e) / len(fut) / median(fut))
        records.append(rec)
print('roll-origins with >=1 future sale:', len(records),
      ' with n48>=1:', sum(1 for r in records if r['n48'] >= 1),
      ' distinct rolls:', len(set(r['key'] for r in records)))

def table(recs, names, title):
    print('\n== %s  (roll-origins=%d, rolls=%d, future sales=%d) ==' % (
        title, len(recs), len(set(r['key'] for r in recs)), sum(r['nfut'] for r in recs)))
    print('%-10s %7s %7s %7s %7s %7s | %s' % ('estimator', 'relMAE%', 'medAE%', 'bias%', 'sold%', 'rev', 'dRelMAE vs med48 [95% cluster-boot CI]'))
    base = [r['losses']['med48'][0] for r in recs]
    for name in names:
        L = [r['losses'][name] for r in recs if name in r['losses']]
        if len(L) != len(recs):
            print('%-10s  (defined on %d of %d)' % (name, len(L), len(recs)))
            continue
        mae = statistics.mean(l[0] for l in L) * 100
        medae = statistics.median(l[0] for l in L) * 100
        bias = statistics.mean(l[1] for l in L) * 100
        sold = statistics.mean(l[2] for l in L) * 100
        rev = statistics.mean(l[3] for l in L)
        # paired diff, cluster bootstrap by roll
        diffs = [(r['key'], r['losses'][name][0] - r['losses']['med48'][0]) for r in recs]
        by = {}
        for k, d in diffs: by.setdefault(k, []).append(d)
        keys = list(by)
        boots = []
        for _ in range(400):
            s = [by[random.choice(keys)] for _ in keys]
            flat = [d for grp in s for d in grp]
            boots.append(statistics.mean(flat) * 100)
        boots.sort()
        md = statistics.mean(d for _, d in diffs) * 100
        print('%-10s %7.2f %7.2f %+7.2f %7.1f %7.3f | %+6.2f [%+.2f, %+.2f]' % (
            name, mae, medae, bias, sold, rev, md, boots[int(.025 * len(boots))], boots[int(.975 * len(boots))]))

pop = [r for r in records if r['n48'] >= 1]
table(pop, [e for e in EST if e != 'med24'], '(b) all roll-origins with >=1 sale in the 48h before T')
table([r for r in pop if r['n48'] >= 5], [e for e in EST if e != 'med24'], '(b) n48 >= 5')
table([r for r in pop if r['n48'] >= 30], [e for e in EST if e != 'med24'], '(b) n48 >= 30')
table([r for r in pop if r['nfut'] >= 5], [e for e in EST if e != 'med24'], '(b) future sales >= 5 (scoring less noisy)')

# by tier
for tier in ['basic', 'reinforced', 'advanced', 'elite', 'legendary', 'mythic']:
    sub = [r for r in pop if r['tier'] == tier]
    if sub: table(sub, ['med48', 'selected', 'rwmed', 'rwmean', 'trim20', 'last3', 'ret7'], '(b) tier ' + tier)

# (c) 24h vs 48h where both populated (n24 >= 3)
both = [r for r in pop if r['n24'] >= 3]
table(both, ['med48', 'med24', 'selected', 'rwmed', 'last3'], '(c) n24 >= 3: 24h median vs 48h median')
for lo, hi in [(3, 4), (5, 9), (10, 29), (30, 10 ** 9)]:
    sub = [r for r in both if lo <= r['n24'] <= hi]
    if sub: table(sub, ['med48', 'med24', 'rwmed'], '(c) n24 in [%d,%s]' % (lo, hi if hi < 10 ** 9 else 'inf'))
# alternative switch thresholds
print('\n== (c) switch threshold sweep: relMAE% of "24h median if n24>=k else 48h median" over all pop ==')
for k in [1, 2, 3, 5, 8, 10, 15, 20, 10 ** 9]:
    L = []
    for r in pop:
        e = r['est']['med24'] if r['n24'] >= k and r['est']['med24'] is not None else r['est']['med48']
        fut_rel = None
        # recompute losses from est
        L.append(e)
    # need future prices: recompute quickly
    maes = []; sold = []
    for r, e in zip(pop, L):
        # approximate using stored losses if e equals one of the stored estimators
        if e == r['est']['med24']: maes.append(r['losses']['med24'][0]); sold.append(r['losses']['med24'][2])
        else: maes.append(r['losses']['med48'][0]); sold.append(r['losses']['med48'][2])
    print('  k=%-9s relMAE %.3f%%  sold %.1f%%' % (k if k < 10 ** 9 else 'never', 100 * statistics.mean(maes), 100 * statistics.mean(sold)))

# (d-support) relMAE of med48 by n48 bucket: is count<5 predictive of a worse estimate?
print('\n== (d) plain med48 error by n48 bucket (is the thin cut at 5 where the error changes?) ==')
print('bucket      roll-origins  relMAE%  medAE%  p90AE%  |bias|>10%% share  sold%')
for lo, hi in [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 7), (8, 9), (10, 14), (15, 29), (30, 59), (60, 10 ** 9)]:
    sub = [r for r in pop if lo <= r['n48'] <= hi]
    if not sub: continue
    ae = sorted(r['losses']['med48'][0] for r in sub)
    print('%-3d-%-6s %8d   %6.2f  %6.2f  %6.2f   %5.1f%%   %5.1f' % (
        lo, hi if hi < 10 ** 9 else 'inf', len(sub), 100 * statistics.mean(ae), 100 * statistics.median(ae),
        100 * ae[int(.9 * len(ae))], 100 * sum(1 for r in sub if abs(r['losses']['med48'][1]) > .1) / len(sub),
        100 * statistics.mean(r['losses']['med48'][2] for r in sub)))

# (e) thin rolls: 48h median vs retained 7d median
thin = [r for r in pop if r['n48'] <= 4]
table(thin, ['med48', 'selected', 'ret7', 'last3', 'rwmed'], '(e) thin: n48 in 1..4 -> 48h median vs 7-day retained median')
for n in (1, 2, 3, 4):
    sub = [r for r in thin if r['n48'] == n]
    table(sub, ['med48', 'ret7'], '(e) n48 == %d' % n)
# thin rolls where the 7d window adds material history (n7 >= n48+3)
sub = [r for r in thin if r['n7'] >= r['n48'] + 3]
table(sub, ['med48', 'ret7'], '(e) thin AND n7 >= n48+3 (retained adds >=3 older sales)')
# blend: if n48<5 use ret7 else med48
print('\n== (e) policy comparison over ALL pop: relMAE% ==')
for label, fn in [('med48 always', lambda r: r['losses']['med48']),
                  ('selected (page)', lambda r: r['losses']['selected']),
                  ('ret7 if n48<5 else selected', lambda r: r['losses']['ret7'] if r['n48'] < 5 else r['losses']['selected']),
                  ('ret7 if n48<3 else selected', lambda r: r['losses']['ret7'] if r['n48'] < 3 else r['losses']['selected']),
                  ('ret7 always', lambda r: r['losses']['ret7'])]:
    L = [fn(r) for r in pop]
    print('  %-30s relMAE %.3f%%  bias %+.3f%%  sold %.1f%%' % (label, 100 * statistics.mean(l[0] for l in L),
                                                               100 * statistics.mean(l[1] for l in L), 100 * statistics.mean(l[2] for l in L)))
# quiet rolls (n48 == 0, but retained): ret7 error
quiet = [r for r in records if r['n48'] == 0 and 'ret7' in r['losses']]
if quiet:
    ae = sorted(r['losses']['ret7'][0] for r in quiet)
    print('\n(e) quiet roll-origins (no 48h sale, retained exists): %d ; ret7 relMAE %.2f%% medAE %.2f%% bias %+.2f%% sold %.1f%%' % (
        len(quiet), 100 * statistics.mean(ae), 100 * statistics.median(ae),
        100 * statistics.mean(r['losses']['ret7'][1] for r in quiet), 100 * statistics.mean(r['losses']['ret7'][2] for r in quiet)))
