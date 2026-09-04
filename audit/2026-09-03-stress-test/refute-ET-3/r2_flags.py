"""Independent check of ET-3's flag-precision claim. Rolling origins every 8h (offset 3h from
ET's 6h grid), estimate = collector rule (24h median if n24>=3 else 48h median), target =
next-24h realised median. Rules: selected count<5, n48<5, selected-window (max-min)/median
(what factsFor lo/hi actually shows), 48h range, IQR/median>5%."""
import json, glob, os, statistics, datetime, collections, bisect
P='/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/public'
S=json.load(open(P+'/summary.json'))
NOW=int(datetime.datetime.fromisoformat(S['generated_at'].replace('Z','+00:00')).timestamp())
H=3600
def q(s,p):
    s=sorted(s);pos=(len(s)-1)*p;lo=int(pos);hi=min(lo+1,len(s)-1);return s[lo]+(s[hi]-s[lo])*(pos-lo)
rolls=collections.defaultdict(list)
for f in glob.glob(P+'/prices/*.json'):
    d=json.load(open(f))
    for p,t,tts,ri in d['sales']:
        if tts is not None and tts>48*H: continue
        rolls[(d['item_code'],ri)].append((t,p))
first=min(v[0][0] for v in rolls.values() if v)
for v in rolls.values(): v.sort()
origins=list(range(first+48*H+3*H, NOW-24*H+1, 8*H))
rows=[]
for k,v in rolls.items():
    ts=[t for t,_ in v]
    for T in origins:
        i=bisect.bisect_right(ts,T); j=bisect.bisect_right(ts,T+24*H)
        fut=[p for _,p in v[i:j]]
        p48=[p for t,p in v[:i] if t>T-48*H]; p24=[p for t,p in v[:i] if t>T-24*H]
        if not fut or not p48: continue
        sel=p24 if len(p24)>=3 else p48
        m=statistics.median(sel); err=abs(statistics.median(fut)/m-1)
        rows.append(dict(n=len(sel),n48=len(p48),err=err,rsel=(max(sel)-min(sel))/m,
                         r48=(max(p48)-min(p48))/statistics.median(p48),
                         iqr=(q(p48,.75)-q(p48,.25))/statistics.median(p48)))
N=len(rows); b5=sum(r['err']>.05 for r in rows); b10=sum(r['err']>.10 for r in rows)
print('roll-origins %d  base rate |err|>5%%: %.1f%%  >10%%: %.1f%%'%(N,100*b5/N,100*b10/N))
rules=[('count<5',lambda r:r['n']<5),('n48<5',lambda r:r['n48']<5),('n48<5 & count<5',lambda r:r['n48']<5 and r['n']<5),
       ('count<5 & n48>=5 (the 50-type)',lambda r:r['n']<5 and r['n48']>=5),
       ('selected range>10% (page lo/hi)',lambda r:r['rsel']>.1),('48h range>10%',lambda r:r['r48']>.1),('48h range>20%',lambda r:r['r48']>.2),
       ('IQR/med>5%',lambda r:r['iqr']>.05),('IQR/med>10%',lambda r:r['iqr']>.10)]
print('%-34s %6s %7s %7s %8s %9s %9s'%('rule','flag%','prec5','prec10','rec5','medErrIn','medErrOut'))
for name,fn in rules:
    fl=[r for r in rows if fn(r)]; un=[r for r in rows if not fn(r)]
    if not fl: continue
    print('%-34s %5.1f%% %6.1f%% %6.1f%% %7.1f%% %8.2f%% %8.2f%%'%(name,100*len(fl)/N,100*sum(r['err']>.05 for r in fl)/len(fl),
          100*sum(r['err']>.10 for r in fl)/len(fl),100*sum(r['err']>.05 for r in fl)/b5,
          100*statistics.median(r['err'] for r in fl),100*statistics.median(r['err'] for r in un) if un else float('nan')))
