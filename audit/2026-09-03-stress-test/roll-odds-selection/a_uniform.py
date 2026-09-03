"""(a) Are draws uniform within a band?  Per-item counts per roll, chi-square dispersion vs
uniform, split by whether the Sort tab says every roll sells; excess at band maximum; and
the same after removing flip resales (seller was an earlier buyer of same item+roll)."""
import json, math, statistics, collections, sys
from load import load, TIERS
import ev_ref
p,now,rows=load()
bad=[r for r in rows if r['ri']<0]; print('rolls outside space:',[(r['code'],r['roll']) for r in bad])
m=ev_ref.Model(p,tax=1.0,bar_abs=0.10)
def chi(counts):
    n=sum(counts);k=len(counts);e=n/k
    c2=sum((o-e)**2/e for o in counts)
    return c2,c2/(k-1),n,k
# survival function of chi2 via Wilson-Hilferty normal approx
def chi2_sf(x,df):
    z=((x/df)**(1/3)-(1-2/(9*df)))/math.sqrt(2/(9*df))
    return 0.5*math.erfc(z/math.sqrt(2))
def flips(rs):
    """mark sale as flip-resale if its seller bought the same item+roll earlier (first-come pairing)."""
    rs=sorted(rs,key=lambda r:r['sold'])
    open_buys=collections.defaultdict(list) # (code,roll,player)->[sold times of purchases]
    flip=set()
    for r in rs:
        key=(r['code'],r['roll'],r['seller'])
        if open_buys[key]:
            open_buys[key].pop(0); flip.add(r['id'])
        open_buys[(r['code'],r['roll'],r['buyer'])].append(r['sold'])
    return flip
comp=[r for r in rows if r['elig'] and not r['stale'] and r['ri']>=0]
flip=flips(comp)
print('comps sales',len(comp),'flip resales',len(flip))
out={}
print('\n%-8s %5s %5s %7s %8s %7s  %-10s %s'%('item','n','k','chi2/df','p','max/mean','allsell?','top-3 rolls by count'))
for code,cat in p['categories'].items():
    slot=cat['slot'];t=TIERS.index(cat['tier'])+1
    space=ev_ref.roll_space(slot,t)
    cnt=[0]*len(space); cntnf=[0]*len(space)
    for r in comp:
        if r['code']!=code:continue
        cnt[r['ri']]+=1
        if r['id'] not in flip: cntnf[r['ri']]+=1
    sv=m.slot_value(slot,t)
    allsell=sv is not None and sv['covered']==len(space) and all(x[3] for x in sv['rows'])
    nsell=sum(x[3] for x in sv['rows']) if sv else 0
    c2,disp,n,k=chi(cnt); pv=chi2_sf(c2,k-1) if n else None
    c2n,dispn,nn,_=chi(cntnf)
    if slot=='weapon':
        (a0,a1),(c0,c1)=ev_ref.WEAPON_STATS[t-1]
        na=a1-a0+1;nc=c1-c0+1
        att=[0]*na;crit=[0]*nc;attnf=[0]*na;critnf=[0]*nc
        for i,c in enumerate(cnt):
            att[i//nc]+=c;crit[i%nc]+=c
        for i,c in enumerate(cntnf):
            attnf[i//nc]+=c;critnf[i%nc]+=c
        def ex(v): return v[-1]/ (statistics.mean(v[:-1]) if len(v)>1 and statistics.mean(v[:-1])>0 else float('nan'))
        # independence chi2 on attack x crit table
        tab=[[cnt[i*nc+j] for j in range(nc)] for i in range(na)]
        rs_=[sum(x) for x in tab];cs_=[sum(tab[i][j] for i in range(na)) for j in range(nc)]
        ind=sum((tab[i][j]-rs_[i]*cs_[j]/n)**2/(rs_[i]*cs_[j]/n) for i in range(na) for j in range(nc) if rs_[i] and cs_[j])
        dfi=(na-1)*(nc-1)
        info={'attack':att,'crit':crit,'attack_noflip':attnf,'crit_noflip':critnf,
              'att_max_excess':ex(att),'crit_max_excess':ex(crit),'att_max_excess_noflip':ex(attnf),'crit_max_excess_noflip':ex(critnf),
              'att_chi2_df':chi(att)[1],'crit_chi2_df':chi(crit)[1],'att_chi2_df_noflip':chi(attnf)[1],'crit_chi2_df_noflip':chi(critnf)[1],
              'indep_chi2_df':ind/dfi,'indep_p':chi2_sf(ind,dfi)}
        mx=ex(att)
        top=sorted(zip(space,cnt),key=lambda x:-x[1])[:3]
        print('%-8s %5d %5d %7.2f %8.2g %7.2f  %-10s %s | attack marg %s | crit marg %s | noflip att-max %.2f crit-max %.2f | indep chi2/df %.2f'%(code,n,k,disp,pv,mx,'ALL' if allsell else '%d/%d'%(nsell,sv['covered'] if sv else 0),top,att,crit,ex(attnf),ex(critnf),ind/dfi))
    else:
        mx=cnt[-1]/statistics.mean(cnt[:-1]) if statistics.mean(cnt[:-1])>0 else float('nan')
        mxnf=cntnf[-1]/statistics.mean(cntnf[:-1]) if statistics.mean(cntnf[:-1])>0 else float('nan')
        info={'max_excess':mx,'max_excess_noflip':mxnf,'chi2_df_noflip':dispn}
        print('%-8s %5d %5d %7.2f %8.2g %7.2f  %-10s counts %s | noflip %s max-excess %.2f'%(code,n,k,disp,pv,mx,'ALL' if allsell else '%d/%d'%(nsell,sv['covered'] if sv else 0),cnt,cntnf,mxnf))
    out[code]={'n':n,'k':k,'chi2':c2,'chi2_df':disp,'p':pv,'allsell':allsell,'nsell':nsell,'covered':sv['covered'] if sv else 0,'counts':cnt,'counts_noflip':cntnf,**info}
json.dump(out,open('a_uniform.json','w'),indent=1)
# summary: dispersion for all-sell vs not
a=[v['chi2_df'] for v in out.values() if v['allsell']];b=[v['chi2_df'] for v in out.values() if not v['allsell']]
print('\nchi2/df median: all-sell items %.2f (n=%d)  rest %.2f (n=%d)'%(statistics.median(a),len(a),statistics.median(b),len(b)))
