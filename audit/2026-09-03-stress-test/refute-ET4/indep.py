"""Independent re-derivation of ET-4 from the RAW rolling cache (not the published shards),
using collector.unpack_transaction/stale_listing so the eligibility rule is the collector's own."""
import sys, json, statistics, math
from datetime import timedelta
sys.path.insert(0, '/home/user/-warera-case1-collector')
import collector as c
SNAP='/home/user/-warera-case1-collector/data/warera_case1_market.json'
p=json.load(open(SNAP)); now=c.parse_time(p['generated_at'])
lo=now-timedelta(hours=48)
rolls={}; tier={}
tot=0; stale=0
for code,cat in p['categories'].items():
    tier[code]=cat['tier']
    for st in cat['transactions']:
        tx=c.unpack_transaction(st,code)
        if not tx['eligible_for_comps']: continue
        sold=c.parse_time(tx['sold_at'])
        if not (lo<=sold<=now): continue
        tot+=1
        if c.stale_listing(tx): stale+=1; continue
        rolls.setdefault((code,tx['roll_key']),[]).append((tx['unit_price'],tx['time_to_sell_seconds'],sold))
print('48h eligible sales',tot,'stale',stale,'kept',tot-stale,'rolls',len(rolls))
def q7(xs,q):
    s=sorted(xs);n=len(s);pos=(n-1)*q;i=int(pos);j=min(i+1,n-1);return s[i]+(s[j]-s[i])*(pos-i)
def q_floor(xs,q):  # page's dispersion() index rule, line 5791
    s=sorted(xs);return s[int(math.floor((len(s)-1)*q))]
def run(thr, qfn, tiers=None, label=''):
    sel={k:v for k,v in rolls.items() if len(v)>=thr and (tiers is None or tier[k[0]] in tiers)}
    upl=[];hi=[];le=[];lt=[];eq=[];hirel=[];paired=[];tw=0;nw=0
    for k,v in sel.items():
        ps=[x[0] for x in v]; m=statistics.median(ps); q3=qfn(ps,.75)
        upl.append(q3/m-1); tw+=(q3/m-1)*len(ps); nw+=len(ps)
        h=[t for pr,t,_ in v if pr>=q3 and t is not None]; l=[t for pr,t,_ in v if pr<=m and t is not None]
        hi+=h; le+=l; eq+=[t for pr,t,_ in v if pr==m and t is not None]; lt+=[t for pr,t,_ in v if pr<q3 and t is not None]
        hirel+=[pr/m-1 for pr,_,_ in v if pr>=q3]
        if h and l: paired.append((statistics.median(h),statistics.median(l)))
    md=lambda x: statistics.median(x)/60
    print('%-28s thr=%d rolls=%d sales=%d | Q3/med-1 mean=%.2f%% median=%.2f%% sw=%.2f%% | hi_sales=%d hi_rel=%.2f%% | tts min: >=Q3 %.1f ==med %.1f <=med %.1f <Q3 %.1f | paired rolls %d: hi>le in %d (%.0f%%), median ratio %.2f'%(
        label,thr,len(sel),sum(len(v) for v in sel.values()),100*statistics.mean(upl),100*statistics.median(upl),100*tw/nw,len(hirel),100*statistics.mean(hirel),
        md(hi),md(eq),md(le),md(lt),len(paired),sum(1 for a,b in paired if a>b),100*sum(1 for a,b in paired if a>b)/len(paired),
        statistics.median([a/b if b>0 else float('inf') for a,b in paired])))
for thr in (6,7,8): run(thr,q7,label='type7 quantile')
run(7,q_floor,label='page floor-index Q3')
for t in ('basic','reinforced','advanced','elite','legendary'): run(10,q7,{t},label='tier '+t)
# attack: are >=Q3 sales just older listings (offer created before the 48h window)?
sel={k:v for k,v in rolls.items() if len(v)>=7}
old_hi=old_le=n_hi=n_le=0
for k,v in sel.items():
    ps=[x[0] for x in v]; m=statistics.median(ps); q3=q7(ps,.75)
    for pr,t,sold in v:
        if t is None: continue
        created=sold-timedelta(seconds=t)
        if pr>=q3: n_hi+=1; old_hi+= created<lo
        if pr<=m: n_le+=1; old_le+= created<lo
print('listings created before window start: >=Q3 %d/%d (%.1f%%)  <=med %d/%d (%.1f%%)'%(old_hi,n_hi,100*old_hi/n_hi,old_le,n_le,100*old_le/n_le))
# expected-revenue arithmetic from b_oos proxies: +1.05% price x (47.9/61.6) sell share
print('naive revenue proxy: median 1.000*0.616=%.3f  Q3 1.0105*0.479=%.3f'%(0.616,1.0105*0.479))
