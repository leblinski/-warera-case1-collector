"""(c) forward test: rebuild the collector's roll stats as of T0 from the raw retained sales
(collector.aggregate, identical code), apply the page's verdicts at T0, and score them against
the median of the roll's own sales in (T0, T0+24h]."""
import sys, collections, statistics
from datetime import timedelta
sys.path.insert(0,'/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit/neighbour-fill')
sys.path.insert(0,'/home/user/-warera-case1-collector')
import collector as C
from nf_common import *
snap=load(); bid=snap['commodities']['scraps']['order_book']['best_bid']
gen=C.parse_time(snap['generated_at'])
MIN_FWD=int(sys.argv[1]) if len(sys.argv)>1 else 1   # min next-24h eligible sales to count as truth
print('generated_at',snap['generated_at'],'scrap bid (current, used for every T0)',bid,'MIN_FWD',MIN_FWD)
rows_by={code:[C.unpack_transaction(r,code) for r in cat['transactions']] for code,cat in snap['categories'].items()}

class Acc:
    def __init__(s): s.n=0;s.ok=0;s.cm=collections.Counter()
    def add(s,truth,pred):
        s.n+=1;s.ok+=(pred==truth);s.cm[(truth,pred)]+=1
    def line(s): return 'n=%d acc=%.1f%% [T sell,P sell]=%d [sell,break]=%d [break,sell]=%d [break,break]=%d base=%.1f%%'%(
        s.n,100*s.ok/max(1,s.n),s.cm[(True,True)],s.cm[(True,False)],s.cm[(False,True)],s.cm[(False,False)],
        100*max(s.cm[(True,True)]+s.cm[(True,False)],s.cm[(False,True)]+s.cm[(False,False)])/max(1,s.n))

tot=collections.defaultdict(Acc); vind=collections.Counter(); vind_items=collections.Counter()
for back in (72,48,24):
    T0=gen-timedelta(hours=back); T1=T0+timedelta(hours=24)
    accs=collections.defaultdict(Acc)
    for t in range(1,7):
        for slot in SLOTS:
            code=item_code(slot,t); rows=rows_by.get(code)
            if rows is None: continue
            rolls=C.aggregate(rows,T0)
            out,dis,scrap=build_out(rolls,slot,t,bid)
            fill_quiet(out,slot,dis)
            # truth: next-24h eligible non-stale sales of the same roll
            fwd=collections.defaultdict(list)
            for tx in rows:
                if C.stale_listing(tx) or not tx['eligible_for_comps']: continue
                s=C.parse_time(tx['sold_at'])
                if T0<s<=T1: fwd[roll_key(slot,tx['skills'])].append(tx['unit_price'])
            for x in out:
                f=fwd.get(x['key'])
                if not f or len(f)<MIN_FWD: continue
                truth=statistics.median(f)*TAX_MUL>dis
                if x['net'] is not None:
                    accs['A own selected median @T0'].add(truth,x['sell'])
                    if x.get('wide'):
                        wv=x['wide']['price']*TAX_MUL>dis
                        accs['B own retained median @T0 (rolls with both)'].add(truth,wv)
                        if wv!=x['sell']:
                            vind['selected right' if x['sell']==truth else 'retained right']+=1
                            vind_items[(code,'sel=%s'%('sell' if x['sell'] else 'break'),'winner=%s'%('selected' if x['sell']==truth else 'retained'))]+=1
                    # held-one-out neighbour at T0, scored forward
                    saved=(x['net'],x.get('wide')); x['net']=None; x['wide']=None
                    y=None
                    for z in out:
                        if z is x or (z['net'] is None and not z.get('wide')): continue
                        if band(slot,z['key'])!=band(slot,x['key']) or pos(slot,z['key'])>=pos(slot,x['key']): continue
                        if y is None or pos(slot,z['key'])>pos(slot,y['key']): y=z
                    x['net'],x['wide']=saved
                    if y is not None:
                        pred=y['sell'] if y['net'] is not None else y['wide']['price']*TAX_MUL>dis
                        accs['D held-one-out neighbour @T0, scored forward'].add(truth,pred)
                elif x.get('wide'):
                    accs['E quiet-48h roll: week median verdict @T0'].add(truth,x['sell'])
                elif x.get('from'):
                    accs['C quiet roll (no week median): neighbour verdict @T0'].add(truth,x['from']['sell'])
                    accs['C by tier %d'%t].add(truth,x['from']['sell'])
    print('\n--- T0 = generated_at - %dh = %s ; truth = median of sales in next 24h ---'%(back,T0.isoformat()))
    for k in sorted(accs): print('  %-52s %s'%(k,accs[k].line()))
    for k,v in accs.items():
        tot[k].n+=v.n; tot[k].ok+=v.ok; tot[k].cm+=v.cm
