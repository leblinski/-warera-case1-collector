"""Is the +bias of the median vs next-day sales a market drift?  Per-day median of (price / roll's
7-day median), by tier, over the retained window; and the pooled day-over-day change."""
import sys, os, statistics, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
rolls, meta = load()
by = {}
for (code, ri), v in rolls.items():
    if len(v) < 10: continue
    m = median([p for _, p, _ in v]); tier = meta[code]['tier']
    for t, p, _ in v:
        day = datetime.datetime.utcfromtimestamp(t).strftime('%m-%d')
        by.setdefault(tier, {}).setdefault(day, []).append(p / m - 1)
days = sorted({d for t in by.values() for d in t})
print('median of price/roll_median-1 (%) by UTC day, rolls with >=10 sales:')
print('%-10s ' % 'tier' + ' '.join('%7s' % d for d in days))
for tier in ['basic', 'reinforced', 'advanced', 'elite', 'legendary', 'mythic']:
    if tier not in by: continue
    print('%-10s ' % tier + ' '.join('%+6.2f%%' % (100 * statistics.median(by[tier][d])) if d in by[tier] else '      -' for d in days))
allb = {}
for t in by.values():
    for d, xs in t.items(): allb.setdefault(d, []).extend(xs)
print('%-10s ' % 'ALL' + ' '.join('%+6.2f%%' % (100 * statistics.median(allb[d])) for d in days))
print('%-10s ' % 'n' + ' '.join('%7d' % len(allb[d]) for d in days))
