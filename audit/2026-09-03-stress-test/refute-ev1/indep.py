"""Independent re-derivation of EV-1 from the raw snapshot (no ev_ref import).
Mirrors craftSlotValue/craftExpected/paintCase (test60.html 4316-4360, 5049-5054)."""
import json
SNAP='/home/user/-warera-case1-collector/data/warera_case1_market.json'
snap=json.load(open(SNAP)); cats=snap['categories']
BID=snap['commodities']['scraps']['order_book']['best_bid']
ASK=snap['commodities']['case1']['order_book']['best_ask']
Y=[6,18,54,162,486,1458]; ODDS=[0.62,0.30,0.071,0.0085,0.0004,0.0001]
W={'weapon':0.30,'helmet':0.14,'chest':0.14,'boots':0.14,'gloves':0.14,'pants':0.14}
WC=['knife','gun','rifle','sniper','tank','jet']
WS=[((21,40),(1,5)),((51,60),(6,10)),((71,90),(11,15)),((101,130),(16,20)),((141,170),(26,35)),((221,300),(41,50))]
SR={'helmet':('criticalDamages',[(1,15),(16,30),(31,50),(71,90),(91,110),(121,150)]),
 'boots':('dodge',[(1,5),(6,10),(11,15),(21,25),(31,40),(51,60)]),
 'chest':('armor',[(1,5),(6,10),(11,15),(21,30),(36,50),(56,70)]),
 'pants':('armor',[(1,5),(6,10),(11,15),(21,30),(36,50),(56,70)]),
 'gloves':('precision',[(1,5),(6,10),(11,15),(21,25),(31,40),(51,60)])}
def space(slot,t):
    if slot=='weapon':
        (a0,a1),(c0,c1)=WS[t-1]; return ['%d/%d'%(a,c) for a in range(a0,a1+1) for c in range(c0,c1+1)]
    lo,hi=SR[slot][1][t-1]; return [str(v) for v in range(lo,hi+1)]
def rkey(slot,sk):
    if not sk: return None
    if slot=='weapon':
        return None if sk.get('attack') is None or sk.get('criticalChance') is None else '%s/%s'%(sk['attack'],sk['criticalChance'])
    k=SR[slot][0]; return None if sk.get(k) is None else str(sk[k])
# cache: per (slot,t) list of net sale prices (median*0.99) over priced rolls
TAX=0.99
SALES={}
for t in range(1,7):
    for slot in W:
        code=WC[t-1] if slot=='weapon' else slot+str(t)
        cat=cats.get(code)
        if not cat: continue
        seen={}
        for key,row in cat['rolls'].items():
            k=rkey(slot,(row.get('exact_roll') or {}).get('skills'))
            if k is not None: seen[k]=row
        vals=[]
        for k in space(slot,t):
            row=seen.get(k)
            if not row: continue
            st=row.get('selected') or row.get('fallback_48h')
            if not st or st.get('median') is None: continue
            vals.append(st['median']*TAX)
        if vals: SALES[(slot,t)]=vals
def need_of(dis,abs_,pct,join):
    bars=[]
    if abs_>0: bars.append(dis+abs_)
    if pct>0: bars.append(dis*(1+pct/100))
    if not bars: return dis
    if len(bars)==1: return bars[0]
    return min(bars) if join=='either' else max(bars)
def gross(bid=BID,abs_=0.10,pct=0,join='both',fee=0.0,detail=False):
    g=0; lst=0; parts=[]
    for t in range(1,7):
        dis=Y[t-1]*bid; need=need_of(dis,abs_,pct,join)
        ws=net=l=0; brk=0; n=0
        for slot in W:
            v=SALES.get((slot,t))
            if not v: continue
            w=W[slot]; ws+=w
            vals=[(s-fee) if s>need else dis for s in v]
            net+=w*sum(vals)/len(vals); l+=w*sum(1 for s in v if s>need)/len(vals)
            brk+=w*sum(1 for s in v if not s>need); n+=w*len(v)
        parts.append((net/ws,brk/n)); g+=ODDS[t-1]*net/ws; lst+=ODDS[t-1]*l/ws
    return (g,lst,parts) if detail else (g,lst)
def pct(g): return (g-ASK)/ASK*100
print('bid %.3f ask %.2f'%(BID,ASK))
g,l,parts=gross(detail=True)
print('page default (bar 0.10, fee 0):   gross %.4f edge %+.4f pct %+.2f%% listings/case %.3f'%(g,g-ASK,pct(g),l))
print('  per-tier net:',' '.join('%.4f'%p[0] for p in parts),'| broken:',' '.join('%.0f%%'%(p[1]*100) for p in parts))
for fee in (0.05,0.10,0.20):
    g,l=gross(fee=fee); print('bar 0.10, fee %.2f:                gross %.4f edge %+.4f pct %+.2f%% listings/case %.3f'%(fee,g,g-ASK,pct(g),l))
g,l=gross(abs_=0); print('bar 0, fee 0:                     gross %.4f pct %+.2f%% listings/case %.3f'%(g,pct(g),l))
g,l=gross(abs_=0,fee=0.10); print('bar 0, fee 0.10:                  gross %.4f pct %+.2f%% listings/case %.3f'%(g,pct(g),l))
# optimal threshold for fee 0.10: sweep bar
best=max(((gross(abs_=b,fee=0.10)[0],b) for b in [x/100 for x in range(0,41)]))
print('fee 0.10: best bar in 0..0.40 step 0.01 -> bar %.2f gross %.4f'%(best[1],best[0]))
# forgone-edge per dropped listing (the comment's "five copper a listing")
g0,l0=gross(abs_=0); g1,l1=gross()
print('comment check: dropped listings/100 cases %.2f, gold given up/100 %.3f, per dropped listing %.4f'%((l0-l1)*100,(g0-g1)*100,(g0-g1)/(l0-l1)))
# scrap bid cliff and monotonicity
print('bid 0.214 gross %.4f | 0.215 gross %.4f'%(gross(bid=0.214)[0],gross(bid=0.215)[0]))
for lab,kw in (('threshold bar 0.10',dict()),('threshold bar 0',dict(abs_=0)),('fee model max(sale-0.10,dis)',dict(fee=0.10))):
    prev=None; drops=[]
    for i in range(150,301):
        b=i/1000; g=gross(bid=b,**kw)[0]
        if prev is not None and g<prev-1e-9: drops.append((b,prev,g))
        prev=g
    print('%-32s bid sweep 0.150..0.300 step 0.001: %d decreasing steps; largest %s'%(lab,len(drops),max(drops,key=lambda d:d[1]-d[2]) if drops else '-'))
# either join with pct
for p in (0,0.5,1,2,5):
    print('abs 0.10 + pct %.1f join=either gross %.4f | join=both gross %.4f'%(p,gross(pct=p,join='either')[0],gross(pct=p,join='both')[0]))
