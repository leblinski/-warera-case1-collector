"""Independent re-check of EV-3: knife slot value renormalised vs filled; confound test
(are unpriced rolls cheaper, or are 7-day medians just older/lower?)."""
import json, sys, os, statistics as S
from datetime import datetime, timezone
AUDIT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0,AUDIT)
import ev_ref as E
p=json.load(open('/home/user/-warera-case1-collector/data/warera_case1_market.json'))
M=E.Model(p,tax=1,bar_abs=0.10); c0=M.case(1); g0=c0['gross']; cost=c0['cost']['unit']
print('baseline gross %.4f pct %+.2f%% cost %.4f'%(g0,c0['pct'],cost))
tax=0.99; t=1; dis=M.dismantle(1); need=M.need(1); print('knife dis %.4f need %.4f'%(dis,need))
cat=p['categories']['knife']; seen={}
for row in cat['rolls'].values(): seen[E.roll_key('weapon',row['exact_roll']['skills'])]=row
space=E.roll_space('weapon',1)
pos=lambda k:int(k.split('/')[0]); band=lambda k:k.split('/')[1]
priced={};wide={}
for k in space:
    r=seen.get(k)
    if not r: continue
    st=r['selected'] or r['fallback_48h']
    if st and st.get('median') is not None: priced[k]=st['median']
    rw=r.get('retained_window') or {}
    if rw.get('median') is not None: wide[k]=(rw['median'],rw['count'])
unp=[k for k in space if k not in priced]
print('priced %d unpriced %d; wide-available on unpriced %d'%(len(priced),len(unp),sum(1 for k in unp if k in wide)))
sells={k:priced[k]*tax>need for k in priced}
print('priced sell %d break %d; mean price %.4f; page slot value %.4f (ev_ref %.4f)'%(sum(sells.values()),len(priced)-sum(sells.values()),
   S.mean(priced.values()), S.mean(priced[k]*tax if sells[k] else dis for k in priced), M.slot_value('weapon',1)['net']))
# fill exactly per finding: wide -> retained median; else nearest worse neighbour same band, neighbour's price
fillp={};src={}
for k in unp:
    if k in wide: fillp[k]=wide[k][0]; src[k]='wide'; continue
    best=None
    for y in space:
        if y not in priced and y not in wide: continue
        if band(y)!=band(k) or pos(y)>=pos(k): continue
        if best is None or pos(y)>pos(best): best=y
    if best is None: src[k]='none'; continue
    fillp[k]=priced[best] if best in priced else wide[best][0]; src[k]='nbr'
from collections import Counter
print('fill sources',Counter(src.values()))
wideonly=[k for k in unp if src[k]=='wide']
print('wide-filled mean retained median %.4f (n=%d)'%(S.mean(fillp[k] for k in wideonly),len(wideonly)))
nbr=[k for k in unp if src[k]=='nbr']
print('nbr-filled mean price %.4f (n=%d)'%(S.mean(fillp[k] for k in nbr),len(nbr)))
vals=[priced[k]*tax if sells[k] else dis for k in priced]+[max(fillp[k]*tax,dis) if fillp[k]*tax>need else dis for k in fillp]
vf=S.mean(vals); print('fill slot value %.4f over %d; verdicts sell %d'%(vf,len(vals),sum(1 for k in fillp if fillp[k]*tax>need)))
w=E.CASE_TIER_ODDS[0]*E.CRAFT_SLOT_WEIGHT['weapon']; vp=M.slot_value('weapon',1)['net']
gf=g0+w*(vf-vp); print('case gross fill %.4f (%+.4f) pct %+.2f%%'%(gf,gf-g0,(gf-cost)/cost*100))
vd=S.mean([priced[k]*tax if sells[k] else dis for k in priced]+[dis]*len(unp)); gd=g0+w*(vd-vp)
print('case gross scrap-for-unpriced %.4f pct %+.2f%%'%(gd,(gd-cost)/cost*100))
# ---- CONFOUND: apples to apples. retained (7d) median of the PRICED rolls vs of the unpriced ones
rp=[wide[k][0] for k in priced if k in wide]
print('\nCONFOUND: 7d retained median, priced rolls: mean %.4f median %.4f (n=%d)  | unpriced rolls: mean %.4f (n=%d)'%(S.mean(rp),S.median(rp),len(rp),S.mean(fillp[k] for k in wideonly),len(wideonly)))
print(' priced rolls: selected median mean %.4f vs their own retained median mean %.4f -> drift %.4f'%(S.mean(priced.values()),S.mean(rp),S.mean(priced.values())-S.mean(rp)))
# retained-count weighting: how many sales back the 22 wide-filled rolls
print(' wide-filled rolls retained counts:',sorted(wide[k][1] for k in wideonly))
# consistent estimator: retained median for everyone who has one
allw=[k for k in space if k in wide]
vr=S.mean(max(wide[k][0]*tax,dis) if wide[k][0]*tax>need else dis for k in allw)
gr=g0+w*(vr-vp); print(' knife value using retained median for all %d rolls with one: %.4f -> case %.4f pct %+.2f%%'%(len(allw),vr,gr,(gr-cost)/cost*100))
# ---- knife price by UTC day from raw transactions (full condition, qty1)
tx=cat['transactions']; byday={}
for x in tx:
    if x.get('state')!=x.get('max_state') or x.get('quantity')!=1: continue
    d=x['sold_at'][:10]; byday.setdefault(d,[]).append(x['money'])
