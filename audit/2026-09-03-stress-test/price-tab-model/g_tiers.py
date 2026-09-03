"""(g) Tier inference from a typed price: rarityRanges/tiersForPrice (test60.html 3945-3997) vs the
RARITY_BANDS fallback and vs the volume of sales at that price. Run: python3 g_tiers.py"""
import json, glob, os, math
from model import load_shard, PUBLIC, TIER_OF_RARITY

summary = json.load(open(f'{PUBLIC}/summary.json'))
RARITY_BANDS = [2.485, 8.069, 27.346, 92.080, 268.430, float('inf')]
NAMES = ['Common', 'Uncommon', 'Rare', 'Epic', 'Legendary', 'Mythic']

# rarityRanges: per tier min/max of fallback_48h (or selected) across every roll of every item of the tier
by = {}
by_item = {}
for code, cat in summary['categories'].items():
    t = TIER_OF_RARITY[cat['rarity']]
    for key, r in cat['rolls'].items():
        st = r.get('fallback_48h') or r.get('selected')
        if not st or st.get('min') is None or st.get('max') is None: continue
        cur = by.setdefault(t, [math.inf, 0, None, None]); ci = by_item.setdefault(code, [math.inf, 0])
        if st['min'] < cur[0]: cur[0] = st['min']; cur[2] = (code, key)
        if st['max'] > cur[1]: cur[1] = st['max']; cur[3] = (code, key)
        ci[0] = min(ci[0], st['min']); ci[1] = max(ci[1], st['max'])
ranges = [by.get(t) for t in range(1, 7)]
print('observed ranges (48h fallback min/max across all rolls of the tier):')
for t in range(1, 7):
    r = ranges[t - 1]
    print(f'  {t} {NAMES[t-1]:10} {r[0]:9.3f} - {r[1]:9.3f}   min from {r[2]}  max from {r[3]}   | RARITY_BANDS upper edge {RARITY_BANDS[t-1]}')
print('overlaps between consecutive tiers:')
for t in range(1, 6):
    a, b = ranges[t - 1], ranges[t]
    if b[0] <= a[1]: print(f'  {NAMES[t-1]}/{NAMES[t]}: overlap {b[0]:.3f} - {a[1]:.3f}')
    else: print(f'  {NAMES[t-1]}/{NAMES[t]}: gap {a[1]:.3f} - {b[0]:.3f}')
print('non-adjacent overlaps:')
for i in range(6):
    for j in range(i + 2, 6):
        a, b = ranges[i], ranges[j]
        if b[0] <= a[1]: print(f'  {NAMES[i]}/{NAMES[j]}: overlap {b[0]:.3f} - {a[1]:.3f}')


def tiersForPrice(v):
    hits = [t for t in range(1, 7) if ranges[t - 1] and ranges[t - 1][0] <= v <= ranges[t - 1][1]]
    if hits: return hits
    best, gap = None, math.inf
    for t in range(1, 7):
        q = ranges[t - 1]; g = q[0] - v if v < q[0] else v - q[1]
        if g < gap: gap, best = g, t
    return [best]


def fallback(v):
    for i, b in enumerate(RARITY_BANDS):
        if v < b: return i + 1
    return 6


# Volume view: every sale in the 7-day shards, which tier the page would infer from its own price
codes = sorted(os.path.basename(p)[:-5] for p in glob.glob(f'{PUBLIC}/prices/*.json'))
mis = {t: [0, 0, 0] for t in range(1, 7)}  # [wrong tier chosen, ambiguous (more than one hit), total]
mis_fb = {t: [0, 0] for t in range(1, 7)}
price_hist = {}
for code in codes:
    shard = load_shard(code); t = TIER_OF_RARITY[shard['rarity']]
    for it in shard['_sales']:
        hits = tiersForPrice(it['money']); chosen = hits[-1]
        mis[t][2] += 1
        if chosen != t: mis[t][0] += 1
        if len(hits) > 1: mis[t][1] += 1
        if fallback(it['money']) != t: mis_fb[t][0] += 1
        mis_fb[t][1] += 1
print('\nsales of tier t whose own price the page assigns to another tier ("higher tier wins"):')
for t in range(1, 7):
    w, amb, n = mis[t]
    print(f'  {NAMES[t-1]:10}: wrong {w}/{n} = {w/n*100:.1f}%   ambiguous(>1 hit) {amb}/{n} = {amb/n*100:.1f}%   | RARITY_BANDS fallback wrong {mis_fb[t][0]}/{mis_fb[t][1]} = {mis_fb[t][0]/mis_fb[t][1]*100:.1f}%')

# Specific prices
print('\ntyped price -> hits (page picks the last = highest):')
for v in (1.86, 4.05, 4.2, 4.329, 4.385, 8.0, 13.0, 27.0, 40.0, 66.599, 92.0, 145.0, 268.0, 400.0):
    hits = tiersForPrice(v)
    print(f'  {v:8.3f}: hits {[NAMES[h-1] for h in hits]} -> page uses {NAMES[hits[-1]-1]}; RARITY_BANDS fallback -> {NAMES[fallback(v)-1]}')

# Volume at a price: how many 7-day sales within +-1% of 4.329 per tier
print('\nsales within +-1% of 4.329 in the 7-day shards, per tier / item:')
for code in codes:
    shard = load_shard(code)
    n = sum(1 for it in shard['_sales'] if abs(it['money'] - 4.329) <= 0.04329)
    if n: print(f'  {code:8} ({shard["rarity"]}): {n}')
# Common knife 40/5 sales: how many fall inside the Uncommon range
shard = load_shard('knife')
k405 = [it['money'] for it in shard['_sales'] if it['skills'] == {'attack': 40, 'criticalChance': 5}]
inside = sum(1 for p in k405 if ranges[1][0] <= p <= ranges[1][1])
print(f'\nCommon knife 40/5: {len(k405)} sales in 7d; {inside} ({inside/len(k405)*100:.1f}%) priced inside the Uncommon range -> page infers Uncommon (Gun) unless the user pins Common')
print('per-item observed ranges (48h):')
for code in codes:
    print(f'  {code:8} {by_item[code][0]:9.3f} - {by_item[code][1]:9.3f}')
