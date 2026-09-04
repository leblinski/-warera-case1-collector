"""Independent recount of ET-3's summary figures, from summary.json (what loadSummary reads)
and the shards (for IQR). No code shared with estimator-thin."""
import json, glob, os, statistics, datetime, collections
P='/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/public'
S=json.load(open(P+'/summary.json'))
NOW=int(datetime.datetime.fromisoformat(S['generated_at'].replace('Z','+00:00')).timestamp())
T=5
priced=quiet=marked=marked24=marked_fb5=unmarked=0
rng=[];fb5_by_item=collections.Counter();examples=[];cnt=collections.Counter()
price_shift=[]
for code,cat in S['categories'].items():
    for key,row in cat['rolls'].items():
        st=row['selected'] or row['fallback_48h']   # factsFor / sortRolls: row.selected||row.fallback_48h
        if not st or st.get('median') is None: quiet+=1; continue
        priced+=1; n=st['count'] or 0; fb=row['fallback_48h']
        b='1' if n==1 else '2' if n==2 else '3-4' if n<5 else '5-9' if n<10 else '10-29' if n<30 else '30+'
        cnt[b]+=1
        if n<T:
            marked+=1
            if row['selected_window_hours']==24: marked24+=1
            if (fb['count'] or 0)>=T:
                marked_fb5+=1; fb5_by_item[code]+=1
                examples.append((code,key,n,fb['count'],st['median'],fb['median']))
                price_shift.append((fb['median']-st['median'])/st['median'])
        else:
            unmarked+=1
            rng.append((fb['max']-fb['min'])/fb['median'])
print('priced',priced,'quiet',quiet,'marked',marked,'marked&24h',marked24,'marked&fb48>=5',marked_fb5,'unmarked',unmarked)
print('marked&fb48>=5 by item',dict(fb5_by_item))
print('count dist',dict(cnt))
rng.sort()
print('unmarked range>10%%: %d (%.1f%%) >20%%: %d >30%%: %d median %.1f%%'%(sum(r>.1 for r in rng),100*sum(r>.1 for r in rng)/len(rng),sum(r>.2 for r in rng),sum(r>.3 for r in rng),100*statistics.median(rng)))
ps=sorted(abs(x) for x in price_shift)
print('for the 50: |48h median - 24h median|/24h median: median %.2f%% p90 %.2f%% max %.2f%%; >1%%: %d, >3%%: %d'%(100*statistics.median(ps),100*ps[int(.9*len(ps))],100*max(ps),sum(p>.01 for p in ps),sum(p>.03 for p in ps)))
for e in examples:
    if e[0]=='rifle': print('  ',e)
# IQR from shards, non-stale, 48h window
def q(s,p):
    s=sorted(s);pos=(len(s)-1)*p;lo=int(pos);hi=min(lo+1,len(s)-1);return s[lo]+(s[hi]-s[lo])*(pos-lo)
iqr=[]
for f in glob.glob(P+'/prices/*.json'):
    d=json.load(open(f)); by=collections.defaultdict(list)
    for p,t,tts,ri in d['sales']:
        if tts is not None and tts>48*3600: continue
        if t>NOW-48*3600: by[ri].append(p)
    for ri,v in by.items():
        if len(v)>=T: iqr.append((q(v,.75)-q(v,.25))/statistics.median(v))
print('rolls >=5 nonstale 48h (shards): %d  IQR/med>10%%: %d (%.1f%%)  median IQR/med %.2f%%'%(len(iqr),sum(r>.1 for r in iqr),100*sum(r>.1 for r in iqr)/len(iqr),100*statistics.median(iqr)))
