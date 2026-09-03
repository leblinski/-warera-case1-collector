"""(f) Live/shard dedupe seam: saleKey rounds ms to the nearest second, the shard floors.
Measures the sub-second distribution of sold_at in the committed snapshot and simulates the merge
with the page's own key logic. Run: python3 f_seam.py"""
import json, math, datetime
SNAP = '/home/user/-warera-case1-collector/data/warera_case1_market.json'
p = json.load(open(SNAP))
total = ge500 = 0
per_item = {}
ms_hist = [0] * 10
for code, cat in p['categories'].items():
    n = k = 0
    for tx in cat['transactions']:
        s = tx['sold_at']
        ms = int(s[20:23]) if len(s) >= 23 and s[19] == '.' else 0
        ms_hist[ms // 100] += 1
        n += 1
        if ms >= 500: k += 1
    per_item[code] = (k, n)
    total += n; ge500 += k
print(f'retained sales {total}; sold_at with ms >= 500: {ge500} = {ge500/total*100:.2f}% (these live rows fail saleKey dedupe against their shard copy)')
print('ms decile histogram (0-99,100-199,...):', ms_hist)
worst = sorted(per_item.items(), key=lambda kv: -kv[1][0] / max(1, kv[1][1]))[:3]
print('per-item share range:', min(v[0] / max(1, v[1]) for v in per_item.values()), '-', max(v[0] / max(1, v[1]) for v in per_item.values()))


def js_round(x):  # Math.round: half toward +inf
    return math.floor(x + 0.5)


def sale_key_shard(money, sold_epoch_s, skills):
    return f'{money}|{js_round(sold_epoch_s * 1000 / 1000)}|' + ','.join(f'{k}:{skills[k]}' for k in sorted(skills))


def sale_key_live(money, iso, skills):
    ms = datetime.datetime.fromisoformat(iso.replace('Z', '+00:00')).timestamp() * 1000
    return f'{money}|{js_round(ms / 1000)}|' + ','.join(f'{k}:{skills[k]}' for k in sorted(skills))


# Simulate: the live Gateway returns the newest 100 sales of an item (with ms); the shard has floor-second copies.
for code in ('knife', 'boots4', 'tank'):
    cat = p['categories'][code]
    rows = sorted(cat['transactions'], key=lambda t: t['sold_at'], reverse=True)[:100]
    dup = 0
    for tx in rows:
        sk = tx['skills'] or {}
        money = tx['money'] / max(1, tx.get('quantity') or 1)
        epoch = int(datetime.datetime.fromisoformat(tx['sold_at'].replace('Z', '+00:00')).timestamp())
        if sale_key_shard(money, epoch, sk) != sale_key_live(money, tx['sold_at'], sk): dup += 1
    print(f'{code}: of the newest 100 snapshot sales, {dup} would be re-added as "live" duplicates by mergeSales (double-counted in the model)')
print('\nNote: unit_price in the shard is money/quantity; every retained sale has quantity 1 (README), so the money component of the key matches.')
