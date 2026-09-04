"""Independent re-check of EV-6 (scrap side). Only roll_space/roll_key/constants borrowed from ev_ref."""
import json,sys
sys.path.insert(0,'/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit')
from ev_ref import roll_space,roll_key,SCRAP_YIELDS as Y,CASE_TIER_ODDS as ODDS,CRAFT_SLOT_WEIGHT as W,SLOTS,item_code
snap=json.load(open('/home/user/-warera-case1-collector/data/warera_case1_market.json'))
ob=snap['commodities']['scraps']['order_book']; cb=snap['commodities']['case1']['order_book']
buys=sorted(ob['buy_orders'],key=lambda o:-o['price'])
lv={}
for o in buys: lv[o['price']]=lv.get(o['price'],0)+o['quantity']
print('scrap best_bid',ob['best_bid'],'rows',len(buys),'levels',sorted(lv.items(),reverse=True)[:6],'sum>=0.22275',sum(q for p,q in lv.items() if p>=0.22275))
allscrap=sum(o*y for o,y in zip(ODDS,Y)); print('sum odds*yield %.4f'%allscrap)
cats=snap['categories']
def slot_val(slot,t,bid,tax=0.01,bar=0.10):
    cat=cats.get(item_code(slot,t))
    if not cat: return None
    seen={}
    for k,row in cat['rolls'].items():
        kk=roll_key(slot,(row.get('exact_roll') or {}).get('skills'))
        if kk is not None: seen[kk]=row
    dis=Y[t-1]*bid; need=dis+bar if bar>0 else dis
    n=0;v=0;b=0
    for r in roll_space(slot,t):
        row=seen.get(r)
        if not row: continue
        st=row.get('selected') or row.get('fallback_48h')
        if not st or st.get('median') is None: continue
        sale=st['median']*(1-tax); sells=sale>need
        v+= sale if sells else dis; n+=1; b+= 0 if sells else 1
    return (v/n,b/n,n) if n else None
def gross(bid,bar=0.10):
    g=0; slope=0; bs=[]
    for t in range(1,7):
        ws=0;net=0;bw=0;rollw=0;brk=0;fs=0
        for s in SLOTS:
            sv=slot_val(s,t,bid,bar=bar)
            if not sv: continue
            w=W[s]; ws+=w; net+=w*sv[0]; fs+=w*sv[1]; brk+=w*sv[1]*sv[2]; rollw+=w*sv[2]
        g+=ODDS[t-1]*net/ws; slope+=ODDS[t-1]*Y[t-1]*fs/ws; bs.append(brk/rollw)
    return g,slope,bs
g,sl,bs=gross(0.225)
print('gross@0.225 %.4f edge %+.4f pct %+.2f%%; exact fixed-decision slope d(gross)/d(bid)=%.3f; page brokenShare/tier %s; sum odds*yield*brokenShare=%.3f'%(g,g-3.55,(g/3.55-1)*100,sl,' '.join('%.0f%%'%(x*100) for x in bs),sum(o*y*b for o,y,b in zip(ODDS,Y,bs))))
for b in (0.0,0.15,0.20,0.215,0.220,0.224,0.2245,0.2255,0.226,0.230,0.240):
    gg=gross(b)[0]; print('  bid %.4f gross %.4f pct %+.2f%%  (delta pp vs base %+.2f)'%(b,gg,(gg/3.55-1)*100,(gg-g)/3.55*100))
gp=gross(0.2255)[0]; gm=gross(0.2245)[0]; print('central FD slope h=0.0005: %.3f'%((gp-gm)/0.001))
print('one-sided: +0.005 -> %.3f/unit; -0.005 -> %.3f/unit; +0.015 -> %.3f/unit'%((gross(0.230)[0]-g)/0.005,(g-gross(0.220)[0])/0.005,(gross(0.240)[0]-g)/0.015))
# walk of bid book for scrap quantities
def walk(q):
    need=q;got=0
    for o in buys:
        if need<=0:break
        t=min(need,o['quantity']);got+=t*o['price'];need-=t
    return got/(q-need),need
for n in (100,1000,10000):
    for per in (sum(o*y*b for o,y,b in zip(ODDS,Y,bs)),allscrap):
        q=round(n*per); a,l=walk(q); print('  %5d cases %6d scraps avg %.5f unfilled %d'%(n,q,a,l))
sells=sorted(cb['sell_orders'],key=lambda o:o['price'])
def cw(q):
    need=q;c=0;last=None
    for o in sells:
        if need<=0:break
        t=min(need,o['quantity']);c+=t*o['price'];need-=t;last=o['price']
    return (c+need*last)/q,need>0
print('case ask',cb['best_ask'],'depth at best',sum(o['quantity'] for o in sells if o['price']<=cb['best_ask']))
for n in (187,188,500,1000,3500,10000): u,th=cw(n); print('  n %5d unit %.4f thin %s pct %+.2f%%'%(n,u,th,(g/u-1)*100))
print('zero-edge ask = gross %.4f (+%.2f%%)'%(g,(g/3.55-1)*100))
