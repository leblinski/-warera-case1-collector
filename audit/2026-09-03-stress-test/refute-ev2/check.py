"""Independent re-derivation of EV-2: case EV under tax models, dismantle floors on the
Price tab (paintScrap) vs Sort tab (sortNeed/taxMul), and between-floor counts.
Uses only the roll space / roll key definitions (README-established) from ev_ref."""
import json,sys,os
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ev_ref import roll_space,roll_key,item_code,SLOTS,craft_walk
SNAP='/home/user/-warera-case1-collector/data/warera_case1_market.json'
snap=json.load(open(SNAP))
YIELDS=[6,18,54,162,486,1458];ODDS=[0.62,0.30,0.071,0.0085,0.0004,0.0001];STEEL=[1,2,4,8,16,32]
W={'weapon':0.30,'helmet':0.14,'chest':0.14,'boots':0.14,'gloves':0.14,'pants':0.14}
bid=snap['commodities']['scraps']['order_book']['best_bid']
case_ask=min(o['price'] for o in snap['commodities']['case1']['order_book']['sell_orders'])
print('bid',bid,'case ask',case_ask)
def medians(slot,t):
    cat=snap['categories'].get(item_code(slot,t))
    if not cat:return {}
    seen={}
    for row in cat['rolls'].values():
        k=roll_key(slot,(row.get('exact_roll') or {}).get('skills'))
        if k is None:continue
        st=row.get('selected') or row.get('fallback_48h')
        if st and st.get('median') is not None:seen[k]=st['median']
    return {k:seen[k] for k in roll_space(slot,t) if k in seen}
def case(netmul,scrapnet,bar=0.10):
    gross=0;per=[];rows_all={}
    for t in range(1,7):
        dis=YIELDS[t-1]*scrapnet;need=dis+bar if bar>0 else dis
        wsum=vsum=0;bro=rw=0
        for s in SLOTS:
            m=medians(s,t)
            if not m:continue
            vals=[(p*netmul if p*netmul>need else dis) for p in m.values()]
            b=sum(1 for p in m.values() if not p*netmul>need)
            wsum+=W[s];vsum+=W[s]*sum(vals)/len(vals);bro+=W[s]*b;rw+=W[s]*len(vals)
        net=vsum/wsum;gross+=ODDS[t-1]*net;per.append((net,bro/rw))
    return gross,per
for label,nm,sn in [('A page: net=med*0.99, scrap=bid',0.99,bid),('B typed: net=med, scrap=bid',1.0,bid),
                    ('C both: net=med*0.99, scrap=bid*0.99',0.99,bid*0.99),('D paintScrap: net=med, scrap=bid/1.01',1.0,bid/1.01)]:
    for bar in (0.10,0.0):
        g,per=case(nm,sn,bar)
        print('%-42s bar %.2f gross %.4f edge %+.4f pct %+.2f%% broken %s'%(label,bar,g,g-case_ask,(g-case_ask)/case_ask*100,' '.join('%.0f%%'%(b*100) for _,b in per)))
print('\nCraft rows profit%% (walked scrap+steel cost)')
for label,nm,sn in [('A',0.99,bid),('B',1.0,bid),('C',0.99,bid*0.99)]:
    g,per=case(nm,sn,0.10);out=[]
    for t in range(1,7):
        sc=craft_walk(snap['commodities']['scraps']['order_book'],YIELDS[t-1]);st=craft_walk(snap['commodities']['steel']['order_book'],STEEL[t-1])
        cost=sc['cost']+st['cost'];out.append('%+.1f%%'%((per[t-1][0]-cost)/cost*100))
    print(' ',label,' '.join(out))
print('\nFloors (tax 1%%, bid %.3f)'%bid)
print(' t   S      Price listed S/1.01  Price typed S/1.01^2  Sort bar0 S/0.99  Sort bar0.10 (S+0.1)/0.99  Sort bar0.10 in displayed terms *1.01')
for t in range(1,7):
    S=YIELDS[t-1]*bid
    print(' %d %8.4f %9.4f %9.4f %9.4f %9.4f %9.4f'%(t,S,S/1.01,S/1.01**2,S/0.99,(S+0.1)/0.99,(S+0.1)/0.99*1.01))
print('\nBetween-floor counts (median typed p): (i) finding criterion S/1.01 < p <= (S+bar)/0.99;'
      ' (ii) user enters displayed p*1.01 on Price tab: S/1.01^2 < p <= (S+bar)/0.99')
for bar in (0.0,0.10):
    tot1=tot2=0;per1=[];per2=[]
    for t in range(1,7):
        S=YIELDS[t-1]*bid;hi=(S+bar)/0.99;n1=n2=pr=0
        for s in SLOTS:
            for p in medians(s,t).values():
                pr+=1
                if S/1.01<p<=hi:n1+=1
                if S/1.01**2<p<=hi:n2+=1
        per1.append('t%d %d/%d'%(t,n1,pr));per2.append('t%d %d/%d'%(t,n2,pr));tot1+=n1;tot2+=n2
    print(' bar %.2f (i) %s total %d'%(bar,' '.join(per1),tot1))
    print(' bar %.2f (ii) %s total %d'%(bar,' '.join(per2),tot2))
# listings-per-100-cases weight of between-floor rolls, and sort flips A->B
print('\nA->B sort flips (0.99p<=need<p) and weight per 100 cases')
for bar in (0.10,0.0):
    n=0;w=0;gold=0
    for t in range(1,7):
        dis=YIELDS[t-1]*bid;need=dis+bar
        for s in SLOTS:
            m=medians(s,t);sp=len(roll_space(s,t));each=ODDS[t-1]*W[s]/sp
            for p in m.values():
                if not p*0.99>need and p>need:n+=1;w+=each;gold+=each*(p-dis)
    print(' bar %.2f flips %d listings/100 %.2f gold/100 %.3f'%(bar,n,w*100,gold*100))
print('\nBetween-floor (criterion i, bar 0.10) weight per 100 cases')
n=0;w=0
for t in range(1,7):
    S=YIELDS[t-1]*bid;hi=(S+0.1)/0.99
    for s in SLOTS:
        m=medians(s,t);sp=len(roll_space(s,t));each=ODDS[t-1]*W[s]/sp
        for p in m.values():
            if S/1.01<p<=hi:n+=1;w+=each
print(' rolls %d, pieces per 100 cases %.2f'%(n,w*100))
