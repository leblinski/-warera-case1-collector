"""(c) Coverage handling: drop one slot / one tier; knife priced vs unpriced under fillQuiet."""
from common import *
import copy
snap=load(); base=E.Model(snap,tax=1,bar_abs=0.10); c0=base.case(1); g0=c0['gross']; cost=c0['cost']['unit']
print('baseline gross %.4f edge %+.4f pct %+.2f%%'%(g0,c0['edge'],c0['pct']))
print('\n== remove one slot (all tiers): page renormalises the remaining slot weights ==')
for slot in E.SLOTS:
    s2=copy.copy(snap); s2['categories']={k:v for k,v in snap['categories'].items() if slot_of(k)!=slot}
    c=E.Model(s2,tax=1,bar_abs=0.10).case(1)
    print('  drop %-7s gross %.4f (%+.4f) pct %+.2f%%'%(slot,c['gross'],c['gross']-g0,c['pct']))
print('\n== remove one tier: page adds nothing for it (treated as worthless) ==')
for t in range(1,7):
    s2=copy.copy(snap); s2['categories']={k:v for k,v in snap['categories'].items() if tier_of(k)!=t}
    c=E.Model(s2,tax=1,bar_abs=0.10).case(1)
    print('  drop tier %d gross %.4f (%+.4f) pct %+.2f%%   [tier adds %.4f]'%(t,c['gross'],c['gross']-g0,c['pct'],c0['parts'][t-1]['add']))
print('\n== remove one slot within one tier (renormalised): the 8 biggest moves ==')
mv=[]
for t in range(1,7):
    for slot in E.SLOTS:
        code=E.item_code(slot,t)
        if code not in snap['categories']: continue
        s2=copy.copy(snap); s2['categories']={k:v for k,v in snap['categories'].items() if k!=code}
        c=E.Model(s2,tax=1,bar_abs=0.10).case(1); mv.append((abs(c['gross']-g0),code,c['gross'],c['pct']))
for d,code,g,p in sorted(mv,reverse=True)[:8]: print('  drop %-8s gross %.4f (%+.4f) pct %+.2f%%'%(code,g,g-g0,p))
print('\n== knife (tier 1 weapon, 30% of 62% = 18.6% of outcomes): priced vs unpriced rolls ==')
t=1; slot='weapon'; cat=snap['categories']['knife']; need=base.need(1); dis=base.dismantle(1); taxMul=0.99
seen={}
for key,row in cat['rolls'].items():
    k=E.roll_key(slot,row['exact_roll']['skills']); seen[k]=row
space=E.roll_space(slot,1)
out=[]
for k in space:
    row=seen.get(k); st=row and (row['selected'] or row['fallback_48h']); wide=row and row.get('retained_window')
    if not st or st.get('median') is None:
        out.append({'key':k,'net':None,'wide':{'price':wide['median'],'count':wide['count']} if wide and wide.get('median') is not None else None})
    else:
        net=st['median']*taxMul; out.append({'key':k,'net':net,'price':st['median'],'sell':net>need,'n':st['count']})
pos=lambda k:int(k.split('/')[0]); band=lambda k:k.split('/')[1]
for x in out:
    if x['net'] is not None: continue
    if x['wide']: x['sell']=x['wide']['price']*taxMul>need; x['src']='wide'; x['fillprice']=x['wide']['price']; continue
    best=None
    for y in out:
        if y['net'] is None and not y['wide']: continue
        if band(y['key'])!=band(x['key']) or pos(y['key'])>=pos(x['key']): continue
        if not best or pos(y['key'])>pos(best['key']): best=y
    if best:
        x['src']='nbr:'+best['key']; x['sell']=best['sell']; x['fillprice']=best['price'] if best['net'] is not None else best['wide']['price']
    else: x['src']='none'; x['sell']=None; x['fillprice']=None
priced=[x for x in out if x['net'] is not None]; unp=[x for x in out if x['net'] is None]
print(' priced %d/%d; of priced %d sell, %d break; mean price %.4f; page slot value (renormalised) %.4f'%(len(priced),len(space),sum(x['sell'] for x in priced),sum(not x['sell'] for x in priced),
      sum(x['price'] for x in priced)/len(priced),sum(x['net'] if x['sell'] else dis for x in priced)/len(priced)))
