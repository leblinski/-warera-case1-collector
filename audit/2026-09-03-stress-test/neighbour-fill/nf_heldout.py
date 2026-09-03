"""(a)(b)(c)(d): held-one-out neighbour test on the committed snapshot, exactly per fillQuiet."""
import sys, argparse, collections, statistics
sys.path.insert(0,'/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit/neighbour-fill')
from nf_common import *
ap=argparse.ArgumentParser(); ap.add_argument('--bar',type=float,default=BAR_ABS); ap.add_argument('--tax',type=float,default=1.0)
a=ap.parse_args(); taxMul=1-a.tax/100
snap=load(); bid=snap['commodities']['scraps']['order_book']['best_bid']
print('generated_at',snap['generated_at'],'scrap bid',bid,'bar',a.bar,'taxMul',taxMul)
TIER=['basic','uncommon','rare','epic','legendary','mythic']

def verdict_of(y,dis):
    return y['sell'] if y['net'] is not None else (y['wide']['price']*taxMul>dis if y.get('wide') else None)
def price_of(y):
    return y['price'] if y['net'] is not None else (y['wide']['price'] if y.get('wide') else None)

# ---- strategies, all applied to a hidden roll x within `others` (same band candidates) ----
def cands(out,slot,x,hidden):
    return [y for y in out if y is not x and y['key']!=hidden and (y['net'] is not None or y.get('wide')) and band(slot,y['key'])==band(slot,x['key'])]
def s_lower(out,slot,x,dis):        # fillQuiet: nearest lower pos, same band
    c=[y for y in cands(out,slot,x,x['key']) if pos(slot,y['key'])<pos(slot,x['key'])]
    if not c: return None
    b=max(c,key=lambda y:pos(slot,y['key'])); return b
def s_either(out,slot,x,dis):       # nearest either direction, tie -> lower
    c=cands(out,slot,x,x['key'])
    if not c: return None
    px=pos(slot,x['key'])
    return min(c,key=lambda y:(abs(pos(slot,y['key'])-px), pos(slot,y['key'])>px))
def s_critdown(out,slot,x,dis):     # weapons: same attack, next crit down (nearest lower crit with data)
    if slot!='weapon': return None
    atk,crit=x['key'].split('/')
    c=[y for y in out if y is not x and (y['net'] is not None or y.get('wide')) and y['key'].split('/')[0]==atk and int(y['key'].split('/')[1])<int(crit)]
    if not c: return None
    return max(c,key=lambda y:int(y['key'].split('/')[1]))
def s_interp(out,slot,x,dis):       # linear interpolation between nearest lower & higher priced in band; one side -> that side
    c=cands(out,slot,x,x['key']); px=pos(slot,x['key'])
    lo=[y for y in c if pos(slot,y['key'])<px]; hi=[y for y in c if pos(slot,y['key'])>px]
    if not lo and not hi: return None
    if lo and hi:
        l=max(lo,key=lambda y:pos(slot,y['key'])); h=min(hi,key=lambda y:pos(slot,y['key']))
        pl,ph=pos(slot,l['key']),pos(slot,h['key'])
        p=price_of(l)+(price_of(h)-price_of(l))*(px-pl)/(ph-pl)
        return {'key':l['key']+'..'+h['key'],'price':p}
    y=max(lo,key=lambda y:pos(slot,y['key'])) if lo else min(hi,key=lambda y:pos(slot,y['key']))
    return {'key':y['key'],'price':price_of(y)}

STRATS=[('fillQuiet lower-same-band',s_lower),('nearest either direction',s_either),
        ('same attack, crit down (weapons)',s_critdown),('linear interpolation',s_interp)]

class Acc:
    def __init__(s): s.n=0;s.ok=0;s.cm=collections.Counter();s.nocov=0;s.lb=0;s.lbn=0;s.err=[];s.abserr=[]
    def add(s,truth,pred,tp,pp):
        if pred is None: s.nocov+=1; return
        s.n+=1; s.ok+=(pred==truth); s.cm[(truth,pred)]+=1
        if pp is not None: s.lbn+=1; s.lb+=(tp>=pp); s.err.append((pp-tp)/tp); s.abserr.append(abs(pp-tp)/tp)
    def acc(s): return s.ok/s.n if s.n else float('nan')
    def line(s): return 'n=%d acc=%.1f%% nocov=%d  cm[T:sell,P:sell]=%d [sell,break]=%d [break,sell]=%d [break,break]=%d'%(
        s.n,100*s.acc(),s.nocov,s.cm[(True,True)],s.cm[(True,False)],s.cm[(False,True)],s.cm[(False,False)])

