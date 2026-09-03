"""(e) code checks quantified on the snapshot: heat-grid bar mismatch, hard-coded 0.99, cutRule
treatment of quiet rolls (weapon vs armour), strict lower-bound share, per-item base rate."""
import sys, collections, argparse
sys.path.insert(0,'/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit/neighbour-fill')
from nf_common import *
from ev_ref import WEAPON_STATS, WEAPON_CODES
ap=argparse.ArgumentParser(); ap.add_argument('--tax',type=float,default=1.0); ap.add_argument('--bar',type=float,default=0.10)
a=ap.parse_args(); taxMul=1-a.tax/100
snap=load(); bid=snap['commodities']['scraps']['order_book']['best_bid']
print('tax',a.tax,'taxMul',taxMul,'bar',a.bar)

def cut_rule_weapon(out, mode):
    """cutRule 4534-4567. mode: 'page' (x.sell undefined for quiet -> stops run; wide rolls count),
    'skip' (armour-style: skip rolls with net==null), 'from' (use neighbour/wide verdicts as sell)."""
    bands=collections.defaultdict(list)
    for x in out:
        atk,crit=x['key'].split('/')
        if mode=='page': s=x.get('sell')            # undefined -> falsy -> break
        elif mode=='skip': s=None if x['net'] is None else x['sell']
        else: s=x['sell'] if x['net'] is not None or x.get('wide') else (x['from']['sell'] if x.get('from') else None)
        bands[crit].append((int(atk),s))
    res={}
    for c,rolls in bands.items():
        rolls.sort(); cut=None; i=len(rolls)-1
        while i>=0:
            s=rolls[i][1]
            if mode!='page' and s is None: i-=1; continue
            if not s: break
            cut=rolls[i][0]; i-=1
        res[c]=(cut, i<0)
    return res
def cut_text(res):
    order=sorted(res,key=lambda c:-int(c)); out=[]; run=[]
    def flush():
        if run: out.append(run[-1]+('+' if len(run)>1 else '')+' all')
        run.clear()
    for c in order:
        cut,whole=res[c]
        if whole and cut is not None: run.append(c); continue
        flush()
        if cut is not None: out.append(c+' from '+str(cut))
    flush(); return 'crit '+' · '.join(out)

heat_bar=0; heat_bar_rolls=[]; tax99=0; tax99_rolls=[]; wide_weapon=0
print('\n=== weapon cut lines: as coded vs quiet-skipped vs neighbour-included ===')
for t in range(1,7):
    code=WEAPON_CODES[t-1]; cat=snap['categories'][code]
    out,dis,scrap=build_out(cat['rolls'],'weapon',t,bid,taxMul,a.bar); fill_quiet(out,'weapon',dis,taxMul)
    n_priced=sum(x['net'] is not None for x in out); n_wide=sum(x['net'] is None and bool(x.get('wide')) for x in out)
    n_from=sum(x['net'] is None and not x.get('wide') and bool(x.get('from')) for x in out); n_none=len(out)-n_priced-n_wide-n_from
    sells=sum(1 for x in out if x['net'] is not None and x['sell']); 
    print('%-7s priced %3d wide-only %3d from-only %3d none %3d | priced sell %d/%d'%(code,n_priced,n_wide,n_from,n_none,sells,n_priced))
    for mode in ('page','skip','from'):
        txt=cut_text(cut_rule_weapon(out,mode))
        if mode=='page':   # cutRule 4517-4519 short-circuits on the priced counts before the band logic
            if sells==0: txt='none (short-circuit r.sell===0)'
            elif sells==n_priced: txt='every roll (short-circuit r.sell===r.known)'
        print('   %-5s %s'%(mode,txt))
    # heat grid: sells=m>=0 with m=margin (vs scrap), list: sell=net>dis (vs need)
    for x in out:
        if x['net'] is not None:
            if (x['margin']>=0)!=x['sell']: heat_bar+=1; heat_bar_rolls.append((code,x['key'],round(x['price'],3),round(x['margin'],3)))
        elif x.get('wide'):
            wide_weapon+=1
            m=x['wide']['price']*0.99-scrap
            if (m>=0)!=x['sell']: tax99+=1; tax99_rolls.append((code,x['key'],round(x['wide']['price'],3)))
print('\nheat cells whose green/break class (margin>=0 vs scrap) contradicts the list verdict (net>need):',heat_bar)
print('  ',heat_bar_rolls[:40])
print('wide-only weapon cells',wide_weapon,'; heat class (0.99 hard-coded, vs scrap) contradicts x.sell (taxMul, vs need):',tax99)
print('  ',tax99_rolls[:40])

print('\n=== armour cut lines: as coded (skip quiet) vs neighbour/wide included ===')
for t in range(1,7):
    for slot in SLOTS[1:]:
        cat=snap['categories'].get(item_code(slot,t))
        if not cat: continue
        out,dis,scrap=build_out(cat['rolls'],slot,t,bid,taxMul,a.bar); fill_quiet(out,slot,dis,taxMul)
        def cut(mode):
            c=None
            for x in reversed(out):
                if mode=='skip':
                    if x['net'] is None: continue
                    s=x['sell']
                else:
                    s=x.get('sell') if (x['net'] is not None or x.get('wide')) else (x['from']['sell'] if x.get('from') else None)
                    if s is None: continue
                if not s: break
                c=x['key']
            return c
        quiet=[x['key'] for x in out if x['net'] is None]
        if quiet and cut('skip')!=cut('from'): print('  %-8s quiet=%s cut(skip)=%s cut(from)=%s'%(item_code(slot,t),quiet,cut('skip'),cut('from')))
print('(armour bands with no line above: quiet rolls never change the cut)')

print('\n=== strict lower-bound share, and per-item majority baseline (held-one-out, fillQuiet) ===')
n=0; ge=0; gt=0; item_maj=0; tot=0; wide_nb=0
for t in range(1,7):
    for slot in SLOTS:
        cat=snap['categories'].get(item_code(slot,t))
        if not cat: continue
        out,dis,scrap=build_out(cat['rolls'],slot,t,bid,taxMul,a.bar); fill_quiet(out,slot,dis,taxMul)
        pr=[x for x in out if x['net'] is not None]; tot+=len(pr)
        item_maj+=max(sum(x['sell'] for x in pr),sum(not x['sell'] for x in pr))
        for x in pr:
            y=None
            for z in out:
                if z is x or (z['net'] is None and not z.get('wide')): continue
                if band(slot,z['key'])!=band(slot,x['key']) or pos(slot,z['key'])>=pos(slot,x['key']): continue
                if y is None or pos(slot,z['key'])>pos(slot,y['key']): y=z
            if y is None: continue
            p=y['price'] if y['net'] is not None else y['wide']['price']
            if y['net'] is None: wide_nb+=1
            n+=1; ge+=(x['price']>=p); gt+=(x['price']>p)
print('neighbours n=%d  true>=nb %.1f%%  true>nb (strict) %.1f%%  neighbours that were wide-only %d'%(n,100*ge/n,100*gt/n,wide_nb))
print('per-item majority baseline: %d/%d = %.1f%%'%(item_maj,tot,100*item_maj/tot))
