"""Reference re-implementation of test60.html's Case/Craft EV arithmetic, run on the
committed collector snapshot. Mirrors craftSlotValue / craftExpected / paintCase /
craftWalk / sortNeed / craftDismantle exactly, so any difference from the page is a bug
in one of them, and any agreement lets the page's number be interrogated offline."""
import json, sys, argparse, statistics

SCRAP_YIELDS=[6,18,54,162,486,1458]
CASE_TIER_ODDS=[0.62,0.30,0.071,0.0085,0.0004,0.0001]
CRAFT_STEEL=[1,2,4,8,16,32]
CRAFT_SLOT_WEIGHT={'weapon':0.30,'helmet':0.14,'chest':0.14,'boots':0.14,'gloves':0.14,'pants':0.14}
SLOTS=['weapon','helmet','chest','gloves','pants','boots']
WEAPON_CODES=['knife','gun','rifle','sniper','tank','jet']
WEAPON_STATS=[((21,40),(1,5)),((51,60),(6,10)),((71,90),(11,15)),((101,130),(16,20)),((141,170),(26,35)),((221,300),(41,50))]
STAT_RANGES={
 'helmet':('criticalDamages',[(1,15),(16,30),(31,50),(71,90),(91,110),(121,150)]),
 'boots':('dodge',[(1,5),(6,10),(11,15),(21,25),(31,40),(51,60)]),
 'chest':('armor',[(1,5),(6,10),(11,15),(21,30),(36,50),(56,70)]),
 'pants':('armor',[(1,5),(6,10),(11,15),(21,30),(36,50),(56,70)]),
 'gloves':('precision',[(1,5),(6,10),(11,15),(21,25),(31,40),(51,60)]),
}
def item_code(slot,t): return WEAPON_CODES[t-1] if slot=='weapon' else slot+str(t)
def roll_space(slot,t):
    if slot=='weapon':
        (a0,a1),(c0,c1)=WEAPON_STATS[t-1]
        return ['%d/%d'%(a,c) for a in range(a0,a1+1) for c in range(c0,c1+1)]
    key,tiers=STAT_RANGES[slot]; lo,hi=tiers[t-1]
    return [str(v) for v in range(lo,hi+1)]
def roll_key(slot,skills):
    if not skills: return None
    if slot=='weapon':
        if skills.get('attack') is None or skills.get('criticalChance') is None: return None
        return '%s/%s'%(skills['attack'],skills['criticalChance'])
    key=STAT_RANGES[slot][0]
    return None if skills.get(key) is None else str(skills[key])

def craft_walk(book,qty):
    lst=sorted(book['sell_orders'],key=lambda o:o['price'])
    need=qty;cost=0.0;last=None
    for o in lst:
        if need<=0:break
        take=min(need,o['quantity'] or 0)
        if take<=0:continue
        cost+=take*o['price'];need-=take;last=o['price']
    if last is None:return None
    if need>0:return {'unit':(cost+need*last)/qty,'cost':cost+need*last,'thin':True}
    return {'unit':cost/qty,'cost':cost,'thin':False}

