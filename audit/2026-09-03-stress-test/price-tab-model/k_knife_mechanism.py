"""Why a Common knife 40/5 gets a 1.859 target: the 12 weapon comparables before robustFilter."""
import math
from model import load_shard, State, Model, median
shard = load_shard('knife'); st = State(shard, {'attack': 40, 'criticalChance': 5}, 4.2); M = Model(st)
sales, meta = M.analyse_sales(shard)
target = M.weaponScore(st.rolls)
rows = []
for it in sales:
    s = M.weaponScore(it['skills']); rel = M.weaponRelation(it)
    rows.append((0 if rel == 'same' else (1 if rel == 'higher' else 2), abs(s - target), M.saleAge(it), it))
rows.sort(key=lambda r: (r[0], r[1], r[2]))
top = [r[3] for r in rows[:12]]
prices = [it['money'] for it in top]; med = median(prices)
dev = [abs(math.log(p / med)) for p in prices]; mad = median(dev); thr = max(.12, mad * 3.5)
print('target score', target)
for r in rows[:12]: print(f'  rank {r[0]} d={r[1]:.2f} age={r[2]:.2f}h price={r[3]["money"]} roll={r[3]["skills"]} kept={abs(math.log(r[3]["money"]/med))<=thr}')
print(f'median of 12 = {med:.4f}, MAD(log)={mad:.4f}, threshold={thr:.4f} -> keeps only |log(p/med)|<={thr:.3f}: prices within {med*math.exp(-thr):.3f}..{med*math.exp(thr):.3f}')
print('exact 40/5 sales in window:', [(round(M.saleAge(it),2), it['money']) for it in sales if M.exactMatch(it)])
print('selected.median (24h) for 40/5 =', shard['summary']['{"skills":{"attack":40,"criticalChance":5}}']['selected']['median'])