print('\n=== pooled over the three non-overlapping forward windows ===')
for k in sorted(tot): print('  %-52s %s'%(k,tot[k].line()))
print('\nselected vs retained disagreements, who the next 24h vindicated:',dict(vind))
for k,v in sorted(vind_items.items()): print('   ',k,v)

# ---- (d) price-error benchmark against the next 24h: own selected median, own week median,
#      lower neighbour price (fillQuiet's candidate), linear interpolation ----
print('\n=== (d) relative error of candidate prices vs the roll\'s own next-24h median (>= %d sales), pooled 3 windows ==='%MIN_FWD)
errs=collections.defaultdict(list)
for back in (72,48,24):
    T0=gen-timedelta(hours=back); T1=T0+timedelta(hours=24)
    for t in range(1,7):
        for slot in SLOTS:
            code=item_code(slot,t); rows=rows_by.get(code)
            if rows is None: continue
            rolls=C.aggregate(rows,T0); out,dis,scrap=build_out(rolls,slot,t,bid)
            fwd=collections.defaultdict(list)
            for tx in rows:
                if C.stale_listing(tx) or not tx['eligible_for_comps']: continue
                s=C.parse_time(tx['sold_at'])
                if T0<s<=T1: fwd[roll_key(slot,tx['skills'])].append(tx['unit_price'])
            def pr(y): return y['price'] if y['net'] is not None else (y['wide']['price'] if y.get('wide') else None)
            for x in out:
                f=fwd.get(x['key'])
                if not f or len(f)<MIN_FWD: continue
                truth=statistics.median(f)
                c=[y for y in out if y is not x and pr(y) is not None and band(slot,y['key'])==band(slot,x['key'])]
                px=pos(slot,x['key']); lo=[y for y in c if pos(slot,y['key'])<px]; hi=[y for y in c if pos(slot,y['key'])>px]
                l=max(lo,key=lambda y:pos(slot,y['key'])) if lo else None; h=min(hi,key=lambda y:pos(slot,y['key'])) if hi else None
                if x['net'] is not None:
                    errs['own selected median'].append((x['price']-truth)/truth)
                    if x.get('wide'): errs['own week median'].append((x['wide']['price']-truth)/truth)
                    if l: errs['lower neighbour (priced roll hidden)'].append((pr(l)-truth)/truth)
                    if l and h:
                        p=pr(l)+(pr(h)-pr(l))*(px-pos(slot,l['key']))/(pos(slot,h['key'])-pos(slot,l['key']))
                        errs['interpolation (priced roll hidden)'].append((p-truth)/truth)
                else:
                    if x.get('wide'): errs['QUIET roll: own week median (page shows it)'].append((x['wide']['price']-truth)/truth)
                    elif l: errs['QUIET roll: lower neighbour price (page shows dash)'].append((pr(l)-truth)/truth)
                    if not x.get('wide') and l and h:
                        p=pr(l)+(pr(h)-pr(l))*(px-pos(slot,l['key']))/(pos(slot,h['key'])-pos(slot,l['key']))
                        errs['QUIET roll: interpolation'].append((p-truth)/truth)
for k in sorted(errs):
    e=errs[k]; ab=[abs(v) for v in e]
    print('  %-50s n=%4d  %s  |err| p50=%.1f%% p90=%.1f%%  share within 5%%=%.0f%%'%(k,len(e),fmtq(quantiles(e,(0.1,0.25,0.5,0.75,0.9))),100*statistics.median(ab),100*quantiles(ab,(0.9,))[0.9],100*sum(v<=0.05 for v in ab)/len(ab)))
