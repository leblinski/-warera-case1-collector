"""Independent EV-2 check (no ev_ref.Model): case EV under 4 tax models, floors, between-floor
counts under two conventions, and decomposition tax-gap vs bar-gap."""
import json,sys,os
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ev_ref import roll_space,roll_key,item_code,SLOTS   # README-established roll space/key only
snap=json.load(open('/home/user/-warera-case1-collector/data/warera_case1_market.json'))
Y=[6,18,54,162,486,1458];O=[0.62,0.30,0.071,0.0085,0.0004,0.0001]
W={'weapon':0.30,'helmet':0.14,'chest':0.14,'boots':0.14,'gloves':0.14,'pants':0.14}
bid=snap['commodities']['scraps']['order_book']['best_bid']
ask=min(o['price'] for o in snap['commodities']['case1']['order_book']['sell_orders'])
def meds(s,t):
    cat=snap['categories'].get(item_code(s,t));out={}
    if not cat:return out
    for row in cat['rolls'].values():
        k=roll_key(s,(row.get('exact_roll') or {}).get('skills'))
        st=row.get('selected') or row.get('fallback_48h')
        if k is not None and st and st.get('median') is not None:out[k]=st['median']
    return {k:out[k] for k in roll_space(s,t) if k in out}
M={(s,t):meds(s,t) for s in SLOTS for t in range(1,7)}
def case(nm,sb,bar):
    g=0
    for t in range(1,7):
        dis=Y[t-1]*sb;need=dis+bar;ws=vs=0
        for s in SLOTS:
            m=M[(s,t)]
            if not m:continue
            ws+=W[s];vs+=W[s]*sum((p*nm if p*nm>need else dis) for p in m.values())/len(m)
        g+=O[t-1]*vs/ws
    return g
print('bid',bid,'ask',ask)
for lab,nm,sb in [('A page',0.99,bid),('B typed',1.0,bid),('C both',0.99,bid*0.99),('D paintScrap',1.0,bid/1.01)]:
    for bar in (0.10,0.0):
        g=case(nm,sb,bar);print('%-12s bar %.2f gross %.4f pct %+.2f%%'%(lab,bar,g,(g-ask)/ask*100))
print('\nfloors t: S/1.01 | S/1.01^2 | S/0.99 | (S+0.1)/0.99')
for t in range(1,7):
    S=Y[t-1]*bid;print(' %d %.4f %.4f %.4f %.4f'%(t,S/1.01,S/1.01**2,S/0.99,(S+0.1)/0.99))
# between-floor: (i) typed median compared to Price floor directly; (ii) user types displayed=round3(median*1.01)
r3=lambda x:round(x*1000)/1000
for bar in (0.0,0.10):
    for crit in ('i','ii'):
        tot=0;pieces=0;per=[]
        for t in range(1,7):
            S=Y[t-1]*bid;hi=(S+bar)/0.99;n=0;npr=0
            for s in SLOTS:
                m=M[(s,t)];each=O[t-1]*W[s]/len(roll_space(s,t))
                for p in m.values():
                    npr+=1
                    target=p if crit=='i' else r3(p*1.01)
                    price_says_list=target>S/1.01+0.0005   # paintScrap: wins(dismantle) iff target<=mine+.0005
                    sort_says_break=not(p*0.99>hi*0.99)     # sortRolls: net>need
                    if price_says_list and sort_says_break:n+=1;pieces+=each
            per.append('t%d %d/%d'%(t,n,npr));tot+=n
        print('bar %.2f crit %-2s %s total %d  pieces/100 cases %.2f'%(bar,crit,' '.join(per),tot,pieces*100))
# decomposition at bar 0.10 crit i: tax-gap (S/1.01,S/0.99] vs bar-gap (S/0.99,(S+0.1)/0.99]
tg=bg=0
for t in range(1,7):
    S=Y[t-1]*bid
    for s in SLOTS:
        for p in M[(s,t)].values():
            if S/1.01<p<=S/0.99:tg+=1
            elif S/0.99<p<=(S+0.1)/0.99:bg+=1
print('bar0.10 crit i split: tax-gap rolls',tg,'bar-gap rolls',bg)
