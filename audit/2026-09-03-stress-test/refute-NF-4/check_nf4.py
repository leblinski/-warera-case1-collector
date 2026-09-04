"""Independent check of NF-4 from the raw snapshot: for every weapon roll with a priced
median, compare the heat-grid test (sortHeat 5337: margin=net-scrap >= 0) with the list test
(sortRolls 4487: net > need = scrap + bar). Also check wide-only cells (0.99 vs taxMul)."""
import json, sys
tax=float(sys.argv[1]) if len(sys.argv)>1 else 1.0
bar=float(sys.argv[2]) if len(sys.argv)>2 else 0.10
taxMul=1-tax/100
snap=json.load(open('/home/user/-warera-case1-collector/data/warera_case1_market.json'))
bid=snap['commodities']['scraps']['order_book']['best_bid']
Y=[6,18,54,162,486,1458]; codes=['knife','gun','rifle','sniper','tank','jet']
priced=0; wide=0; bad=[]; badw=[]
for t,code in enumerate(codes,1):
    scrap=Y[t-1]*bid; need=scrap+bar
    for key,row in snap['categories'][code]['rolls'].items():
        st=row.get('selected') or row.get('fallback_48h')
        if st and st.get('median') is not None:
            priced+=1
            net=float(st['median'])*taxMul; m=net-scrap
            heat=m>=0; lst=net>need
            if heat!=lst: bad.append((code,key,float(st['median']),round(m,4),round(net,4),round(need,4),st.get('count')))
        else:
            w=row.get('retained_window')
            if w and w.get('median') is not None:
                wide+=1
                heat=float(w['median'])*0.99-scrap>=0; lst=float(w['median'])*taxMul>need
                if heat!=lst: badw.append((code,key,float(w['median'])))
print('tax',tax,'bar',bar,'bid',bid,'priced weapon rolls',priced,'wide-only',wide)
print('priced cells: heat(margin>=0) != list(net>need):',len(bad))
for b in bad: print('  ',b)
print('wide-only cells: heat(0.99) != list(taxMul,need):',len(badw), badw)
