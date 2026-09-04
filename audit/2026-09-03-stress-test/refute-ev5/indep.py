"""Independent re-derivation of EV-5 straight from the published shards (no ev_ref, no snapshot summaries).
Page logic re-implemented from test60.html: craftSlotValue 4316, craftExpected 4346, paintCase 5024,
sortNeed 4437, craftDismantle 4569, craftWalk 4585. Collector filter from collector.py aggregate 446-483."""
import json, glob, statistics, random, datetime, os
PUB='/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/public'
SCRAP_YIELDS=[6,18,54,162,486,1458]; ODDS=[0.62,0.30,0.071,0.0085,0.0004,0.0001]
SLOTW={'weapon':0.30,'helmet':0.14,'chest':0.14,'boots':0.14,'gloves':0.14,'pants':0.14}
WEAP=['knife','gun','rifle','sniper','tank','jet']
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
def key(slot,sk):
    if slot=='weapon': return '%s/%s'%(sk['attack'],sk['criticalChance'])
    return str(sk[SR[slot][0]])
idx=json.load(open(PUB+'/index.json')); com=json.load(open(PUB+'/commodities.json'))
gen=int(datetime.datetime.fromisoformat(idx['generated_at'].replace('Z','+00:00')).timestamp())
scrap_bid=com['commodities']['scraps']['order_book']['best_bid']
asks=sorted(com['commodities']['case1']['order_book']['sell_orders'],key=lambda o:o['price'])
case_cost=asks[0]['price']   # craftWalk qty=1 = best ask
TAX=0.01; BAR=0.10
def need(t): return SCRAP_YIELDS[t-1]*scrap_bid+BAR
def dis(t): return SCRAP_YIELDS[t-1]*scrap_bid
# --- load shards: per code -> roll key -> list of (sold, price, tts) within 48h & not stale
rolls={}  # code -> key -> rows
for f in sorted(glob.glob(PUB+'/prices/*.json')):
    p=json.load(open(f)); code=p['item_code']; slot='weapon' if code in WEAP else code[:-1]
    d={}
    for price,sold,tts,ri in p['sales']:
        if sold< gen-48*3600 or sold>gen: continue
        if tts is not None and tts>48*3600: continue
        d.setdefault(key(slot,p['rolls'][ri]['skills']),[]).append((sold,price,tts))
    rolls[code]=d
    # cross-check the shard's own summary median vs recompute
summ_mismatch=0; npriced=0
for f in sorted(glob.glob(PUB+'/prices/*.json')):
    p=json.load(open(f)); code=p['item_code']; slot='weapon' if code in WEAP else code[:-1]
    for k,row in p['summary']['rolls'].items() if isinstance(p['summary'].get('rolls'),dict) else []:
        pass
def sel_rows(rows):
    r24=[r for r in rows if r[0]>=gen-24*3600]
    return r24 if len(r24)>=3 else rows
def Q(xs,q,method='inclusive'):
    xs=sorted(xs)
    if len(xs)==1: return xs[0]
    return statistics.quantiles(xs,n=4,method=method)[{0.25:0,0.5:1,0.75:2}[q]]
def ev(pricefn):
    """pricefn(rows)->price|None ; returns gross, per-tier broken"""
    gross=0; parts=[]
    for t in range(1,7):
        wsum=net=0; brk=rw=0
        for slot in SLOTW:
            code=WEAP[t-1] if slot=='weapon' else slot+str(t)
            d=rolls.get(code,{}); vs=0; ws=0; b=0
            for k in space(slot,t):
                rows=d.get(k)
                if not rows: continue
                pr=pricefn(rows)
                if pr is None: continue
                sale=pr*(1-TAX); sells=sale>need(t); vs+=sale if sells else dis(t); ws+=1; b+=0 if sells else 1
            if not ws: continue
            w=SLOTW[slot]; wsum+=w; net+=w*vs/ws; brk+=w*b; rw+=w*ws
        gross+=ODDS[t-1]*net/wsum; parts.append((net/wsum,brk/rw))
    return gross,parts