class Model:
    def __init__(self,snap,tax=1.0,bar_abs=0.10,bar_pct=0.0,join='both',estimator='median',weighting='even',scrap_bid=None):
        self.cats=snap['categories']; self.books=snap['commodities']
        self.taxMul=1-tax/100; self.bar_abs=bar_abs; self.bar_pct=bar_pct; self.join=join
        self.estimator=estimator; self.weighting=weighting
        self.scrap_bid=scrap_bid if scrap_bid is not None else self.books['scraps']['order_book']['best_bid']
    def dismantle(self,t): return 0 if self.scrap_bid is None else SCRAP_YIELDS[t-1]*self.scrap_bid
    def need(self,t):
        dis=self.dismantle(t);bars=[]
        if self.bar_abs>0:bars.append(dis+self.bar_abs)
        if self.bar_pct>0:bars.append(dis*(1+self.bar_pct/100))
        if not bars:return dis
        if len(bars)==1:return bars[0]
        return min(bars) if self.join=='either' else max(bars)
    def price_of(self,row):
        st=row['selected'] or row['fallback_48h']
        if not st or st.get('median') is None:return None
        if self.estimator=='median':return st['median']
        if self.estimator=='weighted_median':return st['weighted_median']
        if self.estimator=='recency_mean':return st['recency_weighted_price']
        if self.estimator=='min':return st['min']
        if self.estimator=='retained_median':
            w=row.get('retained_window') or {}
            return w.get('median') if w.get('median') is not None else st['median']
        raise ValueError(self.estimator)
    def slot_value(self,slot,t):
        cat=self.cats.get(item_code(slot,t))
        if not cat:return None
        seen={}
        for key,row in cat['rolls'].items():
            k=roll_key(slot,(row.get('exact_roll') or {}).get('skills'))
            if k is not None:seen[k]=row
        space=roll_space(slot,t);dis=self.dismantle(t);need=self.need(t)
        wsum=vsum=0.0;covered=samples=broken=0;rows=[]
        for k in space:
            row=seen.get(k)
            if not row:continue
            price=self.price_of(row)
            if price is None:continue
            w=1.0
            if self.weighting=='as_traded':
                w=(row.get('fallback_48h') or {}).get('count') or 0
                if w<=0:continue
            sale=price*self.taxMul;sells=sale>need;best=sale if sells else dis
            if not sells:broken+=w
            covered+=1;samples+=(row.get('fallback_48h') or {}).get('count') or 0
            wsum+=w;vsum+=w*best;rows.append((k,price,sale,sells))
        if not wsum:return None
        return {'net':vsum/wsum,'covered':covered,'space':len(space),'samples':samples,'broken':broken,'weight':wsum,'rows':rows}
    def craft_expected(self,t):
        wsum=net=0.0;covered=space=samples=missing=0;broken=rollw=0.0;per={}
        for slot in SLOTS:
            w=CRAFT_SLOT_WEIGHT[slot];v=self.slot_value(slot,t)
            if not v:missing+=1;continue
            per[slot]=v
            wsum+=w;net+=w*v['net'];covered+=v['covered'];space+=v['space'];samples+=v['samples']
            broken+=w*v['broken'];rollw+=w*v['weight']
        if not wsum:return None
        return {'net':net/wsum,'covered':covered,'space':space,'samples':samples,'missingSlots':missing,
                'brokenShare':broken/rollw if rollw>0 else 0,'per':per}
    def case(self,n=1):
        cost=craft_walk(self.books['case1']['order_book'],n)
        gross=0.0;parts=[];covered=space=samples=missing=0
        for t in range(1,7):
            e=self.craft_expected(t);odds=CASE_TIER_ODDS[t-1]
            if not e:missing+=1;parts.append(None);continue
            covered+=e['covered'];space+=e['space'];samples+=e['samples']
            gross+=odds*e['net'];parts.append({'net':e['net'],'odds':odds,'add':odds*e['net'],'broken':e['brokenShare'],'exp':e})
        var=sum(p['odds']*(p['net']-gross)**2 for p in parts if p)
        return {'gross':gross,'cost':cost,'edge':gross-cost['unit'],'pct':(gross*n-cost['cost'])/cost['cost']*100,
                'parts':parts,'sd':var**0.5,'covered':covered,'space':space,'samples':samples,'missing':missing}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--snap',default='/home/user/-warera-case1-collector/data/warera_case1_market.json')
    ap.add_argument('--tax',type=float,default=1.0);ap.add_argument('--bar',type=float,default=0.10)
    a=ap.parse_args()
    snap=json.load(open(a.snap))
    print('generated_at',snap['generated_at'])
    m=Model(snap,tax=a.tax,bar_abs=a.bar)
    c=m.case(1)
    print('scrap best_bid',m.scrap_bid,' case unit cost (n=1)',c['cost'])
    print('CASE gross %.4f  edge %.4f  pct %+.2f%%  sd %.3f  coverage %d/%d  samples %d'%(c['gross'],c['edge'],c['pct'],c['sd'],c['covered'],c['space'],c['samples']))
    for t,p in enumerate(c['parts'],1):
        if not p:print(' tier',t,'no data');continue
        e=p['exp'];print(' tier %d odds %.4f net %.4f adds %.4f broken %.0f%%  covered %d/%d  slots:'%(t,p['odds'],p['net'],p['add'],p['broken']*100,e['covered'],e['space']),
              ' '.join('%s=%.3f(%d/%d)'%(s,v['net'],v['covered'],v['space']) for s,v in e['per'].items()))
    print('\nBar sweep (abs bar in gold -> case gross):')
    prev=None
    for bar in [0,0.02,0.05,0.1,0.15,0.2,0.3,0.5,0.75,1,2,5,1000]:
        g=Model(snap,tax=a.tax,bar_abs=bar).case(1)['gross']
        flag='' if prev is None or g<=prev+1e-12 else '  <-- NOT monotone'
        print('  bar %7.2f  gross %.4f%s'%(bar,g,flag));prev=g
    print('\nEstimator / weighting sensitivity (bar %.2f):'%a.bar)
    for est in ['median','weighted_median','recency_mean','min','retained_median']:
        for wt in ['even','as_traded']:
            g=Model(snap,tax=a.tax,bar_abs=a.bar,estimator=est,weighting=wt).case(1)
            print('  %-16s %-9s gross %.4f edge %+.4f pct %+.2f%%'%(est,wt,g['gross'],g['edge'],g['pct']))
    print('\nCraft rows (tax %.1f%%, bar %.2f):'%(a.tax,a.bar))
    for t in range(1,7):
        e=m.craft_expected(t)
        sc=craft_walk(m.books['scraps']['order_book'],SCRAP_YIELDS[t-1]);st=craft_walk(m.books['steel']['order_book'],CRAFT_STEEL[t-1])
        if not e or not sc or not st:print(' tier',t,'-');continue
        cost=sc['cost']+st['cost'];print(' tier %d cost %.3f sells %.3f profit %+.1f%%'%(t,cost,e['net'],(e['net']-cost)/cost*100))
if __name__=='__main__':main()
