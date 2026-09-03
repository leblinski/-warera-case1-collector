"""(b) Scrap side: bid depth, scraps produced, walk, sensitivities."""
from common import *
snap=load(); ob=snap['commodities']['scraps']['order_book']; cb=snap['commodities']['case1']['order_book']
bid=ob['best_bid']; buys=sorted(ob['buy_orders'],key=lambda o:-o['price'])
def depth(orders,pred): return sum(o['quantity'] for o in orders if pred(o['price']))
print('scrap best bid %.3f; depth at best %d; within 1%% (>=%.5f) %d; within 2%% %d; total shown (100 rows) %d; lowest shown %.3f'%(
    bid,depth(buys,lambda p:p>=bid),bid*0.99,depth(buys,lambda p:p>=bid*0.99),depth(buys,lambda p:p>=bid*0.98),sum(o['quantity'] for o in buys),buys[-1]['price']))
levels={}
for o in buys: levels[o['price']]=levels.get(o['price'],0)+o['quantity']
print(' bid levels:',' '.join('%.3f:%d'%(p,q) for p,q in sorted(levels.items(),reverse=True)[:8]))
sells=sorted(cb['sell_orders'],key=lambda o:o['price'])
print('case best ask %.3f; depth at best %d; within 1%% %d; total shown %d; highest shown %.3f'%(cb['best_ask'],depth(sells,lambda p:p<=cb['best_ask']),depth(sells,lambda p:p<=cb['best_ask']*1.01),sum(o['quantity'] for o in sells),sells[-1]['price']))
cbuys=sorted(cb['buy_orders'],key=lambda o:-o['price'])
print('case best bid %.3f; bid depth at best %d; within 1%% %d; total shown %d'%(cb['best_bid'],depth(cbuys,lambda p:p>=cb['best_bid']),depth(cbuys,lambda p:p>=cb['best_bid']*0.99),sum(o['quantity'] for o in cbuys)))
m=E.Model(snap,tax=1,bar_abs=0.10); c=m.case(1)
allscrap=sum(o*y for o,y in zip(E.CASE_TIER_ODDS,E.SCRAP_YIELDS))
brk=sum(o*y*p['broken'] for o,y,p in zip(E.CASE_TIER_ODDS,E.SCRAP_YIELDS,c['parts']))
print('\nscraps per case: dismantle everything %.3f; at the page break shares %.3f (%s)'%(allscrap,brk,' '.join('t%d %.0f%%'%(i+1,p['broken']*100) for i,p in enumerate(c['parts']))))
def walk_bids(qty):
    need=qty; got=0.0
    for o in buys:
        if need<=0: break
        take=min(need,o['quantity']); got+=take*o['price']; need-=take
    return got/(qty-need) if qty>need else None, need
for n in (100,1000,3500,10000):
    for lab,per in (('break-share',brk),('all',allscrap)):
        q=int(round(n*per)); avg,left=walk_bids(q)
        print(' %5d cases, %-11s %6d scraps -> walked avg bid %.5f (vs %.3f, %+.3f%%), unfilled %d'%(n,lab,q,avg,bid,(avg/bid-1)*100,left))
print('\nsensitivity to scrap bid (tax 1, bar 0.10, case cost %.3f):'%c['cost']['unit'])
prev=None
for b in [0.15,0.18,0.20,0.21,0.22,0.224,0.225,0.226,0.23,0.24,0.25,0.30]:
    g=E.Model(snap,tax=1,bar_abs=0.10,scrap_bid=b).case(1)
    print('  bid %.3f gross %.4f edge %+.4f pct %+.2f%%'%(b,g['gross'],g['edge'],g['pct']))
h=0.0005
gp=E.Model(snap,tax=1,bar_abs=0.10,scrap_bid=bid+h).case(1)['gross']; gm=E.Model(snap,tax=1,bar_abs=0.10,scrap_bid=bid-h).case(1)['gross']
print(' d(gross)/d(bid) at 0.225 (central, h=%.4f): %.3f gold per 1.0 of bid = %.4f per 0.001'%(h,(gp-gm)/(2*h),(gp-gm)/(2*h)*0.001))
print(' pure-scrap slope Σ odds*yield = %.3f; effective slope/pure = %.2f'%(allscrap,(gp-gm)/(2*h)/allscrap))
lo,hi=0.10,0.225
f=lambda b:E.Model(snap,tax=1,bar_abs=0.10,scrap_bid=b).case(1)['edge']
for _ in range(40):
    mid=(lo+hi)/2
    if f(mid)>0: hi=mid
    else: lo=mid
print(' zero-edge scrap bid: %.5f (%.2f%% below 0.225); edge at 0.215: %+.4f'%(hi,(1-hi/bid)*100,f(0.215)))
print('\nsensitivity to case ask: n=1 edge falls 1:1 with the ask. Walked unit cost by n:')
for n in (1,100,187,500,1000,3500,10000):
    w=E.craft_walk(cb,n); print('  n %5d unit %.5f thin %s  edge %+.4f pct %+.2f%%'%(n,w['unit'],w['thin'],c['gross']-w['unit'],(c['gross']/w['unit']-1)*100))
print(' zero-edge case ask = gross = %.4f (+%.2f%% above best ask)'%(c['gross'],(c['gross']/cb['best_ask']-1)*100))

print('\n== fine sweep of scrap bid 0.195..0.235 step 0.001: is gross monotone? ==')
prev=None; drops=[]
for i in range(195,236):
    b=i/1000; g=E.Model(snap,tax=1,bar_abs=0.10,scrap_bid=b).case(1)['gross']
    if prev is not None and g<prev-1e-9: drops.append((b,prev,g))
    prev=g
print(' non-monotone steps (bid, gross before, gross after):',['%.3f %.4f->%.4f'%d for d in drops])
print(' same sweep with bar 0 (pure threshold at dis):')
prev=None; drops=[]
for i in range(195,236):
    b=i/1000; g=E.Model(snap,tax=1,bar_abs=0.0,scrap_bid=b).case(1)['gross']
    if prev is not None and g<prev-1e-9: drops.append((b,prev,g))
    prev=g
print(' non-monotone steps:',['%.3f %.4f->%.4f'%d for d in drops])
for b in (0.0,0.05,0.10,0.15):
    c=E.Model(snap,tax=1,bar_abs=0.10,scrap_bid=b).case(1); print(' bid %.2f gross %.4f edge %+.4f broken %s'%(b,c['gross'],c['edge'],' '.join('%.0f%%'%(p['broken']*100) for p in c['parts'])))
print(' => no scrap bid in [0,0.225] zeroes the edge because the model holds equipment prices fixed while scrap falls;')
print('    Uncommon (30%% of cases) clears at scrap value (README), so its price would fall with the bid. Bounds on d(gross)/d(bid):')
print('    page (equipment exogenous) %.2f; pure scrap Σodds*yield %.2f; scrap-bound share only Σodds*yield*broken %.2f'%((gp-gm)/(2*h),allscrap,brk))
