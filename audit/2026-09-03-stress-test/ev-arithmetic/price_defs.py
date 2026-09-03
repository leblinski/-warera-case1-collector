"""(f) Bracket the case EV under alternative per-roll price definitions computed from the shards."""
from common import *
import glob, statistics, copy
snap=load(); gen=int(__import__('datetime').datetime.fromisoformat(snap['generated_at'].replace('Z','+00:00')).timestamp())
W48=48*3600; W24=24*3600; STALE=48*3600; FAST=1800
def q25(xs):
    xs=sorted(xs); 
    if len(xs)==1: return xs[0]
    return statistics.quantiles(xs,n=4,method='inclusive')[0]
defs={}
per_roll={}  # code -> key -> dict of alt prices
for path in sorted(glob.glob(PUBLIC+'/prices/*.json')):
    p=json.load(open(path)); code=p['item_code']; slot=slot_of(code)
    rolls=p['rolls']; by={}
    for price,sold,tts,idx in p['sales']:
        if gen-sold>W48: continue
        if tts is not None and tts>STALE: continue
        by.setdefault(idx,[]).append((sold,price,tts))
    per_roll[code]={}
    for idx,rows in by.items():
        key=E.roll_key(slot,rolls[idx]['skills']); rows.sort()
        prices=[r[1] for r in rows]; last24=[r[1] for r in rows if gen-r[0]<=W24]
        fast=[r[1] for r in rows if r[2] is not None and r[2]<=FAST]
        sel=last24 if len(last24)>=3 else prices
        per_roll[code][key]={'median48':statistics.median(prices),'selected_recomputed':statistics.median(sel),'p25_48':q25(prices),'p75_48':statistics.quantiles(sorted(prices),n=4,method='inclusive')[2] if len(prices)>1 else prices[0],
            'min48':min(prices),'last':rows[-1][1],'fast30':statistics.median(fast) if fast else None,'fast30_n':len(fast),'n48':len(prices),
            'p25_sel':q25(sel)}
# check the recomputed selected median against the page's selected.median
mism=0; tot=0; maxd=0
for code,cat in snap['categories'].items():
    for k,row in cat['rolls'].items():
        key=E.roll_key(slot_of(code),row['exact_roll']['skills']); st=row['selected']
        if st['median'] is None: continue
        tot+=1; alt=per_roll[code].get(key)
        if not alt: mism+=1; continue
        d=abs(alt['selected_recomputed']-st['median'])
        if d>1e-9: mism+=1; maxd=max(maxd,d)
print('recomputed selected median from shards: %d priced rolls, %d mismatches (max abs diff %.4f) -> shard filter replicates the page'%(tot,mism,maxd))
def run(defn):
    s2=copy.deepcopy(snap); priced=0
    for code,cat in s2['categories'].items():
        for k,row in cat['rolls'].items():
            key=E.roll_key(slot_of(code),row['exact_roll']['skills']); alt=per_roll.get(code,{}).get(key)
            v=alt.get(defn) if alt else None
            if v is None: row['selected']={'median':None,'count':0}; row['fallback_48h']={'median':None,'count':0}
            else: row['selected']=dict(row['selected'],median=v); priced+=1
    c=E.Model(s2,tax=1,bar_abs=0.10).case(1)
    return c,priced
base=E.Model(snap,tax=1,bar_abs=0.10).case(1)
print('page (selected.median):        gross %.4f edge %+.4f pct %+.2f%%  broken %s'%(base['gross'],base['edge'],base['pct'],' '.join('%.0f%%'%(p['broken']*100) for p in base['parts'])))
for defn,lab in [('selected_recomputed','selected median recomputed'),('median48','48h median'),('p25_sel','25th pct of selected window'),('p25_48','25th pct of last 48h'),('p75_48','75th pct of last 48h'),('min48','48h min'),('last','last sale'),('fast30','median of sales that cleared <=30 min')]:
    c,priced=run(defn)
    print('%-32s gross %.4f edge %+.4f pct %+.2f%%  priced rolls %4d  broken %s'%(lab,c['gross'],c['edge'],c['pct'],priced,' '.join('%.0f%%'%(p['broken']*100) for p in c['parts'])))
# how many rolls have any fast sale
nf=sum(1 for code in per_roll for k,v in per_roll[code].items() if v['fast30'] is not None); n48=sum(len(v) for v in per_roll.values())
print('rolls with >=1 sale in 48h: %d; with >=1 fast (<=30min) sale: %d'%(n48,nf))
# per tier: mean ratio of alt/median for priced rolls
print('\nmean ratio alt/median48 by tier (priced rolls):')
for defn in ('p25_48','min48','last','fast30'):
    out=[]
    for t in range(1,7):
        rs=[v[defn]/v['median48'] for code in per_roll if tier_of(code)==t for v in per_roll[code].values() if v.get(defn) is not None]
        out.append('t%d %.3f(n%d)'%(t,sum(rs)/len(rs),len(rs)) if rs else 't%d -'%t)
    print('  %-8s %s'%(defn,' '.join(out)))
