"""Supporting figures: knife crit-4 band at bar 0.5, dash share by item, guessed-break count,
cost of held-one-out misclassifications, tier-1 cut-card count, rolls outside the roll space."""
import sys, collections
sys.path.insert(0,'/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit/neighbour-fill')
from nf_common import *
snap=load(); bid=snap['commodities']['scraps']['order_book']['best_bid']
def status(x): return 'priced %.3f %s'%(x['price'],'sell' if x['sell'] else 'break') if x['net'] is not None else ('wide %.3f %s'%(x['wide']['price'],'sell' if x['sell'] else 'break') if x.get('wide') else ('from %s %s'%(x['from']['key'],'sell' if x['from']['sell'] else 'break') if x.get('from') else 'none'))
print('=== knife crit 4 band, bar 0.5 (cutRule as coded says "4 from 38"; skipping quiet rolls says "4 all") ===')
out,dis,scrap=build_out(snap['categories']['knife']['rolls'],'weapon',1,bid,0.99,0.5); fill_quiet(out,'weapon',dis,0.99)
print('need',round(dis,3),'scrap',round(scrap,3))
for x in out:
    if x['key'].endswith('/4'): print('  ',x['key'],status(x))
print('\n=== dash (no price on Sort tab) share of case draws by item, default bar ===')
dash=collections.Counter(); dash_n=collections.Counter(); guess_break=collections.Counter(); guess_n=collections.Counter()
for t in range(1,7):
    for slot in SLOTS:
        cat=snap['categories'].get(item_code(slot,t))
        if not cat: continue
        out,dis,scrap=build_out(cat['rolls'],slot,t,bid); fill_quiet(out,slot,dis)
        for x in out:
            if x['net'] is None and not x.get('wide'):
                dash[item_code(slot,t)]+=x['each']; dash_n[item_code(slot,t)]+=1
                if x.get('from'):
                    guess_n[item_code(slot,t)]+=1; guess_break[item_code(slot,t)]+=(not x['from']['sell'])
for k in dash: print('  %-8s dash rolls %3d  share of draws %.2f%%  guessed %d of which guessed-break %d'%(k,dash_n[k],100*dash[k],guess_n[k],guess_break[k]))
print('  total dash share %.2f%%'%(100*sum(dash.values())))
print('\n=== cost of fillQuiet held-one-out errors (default bar) ===')
sb=[];bs=[]
for t in range(1,7):
    for slot in SLOTS:
        cat=snap['categories'].get(item_code(slot,t))
        if not cat: continue
        out,dis,scrap=build_out(cat['rolls'],slot,t,bid); fill_quiet(out,slot,dis)
        for x in out:
            if x['net'] is None: continue
            y=None
            for z in out:
                if z is x or (z['net'] is None and not z.get('wide')): continue
                if band(slot,z['key'])!=band(slot,x['key']) or pos(slot,z['key'])>=pos(slot,x['key']): continue
                if y is None or pos(slot,z['key'])>pos(slot,y['key']): y=z
            if y is None: continue
            pred=y['sell'] if y['net'] is not None else y['wide']['price']*0.99>dis
            if pred!=x['sell']:
                (sb if x['sell'] else bs).append((item_code(slot,t),x['key'],round(x['price'],3),round(x['margin'],3),y['key'],round(y['price'] if y['net'] is not None else y['wide']['price'],3)))
print('truth sell, neighbour says break (user breaks a sellable roll): n=%d  margins over scrap: mean %.3f, min %.3f, max %.3f'%(len(sb),sum(r[3] for r in sb)/len(sb),min(r[3] for r in sb),max(r[3] for r in sb)))
for r in sb: print('   ',r)
print('truth break, neighbour says sell (user lists a roll under the bar): n=%d'%len(bs))
for r in bs: print('   ',r)
print('\n=== tier-1 cut card count check (page says "64 of 81 rolls clear the bar") ===')
sell=known=0
for slot in SLOTS:
    out,dis,scrap=build_out(snap['categories'][item_code(slot,1)]['rolls'],slot,1,bid)
    known+=sum(x['net'] is not None for x in out); sell+=sum(bool(x['net'] is not None and x['sell']) for x in out)
print('  python: %d of %d'%(sell,known))
print('\n=== seen rolls outside craftRollSpace (README 1,295 seen / 255 quiet vs my 253 wide-only) ===')
seen=0; outside=[]
for code,cat in snap['categories'].items():
    slot=t=None
    for tt in range(1,7):
        for sl in SLOTS:
            if item_code(sl,tt)==code: slot,t=sl,tt
    sp=set(roll_space(slot,t))
    for rk,row in cat['rolls'].items():
        seen+=1; k=roll_key(slot,row['exact_roll']['skills'])
        if k not in sp: outside.append((code,k,row['selected']['median'],row['retained_window']['count']))
print('  seen rolls',seen,'outside roll space',len(outside),outside)
