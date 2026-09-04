"""Independent forward error test on QUIET rolls: at T0 (gen-72h/-48h/-24h) rebuild roll stats with
collector.aggregate, then for rolls with no selected/fallback median compare candidate prices with
the median of the roll's own comps-eligible non-stale sales in (T0,T0+24h]. Breakdown by item."""
import sys, json, statistics, collections
from datetime import timedelta
sys.path.insert(0,'/home/user/-warera-case1-collector'); import collector as C
S=json.load(open('/home/user/-warera-case1-collector/data/warera_case1_market.json'))
gen=C.parse_time(S['generated_at'])
WS=[([21,40],[1,5]),([51,60],[6,10]),([71,90],[11,15]),([101,130],[16,20]),([141,170],[26,35]),([221,300],[41,50])]
SR={'helmet':('criticalDamages',[[1,15],[16,30],[31,50],[71,90],[91,110],[121,150]]),
    'boots':('dodge',[[1,5],[6,10],[11,15],[21,25],[31,40],[51,60]]),
    'chest':('armor',[[1,5],[6,10],[11,15],[21,30],[36,50],[56,70]]),
    'pants':('armor',[[1,5],[6,10],[11,15],[21,30],[36,50],[56,70]]),
    'gloves':('precision',[[1,5],[6,10],[11,15],[21,25],[31,40],[51,60]])}
WC=['knife','gun','rifle','sniper','tank','jet']
def q(v,p):
  v=sorted(v); i=p*(len(v)-1); lo=int(i); hi=min(lo+1,len(v)-1); return v[lo]+(v[hi]-v[lo])*(i-lo)
def summ(name,e):
  if not e: print('  %-46s n=0'%name); return
  ab=[abs(x) for x in e]
  print('  %-46s n=%4d p50=%+.1f%% |err| p50=%.1f%% p90=%.1f%% within5%%=%.0f%% truth>=cand=%.0f%%'%(name,len(e),100*q(e,.5),100*q(ab,.5),100*q(ab,.9),100*sum(a<=.05 for a in ab)/len(ab),100*sum(x<=0 for x in e)/len(e)))
errs=collections.defaultdict(list)
rows_by={code:[C.unpack_transaction(r,code) for r in cat['transactions']] for code,cat in S['categories'].items()}
for back in (72,48,24):
  T0=gen-timedelta(hours=back); T1=T0+timedelta(hours=24)
  for t in range(1,7):
    for slot in ['weapon','helmet','chest','gloves','pants','boots']:
      code=WC[t-1] if slot=='weapon' else slot+str(t)
      rows=rows_by[code]; rolls=C.aggregate(rows,T0)
      if slot=='weapon':
        a,c=WS[t-1]; sp=[(i,j) for i in range(a[0],a[1]+1) for j in range(c[0],c[1]+1)]
        keyf=lambda sk:(sk.get('attack'),sk.get('criticalChance'))
      else:
        k,b=SR[slot]; sp=[(i,0) for i in range(b[t-1][0],b[t-1][1]+1)]; keyf=lambda sk,k=k:(sk.get(k),0)
      seen={keyf(r['exact_roll']['skills']):r for r in rolls.values()}
      price={}  # key -> (price, kind)
      for key in sp:
        r=seen.get(key); st=r and (r.get('selected') or r.get('fallback_48h'))
        if st and st.get('median') is not None: price[key]=(float(st['median']),'sel')
        elif r and r.get('retained_window',{}).get('median') is not None: price[key]=(float(r['retained_window']['median']),'wide')
      fwd=collections.defaultdict(list)
      for tx in rows:
        if C.stale_listing(tx) or not tx['eligible_for_comps']: continue
        s=C.parse_time(tx['sold_at'])
        if T0<s<=T1: fwd[keyf(tx['skills'])].append(tx['unit_price'])
      for key in sp:
        if key in price and price[key][1]=='sel': continue   # only quiet rolls
        f=fwd.get(key)
        if not f: continue
        truth=statistics.median(f)
        same=[k for k in price if k[1]==key[1] and k!=key]
        lo=[k for k in same if k[0]<key[0]]; hi=[k for k in same if k[0]>key[0]]
        l=max(lo) if lo else None; h=min(hi) if hi else None
        tag='knife' if code=='knife' else ('jet' if code=='jet' else 'other')
        if key in price:  # wide-only
          errs[('wide-only: week median (shown)','all')].append((price[key][0]-truth)/truth)
          errs[('wide-only: week median (shown)',tag)].append((price[key][0]-truth)/truth)
          if l: errs[('wide-only: lower nb price','all')].append((price[l][0]-truth)/truth)
        else:
          if l:
            errs[('from-only: lower nb price (dash shown)','all')].append((price[l][0]-truth)/truth)
            errs[('from-only: lower nb price (dash shown)',tag)].append((price[l][0]-truth)/truth)
            if h:
              p=price[l][0]+(price[h][0]-price[l][0])*(key[0]-l[0])/(h[0]-l[0])
              errs[('from-only: interpolation','all')].append((p-truth)/truth)
              errs[('from-only: interpolation',tag)].append((p-truth)/truth)
          if h: errs[('from-only: upper nb price','all')].append((price[h][0]-truth)/truth)
for k in sorted(errs): summ('%s [%s]'%k,errs[k])
