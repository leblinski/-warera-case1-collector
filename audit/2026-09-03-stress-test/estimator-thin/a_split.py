"""(a) Reproduce the brief's split test: sales priced at >= Q3 of their roll's 48h window vs
sales priced at the roll median: price uplift and median time-to-sell.
Sweeps the per-roll count threshold and prints several definitions of 'uplift' and 'at median'."""
import sys, os, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

NOW = now_epoch()
rolls, meta = load()
w48 = {k: [r for r in v if r[0] > NOW - 48 * H] for k, v in rolls.items()}
w48 = {k: v for k, v in w48.items() if v}
print('now', NOW, 'rolls with >=1 non-stale sale in 48h:', len(w48), 'sales:', sum(len(v) for v in w48.values()))

def split(threshold, window):
    sel = {k: v for k, v in window.items() if len(v) >= threshold}
    nroll = len(sel); nsales = sum(len(v) for v in sel.values())
    hi_p, hi_t, med_p, med_t, lo_t, le_t = [], [], [], [], [], []
    upl_roll, upl_w = [], []
    hi_rel = []
    for k, v in sel.items():
        ps = [p for _, p, _ in v]
        m = median(ps); q3 = quantile(ps, 0.75)
        upl_roll.append(q3 / m - 1); upl_w.append((q3 / m - 1, len(ps)))
        for t, p, tts in v:
            if p >= q3:
                hi_p.append(p); hi_rel.append(p / m - 1)
                if tts is not None: hi_t.append(tts)
            if p == m:
                med_p.append(p)
                if tts is not None: med_t.append(tts)
            if p <= m and tts is not None:
                le_t.append(tts)
            if p < q3 and tts is not None:
                lo_t.append(tts)
    mt = lambda x: statistics.median(x) / 60 if x else float('nan')
    return dict(threshold=threshold, rolls=nroll, sales=nsales,
                q3_over_med_mean_by_roll=100 * statistics.mean(upl_roll),
                q3_over_med_sales_weighted=100 * sum(u * n for u, n in upl_w) / sum(n for _, n in upl_w),
                q3_over_med_median_by_roll=100 * statistics.median(upl_roll),
                hi_sales=len(hi_p), hi_sale_rel_mean=100 * statistics.mean(hi_rel) if hi_rel else float('nan'),
                med_sales=len(med_p),
                tts_hi_min=mt(hi_t), tts_at_med_min=mt(med_t), tts_le_med_min=mt(le_t), tts_below_q3_min=mt(lo_t),
                rolls_q3_eq_med=sum(1 for u in upl_roll if u == 0))

print('\n== sweep threshold on 48h non-stale count ==')
print('thr rolls sales | Q3/med-1: byroll% sw% medroll% | hi_sales hi_rel% | tts(min): >=Q3  ==med  <=med  <Q3 | rolls Q3==med')
for thr in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 20, 25, 30]:
    r = split(thr, w48)
    print('%3d %4d %6d | %6.2f %6.2f %6.2f | %6d %6.2f | %6.1f %6.1f %6.1f %6.1f | %d' % (
        r['threshold'], r['rolls'], r['sales'], r['q3_over_med_mean_by_roll'], r['q3_over_med_sales_weighted'],
        r['q3_over_med_median_by_roll'], r['hi_sales'], r['hi_sale_rel_mean'], r['tts_hi_min'], r['tts_at_med_min'],
        r['tts_le_med_min'], r['tts_below_q3_min'], r['rolls_q3_eq_med']))

# Also: 7-day retained window (all sales), same sweep
w7 = {k: v for k, v in rolls.items() if v}
print('\n== same on 7-day retained window (all non-stale sales) ==')
for thr in [5, 10, 20, 30, 40, 50, 60, 80, 100]:
    r = split(thr, w7)
    print('%3d %4d %6d | %6.2f %6.2f %6.2f | %6d %6.2f | %6.1f %6.1f %6.1f %6.1f | %d' % (
        r['threshold'], r['rolls'], r['sales'], r['q3_over_med_mean_by_roll'], r['q3_over_med_sales_weighted'],
        r['q3_over_med_median_by_roll'], r['hi_sales'], r['hi_sale_rel_mean'], r['tts_hi_min'], r['tts_at_med_min'],
        r['tts_le_med_min'], r['tts_below_q3_min'], r['rolls_q3_eq_med']))

# Including stale sales (the raw shard), 48h window
rolls_all, _ = load(drop_stale=False)
w48s = {k: [r for r in v if r[0] > NOW - 48 * H] for k, v in rolls_all.items()}
w48s = {k: v for k, v in w48s.items() if v}
print('\n== 48h window INCLUDING stale listings ==')
for thr in [5, 8, 10, 12, 15]:
    r = split(thr, w48s)
    print('%3d %4d %6d | %6.2f %6.2f %6.2f | %6d %6.2f | %6.1f %6.1f %6.1f %6.1f | %d' % (
        r['threshold'], r['rolls'], r['sales'], r['q3_over_med_mean_by_roll'], r['q3_over_med_sales_weighted'],
        r['q3_over_med_median_by_roll'], r['hi_sales'], r['hi_sale_rel_mean'], r['tts_hi_min'], r['tts_at_med_min'],
        r['tts_le_med_min'], r['tts_below_q3_min'], r['rolls_q3_eq_med']))

# Per-tier breakdown at the chosen threshold (48h, non-stale)
print('\n== per tier at threshold 10 (48h non-stale) ==')
by_tier = {}
for k, v in w48.items():
    if len(v) < 10: continue
    by_tier.setdefault(meta[k[0]]['tier'], {})[k] = v
for tier in ['basic', 'reinforced', 'advanced', 'elite', 'legendary', 'mythic']:
    if tier not in by_tier: continue
    r = split(10, by_tier[tier])
    print('%-10s rolls %4d sales %6d Q3/med byroll %5.2f%% sw %5.2f%% | tts >=Q3 %6.1f  ==med %6.1f  <=med %6.1f' % (
        tier, r['rolls'], r['sales'], r['q3_over_med_mean_by_roll'], r['q3_over_med_sales_weighted'],
        r['tts_hi_min'], r['tts_at_med_min'], r['tts_le_med_min']))