res={nm:Acc() for nm,_ in STRATS}
per_tier=collections.defaultdict(Acc); per_slot=collections.defaultdict(Acc); per_class=collections.defaultdict(Acc)
per_item=collections.defaultdict(Acc)
truth_counts=collections.Counter(); priced=0
space_total=0; dash=0; dash_each=0.0; from_only=0; wide_only=0; per_tier_dash=collections.Counter(); per_tier_space=collections.Counter()
thin_hidden=Acc()
for t in range(1,7):
    for slot in SLOTS:
        cat=snap['categories'].get(item_code(slot,t))
        if not cat: continue
        out,dis,scrap=build_out(cat['rolls'],slot,t,bid,taxMul,a.bar)
        fill_quiet(out,slot,dis,taxMul)
        space_total+=len(out); per_tier_space[t]+=len(out)
        for x in out:
            if x['net'] is None:
                if x.get('wide'): wide_only+=1
                elif x.get('from'): from_only+=1; dash+=1; dash_each+=x['each']; per_tier_dash[t]+=1
                else: dash+=1; dash_each+=x['each']; per_tier_dash[t]+=1
        for x in out:
            if x['net'] is None: continue
            priced+=1; truth=x['sell']; truth_counts[truth]+=1
            for nm,fn in STRATS:
                b=fn(out,slot,x,dis)
                if b is None: pred=None; pp=None
                elif 'net' in b: pred=verdict_of(b,dis); pp=price_of(b)
                else: pp=b['price']; pred=pp*taxMul>dis
                res[nm].add(truth,pred,x['price'],pp)
                if nm==STRATS[0][0]:
                    per_tier[t].add(truth,pred,x['price'],pp); per_slot[slot].add(truth,pred,x['price'],pp)
                    per_class[truth].add(truth,pred,x['price'],pp); per_item[item_code(slot,t)].add(truth,pred,x['price'],pp)
                    if x['n']<5: thin_hidden.add(truth,pred,x['price'],pp)

print('\n=== (a) held-one-out, hidden roll removed entirely (no net, no wide); neighbour per fillQuiet ===')
print('priced rolls',priced,' true sell',truth_counts[True],' true break',truth_counts[False],
      ' majority base rate %.1f%%'%(100*max(truth_counts.values())/priced))
print('space',space_total,' priced',priced,' wide-only',wide_only,' from-only(dash+guess)',from_only,' dash total',dash,' dash odds-weighted share of draws %.2f%%'%(100*dash_each))
for nm,_ in STRATS:
    r=res[nm]; print('%-34s %s'%(nm,r.line()))
    if r.lbn: print('   %-31s lower-bound share %.1f%% (n=%d)  rel err %s  |err| median %.1f%% p90 %.1f%%'%('',100*r.lb/r.lbn,r.lbn,fmtq(quantiles(r.err)),100*statistics.median(r.abserr),100*quantiles(r.abserr,(0.9,))[0.9]))
print('\nfillQuiet by tier:')
for t in range(1,7): r=per_tier[t]; print('  tier %d %-10s %s  base=%.1f%%  dash %d/%d'%(t,TIER[t-1],r.line(),100*max(r.cm[(True,True)]+r.cm[(True,False)],r.cm[(False,True)]+r.cm[(False,False)])/max(1,r.n),per_tier_dash[t],per_tier_space[t]))
print('fillQuiet by slot:')
for s in SLOTS: r=per_slot[s]; print('  %-7s %s'%(s,r.line()))
print('fillQuiet by true class:')
for c in (True,False): r=per_class[c]; print('  true %-5s %s'%('sell' if c else 'break',r.line()))
print('fillQuiet by item:')
for k,r in per_item.items(): print('  %-10s %s'%(k,r.line()))
print('fillQuiet on hidden rolls that are thin (n<5):',thin_hidden.line())

print('\n=== (c4) retained-window verdict vs selected verdict, rolls with both ===')
both=0;agree=0;dis_r=collections.Counter()
for t in range(1,7):
    for slot in SLOTS:
        cat=snap['categories'].get(item_code(slot,t))
        if not cat: continue
        out,dis,scrap=build_out(cat['rolls'],slot,t,bid,taxMul,a.bar)
        for x in out:
            if x['net'] is None or not x.get('wide'): continue
            both+=1; wv=x['wide']['price']*taxMul>dis
            if wv==x['sell']: agree+=1
            else: dis_r[(item_code(slot,t),'sel=sell' if x['sell'] else 'sel=break')]+=1
print('rolls with both',both,' agree',agree,'(%.1f%%)'%(100*agree/both),' disagree',both-agree)
for k,v in sorted(dis_r.items()): print('  ',k,v)
