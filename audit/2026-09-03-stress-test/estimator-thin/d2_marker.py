"""(d) Which 'thin/uncertain' treatment actually flags the roll-origins whose 48h median turns
out to be wrong the next day?  Rolling origins as in b_oos.py; the target is
|next-day realised median / estimate - 1| > 5% (and > 10%).  Rules compared:
count<5 (page's marker), count<3, count==1, 48h (max-min)/median > 10%, IQR/median > 5%,
bootstrap-CI half-width of the median > 3%, tier-based (basic|reinforced).
Reports flagged share, precision, recall, and the median next-day error inside/outside the flag."""
import sys, os, statistics, random, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

random.seed(2)
NOW = now_epoch()
rolls, meta = load()
first = min(v[0][0] for v in rolls.values())
origins = list(range(first + 48 * H, NOW - 24 * H + 1, 6 * H))

def boot_halfwidth(ps, reps=200):
    if len(ps) < 2: return float('inf')
    ms = sorted(median([random.choice(ps) for _ in ps]) for _ in range(reps))
    m = median(ps)
    return (ms[int(.95 * reps)] - ms[int(.05 * reps)]) / 2 / m

rows = []
for key, v in rolls.items():
    ts = [t for t, _, _ in v]
    tier = meta[key[0]]['tier']
    for T in origins:
        i = bisect.bisect_right(ts, T); j = bisect.bisect_right(ts, T + 24 * H)
        fut = [p for _, p, _ in v[i:j]]
        p48 = [p for t, p, _ in v[:i] if t > T - 48 * H]
        p24 = [p for t, p, _ in v[:i] if t > T - 24 * H]
        if not fut or not p48: continue
        sel = p24 if len(p24) >= 3 else p48
        m = median(sel); fm = median(fut)
        err = abs(fm / m - 1)
        rows.append(dict(tier=tier, n=len(sel), n48=len(p48), err=err, nfut=len(fut),
                         rng=(max(p48) - min(p48)) / median(p48),
                         iqr=(quantile(p48, .75) - quantile(p48, .25)) / median(p48),
                         bw=boot_halfwidth(p48)))
print('roll-origins:', len(rows), ' share with next-day |err|>5%%: %.1f%%  >10%%: %.1f%%' % (
    100 * sum(r['err'] > .05 for r in rows) / len(rows), 100 * sum(r['err'] > .10 for r in rows) / len(rows)))

rules = [
    ('count<5 (page marker, selected.count)', lambda r: r['n'] < 5),
    ('count<3', lambda r: r['n'] < 3),
    ('count==1', lambda r: r['n'] == 1),
    ('n48<5', lambda r: r['n48'] < 5),
    ('48h range/median>10%', lambda r: r['rng'] > .10),
    ('48h range/median>20%', lambda r: r['rng'] > .20),
    ('IQR/median>5%', lambda r: r['iqr'] > .05),
    ('IQR/median>3%', lambda r: r['iqr'] > .03),
    ('boot 90% CI halfwidth>3%', lambda r: r['bw'] > .03),
    ('boot 90% CI halfwidth>2%', lambda r: r['bw'] > .02),
    ('tier basic|reinforced', lambda r: r['tier'] in ('basic', 'reinforced')),
    ('count<5 OR range>20%', lambda r: r['n'] < 5 or r['rng'] > .20),
    ('count<5 OR IQR>5%', lambda r: r['n'] < 5 or r['iqr'] > .05),
]
print('\n%-40s %7s | %7s %7s | %7s %7s | %9s %9s' % ('rule', 'flag%', 'prec5%', 'rec5%', 'prec10%', 'rec10%', 'medErr_in', 'medErr_out'))
for name, fn in rules:
    fl = [r for r in rows if fn(r)]; un = [r for r in rows if not fn(r)]
    b5 = sum(r['err'] > .05 for r in rows); b10 = sum(r['err'] > .10 for r in rows)
    p5 = 100 * sum(r['err'] > .05 for r in fl) / len(fl) if fl else float('nan')
    r5 = 100 * sum(r['err'] > .05 for r in fl) / b5
    p10 = 100 * sum(r['err'] > .10 for r in fl) / len(fl) if fl else float('nan')
    r10 = 100 * sum(r['err'] > .10 for r in fl) / b10
    print('%-40s %6.1f%% | %6.1f%% %6.1f%% | %6.1f%% %6.1f%% | %8.2f%% %8.2f%%' % (
        name, 100 * len(fl) / len(rows), p5, r5, p10, r10,
        100 * statistics.median(r['err'] for r in fl) if fl else float('nan'),
        100 * statistics.median(r['err'] for r in un) if un else float('nan')))

# what does the bootstrap band look like vs n, and vs tier?
print('\n== next-day |err| (median, p90) by selected count n ==')
for lo, hi in [(1, 1), (2, 2), (3, 3), (4, 4), (5, 6), (7, 9), (10, 19), (20, 49), (50, 10 ** 9)]:
    sub = sorted(r['err'] for r in rows if lo <= r['n'] <= hi)
    if sub: print('  n %2d-%-4s  N=%5d  med %.2f%%  p90 %.2f%%  >5%%: %.1f%%' % (
        lo, hi if hi < 10 ** 9 else 'inf', len(sub), 100 * statistics.median(sub), 100 * sub[int(.9 * len(sub))],
        100 * sum(e > .05 for e in sub) / len(sub)))
print('\n== next-day |err| by tier ==')
for tier in ['basic', 'reinforced', 'advanced', 'elite', 'legendary', 'mythic']:
    sub = sorted(r['err'] for r in rows if r['tier'] == tier)
    if sub: print('  %-10s N=%5d  med %.2f%%  p90 %.2f%%  >5%%: %.1f%%  | median boot halfwidth %.2f%%  median IQR/med %.2f%%  median range/med %.1f%%' % (
        tier, len(sub), 100 * statistics.median(sub), 100 * sub[int(.9 * len(sub))], 100 * sum(e > .05 for e in sub) / len(sub),
        100 * statistics.median(r['bw'] for r in rows if r['tier'] == tier and r['bw'] < 1e9),
        100 * statistics.median(r['iqr'] for r in rows if r['tier'] == tier),
        100 * statistics.median(r['rng'] for r in rows if r['tier'] == tier)))
# calibration of the bootstrap band: share of next-day medians inside est*(1 +- bw)
inb = [r for r in rows if r['bw'] < 1e9]
print('\nbootstrap 90%% band calibration: next-day median inside est*(1+-halfwidth): %.1f%% of %d roll-origins (n48>=2)' % (
    100 * sum(r['err'] <= r['bw'] for r in inb) / len(inb), len(inb)))
for lo, hi in [(2, 4), (5, 9), (10, 29), (30, 10 ** 9)]:
    sub = [r for r in inb if lo <= r['n48'] <= hi]
    print('   n48 %2d-%-4s coverage %.1f%%  median halfwidth %.2f%%' % (lo, hi if hi < 10 ** 9 else 'inf',
          100 * sum(r['err'] <= r['bw'] for r in sub) / len(sub), 100 * statistics.median(r['bw'] for r in sub)))
