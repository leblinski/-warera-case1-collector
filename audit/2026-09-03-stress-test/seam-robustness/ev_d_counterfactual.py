# (d)/(p) counterfactual: page's craftDismantle returns 0 when scraps best_bid is null/no book.
import sys,json; sys.path.insert(0,'..'); import ev_ref
snap=json.load(open(ev_ref.SNAP if hasattr(ev_ref,'SNAP') else '/home/user/-warera-case1-collector/data/warera_case1_market.json'))
for bid in (0.225, 0.0):
    m=ev_ref.Model(snap,tax=1.0,bar_abs=0.10,scrap_bid=bid); c=m.case(1)
    print('scrap_bid',bid,'case gross',round(c['gross'],4) if isinstance(c,dict) else c)
