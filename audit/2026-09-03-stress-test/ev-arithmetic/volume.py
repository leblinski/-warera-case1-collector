"""(e) 'Free money' sanity: daily volume per tier/item, cases/day at X% of it, variance, capital, labour."""
from common import *
from datetime import datetime, timedelta, timezone
snap=load(); now=datetime.fromisoformat(snap['generated_at'].replace('Z','+00:00'))
m=E.Model(snap,tax=1,bar_abs=0.10); c=m.case(1); edge=c['edge']; sd=c['sd']; cost=c['cost']['unit']
vol24={}; vol7={}; gold24={}; days=7.0
oldest=None
for code,cat in snap['categories'].items():
    n24=n7=0; g=0.0
    for tx in cat['transactions']:
        t=datetime.fromisoformat(tx['sold_at'].replace('Z','+00:00'))
        if oldest is None or t<oldest: oldest=t
        if now-t<=timedelta(hours=24): n24+=1; g+=tx['money']*tx['quantity']
        n7+=1
    vol24[code]=n24; vol7[code]=n7; gold24[code]=g
span=(now-oldest).total_seconds()/86400
print('window: %s .. %s (%.2f days)'%(oldest.isoformat(),now.isoformat(),span))
tier24=[0]*6; tier7=[0]*6; tiergold=[0]*6
for code in vol24:
    t=tier_of(code); tier24[t-1]+=vol24[code]; tier7[t-1]+=vol7[code]; tiergold[t-1]+=gold24[code]
print('\nsales per tier: last 24h | 7d/day | gold 24h ; per case listings = odds*(1-broken) ; cases/day at 10/25/50%% of tier volume')
bind={}
for t in range(1,7):
    lpc=E.CASE_TIER_ODDS[t-1]*(1-c['parts'][t-1]['broken'])
    row=[tier24[t-1],tier7[t-1]/span,tiergold[t-1]]
    xs=[(0.1*tier24[t-1]/lpc if lpc>0 else float('inf')),(0.25*tier24[t-1]/lpc if lpc>0 else float('inf')),(0.5*tier24[t-1]/lpc if lpc>0 else float('inf'))]
    bind[t]=xs
    print(' tier %d: %5d | %7.1f | %9.1f ; %.4f listings/case ; cases/day %8.0f %8.0f %8.0f'%(t,row[0],row[1],row[2],lpc,*xs))
print(' binding tier at 10%%: tier %d (%.0f cases/day); at 25%%: %.0f; at 50%%: %.0f'%(min(bind,key=lambda t:bind[t][0]),min(x[0] for x in bind.values()),min(x[1] for x in bind.values()),min(x[2] for x in bind.values())))
print('\nper item last-24h sales (sorted):')
for code,n in sorted(vol24.items(),key=lambda kv:-kv[1]): print('  %-8s %5d  (7d/day %6.1f)'%(code,n,vol7[code]/span))
# per-item binding: the opener's share of each item's daily volume when opening N cases/day
tot_list=sum(E.CASE_TIER_ODDS[t-1]*(1-c['parts'][t-1]['broken']) for t in range(1,7))
print('\nlistings per case (all tiers): %.3f; scraps per case %.2f'%(tot_list,sum(o*y*p['broken'] for o,y,p in zip(E.CASE_TIER_ODDS,E.SCRAP_YIELDS,c['parts']))))
for N in (100,300,1000,3000):
    shares=[]
    for t in range(1,7):
        for slot in E.SLOTS:
            code=E.item_code(slot,t); v=m.slot_value(slot,t)
            if not v or vol24.get(code,0)==0: continue
            lst=N*E.CASE_TIER_ODDS[t-1]*E.CRAFT_SLOT_WEIGHT[slot]*(1-v['broken']/v['weight'])
            shares.append((lst/vol24[code]*100,code,lst))
    shares.sort(reverse=True)
    print(' %5d cases/day: opener is %s of daily sales'%(N,', '.join('%.0f%% of %s (%.0f/%d)'%(s,cd,l,vol24[cd]) for s,cd,l in shares[:4])))
print('\nvariance: sd %.3f edge %+.4f; cases to 2-sigma = (2sd/edge)^2:'%(sd,edge))
for lab,e in (('page +3.61%%',edge),('+4.3%% (brief)',cost*0.043),('+9.47%% (as-traded)',cost*0.0947),('+2%%',cost*0.02)):
    n=(2*sd/e)**2; print('  %-20s edge %.4f -> %8.0f cases; capital %9.0f gold at 3.55; at 10%%-of-common cap (%.0f/day) %.1f days; listings %.0f; expected profit %.0f'%(lab,e,n,n*cost,min(x[0] for x in bind.values()),n/min(x[0] for x in bind.values()),n*tot_list,n*e))
print('\ncase order book: total ask depth shown %d, bid depth %d (100 rows each, capped by the collector); scrap bid depth %d'%(sum(o['quantity'] for o in snap['commodities']['case1']['order_book']['sell_orders']),sum(o['quantity'] for o in snap['commodities']['case1']['order_book']['buy_orders']),sum(o['quantity'] for o in snap['commodities']['scraps']['order_book']['buy_orders'])))
# case sales volume itself: not in snapshot (no case transactions) - say so
print('case1 daily traded volume: NOT in the snapshot (only the order book is collected); cannot be stated.')
