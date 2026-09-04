"""Independent re-derivation of ET-6. Reads public/prices/*.json shards directly
(rows [unit_price, sold_at_epoch_s, tts_s|null, roll_index]); drops stale (tts>48h).
Rolling origins every STEP h from first+48h to now-HOR h; score each (roll,T) with >=1 sale in (T,T+HOR].
Usage: python3 refute_et6.py [STEP_H=6] [HOR_H=24]"""
import json, glob, os, sys, statistics, bisect, random, datetime
random.seed(7)
STEP=int(sys.argv[1]) if len(sys.argv)>1 else 6
HOR=int(sys.argv[2]) if len(sys.argv)>2 else 24
H=3600
PUB='/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/public'
idx=json.load(open(PUB+'/index.json'))
NOW=int(datetime.datetime.fromisoformat(idx['generated_at'].replace('Z','+00:00')).timestamp())
rolls={}; tier={}
for f in sorted(glob.glob(PUB+'/prices/*.json')):
    d=json.load(open(f)); tier[d['item_code']]=d['tier']
    for p,t,tts,ri in d['sales']:
        if tts is not None and tts>48*H: continue
        rolls.setdefault((d['item_code'],ri),[]).append((t,p))
for k in rolls: rolls[k].sort()
first=min(v[0][0] for v in rolls.values())
origins=list(range(first+48*H, NOW-HOR*H+1, STEP*H))
print('NOW',NOW,'first',first,'span_h %.1f'%((NOW-first)/H),'origins',len(origins),'step',STEP,'hor',HOR)
med=statistics.median
def loss(e,fut):
    rel=[(e-p)/p for p in fut]
    return (statistics.mean(abs(r) for r in rel), statistics.mean(rel), sum(1 for p in fut if p>=e)/len(fut))
recs=[]; quiet_all=0; n1_all=0
for key,v in rolls.items():
    ts=[t for t,_ in v]
    for T in origins:
        i=bisect.bisect_right(ts,T); j=bisect.bisect_right(ts,T+HOR*H)
        p48=[p for t,p in v[:i] if t>T-48*H]; p7=[p for t,p in v[:i] if t>T-168*H]
        if not p7: continue
        if not p48: quiet_all+=1
        if len(p48)==1: n1_all+=1
        fut=[p for _,p in v[i:j]]
        if not fut: continue
        r={'key':key,'T':T,'n48':len(p48),'n7':len(p7),'nfut':len(fut),'tier':tier[key[0]],
           'ages':[(T-t)/H for t,_ in v[:i] if t>T-168*H]}
        r['ret7']=loss(med(p7),fut); r['ret7v']=med(p7)
        if p48: r['med48']=loss(med(p48),fut); r['med48v']=med(p48)
        recs.append(r)
def cboot(pairs,B=1000):
    by={}
    for k,d in pairs: by.setdefault(k,[]).append(d)
    keys=list(by); out=[]
    for _ in range(B):
        flat=[d for k in (random.choice(keys) for _ in keys) for d in by[k]]
        out.append(statistics.mean(flat))
    out.sort(); return out[int(.025*B)], out[int(.975*B)]
def summ(name,L):
    ae=sorted(l[0] for l in L)
    return '%-28s n=%5d relMAE %.2f%% medAE %.2f%% p90AE %.2f%% bias %+.2f%% sold %.1f%%'%(name,len(L),100*statistics.mean(ae),100*med(ae),100*ae[int(.9*len(ae))],100*statistics.mean(l[1] for l in L),100*statistics.mean(l[2] for l in L))
pop=[r for r in recs if r['n48']>=1]
print('roll-origins scored: n48>=1:',len(pop),' quiet:',len(recs)-len(pop),' rolls:',len(set(r['key'] for r in recs)))
print('share of quiet (roll,T) with a sale in next %dh: %d/%d = %.1f%%'%(HOR,len(recs)-len(pop),quiet_all,100*(len(recs)-len(pop))/quiet_all))
print('share of n48==1 (roll,T) with a sale in next %dh: %d/%d = %.1f%%'%(HOR,sum(1 for r in pop if r['n48']==1),n1_all,100*sum(1 for r in pop if r['n48']==1)/n1_all))
# (e) thin
thin=[r for r in pop if r['n48']<=4]
print('\n(e) thin n48 1..4: roll-origins %d rolls %d fut sales %d'%(len(thin),len(set(r['key'] for r in thin)),sum(r['nfut'] for r in thin)))
print(summ('med48',[r['med48'] for r in thin])); print(summ('ret7',[r['ret7'] for r in thin]))
d=[(r['key'],r['ret7'][0]-r['med48'][0]) for r in thin]
print('  dRelMAE ret7-med48 %+.2f CI [%+.2f,%+.2f]'%((100*statistics.mean(x for _,x in d),)+tuple(100*c for c in cboot(d))))
same=[r for r in thin if r['ret7v']==r['med48v']]; diff=[r for r in thin if r['ret7v']!=r['med48v']]
print('  thin roll-origins where ret7==med48 (identical estimate): %d of %d (%.0f%%)'%(len(same),len(thin),100*len(same)/len(thin)))
d=[(r['key'],r['ret7'][0]-r['med48'][0]) for r in diff]
print('  among the %d where they DIFFER: med48 relMAE %.2f%% ret7 %.2f%% d %+.2f CI [%+.2f,%+.2f]'%((len(diff),100*statistics.mean(r['med48'][0] for r in diff),100*statistics.mean(r['ret7'][0] for r in diff),100*statistics.mean(x for _,x in d))+tuple(100*c for c in cboot(d))))
for n in (1,2,3,4):
    s=[r for r in thin if r['n48']==n]; d=[(r['key'],r['ret7'][0]-r['med48'][0]) for r in s]
    print('  n48=%d n=%d med48 %.2f ret7 %.2f d %+.2f [%+.2f,%+.2f]'%((n,len(s),100*statistics.mean(r['med48'][0] for r in s),100*statistics.mean(r['ret7'][0] for r in s),100*statistics.mean(x for _,x in d))+tuple(100*c for c in cboot(d))))
