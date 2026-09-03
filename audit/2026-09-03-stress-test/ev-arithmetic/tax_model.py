"""(a) Tax model: where the page applies tax, and what moves if the seller nets the typed price."""
from common import *
snap=load(); bid=snap['commodities']['scraps']['order_book']['best_bid']
def run(label,**kw):
    m=E.Model(snap,**kw); c=m.case(1)
    print('%-58s gross %.4f edge %+.4f pct %+.2f%%  broken/tier %s'%(label,c['gross'],c['edge'],c['pct'],
          ' '.join('%.0f%%'%(p['broken']*100) for p in c['parts'])))
    return m,c
print('== Case card under alternative tax models (bar 0.10) ==')
models={}
for bar in (0.10,0.0):
    print(' bar',bar)
    models[('page',bar)]=run('page: equipment nets median*(1-1%), scraps net bid',tax=1,bar_abs=bar)
    models[('typed',bar)]=run('seller nets typed (Price-tab model): tax=0, scraps net bid',tax=0,bar_abs=bar)
    models[('both',bar)]=run('tax on both sides: equipment*(0.99), scraps bid*0.99',tax=1,bar_abs=bar,scrap_bid=bid*0.99)
    models[('scrap/1.01',bar)]=run('Price-tab paintScrap model: equipment typed(tax0), scraps bid/1.01',tax=0,bar_abs=bar,scrap_bid=bid/1.01)
print('\n== Craft rows (profit % on walked scrap+steel cost) ==')
for label,kw in [('page tax1',dict(tax=1)),('typed tax0',dict(tax=0)),('both taxed',dict(tax=1,scrap_bid=bid*0.99))]:
    m=E.Model(snap,bar_abs=0.10,**kw); out=[]
    for t in range(1,7):
        e=m.craft_expected(t); sc=E.craft_walk(snap['commodities']['scraps']['order_book'],E.SCRAP_YIELDS[t-1]); st=E.craft_walk(snap['commodities']['steel']['order_book'],E.CRAFT_STEEL[t-1])
        cost=sc['cost']+st['cost']; out.append('%+.1f%%'%((e['net']-cost)/cost*100))
    print(' %-12s'%label,' '.join(out))
print('\n== Sort verdicts that flip between tax=1 and tax=0 (median*0.99 <= need < median) ==')
for bar in (0.10,0.0):
    m1=E.Model(snap,tax=1,bar_abs=bar); m0=E.Model(snap,tax=0,bar_abs=bar)
    tot=0; totw=0.0; totgold=0.0
    print(' bar %.2f'%bar)
    for t in range(1,7):
        n=0; priced=0; w=0.0; gold=0.0; det=[]
        for slot in E.SLOTS:
            v1=m1.slot_value(slot,t); v0=m0.slot_value(slot,t)
            if not v1: continue
            each=E.CASE_TIER_ODDS[t-1]*E.CRAFT_SLOT_WEIGHT[slot]/v1['space']
            r0={k:s for k,p,s,sl in v0['rows']}; 
            for k,p,s,sells in v1['rows']:
                priced+=1
                if (not sells) and (r0[k]>m0.need(t)):
                    n+=1; w+=each; gold+=each*(p-m1.dismantle(t)); det.append('%s %s med %.3f'%(slot,k,p))
        tot+=n; totw+=w; totgold+=gold
        print('  tier %d: %d of %d priced rolls flip break->sell; %.2f listings per 100 cases; gold at stake %.3f/100 cases%s'%(t,n,priced,w*100,gold*100,('  e.g. '+'; '.join(det[:4])) if det else ''))
    print('  total %d rolls, %.2f listings/100 cases, %.3f gold/100 cases'%(tot,totw*100,totgold*100))
print('\n== Dismantle floor: Price tab (paintScrap) vs Sort tab (craftDismantle/sortNeed), tax 1%%, bid %.3f =='%bid)
print(' tier  S=yield*bid  Price"listed"=S/1.01  Price"typed"=S/1.01^2  Sort floor(median terms, bar0)=S/0.99  Sort floor bar0.10=(S+0.10)/0.99')
for t in range(1,7):
    S=E.SCRAP_YIELDS[t-1]*bid
    print('  %d   %8.4f     %8.4f              %8.4f              %8.4f                  %8.4f'%(t,S,S/1.01,S/1.01**2,S/0.99,(S+0.10)/0.99))
print('\n rolls whose median lies between the Price-tab floor (S/1.01) and the Sort-tab floor ((S+bar)/0.99): Price says list, Sort says break')
m1=E.Model(snap,tax=1,bar_abs=0.10)
for bar in (0.0,0.10):
    mm=E.Model(snap,tax=1,bar_abs=bar); tot=0; per=[]
    for t in range(1,7):
        S=E.SCRAP_YIELDS[t-1]*bid; lo=S/1.01; hi=mm.need(t)/0.99; n=0; priced=0
        for slot in E.SLOTS:
            v=mm.slot_value(slot,t)
            if not v: continue
            for k,p,s,sells in v['rows']:
                priced+=1
                if lo<p<=hi: n+=1
        per.append('t%d %d/%d'%(t,n,priced)); tot+=n
    print('  bar %.2f: %s  total %d'%(bar,' '.join(per),tot))