print(' priced rolls by crit band:',{b:sum(1 for x in priced if band(x['key'])==b) for b in '12345'},' attack range of priced: %d-%d; median attack %d'%(min(pos(x['key']) for x in priced),max(pos(x['key']) for x in priced),sorted(pos(x['key']) for x in priced)[len(priced)//2]))
print(' unpriced %d: wide(retained 7d) %d, neighbour %d, none %d'%(len(unp),sum(1 for x in unp if x['src']=='wide'),sum(1 for x in unp if x['src'].startswith('nbr')),sum(1 for x in unp if x['src']=='none')))
print(' unpriced by crit band:',{b:sum(1 for x in unp if band(x['key'])==b) for b in '12345'},' attack range %d-%d'%(min(pos(x['key']) for x in unp),max(pos(x['key']) for x in unp)))
print(' fillQuiet verdicts on unpriced: sell %d, break %d, none %d'%(sum(1 for x in unp if x['sell'] is True),sum(1 for x in unp if x['sell'] is False),sum(1 for x in unp if x['sell'] is None)))
wideonly=[x for x in unp if x['src']=='wide']
if wideonly: print(' wide-priced unpriced rolls: mean retained median %.4f (n=%d) vs priced mean %.4f'%(sum(x['fillprice'] for x in wideonly)/len(wideonly),len(wideonly),sum(x['price'] for x in priced)/len(priced)))
print(' priced rolls: sell/break by crit band:',{b:'%d/%d'%(sum(1 for x in priced if band(x['key'])==b and x['sell']),sum(1 for x in priced if band(x['key'])==b and not x['sell'])) for b in '12345'})
print(' priced rolls attack<30: %d sell %d break; attack>=30: %d sell %d break'%(sum(1 for x in priced if pos(x['key'])<30 and x['sell']),sum(1 for x in priced if pos(x['key'])<30 and not x['sell']),sum(1 for x in priced if pos(x['key'])>=30 and x['sell']),sum(1 for x in priced if pos(x['key'])>=30 and not x['sell'])))
def knife_value(mode):
    vals=[]
    for x in out:
        if x['net'] is not None: vals.append(x['net'] if x['sell'] else dis); continue
        if mode=='renorm': continue
        if mode=='dis': vals.append(dis); continue
        if mode=='fill':
            if x['sell'] and x['fillprice']: vals.append(max(x['fillprice']*taxMul,dis))
            elif x['sell'] is None: continue
            else: vals.append(dis)
    return sum(vals)/len(vals),len(vals)
print('\n knife slot value: renormalised (page) %.4f over %d | fillQuiet neighbour price %.4f over %d | unpriced = scrap %.4f over %d'%(*knife_value('renorm'),*knife_value('fill'),*knife_value('dis')))
w=E.CASE_TIER_ODDS[0]*E.CRAFT_SLOT_WEIGHT['weapon']
for mode in ('fill','dis'):
    v,_=knife_value(mode); vp,_=knife_value('renorm'); dg=w*(v-vp)
    print('  case gross with knife=%s: %.4f (%+.4f) pct %+.2f%%'%(mode,g0+dg,dg,(g0+dg-cost)/cost*100))
# same test across every partially covered slot
print('\n== every slot with unpriced rolls: value under renorm / fill / scrap, and case gross impact ==')
tot_fill=tot_dis=0.0
for t in range(1,7):
    for slot in E.SLOTS:
        code=E.item_code(slot,t); cat=snap['categories'].get(code)
        if not cat: continue
        v=base.slot_value(slot,t); 
        if not v or v['covered']==v['space']: continue
        dis=base.dismantle(t); need=base.need(t); seen={}
        for key,row in cat['rolls'].items(): seen[E.roll_key(slot,row['exact_roll']['skills'])]=row
        space=E.roll_space(slot,t); o2=[]
        for k in space:
            row=seen.get(k); st=row and (row['selected'] or row['fallback_48h']); wide=row and row.get('retained_window')
            if not st or st.get('median') is None: o2.append({'key':k,'net':None,'wide':wide['median'] if wide and wide.get('median') is not None else None})
            else: o2.append({'key':k,'net':st['median']*taxMul,'price':st['median'],'sell':st['median']*taxMul>need})
        pos=(lambda k:int(k.split('/')[0])) if slot=='weapon' else (lambda k:int(k)); band=(lambda k:k.split('/')[1]) if slot=='weapon' else (lambda k:'')
        fillv=[];disv=[]
        for x in o2:
            if x['net'] is not None: val=x['net'] if x['sell'] else dis; fillv.append(val); disv.append(val); continue
            disv.append(dis)
            if x['wide'] is not None: fillv.append(max(x['wide']*taxMul,dis) if x['wide']*taxMul>need else dis); continue
            best=None
            for y in o2:
                if y['net'] is None and y['wide'] is None: continue
                if band(y['key'])!=band(x['key']) or pos(y['key'])>=pos(x['key']): continue
                if not best or pos(y['key'])>pos(best['key']): best=y
            if best:
                bp=best['price'] if best['net'] is not None else best['wide']; bs=best['sell'] if best['net'] is not None else best['wide']*taxMul>need
                fillv.append(max(bp*taxMul,dis) if bs else dis)
        wgt=E.CASE_TIER_ODDS[t-1]*E.CRAFT_SLOT_WEIGHT[slot]
        vf=sum(fillv)/len(fillv); vd=sum(disv)/len(disv)
        tot_fill+=wgt*(vf-v['net']); tot_dis+=wgt*(vd-v['net'])
        print('  %-8s covered %3d/%3d renorm %.4f fill %.4f (case %+.4f) scrap-for-unpriced %.4f (case %+.4f)'%(code,v['covered'],v['space'],v['net'],vf,wgt*(vf-v['net']),vd,wgt*(vd-v['net'])))
print(' case gross if every unpriced roll were filled: %.4f (%+.4f, pct %+.2f%%); if every unpriced roll were scrap: %.4f (%+.4f, pct %+.2f%%)'%(g0+tot_fill,tot_fill,(g0+tot_fill-cost)/cost*100,g0+tot_dis,tot_dis,(g0+tot_dis-cost)/cost*100))
