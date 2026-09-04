"""Hold-one-out bias of nearest-worse-neighbour price on knife priced rolls; priced-roll sample sizes;
alternative counterfactuals (two-sided interpolation)."""
import json, sys, os, statistics as S
AUDIT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0,AUDIT)
import ev_ref as E
p=json.load(open('/home/user/-warera-case1-collector/data/warera_case1_market.json'))
M=E.Model(p,tax=1,bar_abs=0.10); c0=M.case(1); g0=c0['gross']; cost=c0['cost']['unit']
tax=0.99; dis=M.dismantle(1); need=M.need(1)
cat=p['categories']['knife']; seen={}
for row in cat['rolls'].values(): seen[E.roll_key('weapon',row['exact_roll']['skills'])]=row
space=E.roll_space('weapon',1); pos=lambda k:int(k.split('/')[0]); band=lambda k:k.split('/')[1]
priced={};cnt={};win={}
for k in space:
    r=seen.get(k); st=r and (r['selected'] or r['fallback_48h'])
    if st and st.get('median') is not None: priced[k]=st['median']; cnt[k]=st['count']; win[k]=r['selected_window_hours']
from collections import Counter
print('priced rolls selected count distribution:',sorted(Counter(cnt.values()).items()))
print('priced rolls window:',Counter(win.values()), ' priced with count<3:',sum(1 for k in cnt if cnt[k]<3))
# hold-one-out nearest worse neighbour
err=[]
for k in priced:
    best=None
    for y in priced:
        if y==k or band(y)!=band(k) or pos(y)>=pos(k): continue
        if best is None or pos(y)>pos(best): best=y
    if best: err.append(priced[k]-priced[best])
print('hold-one-out nearest-worse-neighbour on %d priced knife rolls: mean(actual-nbr) %+.4f median %+.4f; nbr<=actual %d/%d'%(len(err),S.mean(err),S.median(err),sum(1 for e in err if e>=0),len(err)))
# exclude attack 40 (top roll premium)
err2=[(priced[k]-priced[y]) for k in priced for y in [max((y for y in priced if band(y)==band(k) and pos(y)<pos(k)),key=pos,default=None)] if y and pos(k)<40]
print(' same excluding attack-40 targets: n=%d mean %+.4f'%(len(err2),S.mean(err2)))
# per-roll priced table by band
for b in '12345':
    print(' crit',b,' '.join('%d:%.3f(n%d)'%(pos(k),priced[k],cnt[k]) for k in space if band(k)==b and k in priced))
# two-sided linear interpolation within band (bounded by band ends -> nearest)
vals=[];filled=0
for k in space:
    if k in priced: vals.append(priced[k]*tax if priced[k]*tax>need else dis); continue
    lo=max((y for y in priced if band(y)==band(k) and pos(y)<pos(k)),key=pos,default=None)
    hi=min((y for y in priced if band(y)==band(k) and pos(y)>pos(k)),key=pos,default=None)
    if lo and hi: pr=priced[lo]+(priced[hi]-priced[lo])*(pos(k)-pos(lo))/(pos(hi)-pos(lo))
    elif lo: pr=priced[lo]
    elif hi: pr=priced[hi]
    else: continue
    filled+=1; vals.append(pr*tax if pr*tax>need else dis)
w=E.CASE_TIER_ODDS[0]*E.CRAFT_SLOT_WEIGHT['weapon']; vp=M.slot_value('weapon',1)['net']
vi=S.mean(vals); gi=g0+w*(vi-vp)
print('two-sided interpolation from priced rolls only: knife %.4f over %d (filled %d) -> case %.4f pct %+.2f%%'%(vi,len(vals),filled,gi,(gi-cost)/cost*100))
# interpolation using all 68 rolls with any price (selected else retained)
anyp={k:priced[k] for k in priced}
for k in space:
    r=seen.get(k); rw=r and r.get('retained_window')
    if k not in anyp and rw and rw.get('median') is not None: anyp[k]=rw['median']
vals=[]
for k in space:
    if k in anyp: pr=anyp[k]
    else:
        lo=max((y for y in anyp if band(y)==band(k) and pos(y)<pos(k)),key=pos,default=None)
        hi=min((y for y in anyp if band(y)==band(k) and pos(y)>pos(k)),key=pos,default=None)
        if lo and hi: pr=anyp[lo]+(anyp[hi]-anyp[lo])*(pos(k)-pos(lo))/(pos(hi)-pos(lo))
        elif lo: pr=anyp[lo]
        elif hi: pr=anyp[hi]
        else: continue
    vals.append(pr*tax if pr*tax>need else dis)
vi=S.mean(vals); gi=g0+w*(vi-vp)
print('two-sided interpolation from priced+retained: knife %.4f over %d -> case %.4f pct %+.2f%%'%(vi,len(vals),gi,(gi-cost)/cost*100))
# what the page prints: rounding
print('page pct display: baseline %+.1f%%, fill %+.1f%%; edge %.3f -> %.3f'%(c0['pct'],(g0+w*(1.8306-vp)-cost)/cost*100,c0['edge'],g0+w*(1.8306-vp)-cost))
# craft tier-1 row effect
print('craft_expected t1 baseline', M.craft_expected(1))
