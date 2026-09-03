"""(b) Reproduce the removed 'as traded' weighting (+9.47%) and decompose which items drive it."""
import json,sys
from load import load, TIERS
import ev_ref
p,now,rows=load()
even=ev_ref.Model(p,tax=1.0,bar_abs=0.10,weighting='even')
trad=ev_ref.Model(p,tax=1.0,bar_abs=0.10,weighting='as_traded')
ce,ct=even.case(1),trad.case(1)
print('even: gross %.4f edge %+.4f pct %+.2f%%'%(ce['gross'],ce['edge'],ce['pct']))
print('as_traded: gross %.4f edge %+.4f pct %+.2f%%'%(ct['gross'],ct['edge'],ct['pct']))
print('gap in gross %.4f'%(ct['gross']-ce['gross']))
res={}
print('\n%-9s %-7s %8s %8s %8s %9s  %s'%('item','odds','even','traded','diff','case dGr','note'))
tot=0
for t in range(1,7):
    odds=ev_ref.CASE_TIER_ODDS[t-1]
    ee=even.craft_expected(t);et=trad.craft_expected(t)
    for slot in ev_ref.SLOTS:
        w=ev_ref.CRAFT_SLOT_WEIGHT[slot]
        ve=ee['per'].get(slot);vt=et['per'].get(slot)
        if not ve or not vt:continue
        d=vt['net']-ve['net'];dg=odds*w*d;tot+=dg
        code=ev_ref.item_code(slot,t)
        # top weighted rolls
        rws=sorted(vt['rows'],key=lambda x:-0)
        cat=p['categories'][code]
        cnts={}
        for k,row in cat['rolls'].items():
            kk=ev_ref.roll_key(slot,row['exact_roll']['skills']);cnts[kk]=(row.get('fallback_48h') or {}).get('count') or 0
        top=sorted(cnts.items(),key=lambda x:-x[1])[:2]
        top_s=' '.join('%s:%d'%(k,c) for k,c in top)
        res[code]={'even':ve['net'],'traded':vt['net'],'diff':d,'case_gross_delta':dg,'top':top,'samples':sum(cnts.values())}
        print('%-9s %-7.4f %8.4f %8.4f %+8.4f %+9.4f  top48h %s of %d'%(code,odds,ve['net'],vt['net'],d,dg,top_s,sum(cnts.values())))
print('sum of per-item case gross deltas %.4f'%tot)
# knife 40/5 detail
kn=p['categories']['knife']['rolls']
for k,row in kn.items():
    if row['exact_roll']['skills']=={'attack':40,'criticalChance':5}:
        print('knife 40/5 selected median',row['selected']['median'],'48h count',row['fallback_48h']['count'],'retained count',row['retained_window']['count'])
# where is trade frequency informative? correlate 48h count with price within each all-sell item
json.dump(res,open('b_as_traded.json','w'),indent=1)
