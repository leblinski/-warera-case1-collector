"""(c) robustFilter: sales dropped per roll, which side, and whether it drops the newest sales
(a bracket move). Run: python3 c_robust.py"""
import json, math, glob, os, statistics
from model import load_shard, State, Model, robustFilter, median, PUBLIC

codes = sorted(os.path.basename(p)[:-5] for p in glob.glob(f'{PUBLIC}/prices/*.json'))


def pct(a, q):
    a = sorted(a); pos = (len(a) - 1) * q; lo = math.floor(pos); hi = math.ceil(pos)
    return a[lo] if lo == hi else a[lo] + (a[hi] - a[lo]) * (pos - lo)


def analyse(deep):
    stats = {'rolls': 0, 'rolls_with_drop': 0, 'sales': 0, 'dropped': 0, 'dropped_low': 0, 'dropped_high': 0,
             'floor_binding': 0, 'newest_dropped': 0, 'newest3_all_dropped': 0, 'moves': []}
    per_tier = {t: [0, 0] for t in range(1, 7)}
    examples = []
    for code in codes:
        shard = load_shard(code)
        for roll in shard['rolls']:
            st = State(shard, roll['skills'], 1.0); M = Model(st)
            sales, meta = M.analyse_sales(shard, deep)
            raw = [it for it in sales if M.exactMatch(it)]
            if len(raw) < 5: continue
            kept = robustFilter(raw)
            prices = [it['money'] for it in raw]; med = median(prices)
            dev = [abs(math.log(p / med)) for p in prices]; mad = median(dev) or 0
            thr = max(.12, mad * 3.5)
            stats['rolls'] += 1; stats['sales'] += len(raw); per_tier[st.tier][1] += len(raw)
            if thr == .12: stats['floor_binding'] += 1
            keptset = set(id(it) for it in kept)
            dropped = [it for it in raw if id(it) not in keptset]
            stats['dropped'] += len(dropped); per_tier[st.tier][0] += len(dropped)
            if dropped: stats['rolls_with_drop'] += 1
            stats['dropped_low'] += sum(1 for it in dropped if it['money'] < med)
            stats['dropped_high'] += sum(1 for it in dropped if it['money'] > med)
            newest = sorted(raw, key=lambda it: -it['createdAt'])
            if id(newest[0]) not in keptset: stats['newest_dropped'] += 1
            if len(newest) >= 3 and all(id(it) not in keptset for it in newest[:3]):
                stats['newest3_all_dropped'] += 1
                examples.append((code, roll['skills'], len(raw), len(kept), med, [it['money'] for it in newest[:5]], round(thr, 3)))
            # bracket move: newest 3 sales' median differs from the roll median by more than the threshold
            m3 = median([it['money'] for it in newest[:3]])
            if abs(math.log(m3 / med)) > thr:
                stats['moves'].append((code, roll['skills'], med, m3, len(raw), sum(1 for it in newest[:3] if id(it) in keptset)))
    print(f'\n=== {"full 168h" if deep else "fast window"}: rolls(n>=5 exact)={stats["rolls"]} sales={stats["sales"]} dropped={stats["dropped"]} '
          f'({stats["dropped"]/max(1,stats["sales"])*100:.2f}%) rolls_with_drop={stats["rolls_with_drop"]} '
          f'({stats["rolls_with_drop"]/max(1,stats["rolls"])*100:.1f}%) floor_0.12_binding={stats["floor_binding"]} '
          f'({stats["floor_binding"]/max(1,stats["rolls"])*100:.1f}%)')
    print(f' dropped below median: {stats["dropped_low"]}  above median: {stats["dropped_high"]}')
    print(f' rolls where the newest sale is dropped: {stats["newest_dropped"]}; where the newest 3 are ALL dropped: {stats["newest3_all_dropped"]}')
    print(' per tier dropped/sales:', {t: f'{v[0]}/{v[1]} ({v[0]/max(1,v[1])*100:.2f}%)' for t, v in per_tier.items()})
    print(f' bracket moves (median of newest 3 beyond threshold from roll median): {len(stats["moves"])}')
    for mv in stats['moves'][:12]: print('   ', mv)
    for ex in examples[:8]: print('  newest3-dropped example:', ex)


analyse(False)
analyse(True)

# Synthetic: how big a move survives? Given n sales at the old level and k at the new level, the filter
# keeps the new level iff |log(new/median)| <= max(.12, 3.5*MAD). With k < n/2 the median stays at the old
# level and MAD ~ 0 (tight market), so the new level is dropped whenever the move exceeds 12.75%.
print('\n=== filter floor: exp(0.12)-1 = %.2f%% ; exp(-0.12)-1 = %.2f%%' % ((math.exp(.12) - 1) * 100, (math.exp(-.12) - 1) * 100))
