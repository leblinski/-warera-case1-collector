"""(d) Claim 6: THIN_SALES=5 marker.
1. Subsample test: rolls with >= 30 non-stale sales in the final 48h window; for n=1..10 draw
   subsample medians and measure relative error vs the full 48h median.
2. Published-summary counts: rolls marked thin (selected.count < 5) that have >= 5 in 48h;
   unmarked rolls whose 48h min-max range exceeds 10% of the median; IQR variants."""
import sys, os, statistics, random, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

random.seed(20260903)
NOW = now_epoch()
rolls, meta = load()
w48 = {k: [p for t, p, _ in v if t > NOW - 48 * H] for k, v in rolls.items()}
big = {k: v for k, v in w48.items() if len(v) >= 30}
print('rolls with >=30 non-stale sales in 48h:', len(big), 'sales', sum(len(v) for v in big.values()))

DRAWS = 300
print('\n== subsample median relative error vs full 48h median (pooled over rolls x draws) ==')
print(' n | med|err|%  p75%  p90%  p95% | share|err|>5%  >10% | per-roll median of med|err| (median across rolls) | IQR/med of the rolls (median) %')
iqr_rel = statistics.median([(quantile(v, .75) - quantile(v, .25)) / median(v) * 100 for v in big.values()])
curve = {}
for n in range(1, 13):
    errs, per_roll = [], []
    for k, v in big.items():
        m = median(v); e = []
        for _ in range(DRAWS):
            s = random.sample(v, n)
            e.append(abs(median(s) - m) / m * 100)
        errs.extend(e); per_roll.append(statistics.median(e))
    errs.sort()
    q = lambda p: errs[min(len(errs) - 1, int(p * len(errs)))]
    curve[n] = (statistics.median(errs), q(.9))
    print('%2d | %6.2f %6.2f %6.2f %6.2f | %5.1f%% %5.1f%% | %6.2f | %5.1f' % (
        n, statistics.median(errs), q(.75), q(.9), q(.95),
        100 * sum(1 for x in errs if x > 5) / len(errs), 100 * sum(1 for x in errs if x > 10) / len(errs),
        statistics.median(per_roll), iqr_rel))
print('\nmarginal improvement in p90 error going n -> n+1:')
for n in range(1, 12):
    print('  %2d->%2d  p90 %.2f -> %.2f  (drop %.2f pts, %.0f%%)   median %.2f -> %.2f' % (
        n, n + 1, curve[n][1], curve[n + 1][1], curve[n][1] - curve[n + 1][1],
        100 * (curve[n][1] - curve[n + 1][1]) / curve[n][1], curve[n][0], curve[n + 1][0]))

# by tier at n=3,5,8
print('\n== p90 rel error by tier (n=2,3,5,8) ==')
tiers = {}
for k, v in big.items():
    tiers.setdefault(meta[k[0]]['tier'], []).append(v)
for tier, vs in tiers.items():
    row = []
    for n in (2, 3, 5, 8):
        errs = []
        for v in vs:
            m = median(v)
            for _ in range(DRAWS):
                errs.append(abs(median(random.sample(v, n)) - m) / m * 100)
        errs.sort(); row.append(errs[int(.9 * len(errs))])
    print('  %-10s rolls %3d  p90: n2 %5.2f  n3 %5.2f  n5 %5.2f  n8 %5.2f' % (tier, len(vs), *row))

# ---- published summary counts (what the page actually reads) ----
print('\n== published summary: thin marker vs windows ==')
T = 5
priced = marked = marked_but_48_ge5 = marked_24_selected = unmarked = un_wide = un_wide_iqr = 0
marked_examples = []
un_range = []
quiet = 0
for code, m in meta.items():
    for key, row in m['summary'].items():
        st = row['selected'] or row['fallback_48h']
        if st is None or st.get('median') is None:
            quiet += 1; continue
        priced += 1
        n = st['count'] or 0
        fb = row['fallback_48h']
        if n < T:
            marked += 1
            if (fb['count'] or 0) >= T:
                marked_but_48_ge5 += 1
                marked_examples.append((code, key, row['selected_window_hours'], n, fb['count']))
            if row['selected_window_hours'] == 24: marked_24_selected += 1
        else:
            unmarked += 1
            rng = (fb['max'] - fb['min']) / fb['median'] if fb['median'] else 0
            un_range.append(rng)
            if rng > 0.10: un_wide += 1
print('rolls with a selected.median:', priced, ' quiet (retained only):', quiet)
print('marked thin (selected.count<5):', marked, ' of which selected window is 24h:', marked_24_selected)
print('marked thin but fallback_48h.count >= 5:', marked_but_48_ge5)
for ex in marked_examples: print('   ', ex)
print('unmarked (count>=5):', unmarked, ' with 48h (max-min)/median > 10%:', un_wide,
      ' (%.0f%%)' % (100 * un_wide / unmarked))
un_range.sort()
print('unmarked 48h range/median: median %.1f%%  p25 %.1f%%  p75 %.1f%%  >20%%: %d  >30%%: %d' % (
    100 * un_range[len(un_range) // 2], 100 * un_range[len(un_range) // 4], 100 * un_range[3 * len(un_range) // 4],
    sum(1 for r in un_range if r > .2), sum(1 for r in un_range if r > .3)))

# IQR/median of the actual 48h sales for unmarked rolls (the range is dominated by outliers)
un_iqr = []
for code, m in meta.items():
    for i, rk in enumerate(m['rolls']):
        v = w48.get((code, i), [])
        if len(v) >= T:
            un_iqr.append((quantile(v, .75) - quantile(v, .25)) / median(v))
un_iqr.sort()
print('rolls with >=5 non-stale 48h sales (recomputed): %d ; IQR/median > 10%%: %d (%.0f%%), median IQR/med %.1f%%' % (
    len(un_iqr), sum(1 for r in un_iqr if r > .1), 100 * sum(1 for r in un_iqr if r > .1) / len(un_iqr), 100 * un_iqr[len(un_iqr) // 2]))

# distribution of selected.count among priced rolls
cnt = {}
for code, m in meta.items():
    for key, row in m['summary'].items():
        st = row['selected'] or row['fallback_48h']
        if st is None or st.get('median') is None: continue
        c = st['count']
        b = '1' if c == 1 else '2' if c == 2 else '3-4' if c < 5 else '5-9' if c < 10 else '10-29' if c < 30 else '30+'
        cnt[b] = cnt.get(b, 0) + 1
print('selected.count distribution among priced rolls:', cnt)
