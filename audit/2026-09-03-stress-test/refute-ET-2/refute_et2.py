"""Independent re-derivation of ET-2 (own loader, own quantile/bootstrap), plus stress tests:
tier confound, target noise (nfut>=5), matched flag rate, sampling-vs-drift decomposition,
and 12h origin step."""
import json, glob, os, statistics as st, random, bisect, datetime, sys
PUB='/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/public'
H=3600; random.seed(7)
idx=json.load(open(PUB+'/index.json'))
NOW=int(datetime.datetime.fromisoformat(idx['generated_at'].replace('Z','+00:00')).timestamp())
rolls={}; tier={}
for f in sorted(glob.glob(PUB+'/prices/*.json')):
    d=json.load(open(f)); tier[d['item_code']]=d['tier']
    for p,t,tts,ri in d['sales']:
        if tts is not None and tts>48*H: continue          # collector stale rule
        rolls.setdefault((d['item_code'],ri),[]).append((t,p))
for k in rolls: rolls[k].sort()
first=min(v[0][0] for v in rolls.values())
def q(xs,f):
    s=sorted(xs); n=len(s)
    if n==1: return s[0]
    pos=(n-1)*f; lo=int(pos); hi=min(lo+1,n-1); return s[lo]+(s[hi]-s[lo])*(pos-lo)
def boot(ps,reps=300):
    if len(ps)<2: return float('inf')
    m=st.median(ps); ms=sorted(st.median(random.choices(ps,k=len(ps))) for _ in range(reps))
    return (q(ms,.95)-q(ms,.05))/2/m