print('\nknife median sale price by UTC day (all rolls):')
for d in sorted(byday): print('  %s n=%4d median %.4f mean %.4f'%(d,len(byday[d]),S.median(byday[d]),S.mean(byday[d])))
# within-day: median by day for crit band 1 vs 5 only among rolls priced today
# ---- alternative: median price by crit band in last 48h, to see whether crit band matters
gen=datetime.fromisoformat(p['generated_at'].replace('Z','+00:00'))
rec=[x for x in tx if x.get('state')==x.get('max_state') and (gen-datetime.fromisoformat(x['sold_at'].replace('Z','+00:00'))).total_seconds()<=48*3600]
bb={}
for x in rec: bb.setdefault(x['skills']['criticalChance'],[]).append(x['money'])
print('\n48h sales by crit band: '+'  '.join('c%d n=%d med %.3f'%(c,len(v),S.median(v)) for c,v in sorted(bb.items())))
ba={}
for x in rec: ba.setdefault(x['skills']['attack']//5*5,[]).append(x['money'])
print('48h sales by attack bucket: '+'  '.join('a%d n=%d med %.3f'%(a,len(v),S.median(v)) for a,v in sorted(ba.items())))
# 7d version for unpriced rolls vs priced rolls, restricted to sales in the 48h window: none by definition. Use 7d for both:
allx=[x for x in tx if x.get('state')==x.get('max_state')]
up7=[x['money'] for x in allx if '%d/%d'%(x['skills']['attack'],x['skills']['criticalChance']) in set(unp)]
pr7=[x['money'] for x in allx if '%d/%d'%(x['skills']['attack'],x['skills']['criticalChance']) in priced]
print('\n7d sales: on unpriced rolls n=%d median %.4f mean %.4f | on priced rolls n=%d median %.4f mean %.4f'%(len(up7),S.median(up7),S.mean(up7),len(pr7),S.median(pr7),S.mean(pr7)))
# same but only sales older than 48h (so both populations on equal footing)
old=[x for x in allx if (gen-datetime.fromisoformat(x['sold_at'].replace('Z','+00:00'))).total_seconds()>48*3600]
upo=[x['money'] for x in old if '%d/%d'%(x['skills']['attack'],x['skills']['criticalChance']) in set(unp)]
pro=[x['money'] for x in old if '%d/%d'%(x['skills']['attack'],x['skills']['criticalChance']) in priced]
print('sales OLDER than 48h: unpriced rolls n=%d median %.4f mean %.4f | priced rolls n=%d median %.4f mean %.4f'%(len(upo),S.median(upo),S.mean(upo),len(pro),S.median(pro),S.mean(pro)))