def rep(lab,fn):
    g,parts=ev(fn); print('%-42s gross %.4f edge %+.4f pct %+.2f%%  broken %s'%(lab,g,g-case_cost,(g/case_cost-1)*100,' '.join('%.0f%%'%(p[1]*100) for p in parts)))
    return g
print('gen',idx['generated_at'],'scrap bid',scrap_bid,'case best ask',case_cost, 'rolls priced', sum(len(d) for d in rolls.values()))
base=rep('selected median (page def, from shards)',lambda r: statistics.median([x[1] for x in sel_rows(r)]))
rep('48h median',lambda r: statistics.median([x[1] for x in r]))
rep('p25 selected window (inclusive)',lambda r: Q([x[1] for x in sel_rows(r)],0.25))
rep('p75 selected window (inclusive)',lambda r: Q([x[1] for x in sel_rows(r)],0.75))
rep('p25 48h (inclusive)',lambda r: Q([x[1] for x in r],0.25))
rep('p75 48h (inclusive)',lambda r: Q([x[1] for x in r],0.75))
rep('p25 48h (exclusive)',lambda r: Q([x[1] for x in r],0.25,'exclusive'))
rep('p75 48h (exclusive)',lambda r: Q([x[1] for x in r],0.75,'exclusive'))
rep('p25 selected (exclusive)',lambda r: Q([x[1] for x in sel_rows(r)],0.25,'exclusive'))
rep('p75 selected (exclusive)',lambda r: Q([x[1] for x in sel_rows(r)],0.75,'exclusive'))
rep('48h min',lambda r: min(x[1] for x in r))
rep('selected-window min (page selected.min)',lambda r: min(x[1] for x in sel_rows(r)))
rep('48h max',lambda r: max(x[1] for x in r))
rep('last sale (48h)',lambda r: max(r)[1])
rep('median of tts<=30min sales',lambda r: (lambda f: statistics.median(f) if f else None)([x[1] for x in r if x[2] is not None and x[2]<=1800]))
rep('median of tts<=30min, else selected median',lambda r: (lambda f: statistics.median(f) if f else statistics.median([x[1] for x in sel_rows(r)]))([x[1] for x in r if x[2] is not None and x[2]<=1800]))
rep('mean 48h',lambda r: statistics.fmean([x[1] for x in r]))
# per-tier contribution of the p25->p75 spread
g25,p25=ev(lambda r: Q([x[1] for x in sel_rows(r)],0.25)); g75,p75=ev(lambda r: Q([x[1] for x in sel_rows(r)],0.75))
print('\nper-tier odds*net at p25 / median / p75 (selected window):')
gb,pb=ev(lambda r: statistics.median([x[1] for x in sel_rows(r)]))
for t in range(6): print('  t%d %.4f %.4f %.4f  (delta p75-p25 %.4f)'%(t+1,ODDS[t]*p25[t][0],ODDS[t]*pb[t][0],ODDS[t]*p75[t][0],ODDS[t]*(p75[t][0]-p25[t][0])))
# bootstrap sampling uncertainty of the page's own definition
random.seed(1); B=300; gs=[]
for b in range(B):
    def fn(r):
        s=sel_rows(r); s=[random.choice(s) for _ in s]; return statistics.median([x[1] for x in s])
    gs.append(ev(fn)[0])
gs.sort()
print('\nbootstrap (resample sales within each roll, %d reps): gross mean %.4f  2.5%% %.4f  97.5%% %.4f  -> pct %+.2f%% .. %+.2f%%'%(B,statistics.fmean(gs),gs[int(0.025*B)],gs[int(0.975*B)-1],(gs[int(0.025*B)]/case_cost-1)*100,(gs[int(0.975*B)-1]/case_cost-1)*100))
# counts of rolls with n=1,2 in selected window (where p25=p75 or interpolated)
n1=n2=0; tot=0
for d in rolls.values():
    for r in d.values():
        s=sel_rows(r); tot+=1; n1+=len(s)==1; n2+=len(s)==2
print('rolls priced %d; selected-window n=1: %d, n=2: %d'%(tot,n1,n2))
