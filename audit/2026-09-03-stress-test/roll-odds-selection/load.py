"""Flatten the committed snapshot's transactions into one list, mirroring collector.py's
eligibility (full condition, quantity 1, valid roll/price) and stale rule (tts>48h)."""
import json, sys, datetime, statistics
sys.path.insert(0,'/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit')
import ev_ref
import os
SNAP=os.environ.get('SNAP','/home/user/-warera-case1-collector/data/warera_case1_market.json')
TIERS=['basic','reinforced','advanced','elite','legendary','mythic']
def ts(s): return datetime.datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()
def load():
    p=json.load(open(SNAP)); now=ts(p['generated_at'])
    rows=[]
    for code,cat in p['categories'].items():
        slot=cat['slot']
        t=TIERS.index(cat['tier'])+1
        space=ev_ref.roll_space(slot,t); sidx={k:i for i,k in enumerate(space)}
        for tx in cat['transactions']:
            sk=tx.get('skills') or {}
            k=ev_ref.roll_key(slot,sk)
            price=(tx.get('money') or 0)/(tx.get('quantity') or 1)
            elig=(tx.get('state')==tx.get('max_state') and tx.get('max_state') and k is not None and price>0 and tx.get('quantity')==1)
            sold=ts(tx['sold_at']); off=ts(tx['offer_created_at']) if tx.get('offer_created_at') else None
            tts=(sold-off) if off is not None else None
            if tts is not None and tts<0: tts=None
            rows.append({'code':code,'slot':slot,'tier':t,'roll':k,'ri':sidx.get(k,-1),'price':price,'sold':sold,'tts':tts,
                         'seller':tx['seller_id'],'buyer':tx['buyer_id'],'elig':bool(elig),
                         'stale':tts is not None and tts>48*3600,'retained':sold>=now-168*3600,'id':tx['id']})
    return p,now,rows
if __name__=='__main__':
    p,now,rows=load()
    print('rows',len(rows),'elig',sum(r['elig'] for r in rows),'stale',sum(r['stale'] for r in rows),'retained',sum(r['retained'] for r in rows),'bad roll',sum(r['ri']<0 for r in rows))
    print('sales in comps (elig & !stale & retained):',sum(r['elig'] and not r['stale'] and r['retained'] for r in rows))
