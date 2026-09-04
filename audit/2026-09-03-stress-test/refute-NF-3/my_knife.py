import json
S=json.load(open('/home/user/-warera-case1-collector/data/warera_case1_market.json'))
cat=S['categories']['knife']; seen={}
for r in cat['rolls'].values():
  sk=r['exact_roll']['skills']; seen[(sk['attack'],sk['criticalChance'])]=r
price={}
for a in range(21,41):
  for c in range(1,6):
    r=seen.get((a,c)); st=r and (r.get('selected') or r.get('fallback_48h'))
    if st and st.get('median') is not None: price[(a,c)]=('sel',float(st['median']))
    elif r and r['retained_window'].get('median') is not None: price[(a,c)]=('wide',float(r['retained_window']['median']))
dash=[(a,c) for a in range(21,41) for c in range(1,6) if (a,c) not in price]
print('knife dash rolls',len(dash),sorted(dash,key=lambda k:(k[1],k[0])))
print('dash by attack bucket: <=30:',sum(a<=30 for a,c in dash),' >30:',sum(a>30 for a,c in dash))
# held-one-out lower-neighbour on knife priced rolls: ties vs strict
ge=gt=n=0
for k,(kind,p) in price.items():
  if kind!='sel': continue
  lo=[j for j in price if j[1]==k[1] and j[0]<k[0]]
  if not lo: continue
  l=max(lo); n+=1; ge+=p>=price[l][1]; gt+=p>price[l][1]
print('knife held-out lower nb: n=%d truth>=nb %.0f%% strict %.0f%%'%(n,100*ge/n,100*gt/n))
# all items: ties share (inclusive minus strict) recomputed independently
