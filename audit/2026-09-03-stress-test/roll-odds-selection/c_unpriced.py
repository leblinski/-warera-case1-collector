"""(c) Unpriced rolls: list them per item with fillQuiet's verdict, and recompute the case EV
under: as page (excluded), worth scrap, worth nearest-worse priced neighbour, plus two
variants (wide/retained price first; nearest neighbour either side)."""
import json, statistics
from load import load, TIERS
import ev_ref
p,now,rows=load()
tax=1.0;taxMul=1-tax/100
m=ev_ref.Model(p,tax=tax,bar_abs=0.10)
def pos(slot,k): return int(k.split('/')[0]) if slot=='weapon' else int(k)
def band(slot,k): return k.split('/')[1] if slot=='weapon' else ''
def slot_rows(slot,t):
    cat=p['categories'].get(ev_ref.item_code(slot,t)); space=ev_ref.roll_space(slot,t)
    seen={}
    for key,row in cat['rolls'].items():
        k=ev_ref.roll_key(slot,row['exact_roll']['skills']); seen[k]=row
    dis=m.dismantle(t);need=m.need(t);out=[]
    for k in space:
        row=seen.get(k);st=row and (row['selected'] or row['fallback_48h']);wide=row and row['retained_window']
        if st and st.get('median') is not None:
            net=st['median']*taxMul;out.append({'key':k,'net':net,'sell':net>need,'val':net if net>need else dis,'wide':None})
        else:
            w=None
            if wide and wide.get('median') is not None:
                wn=wide['median']*taxMul;w={'net':wn,'sell':wn>need,'val':wn if wn>need else dis,'count':wide['count']}
            out.append({'key':k,'net':None,'sell':None,'val':None,'wide':w})
    # fillQuiet verdicts + neighbour values
    for x in out:
        if x['net'] is not None:continue
        if x['wide']: x['fq']='wide:'+('sell' if x['wide']['sell'] else 'break');x['fqsell']=x['wide']['sell']
        best=None
        for y in out:
            if y['net'] is None and not y['wide']:continue
            if band(slot,y['key'])!=band(slot,x['key']) or pos(slot,y['key'])>=pos(slot,x['key']):continue
            if not best or pos(slot,y['key'])>pos(slot,best['key']):best=y
        bestp=None  # nearest-worse PRICED (selected) neighbour
        for y in out:
            if y['net'] is None:continue
            if band(slot,y['key'])!=band(slot,x['key']) or pos(slot,y['key'])>=pos(slot,x['key']):continue
            if not bestp or pos(slot,y['key'])>pos(slot,bestp['key']):bestp=y
        nearest=None # nearest priced either side, same band
        for y in out:
            if y['net'] is None or band(slot,y['key'])!=band(slot,x['key']):continue
            d=abs(pos(slot,y['key'])-pos(slot,x['key']))
            if not nearest or d<nearest[0] or (d==nearest[0] and pos(slot,y['key'])<pos(slot,x['key'])):nearest=(d,y)
        if not x['wide']:
            if best: s=best['sell'] if best['net'] is not None else best['wide']['sell'];x['fq']='like %s:%s'%(best['key'],'sell' if s else 'break');x['fqsell']=s
            else: x['fq']='none traded yet';x['fqsell']=None
        x['nb_worse']=bestp['key'] if bestp else None;x['nb_worse_val']=bestp['val'] if bestp else None
        x['nb_any']=nearest[1]['key'] if nearest else None;x['nb_any_val']=nearest[1]['val'] if nearest else None
    return out,dis
def net_under(out,dis,mode):
    vals=[]
    for x in out:
        if x['net'] is not None: vals.append(x['val']);continue
        if mode=='page':continue
        if mode=='scrap':vals.append(dis)
        elif mode=='worse':vals.append(x['nb_worse_val'] if x['nb_worse_val'] is not None else dis)
        elif mode=='nearest':vals.append(x['nb_any_val'] if x['nb_any_val'] is not None else dis)
        elif mode=='wide_then_worse':vals.append(x['wide']['val'] if x['wide'] else (x['nb_worse_val'] if x['nb_worse_val'] is not None else dis))
    return sum(vals)/len(vals) if vals else None
modes=['page','scrap','worse','nearest','wide_then_worse']
cost=ev_ref.craft_walk(p['commodities']['case1']['order_book'],1)['unit']
res={'cost':cost,'items':{},'case':{}}
lines=[]
for mode in modes:
    gross=0;tiers=[]
    for t in range(1,7):
        ws=ns=0
        for slot in ev_ref.SLOTS:
            out,dis=slot_rows(slot,t);n=net_under(out,dis,mode);w=ev_ref.CRAFT_SLOT_WEIGHT[slot]
            if n is None:continue
            ws+=w;ns+=w*n
            res['items'].setdefault(ev_ref.item_code(slot,t),{})[mode]=n
        tiers.append(ns/ws);gross+=ev_ref.CASE_TIER_ODDS[t-1]*ns/ws
    res['case'][mode]={'gross':gross,'edge':gross-cost,'pct':(gross-cost)/cost*100,'tiers':tiers}
    print('%-16s gross %.4f edge %+.4f pct %+.2f%%  tiers %s'%(mode,gross,gross-cost,(gross-cost)/cost*100,' '.join('%.3f'%x for x in tiers)))
print('\nPer-item unpriced rolls (space, priced, wide-only, never-seen) and fillQuiet verdict tallies; item net under page/scrap/worse')
for t in range(1,7):
    for slot in ev_ref.SLOTS:
        code=ev_ref.item_code(slot,t);out,dis=slot_rows(slot,t)
        un=[x for x in out if x['net'] is None]
        if not un:continue
        wide=[x for x in un if x['wide']];never=[x for x in un if not x['wide']]
        fq={'sell':0,'break':0,'none':0}
        for x in un:
            fq['none' if x['fqsell'] is None else ('sell' if x['fqsell'] else 'break')]+=1
        i=res['items'][code]
        print('%-8s space %3d priced %3d wide-only %3d never %3d | fillQuiet sell %d break %d none %d | net page %.3f scrap %.3f worse %.3f nearest %.3f wide %.3f'%(
            code,len(out),len(out)-len(un),len(wide),len(never),fq['sell'],fq['break'],fq['none'],i['page'],i['scrap'],i['worse'],i['nearest'],i['wide_then_worse']))
        if code in('knife','tank','jet','gun','rifle'):
            ks=[x['key']+('(w%d)'%x['wide']['count'] if x['wide'] else '') for x in un]
            print('    unpriced:',' '.join(ks) if len(ks)<=60 else ' '.join(ks[:60])+' ... (%d)'%len(ks))
            print('    verdicts:',' '.join('%s=%s'%(x['key'],x['fq']) for x in un[:40]))
json.dump(res,open('c_unpriced.json','w'),indent=1)
