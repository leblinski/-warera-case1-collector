"""Independent check of ROS-7 using collector.py's own functions (unpack_transaction, aggregate, stale_listing)."""
import sys, json, statistics, collections
sys.path.insert(0,'/home/user/-warera-case1-collector'); sys.path.insert(0,'/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit')
import collector as c, ev_ref
p=json.load(open('/home/user/-warera-case1-collector/data/warera_case1_market.json')); now=c.parse_time(p['generated_at'])
TIERS=['basic','reinforced','advanced','elite','legendary','mythic']
txs={code:[c.unpack_transaction(r,code) for r in cat['transactions']] for code,cat in p['categories'].items()}
tot=sum(len(v) for v in txs.values()); print('transactions',tot)
# 1. stale share per item (all rows, and eligible-only)
res={}
for code,v in txs.items():
    n=len(v); s=sum(c.stale_listing(t) for t in v); e=[t for t in v if t['eligible_for_comps']]; se=sum(c.stale_listing(t) for t in e)
    res[code]=(n,s,round(100*s/n,1),len(e),se,round(100*se/len(e),1) if e else None)
for code,r in sorted(res.items(),key=lambda x:-x[1][2])[:6]: print('stale %-8s all %d/%d=%.1f%%  eligible %d/%d=%.1f%%'%(code,r[1],r[0],r[2],r[4],r[3],r[5]))
# 2. knife per-attack
kn=txs['knife']; byA=collections.defaultdict(list)
for t in kn:
    if t['eligible_for_comps']: byA[int(ev_ref.roll_key('weapon',t['skills']).split('/')[0])].append(t)
lo=[t for a,v in byA.items() if a<40 for t in v]; a40=byA[40]
print('knife eligible sub-40: n %d stale %d (%.1f%%); attack 40: n %d stale %d (%.1f%%)'%(len(lo),sum(map(c.stale_listing,lo)),100*sum(map(c.stale_listing,lo))/len(lo),len(a40),sum(map(c.stale_listing,a40)),100*sum(map(c.stale_listing,a40))/len(a40)))
ns_lo=[t['time_to_sell_seconds'] for t in lo if not c.stale_listing(t) and t['time_to_sell_seconds'] is not None]
print('knife sub-40 nonstale median tts %.1f h'%(statistics.median(ns_lo)/3600))
ke=[t for t in kn if t['eligible_for_comps']]
print('knife eligible: stale median price %.3f (n=%d) vs nonstale %.3f (n=%d)'%(statistics.median([t['unit_price'] for t in ke if c.stale_listing(t)]),sum(map(c.stale_listing,ke)),statistics.median([t['unit_price'] for t in ke if not c.stale_listing(t)]),sum(not c.stale_listing(t) for t in ke)))
# 3. coverage now vs counterfactual (stale counted in retained window)
def cover(code,patch):
    orig=c.stale_listing
    if patch: c.stale_listing=lambda tx,max_hours=48: False
    try: rolls=c.aggregate(txs[code],now)
    finally: c.stale_listing=orig
    return rolls
out={}
for code,slot,t in [('knife','weapon',1),('helmet1','helmet',1),('jet','weapon',6),('tank','weapon',5),('helmet6','helmet',6)]:
    space=ev_ref.roll_space(slot,t)
    base=cover(code,False); cf=cover(code,True)
    pk=lambda d:{ev_ref.roll_key(slot,v['exact_roll']['skills']):v for v in d.values()}
    base=pk(base); cf=pk(cf)
    b=set(k for k in base if base[k]['retained_window']['count']>0); f=set(k for k in cf if cf[k]['retained_window']['count']>0)
    priced=set(k for k in base if base[k]['selected']['median'] is not None)
    # counterfactual with the finding's proposal: stale counted only in retained (not 24/48h comps) -> selected unchanged, retained grows
    print('%s: space %d, retained-covered now %d, with stale counted %d (+%d), selected.median now %d; new rolls: %s'%(code,len(space),len(b),len(f),len(f-b),len(priced),sorted(f-b)[:40]))
    out[code]={'space':len(space),'now':len(b),'cf':len(f),'new':sorted(f-b)}
    if code=='knife':
        dis=6*0.225; taxmul=0.99
        # for each newly-visible roll: stale-only median -> fillQuiet 'wide' verdict; versus current neighbour-fill verdict
        def verdict_now(k):
            a,cr=map(int,k.split('/')); best=None
            for j in base:
                ja,jc=map(int,j.split('/'))
                if jc!=cr or ja>=a: continue
                if best is None or ja>int(best.split('/')[0]): best=j
            if best is None: return None
            r=base[best]; st=r['selected'] if r['selected']['median'] is not None else None
            m=st['median'] if st else r['retained_window']['median']
            return m*taxmul>dis
        flips=0; rows=[]
        for k in sorted(f-b):
            m=cf[k]['retained_window']['median']; vw=m*taxmul>dis; vn=verdict_now(k)
            rows.append((k,cf[k]['retained_window']['count'],m,vw,vn)); flips+=(vn is not None and vw!=vn)
        print(' knife new rolls: verdict via stale median vs current neighbour-fill; differing:',flips)
        for r in rows: print('  ',r)
        out['knife_verdict_flips']=flips
        # does counting stale change retained median/tts of existing knife rolls (page uses wide only when selected empty)
        quiet=[k for k in b if base[k]['selected']['median'] is None]
        ch=[(k,base[k]['retained_window']['median'],cf[k]['retained_window']['median']) for k in quiet if base[k]['retained_window']['median']!=cf[k]['retained_window']['median']]
        vflip=sum((a*taxmul>dis)!=(b_*taxmul>dis) for k,a,b_ in ch)
        print(' knife quiet rolls %d; retained median changes if stale counted: %d; verdict flips: %d'%(len(quiet),len(ch),vflip))
        out['knife_quiet_median_changes']=len(ch); out['knife_quiet_verdict_flips']=vflip
json.dump(out,open('/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit/refute-ros7/check.json','w'),indent=1)
