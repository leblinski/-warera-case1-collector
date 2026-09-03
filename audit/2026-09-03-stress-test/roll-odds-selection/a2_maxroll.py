"""(a) cont.: is the Epic max-roll excess demand-side selection (max rolls sell faster / fewer
stale) or RNG?  Per-attack tts, stale share, price, and the 130/20 cell vs independence.
Also: stale share per item, knife counts on all transactions (README basis), and the README's
15,354 'seller was ever an earlier buyer' flip definition reconciled with one-to-one pairing."""
import json, statistics, collections, math
from load import load, TIERS
import ev_ref
p,now,rows=load()
def med(v): return statistics.median(v) if v else None
out={}
for code,t,(a0,a1),(c0,c1) in [('sniper',4,(101,130),(16,20)),('tank',5,(141,170),(26,35)),('gun',2,(51,60),(6,10)),('rifle',3,(71,90),(11,15)),('knife',1,(21,40),(1,5))]:
    rs=[r for r in rows if r['code']==code and r['ri']>=0]
    print('\n%s: attack -> n(all) n(nonstale) stale%% median tts(min) median price(nonstale) | last 4 vs rest'%code)
    byA=collections.defaultdict(list)
    for r in rs: byA[int(r['roll'].split('/')[0])].append(r)
    tab=[]
    for a in range(a0,a1+1):
        v=byA[a];ns=[r for r in v if not r['stale']]
        tab.append((a,len(v),len(ns),100*sum(r['stale'] for r in v)/len(v) if v else 0,med([r['tts'] for r in ns if r['tts'] is not None]) or 0,med([r['price'] for r in ns]) or 0))
    for a,n,nn,st,tt,pr in tab[-4:]: print('  %d: %d %d %.1f%% %.1f %.3f'%(a,n,nn,st,tt/60,pr))
    rest=tab[:-1]
    print('  rest mean n %.1f nonstale %.1f stale %.1f%% ; median of per-attack tts %.1f min'%(statistics.mean(x[1] for x in rest),statistics.mean(x[2] for x in rest),statistics.mean(x[3] for x in rest),statistics.median(x[4] for x in rest)/60))
    mx=tab[-1];out[code]={'max':mx,'rest_mean_n':statistics.mean(x[1] for x in rest),'rest_mean_nonstale':statistics.mean(x[2] for x in rest),'rest_stale_pct':statistics.mean(x[3] for x in rest),'rest_med_tts_min':statistics.median(x[4] for x in rest)/60,
      'excess_all':mx[1]/statistics.mean(x[1] for x in rest),'sigma_all':(mx[1]-statistics.mean(x[1] for x in rest))/math.sqrt(statistics.mean(x[1] for x in rest))}
    print('  max excess (all tx) %.3f = %.1f sigma; (nonstale) %.3f'%(out[code]['excess_all'],out[code]['sigma_all'],mx[2]/statistics.mean(x[2] for x in rest)))
    # crit max
    byC=collections.defaultdict(int)
    for r in rs: byC[int(r['roll'].split('/')[1])]+=1
    cs=[byC[c] for c in range(c0,c1+1)];print('  crit counts',cs,'max excess %.3f (%.1f sigma)'%(cs[-1]/statistics.mean(cs[:-1]),(cs[-1]-statistics.mean(cs[:-1]))/math.sqrt(statistics.mean(cs[:-1]))))
    out[code]['crit_counts']=cs
    # both-max cell vs independence
    both=sum(1 for r in rs if r['roll']=='%d/%d'%(a1,c1));ea=sum(x[1] for x in tab);exp=tab[-1][1]*cs[-1]/len(rs)
    print('  cell %d/%d: %d observed vs %.1f expected from marginals (uniform: %.1f)'%(a1,c1,both,exp,len(rs)/((a1-a0+1)*(c1-c0+1))))
    out[code]['both_max']={'obs':both,'exp_marg':exp,'exp_uniform':len(rs)/((a1-a0+1)*(c1-c0+1))}
    # low end
    print('  low end attack %d: n %d vs rest mean %.1f'%(a0,tab[0][1],statistics.mean(x[1] for x in tab[1:-1])))
# stale share per item
print('\nstale (tts>48h) share per item:')
st={}
for code in p['categories']:
    rs=[r for r in rows if r['code']==code];s=sum(r['stale'] for r in rs);st[code]=(len(rs),s,100*s/len(rs))
for code,(n,s,pc) in sorted(st.items(),key=lambda x:-x[1][2])[:10]: print('  %-8s %6d stale %5d (%.1f%%)'%(code,n,s,pc))
out['stale']=st
kn=[r for r in rows if r['code']=='knife']
print('knife all tx %d, attack 40: %d; nonstale %d, attack 40: %d; stale knife sales median price %.3f vs nonstale %.3f'%(len(kn),sum(r['roll'].startswith('40/') for r in kn),sum(not r['stale'] for r in kn),sum(r['roll'].startswith('40/') and not r['stale'] for r in kn),med([r['price'] for r in kn if r['stale']]),med([r['price'] for r in kn if not r['stale']])))
# README flip definition: seller was EVER an earlier buyer of same item+roll
by=sorted(rows,key=lambda r:r['sold']);seenbuy=set();ever=0;ever_w=0
for r in by:
    if (r['code'],r['roll'],r['seller']) in seenbuy:
        ever+=1
        if r['code'] in ('knife','gun','rifle','sniper','tank','jet'):ever_w+=1
    seenbuy.add((r['code'],r['roll'],r['buyer']))
print('README-style "seller was ever an earlier buyer": %d of %d (%.1f%%); weapons only %d'%(ever,len(rows),100*ever/len(rows),ever_w))
out['ever_flip']=ever
json.dump(out,open('a2_maxroll.json','w'),indent=1)
