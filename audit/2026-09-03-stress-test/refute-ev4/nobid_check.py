"""Independent re-derivation of the case card with scraps best_bid = 0.225 vs missing (0).
Mirrors craftSlotValue/craftExpected/sortNeed from test60.html lines 4316-4357, 4437-4444, 4569-4572."""
import json
P='/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/public'
S=json.load(open(P+'/summary.json'))['categories']
ODDS=[0.62,0.30,0.071,0.0085,0.0004,0.0001]; YIELD=[6,18,54,162,486,1458]
W={'weapon':0.30,'helmet':0.14,'chest':0.14,'boots':0.14,'gloves':0.14,'pants':0.14}
WEAP=['knife','gun','rifle','sniper','tank','jet']; TAX=0.99; CASE=3.55
def need(dis,abs_=0.10,pct=0,join='both'):
    bars=[]
    if abs_>0: bars.append(dis+abs_)
    if pct>0: bars.append(dis*(1+pct/100))
    if not bars: return dis
    if len(bars)==1: return bars[0]
    return min(bars) if join=='either' else max(bars)
def case(bid,abs_=0.10,pct=0,join='both'):
    gross=0; parts=[]
    for t in range(1,7):
        dis=YIELD[t-1]*bid; nd=need(dis,abs_,pct,join); wsum=net=0; brk=n=0
        for slot in W:
            code=WEAP[t-1] if slot=='weapon' else slot+str(t)
            rolls=S.get(code,{}).get('rolls',{}); vs=[]
            for r in rolls.values():
                st=r.get('selected') or r.get('fallback_48h')
                if not st or st.get('median') is None: continue
                sale=st['median']*TAX; sells=sale>nd; vs.append(sale if sells else dis)
                if not sells: brk+=1
                n+=1
            if not vs: continue
            wsum+=W[slot]; net+=W[slot]*sum(vs)/len(vs)
        v=net/wsum; gross+=ODDS[t-1]*v; parts.append((v,brk,n))
    return gross,parts
for lab,kw in [('bid 0.225 abs0.10',dict(bid=0.225)),('bid MISSING abs0.10',dict(bid=0)),
               ('bid MISSING pct5 only',dict(bid=0,abs_=0,pct=5)),('bid MISSING abs0.10+pct5 either',dict(bid=0,pct=5,join='either')),
               ('bid=index price 0.2255 (fallback)',dict(bid=0.22552436486026955)),('bid=ask 0.226 (fallback)',dict(bid=0.226))]:
    g,p=case(**kw)
    print('%-38s gross %.4f edge %+.4f pct %+.2f%% | tier net/broken: %s'%(lab,g,g-CASE,(g-CASE)/CASE*100,' '.join('%.2f/%d%%'%(v,round(b/n*100)) for v,b,n in p)))
print('sortNeed(dis=0): abs0.10->%.3f  pct5->%.3f  abs0.10+pct5 either->%.3f both->%.3f'%(need(0),need(0,0,5),need(0,0.10,5,'either'),need(0,0.10,5,'both')))
# rolls told to list under missing bid that are told to break under the real bid (priced rolls only)
flip=0; tot=0
for t in range(1,7):
    for slot in W:
        code=WEAP[t-1] if slot=='weapon' else slot+str(t)
        for r in S.get(code,{}).get('rolls',{}).values():
            st=r.get('selected') or r.get('fallback_48h')
            if not st or st.get('median') is None: continue
            tot+=1; sale=st['median']*TAX
            if sale<=need(YIELD[t-1]*0.225) and sale>0.10: flip+=1
print('priced rolls %d; told "break" with bid 0.225 but "sell" with bid missing: %d'%(tot,flip))
