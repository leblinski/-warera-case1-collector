"""(f) Effect of the saleKey ms-rounding seam on the model: emulate a Gateway page (newest 100
sales of the item, ms timestamps) merged into the shard via the page's mergeSales/saleKey, then
re-run the Trends model. Run: python3 i_seam_effect.py"""
import json, math, datetime
from model import load_shard, State, Model, parse_iso

SNAP = '/home/user/-warera-case1-collector/data/warera_case1_market.json'
snap = json.load(open(SNAP))


def js_round(x): return math.floor(x + 0.5)


def key_of(money, ms, skills):
    return f'{float(money)}|{js_round(ms / 1000)}|' + ','.join(f'{k}:{skills[k]}' for k in sorted(skills))


def live_rows(code):
    rows = sorted(snap['categories'][code]['transactions'], key=lambda t: t['sold_at'], reverse=True)[:100]
    out = []
    for tx in rows:
        if tx.get('quantity') != 1 or not tx.get('skills'): continue
        ms = parse_iso(tx['sold_at'])
        oc = tx.get('offer_created_at')
        out.append({'_id': 'live:' + tx['id'], 'money': tx['money'], 'createdAt': ms,
                    'offerCreatedAt': parse_iso(oc) if oc else None, 'skills': tx['skills']})
    return out


def merge(base, extra):
    seen = {}; out = []
    for it in base: seen[key_of(it['money'], it['createdAt'], it['skills'])] = 1; out.append(it)
    added = 0
    for it in extra:
        k = key_of(it['money'], it['createdAt'], it['skills'])
        if k in seen: continue
        seen[k] = 1; out.append(it); added += 1
    out.sort(key=lambda it: -it['createdAt'])
    return out, added


for code, roll, floor in [('knife', {'attack': 40, 'criticalChance': 5}, 4.2), ('boots4', {'dodge': 25}, 60.0),
                          ('tank', {'attack': 141, 'criticalChance': 34}, 150.0), ('sniper', {'attack': 130, 'criticalChance': 20}, 60.0),
                          ('gloves4', {'precision': 25}, 50.0)]:
    shard = load_shard(code)
    st = State(shard, roll, floor, age=48 if code == 'tank' else None); M = Model(st)
    sales0, meta0 = M.analyse_sales(shard); m0 = M.build(sales0, meta0)
    lv = live_rows(code)
    merged, added = merge(shard['_sales'], lv)
    shard2 = dict(shard); shard2['_sales'] = merged
    sales1, meta1 = M.analyse_sales(shard2); m1 = M.build(sales1, meta1)
    ex0 = sum(1 for it in sales0 if M.exactMatch(it)); ex1 = sum(1 for it in sales1 if M.exactMatch(it))
    print(f'{code} {roll} floor {floor}: live rows {len(lv)}, "+{added} live" shown (all duplicates; the snapshot has no sale newer than the shard)')
    print(f'   without live: rows {len(sales0)} exact {ex0} hist {m0["histTarget"]} direct {m0["directPrice"]} score {m0["confidenceScore"]} velocity {m0["velocity"]:.2f} higher {m0["higher"]} strategy {m0["strategy"]}')
    print(f'   with live:    rows {len(sales1)} exact {ex1} hist {m1["histTarget"]} direct {m1["directPrice"]} score {m1["confidenceScore"]} velocity {m1["velocity"]:.2f} higher {m1["higher"]} strategy {m1["strategy"]}')
