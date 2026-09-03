"""Python mirror of test60.html sortRolls (4445) + fillQuiet (4496) over a collector snapshot.
Shared by nf_heldout.py / nf_forward.py / nf_code.py."""
import json, sys
sys.path.insert(0,'/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit')
from ev_ref import SCRAP_YIELDS, CASE_TIER_ODDS, CRAFT_SLOT_WEIGHT, SLOTS, WEAPON_CODES, roll_space, roll_key, item_code
SNAP='/home/user/-warera-case1-collector/data/warera_case1_market.json'
TAX_MUL=0.99          # tax input default 1 (line 2814) -> sortTax() = 0.99
BAR_ABS=0.10          # sortMin default (4415)

def load(): return json.load(open(SNAP))
def dismantle(t,bid): return 0 if bid is None else SCRAP_YIELDS[t-1]*bid
def need(t,bid,bar=BAR_ABS): d=dismantle(t,bid); return d+bar if bar>0 else d
def pos(slot,k): return int(k.split('/')[0]) if slot=='weapon' else int(k)
def band(slot,k): return k.split('/')[1] if slot=='weapon' else ''

def build_out(rolls_by_key, slot, t, bid, taxMul=TAX_MUL, bar=BAR_ABS):
    """sortRolls 4445-4494 minus fillQuiet; rolls_by_key = category['rolls'] (schema 4 rows)."""
    seen={}
    for key,row in rolls_by_key.items():
        k=roll_key(slot,(row.get('exact_roll') or {}).get('skills'))
        if k is not None: seen[k]=row
    space=roll_space(slot,t); dis=need(t,bid,bar); scrap=dismantle(t,bid)
    each=CASE_TIER_ODDS[t-1]*CRAFT_SLOT_WEIGHT[slot]/(len(space) or 1)
    out=[]
    for k in space:
        row=seen.get(k); stat=row and (row.get('selected') or row.get('fallback_48h'))
        wide=row and row.get('retained_window')
        if not stat or stat.get('median') is None:
            out.append({'key':k,'net':None,'each':each,
                        'wide':({'price':float(wide['median']),'count':wide.get('count') or 0,
                                 'secs':wide.get('median_time_to_sell_seconds')} if wide and wide.get('median') is not None else None)})
            continue
        net=float(stat['median'])*taxMul; wins=net>dis
        out.append({'key':k,'net':net,'price':float(stat['median']),'margin':net-scrap,'sell':wins,'each':each,
                    'secs':stat.get('median_time_to_sell_seconds'),'n':stat.get('count') or 0,
                    'wide':({'price':float(wide['median']),'count':wide.get('count') or 0} if wide and wide.get('median') is not None else None)})
    return out, dis, scrap

def fill_quiet(out, slot, dis, taxMul=TAX_MUL):
    """fillQuiet 4496-4512, verbatim."""
    for x in out:
        if x['net'] is not None: continue
        if x.get('wide'):
            x['sell']=x['wide']['price']*taxMul>dis; continue
        best=None
        for y in out:
            if y['net'] is None and not y.get('wide'): continue
            if band(slot,y['key'])!=band(slot,x['key']) or pos(slot,y['key'])>=pos(slot,x['key']): continue
            if best is None or pos(slot,y['key'])>pos(slot,best['key']): best=y
        if best is not None:
            x['from']={'key':best['key'],'sell':best['sell'] if best['net'] is not None else best['wide']['price']*taxMul>dis}

def quantiles(vals, qs=(0.05,0.1,0.25,0.5,0.75,0.9,0.95)):
    v=sorted(vals); n=len(v)
    if not n: return {}
    out={}
    for q in qs:
        i=q*(n-1); lo=int(i); hi=min(lo+1,n-1); out[q]=v[lo]+(v[hi]-v[lo])*(i-lo)
    return out
def fmtq(q): return ' '.join('p%d=%+.1f%%'%(int(k*100),v*100) for k,v in q.items())
