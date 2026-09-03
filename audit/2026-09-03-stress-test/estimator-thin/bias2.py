"""Cleaner signed bias: 48h median (and selected) vs the realised next-day MEDIAN per roll-origin
(mean and median of est/fut_med - 1), by tier; reconciles with the mean-of-(e-p)/p bias in b_oos."""
import sys, os, statistics, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
NOW = now_epoch(); rolls, meta = load()
first = min(v[0][0] for v in rolls.values())
origins = list(range(first + 48 * H, NOW - 24 * H + 1, 6 * H))
rows = []
for key, v in rolls.items():
    ts = [t for t, _, _ in v]
    for T in origins:
        i = bisect.bisect_right(ts, T); j = bisect.bisect_right(ts, T + 24 * H)
        fut = [p for _, p, _ in v[i:j]]; p48 = [p for t, p, _ in v[:i] if t > T - 48 * H]
        p24 = [p for t, p, _ in v[:i] if t > T - 24 * H]
        if not fut or not p48: continue
        m = median(p48); sel = median(p24) if len(p24) >= 3 else m; fm = median(fut)
        rows.append((meta[key[0]]['tier'], m / fm - 1, sel / fm - 1, statistics.mean((m - p) / p for p in fut), len(fut)))
print('%-10s %6s | med48 vs next-day median: mean%%  median%%  | selected: mean%%  median%% | mean (e-p)/p %%' % ('tier', 'N'))
for tier in ['ALL', 'basic', 'reinforced', 'advanced', 'elite', 'legendary', 'mythic']:
    sub = [r for r in rows if tier == 'ALL' or r[0] == tier]
    if not sub: continue
    print('%-10s %6d | %+6.2f %+6.2f | %+6.2f %+6.2f | %+6.2f' % (tier, len(sub),
          100 * statistics.mean(r[1] for r in sub), 100 * statistics.median(r[1] for r in sub),
          100 * statistics.mean(r[2] for r in sub), 100 * statistics.median(r[2] for r in sub),
          100 * statistics.mean(r[3] for r in sub)))
# weighting by future sales (sales-weighted) for ALL
w = sum(r[4] for r in rows)
print('ALL sales-weighted mean med48/fut_med-1: %+.2f%%' % (100 * sum(r[1] * r[4] for r in rows) / w))
