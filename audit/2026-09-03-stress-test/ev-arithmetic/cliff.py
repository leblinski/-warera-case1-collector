"""Why the case gross drops 3.6411->3.6137 when the scrap bid rises 0.214->0.215 (bar 0.10 threshold artefact)."""
from common import *
snap=load()
for b in (0.214,0.215,0.22,0.225):
    m=E.Model(snap,tax=1,bar_abs=0.10,scrap_bid=b); c=m.case(1)
    print('bid %.3f gross %.4f | per-tier net: %s | broken: %s'%(b,c['gross'],' '.join('%.4f'%p['net'] for p in c['parts']),' '.join('%.0f%%'%(p['broken']*100) for p in c['parts'])))
# tier 1 slot detail at 0.214 vs 0.215
for b in (0.214,0.215):
    m=E.Model(snap,tax=1,bar_abs=0.10,scrap_bid=b)
    print(' bid %.3f tier1 need %.4f dis %.4f: '%(b,m.need(1),m.dismantle(1))+' '.join('%s=%.4f(brk %d/%d)'%(s,v['net'],v['broken'],v['weight']) for s in E.SLOTS for v in [m.slot_value(s,1)]))
m=E.Model(snap,tax=1,bar_abs=0.10,scrap_bid=0.214)
rows=[(s,k,p) for s in E.SLOTS for v in [m.slot_value(s,1)] for k,p,sale,sells in v['rows'] if 1.384<sale<=1.394]
print(' tier-1 rolls with net sale in (1.384,1.394]: %d ->'%len(rows),rows[:12])
# the same cliff in per-listing-cost terms: value = max(sale-0.10, dis) is continuous in dis
def cost_gross(bid,fee=0.10):
    m=E.Model(snap,tax=1,bar_abs=fee,scrap_bid=bid); g=0
    for t in range(1,7):
        ws=n=0
        for s in E.SLOTS:
            v=m.slot_value(s,t); w=E.CRAFT_SLOT_WEIGHT[s]
            if not v: continue
            ws+=w; n+=w*sum((sale-fee if sells else m.dismantle(t)) for k,p,sale,sells in v['rows'])/len(v['rows'])
        g+=E.CASE_TIER_ODDS[t-1]*n/ws
    return g
print(' per-listing-cost model (fee 0.10) gross: '+' '.join('%.3f->%.4f'%(b,cost_gross(b)) for b in (0.213,0.214,0.215,0.216,0.22,0.225)))
