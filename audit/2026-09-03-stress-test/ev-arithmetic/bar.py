"""(d) Claim 3: bar as threshold vs per-listing cost; sortNeed edge cases; the line-4410 comment."""
from common import *
snap=load(); bid=snap['commodities']['scraps']['order_book']['best_bid']
m0=E.Model(snap,tax=1,bar_abs=0.0); m1=E.Model(snap,tax=1,bar_abs=0.10)
c0=m0.case(1); c1=m1.case(1); cost=c1['cost']['unit']
print('threshold model: bar 0 gross %.4f (pct %+.2f%%) -> bar 0.10 gross %.4f (pct %+.2f%%); delta %+.4f/case'%(c0['gross'],c0['pct'],c1['gross'],c1['pct'],c1['gross']-c0['gross']))
def cost_model(m,fee):
    """expected value when every listed piece costs `fee` (subtracted), selection by m.need"""
    gross=0.0; listings=0.0
    for t in range(1,7):
        wsum=net=0.0; lst=0.0
        for slot in E.SLOTS:
            v=m.slot_value(slot,t)
            if not v: continue
            w=E.CRAFT_SLOT_WEIGHT[slot]; vals=[(s-fee if sells else m.dismantle(t)) for k,p,s,sells in v['rows']]
            wsum+=w; net+=w*sum(vals)/len(vals); lst+=w*sum(1 for r in v['rows'] if r[3])/len(vals)
        gross+=E.CASE_TIER_ODDS[t-1]*net/wsum; listings+=E.CASE_TIER_ODDS[t-1]*lst/wsum
    return gross,listings
for lab,m in (('select at bar 0',m0),('select at bar 0.10',m1)):
    for fee in (0.0,0.05,0.10,0.20):
        g,l=cost_model(m,fee); print(' per-listing cost %.2f, %-20s gross %.4f edge %+.4f pct %+.2f%% listings/case %.3f'%(fee,lab,g,g-cost,(g-cost)/cost*100,l))
print(' NB: "select at bar b, fee f" is the person who breaks anything not clearing b and pays f attention per listing;')
print('     the page reports the f=0 row. With f=0.10 the optimal threshold is exactly bar=0.10 (list iff sale-0.10>dis), and that row is the true EV of the sorted pile.')
print('\n== the line-4410 comment: "21.5 listings per 100 cases into dismantles, gives up 1.13 gold, 19 of 21.5 Commons" ==')
tot=0.0; gold=0.0; per=[]
for t in range(1,7):
    lt=0.0; gt=0.0
    for slot in E.SLOTS:
        v0=m0.slot_value(slot,t); v1=m1.slot_value(slot,t)
        if not v0: continue
        each=E.CASE_TIER_ODDS[t-1]*E.CRAFT_SLOT_WEIGHT[slot]/v0['space']
        s1={k:sells for k,p,s,sells in v1['rows']}
        for k,p,s,sells in v0['rows']:
            if sells and not s1[k]: lt+=each; gt+=each*(s-m0.dismantle(t))
    per.append('t%d %.2f/%.3f'%(t,lt*100,gt*100)); tot+=lt; gold+=gt
print(' snapshot: %.2f listings per 100 cases become dismantles, giving up %.3f gold per 100 (sortRolls each-weighting: unpriced rolls count as nothing); per tier %s'%(tot*100,gold*100,' '.join(per)))
print(' renormalised (craftExpected) figure: %.3f gold per 100 cases = 100*(%.4f-%.4f)'%((c0['gross']-c1['gross'])*100,c0['gross'],c1['gross']))
# listing counts per 100 cases at each bar (renormalised)
for lab,m in (('bar 0',m0),('bar 0.10',m1)):
    g,l=cost_model(m,0.0); print(' %-8s listings per 100 cases %.1f'%(lab,l*100))
print('\n== sortNeed edge cases ==')
def need(dis,abs_,pct,join):
    bars=[]
    if abs_>0: bars.append(dis+abs_)
    if pct>0: bars.append(dis*(1+pct/100))
    if not bars: return dis
    if len(bars)==1: return bars[0]
    return min(bars) if join=='either' else max(bars)
for t in (1,3,6):
    dis=E.SCRAP_YIELDS[t-1]*bid
    print(' tier %d dis %.3f: abs0.10 both %.4f | pct5 %.4f | abs0.10+pct5 both %.4f either %.4f | abs0+pct5 either %.4f (adding abs bar 0.10 under either LOWERS need by %.4f)'%(
        t,dis,need(dis,0.10,0,'both'),need(dis,0,5,'both'),need(dis,0.10,5,'both'),need(dis,0.10,5,'either'),need(dis,0,5,'either'),need(dis,0,5,'either')-need(dis,0.10,5,'either')))
print(' bid missing (craftDismantle=0): abs0.10 -> need %.3f; pct5 only -> need %.3f (bar vanishes); abs0.10+pct5 either -> need %.3f (bar vanishes); both -> %.3f'%(need(0,0.10,0,'both'),need(0,0,5,'both'),need(0,0.10,5,'either'),need(0,0.10,5,'both')))
for lab,kw in (('bid missing, abs 0.10 (page default)',dict(scrap_bid=0,bar_abs=0.10)),('bid missing, pct 5 only',dict(scrap_bid=0,bar_abs=0,bar_pct=5)),('bid missing, abs 0.10 + pct 5 either',dict(scrap_bid=0,bar_abs=0.10,bar_pct=5,join='either'))):
    c=E.Model(snap,tax=1,**kw).case(1)
    print('  case card with %-40s gross %.4f edge %+.4f pct %+.2f%% broken %s'%(lab,c['gross'],c['edge'],c['pct'],' '.join('%.0f%%'%(p['broken']*100) for p in c['parts'])))
print('\n== bar sweep with join=either, abs 0.10 fixed, pct rising (monotone?) ==')
prev=None
for pct in (0,0.5,1,2,3,5,7.4,7.5,10,20):
    g=E.Model(snap,tax=1,bar_abs=0.10,bar_pct=pct,join='either').case(1)['gross']
    print('  pct %5.1f gross %.4f%s'%(pct,g,'' if prev is None or g<=prev+1e-12 else '  <-- rises'));prev=g
prev=None
print(' join=both:')
for pct in (0,0.5,1,2,3,5,7.4,7.5,10,20):
    g=E.Model(snap,tax=1,bar_abs=0.10,bar_pct=pct,join='both').case(1)['gross']
    print('  pct %5.1f gross %.4f%s'%(pct,g,'' if prev is None or g<=prev+1e-12 else '  <-- rises'));prev=g
