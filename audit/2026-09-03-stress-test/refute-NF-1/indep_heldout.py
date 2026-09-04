"""Independent held-one-out check of fillQuiet (test60.html 4496-4512), written from the page code, not nf_common."""
import json, collections, sys
sys.path.insert(0,'/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit')
from ev_ref import SCRAP_YIELDS, SLOTS, roll_space, roll_key, item_code
SNAP='/home/user/-warera-case1-collector/data/warera_case1_market.json'
snap=json.load(open(SNAP)); bid=snap['commodities']['scraps']['order_book']['best_bid']
TAXMUL=0.99; BAR=0.10
def pos(slot,k): return int(k.split('/')[0]) if slot=='weapon' else int(k)
def band(slot,k): return k.split('/')[1] if slot=='weapon' else ''
tot=collections.Counter(); per_tier=collections.defaultdict(collections.Counter); per_item=collections.defaultdict(collections.Counter)
truth_all=collections.Counter(); item_truth=collections.defaultdict(collections.Counter); item_truth_cov=collections.defaultdict(collections.Counter)
errs=[]; nocov=0; live_from=collections.Counter(); live_from_sell=collections.Counter()
for t in range(1,7):
    scrap=SCRAP_YIELDS[t-1]*bid; dis=scrap+BAR
    for slot in SLOTS:
        cat=snap['categories'].get(item_code(slot,t))
        if not cat: continue
        seen={}
        for row in cat['rolls'].values():
            k=roll_key(slot,(row.get('exact_roll') or {}).get('skills'))
            if k is not None: seen[k]=row
        # table: key -> (price_selected or None, wide_price or None)
        tab={}
        for k in roll_space(slot,t):
            row=seen.get(k); stat=row and (row.get('selected') or row.get('fallback_48h')); wide=row and row.get('retained_window')
            sp=float(stat['median']) if stat and stat.get('median') is not None else None
            wp=float(wide['median']) if wide and wide.get('median') is not None else None
            tab[k]=(sp,wp)
        def verdict(k): sp,wp=tab[k]; return (sp*TAXMUL>dis) if sp is not None else (wp*TAXMUL>dis if wp is not None else None)
        def lower_nb(k, hidden):
            best=None
            for y,(sp,wp) in tab.items():
                if y==hidden or (sp is None and wp is None): continue
                if band(slot,y)!=band(slot,k) or pos(slot,y)>=pos(slot,k): continue
                if best is None or pos(slot,y)>pos(slot,best): best=y
            return best
        # live: what fillQuiet actually does on this snapshot (rolls with no selected and no wide)
        for k,(sp,wp) in tab.items():
            if sp is None and wp is None:
                nb=lower_nb(k,k)
                if nb: live_from[item_code(slot,t)]+=1; live_from_sell[item_code(slot,t)]+=verdict(nb)
        for k,(sp,wp) in tab.items():
            if sp is None: continue
            truth=sp*TAXMUL>dis; truth_all[truth]+=1; item_truth[item_code(slot,t)][truth]+=1
            nb=lower_nb(k,k)
            if nb is None: nocov+=1; continue
            pred=verdict(nb); item_truth_cov[item_code(slot,t)][truth]+=1
            tot[(truth,pred)]+=1; per_tier[t][(truth,pred)]+=1; per_item[item_code(slot,t)][(truth,pred)]+=1
            if pred!=truth: errs.append((item_code(slot,t),k,sp,round(sp*TAXMUL-scrap,3),nb,tab[nb]))
n=sum(tot.values()); ok=tot[(True,True)]+tot[(False,False)]
print('scrap bid',bid,'priced',sum(truth_all.values()),'true sell',truth_all[True],'true break',truth_all[False],'majority base %.1f%%'%(100*max(truth_all.values())/sum(truth_all.values())))
print('held-one-out lower-same-band: n=%d ok=%d acc=%.2f%% nocov=%d cm sell/sell=%d sell/break=%d break/sell=%d break/break=%d'%(n,ok,100*ok/n,nocov,tot[(True,True)],tot[(True,False)],tot[(False,True)],tot[(False,False)]))
for t in range(1,7):
    c=per_tier[t]; m=sum(c.values()); o=c[(True,True)]+c[(False,False)]
    base=max(c[(True,True)]+c[(True,False)],c[(False,True)]+c[(False,False)])
    print('  tier %d n=%d acc=%.1f%% base=%.1f%% diff=%.1fpp sell->break=%d break->sell=%d'%(t,m,100*o/m,100*base/m,100*(o-base)/m,c[(True,False)],c[(False,True)]))
# per-item majority baseline over all 1040 and over the covered 979
maj_all=sum(max(c.values()) for c in item_truth.values()); maj_cov=sum(max(c.values()) for c in item_truth_cov.values())
print('per-item majority baseline: all %d/%d=%.1f%%  covered %d/%d=%.1f%%'%(maj_all,sum(truth_all.values()),100*maj_all/sum(truth_all.values()),maj_cov,n,100*maj_cov/n))
# neighbour beats per-item majority where?
print('items where held-out acc != per-item majority:')
for it,c in per_item.items():
    m=sum(c.values()); o=c[(True,True)]+c[(False,False)]; b=max(item_truth_cov[it].values())
    if o!=b: print('   %-8s n=%d nb=%d maj=%d'%(it,m,o,b))
print('errors (%d):'%len(errs))
for e in errs: print('  ',e)
print('LIVE fillQuiet neighbour path fires on (item: rolls, of which guessed sell):', {k:(v,live_from_sell[k]) for k,v in live_from.items()}, 'total',sum(live_from.values()))