s=[r for r in thin if r['n7']>=r['n48']+3]; d=[(r['key'],r['ret7'][0]-r['med48'][0]) for r in s]
print('  n7>=n48+3: n=%d med48 %.2f ret7 %.2f d %+.2f [%+.2f,%+.2f]'%((len(s),100*statistics.mean(r['med48'][0] for r in s),100*statistics.mean(r['ret7'][0] for r in s),100*statistics.mean(x for _,x in d))+tuple(100*c for c in cboot(d))))
print('\npolicy over all n48>=1 roll-origins (relMAE%):')
for lab,fn in [('med48 always',lambda r:r['med48']),('ret7 if n48<5 else med48',lambda r:r['ret7'] if r['n48']<5 else r['med48']),('ret7 if n48<3 else med48',lambda r:r['ret7'] if r['n48']<3 else r['med48']),('ret7 always',lambda r:r['ret7'])]:
    print('  '+summ(lab,[fn(r) for r in pop]))
# quiet vs n48==1
quiet=[r for r in recs if r['n48']==0]; n1=[r for r in pop if r['n48']==1]
print('\n(quiet) '+summ('quiet ret7',[r['ret7'] for r in quiet]))
print('(n48=1) '+summ('n48=1 med48',[r['med48'] for r in n1]))
print('(n48=2) '+summ('n48=2 med48',[r['med48'] for r in pop if r['n48']==2]))
# unpaired cluster bootstrap of relMAE difference quiet - n48=1
def cb_unpaired(A,Bs,B=1000):
    byA={};byB={}
    for r in A: byA.setdefault(r['key'],[]).append(r['ret7'][0])
    for r in Bs: byB.setdefault(r['key'],[]).append(r['med48'][0])
    ka=list(byA);kb=list(byB);out=[]
    for _ in range(B):
        a=[x for k in (random.choice(ka) for _ in ka) for x in byA[k]]; b=[x for k in (random.choice(kb) for _ in kb) for x in byB[k]]
        out.append(statistics.mean(a)-statistics.mean(b))
    out.sort(); return out[int(.025*B)],out[int(.975*B)]
print('  quiet relMAE - n48=1 relMAE: %+.2f CI [%+.2f,%+.2f]'%((100*(statistics.mean(r['ret7'][0] for r in quiet)-statistics.mean(r['med48'][0] for r in n1)),)+tuple(100*c for c in cb_unpaired(quiet,n1))))
qa=[a for r in quiet for a in r['ages']]; print('  quiet: retained sales per origin median %d; age of retained sales (h): median %.0f p10 %.0f p90 %.0f; n7 dist: '%(med(r['n7'] for r in quiet),med(qa),sorted(qa)[int(.1*len(qa))],sorted(qa)[int(.9*len(qa))]), sorted(statistics.Counter if False else [r['n7'] for r in quiet])[:0], {k:sum(1 for r in quiet if min(r['n7'],5)==k) for k in range(1,6)})
for t in ['basic','reinforced','advanced','elite','legendary','mythic']:
    q=[r for r in quiet if r['tier']==t]; o=[r for r in n1 if r['tier']==t]
    if q: print('  tier %-10s quiet n=%3d relMAE %.2f%% medAE %.2f%% | n48=1 n=%3d relMAE %.2f%%'%(t,len(q),100*statistics.mean(r['ret7'][0] for r in q),100*med(r['ret7'][0] for r in q),len(o),100*statistics.mean(r['med48'][0] for r in o) if o else float('nan')))
# thick vs thin
for lo,hi in [(2,7),(30,10**9)]:
    s=[r for r in pop if lo<=r['n48']<=hi]; print('  n48 %d-%s: '%(lo,hi if hi<10**9 else 'inf')+summ('med48',[r['med48'] for r in s]))
