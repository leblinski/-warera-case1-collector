"""(b) cont.: does trade frequency carry draw information?  Sensitivity of the knife/gun/sniper
slot value and the case gross to a max-roll draw excess of the size the Epic counts show."""
import json
from load import load, TIERS
import ev_ref
p,now,rows=load()
m=ev_ref.Model(p,tax=1.0,bar_abs=0.10)
base=m.case(1)['gross']
def slot_with_maxweight(slot,t,wa,wc=1.0):
    v=m.slot_value(slot,t); dis=m.dismantle(t)
    (a0,a1),(c0,c1)=ev_ref.WEAPON_STATS[t-1]
    ws=vs=0
    for k,price,sale,sells in v['rows']:
        a,c=map(int,k.split('/'))
        w=(wa if a==a1 else 1)*(wc if c==c1 else 1)
        ws+=w;vs+=w*(sale if sells else dis)
    return vs/ws,v['net']
out={}
for code,t in [('knife',1),('gun',2),('rifle',3),('sniper',4),('tank',5)]:
    for wa,wc in [(1.16,1.08),(1.40,1.16),(2,2)]:
        nv,ev=slot_with_maxweight('weapon',t,wa,wc)
        dg=ev_ref.CASE_TIER_ODDS[t-1]*ev_ref.CRAFT_SLOT_WEIGHT['weapon']*(nv-ev)
        out['%s w%.2f/%.2f'%(code,wa,wc)]={'even':ev,'reweighted':nv,'case_gross_delta':dg,'case_pct_delta':dg/3.55*100}
        print('%-7s max-attack x%.2f max-crit x%.2f: net %.4f -> %.4f  case gross %+.4f (%+.3f%% of cost)'%(code,wa,wc,ev,nv,dg,dg/3.55*100))
# empirical-count weighting restricted to Epic+ (where every roll sells) : how far from even?
for code,slot,t in [('sniper','weapon',4),('boots4','boots',4),('helmet4','helmet',4),('tank','weapon',5)]:
    v=m.slot_value(slot,t)
    cat=p['categories'][code];cnt={}
    for k,row in cat['rolls'].items():
        cnt[ev_ref.roll_key(slot,row['exact_roll']['skills'])]=row['retained_window']['count']
    ws=vs=0;dis=m.dismantle(t)
    for k,price,sale,sells in v['rows']:
        w=cnt.get(k,0);ws+=w;vs+=w*(sale if sells else dis)
    print('%-8s even %.4f  retained-count-weighted %.4f  diff %+.4f (%+.2f%%)'%(code,v['net'],vs/ws,vs/ws-v['net'],(vs/ws/v['net']-1)*100))
    out[code+' retained-weighted']={'even':v['net'],'weighted':vs/ws}
json.dump(out,open('b2_informative.json','w'),indent=1)
