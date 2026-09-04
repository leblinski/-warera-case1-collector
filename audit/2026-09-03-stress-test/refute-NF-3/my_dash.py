"""Independent recount: dash rolls, wide-only rolls, odds-weighted dash share, from snapshot directly."""
import json
S=json.load(open('/home/user/-warera-case1-collector/data/warera_case1_market.json'))
WS=[([21,40],[1,5]),([51,60],[6,10]),([71,90],[11,15]),([101,130],[16,20]),([141,170],[26,35]),([221,300],[41,50])]
SR={'helmet':('criticalDamages',[[1,15],[16,30],[31,50],[71,90],[91,110],[121,150]]),
    'boots':('dodge',[[1,5],[6,10],[11,15],[21,25],[31,40],[51,60]]),
    'chest':('armor',[[1,5],[6,10],[11,15],[21,30],[36,50],[56,70]]),
    'pants':('armor',[[1,5],[6,10],[11,15],[21,30],[36,50],[56,70]]),
    'gloves':('precision',[[1,5],[6,10],[11,15],[21,25],[31,40],[51,60]])}
ODDS=[0.62,0.30,0.071,0.0085,0.0004,0.0001]; W={'weapon':0.30,'helmet':0.14,'chest':0.14,'boots':0.14,'gloves':0.14,'pants':0.14}
WC=['knife','gun','rifle','sniper','tank','jet']
bid=S['commodities']['scraps']['order_book']['best_bid']; print('bid',bid)
tot=space=priced=wide_only=dash=0; dash_share=0.0; per={}
for t in range(1,7):
  for slot in W:
    code=WC[t-1] if slot=='weapon' else slot+str(t)
    cat=S['categories'][code]
    if slot=='weapon':
      a,c=WS[t-1]; sp=[f'{i}/{j}' for i in range(a[0],a[1]+1) for j in range(c[0],c[1]+1)]
      keyf=lambda sk: f"{sk.get('attack')}/{sk.get('criticalChance')}"
    else:
      k,b=SR[slot]; sp=[str(i) for i in range(b[t-1][0],b[t-1][1]+1)]
      keyf=lambda sk,k=k: str(sk.get(k))
    seen={}
    for rk,row in cat['rolls'].items(): seen[keyf(row['exact_roll']['skills'])]=row
    each=ODDS[t-1]*W[slot]/len(sp)
    d=w=p=0
    for key in sp:
      row=seen.get(key); stat=row and (row.get('selected') or row.get('fallback_48h'))
      if stat and stat.get('median') is not None: p+=1; continue
      wide=row and row.get('retained_window')
      if wide and wide.get('median') is not None: w+=1
      else: d+=1; dash_share+=each
    space+=len(sp); priced+=p; wide_only+=w; dash+=d
    if d or w: per[code]=(len(sp),p,w,d,round(100*d*each,3))
print('space',space,'priced',priced,'wide_only',wide_only,'dash',dash,'dash share %.3f%%'%(100*dash_share))
for k,v in per.items(): print(' ',k,'space/priced/wide/dash/dash-share%',v)
print('knife check: 0.62*0.30/100*32 = %.4f%%'%(100*0.62*0.30/100*32))