def build(step_h):
    origins=range(first+48*H, NOW-24*H+1, step_h*H); rows=[]
    for (code,ri),v in rolls.items():
        ts=[t for t,_ in v]
        for T in origins:
            i=bisect.bisect_right(ts,T); j=bisect.bisect_right(ts,T+24*H)
            fut=[p for _,p in v[i:j]]
            i48=bisect.bisect_right(ts,T-48*H); i24=bisect.bisect_right(ts,T-24*H)
            p48=[p for _,p in v[i48:i]]; p24=[p for _,p in v[i24:i]]
            if not fut or not p48: continue
            sel=p24 if len(p24)>=3 else p48                 # MIN_PRIMARY_COMPS=3
            m=st.median(sel); err=abs(st.median(fut)/m-1)
            # same-period sampling noise: random half-split of p48
            if len(p48)>=2:
                sh=p48[:]; random.shuffle(sh); a=sh[:len(sh)//2]; b=sh[len(sh)//2:]
                split=abs(st.median(a)/st.median(b)-1)
            else: split=None
            rows.append(dict(tier=tier[code],n=len(sel),n48=len(p48),err=err,nfut=len(fut),split=split,
                             iqr=(q(p48,.75)-q(p48,.25))/st.median(p48),bw=boot(p48) if step_h==6 else None))
    return rows
def table(rows,rules,label):
    N=len(rows); b5=sum(r['err']>.05 for r in rows); b10=sum(r['err']>.10 for r in rows)
    print('\n[%s] roll-origins %d  base >5%%: %.1f%%  >10%%: %.1f%%'%(label,N,100*b5/N,100*b10/N))
    print('%-28s %6s %7s %6s %7s %6s'%('rule','flag%','prec5','rec5','prec10','rec10'))
    for name,fn in rules:
        fl=[r for r in rows if fn(r)]
        if not fl: print('%-28s  none'%name); continue
        h5=sum(r['err']>.05 for r in fl); h10=sum(r['err']>.10 for r in fl)
        print('%-28s %5.1f%% %6.1f%% %5.1f%% %6.1f%% %5.1f%%'%(name,100*len(fl)/N,100*h5/len(fl),100*h5/max(b5,1),100*h10/len(fl),100*h10/max(b10,1)))
rules=[('count<5 (page)',lambda r:r['n']<5),('count<3',lambda r:r['n']<3),('count==1',lambda r:r['n']==1),
       ('IQR/med>5%',lambda r:r['iqr']>.05),('IQR/med>3%',lambda r:r['iqr']>.03),
       ('count<5 OR IQR>5%',lambda r:r['n']<5 or r['iqr']>.05),('tier basic',lambda r:r['tier']=='basic')]
rows=build(6)
table(rows,rules+[('boot hw>3%',lambda r:r['bw']>.03)],'6h origins, all (ET-2 design)')
print('\n== by selected count: N, median err, p90, >5% ==')
for lo,hi in [(1,1),(2,2),(3,4),(5,9),(10,19),(20,49),(50,10**9)]:
    s=sorted(r['err'] for r in rows if lo<=r['n']<=hi)
    print('  n %2d-%-4s N=%5d med %.2f%% p90 %.2f%% >5%%: %.1f%%'%(lo,hi if hi<10**9 else 'inf',len(s),100*st.median(s),100*q(s,.9),100*sum(e>.05 for e in s)/len(s)))
print('\n== tier confound: rules inside non-basic and inside basic ==')
table([r for r in rows if r['tier']!='basic'],rules[:6],'non-basic only')
table([r for r in rows if r['tier']=='basic'],rules[:6],'basic only')
fl=[r for r in rows if r['iqr']>.05]; print('\nIQR>5%% flagged set: %d, of which basic %d (%.0f%%); hits>5%%%%: total %d, basic %d'%(
    len(fl),sum(r['tier']=='basic' for r in fl),100*sum(r['tier']=='basic' for r in fl)/len(fl),sum(r['err']>.05 for r in fl),sum(r['err']>.05 and r['tier']=='basic' for r in fl)))
print('\n== target noise: nfut>=5 only ==')
table([r for r in rows if r['nfut']>=5],rules[:6],'nfut>=5')
print('\n== 12h origin step (less overlap) ==')
table(build(12),rules[:6],'12h origins')
print('\n== sampling vs drift: median |split-half err| vs next-day err, by n48 ==')
for lo,hi in [(2,4),(5,9),(10,29),(30,10**9)]:
    s=[r for r in rows if lo<=r['n48']<=hi and r['split'] is not None]
    print('  n48 %2d-%-4s N=%5d  split-half med %.2f%%  next-day med %.2f%%  boot hw med %.2f%%  boot coverage %.1f%%'%(
        lo,hi if hi<10**9 else 'inf',len(s),100*st.median(r['split'] for r in s),100*st.median(r['err'] for r in s),
        100*st.median(r['bw'] for r in s),100*sum(r['err']<=r['bw'] for r in s)/len(s)))
inb=[r for r in rows if r['bw']<1e9]; print('overall boot 90%% band coverage of next-day median: %.1f%% (N=%d)'%(100*sum(r['err']<=r['bw'] for r in inb)/len(inb),len(inb)))
# empirical band alternative: tier p90 of next-day err, in-sample coverage check
print('\n== empirical tier-p90 band coverage (in-sample) ==')
for t in ['basic','reinforced','advanced','elite','legendary','mythic']:
    s=[r['err'] for r in rows if r['tier']==t]; p90=q(s,.9)
    print('  %-10s p90 %.2f%%  coverage %.1f%%'%(t,100*p90,100*sum(e<=p90 for e in s)/len(s)))
# snapshot-level: how many rolls on the page are dotted today
cnt=0;tot=0
for f in sorted(glob.glob(PUB+'/prices/*.json')):
    d=json.load(open(f))
    for k,r in d['summary'].items():
        s=r.get('selected') or r.get('fallback_48h')
        if s and s.get('median') is not None:
            tot+=1; cnt+=(s.get('count') or 0)<5
print('\nsnapshot: rolls with a selected median %d, dotted (count<5) %d (%.1f%%)'%(tot,cnt,100*cnt/tot))
