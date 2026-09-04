"""Independent check of ROS-5: sniper max-roll excess, day heterogeneity, Epic armour max cells,
price step at 130, EV sensitivity of a 16% top-roll excess, power calc."""
import json,sys,math,collections,statistics,glob,datetime
sys.path.insert(0,'/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit')
import ev_ref
SNAP='/home/user/-warera-case1-collector/data/warera_case1_market.json'
p=json.load(open(SNAP))
def ts(s): return datetime.datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()
now=ts(p['generated_at'])
def sf(x,df):
    z=((x/df)**(1/3)-(1-2/(9*df)))/math.sqrt(2/(9*df)); return 0.5*math.erfc(z/math.sqrt(2))
def zmax(counts):
    n=sum(counts);k=len(counts);pk=1/k;e=n*pk;sd=math.sqrt(n*pk*(1-pk));return counts[-1],e,(counts[-1]-e)/sd, counts[-1]/statistics.mean(counts[:-1])
# 1. sniper marginals, all tx in retained window (7d) and comps-only (elig,non-stale)
sn=p['categories']['sniper']['transactions']
def ok(tx): return tx.get('state')==tx.get('max_state') and tx.get('quantity')==1 and (tx.get('money') or 0)>0
def stale(tx):
    o=tx.get('offer_created_at'); 
    if not o: return False
    d=ts(tx['sold_at'])-ts(o); return d>48*3600
att=collections.Counter(); crit=collections.Counter(); attc=collections.Counter(); critc=collections.Counter()
for tx in sn:
    sk=tx.get('skills') or {}; a=sk.get('attack'); c=sk.get('criticalChance')
    if a is None or c is None: continue
    att[a]+=1; crit[c]+=1
    if ok(tx) and not stale(tx): attc[a]+=1; critc[c]+=1
A=[att[a] for a in range(101,131)]; C=[crit[c] for c in range(16,21)]
Ac=[attc[a] for a in range(101,131)]; Cc=[critc[c] for c in range(16,21)]
print('sniper n=%d; attack130 %d vs rest mean %.1f (x%.3f); multinomial z=%.2f (exp %.1f)'%(sum(A),A[-1],statistics.mean(A[:-1]),A[-1]/statistics.mean(A[:-1]),zmax(A)[2],zmax(A)[1]))
print('  crit20 %d vs rest mean %.1f (x%.3f); z=%.2f'%(C[-1],statistics.mean(C[:-1]),C[-1]/statistics.mean(C[:-1]),zmax(C)[2]))
print('  comps-only: attack130 x%.3f z=%.2f ; crit20 x%.3f z=%.2f'%(Ac[-1]/statistics.mean(Ac[:-1]),zmax(Ac)[2],Cc[-1]/statistics.mean(Cc[:-1]),zmax(Cc)[2]))
print('  attack counts 125..130:',A[-6:],' attack 101..104:',A[:4])
# chi2 for attack marginal with and without 130
def chi(cs):
    n=sum(cs);e=n/len(cs);return sum((o-e)**2/e for o in cs),len(cs)-1
c2,df=chi(A);print('  attack marginal chi2=%.1f df=%d p=%.2g ; excluding 130: chi2=%.1f df=%d p=%.2g'%(c2,df,sf(c2,df),*chi(A[:-1]),sf(*chi(A[:-1]))))
c2,df=chi(C);print('  crit marginal chi2=%.1f df=%d p=%.2g ; excluding 20: chi2=%.1f df=%d p=%.2g'%(c2,df,sf(c2,df),*chi(C[:-1]),sf(*chi(C[:-1]))))
# 2. price step by attack (median price non-stale eligible), 124..130
byA=collections.defaultdict(list)
for tx in sn:
    sk=tx.get('skills') or {}
    if sk.get('attack') is None or not ok(tx) or stale(tx): continue
    byA[sk['attack']].append(tx['money'])
print('  median price by attack 124..130:',[(a,round(statistics.median(byA[a]),2)) for a in range(124,131)])
byC=collections.defaultdict(list)
for tx in sn:
    sk=tx.get('skills') or {}
    if sk.get('criticalChance') is None or not ok(tx) or stale(tx): continue
    byC[sk['criticalChance']].append(tx['money'])
print('  median price by crit 16..20:',[(c,round(statistics.median(byC[c]),2)) for c in range(16,21)])
# 3. day heterogeneity of the 130 share across archive days + partial 09-03 from snapshot
days={}
for f in sorted(glob.glob('/home/user/-warera-case1-collector/data/archive/*.json')):
    a=json.load(open(f)); d=a['date']; m=0;n=0; cm=0
    for s in a['sales']:
        if s.get('item_code')!='sniper': continue
        sk=s.get('skills') or {}
        if sk.get('attack') is None: continue
        n+=1; m+=sk['attack']==130; cm+=sk.get('criticalChance')==20
    days[d]=(m,n,cm)
m=n=cm=0
for tx in sn:
    if tx['sold_at']>='2026-09-03':
        sk=tx.get('skills') or {}
        if sk.get('attack') is None: continue
        n+=1;m+=sk['attack']==130;cm+=sk.get('criticalChance')==20
days['2026-09-03(partial to 15:30Z)']=(m,n,cm)
print('\nsniper per day: 130 count / n / share / x vs uniform(1/30) | crit20 share x vs 1/5')
for d,(m,n,cm) in days.items(): print('  %s %4d /%5d = %.4f  x%.2f | crit20 x%.2f'%(d,m,n,m/n,(m/n)*30,(cm/n)*5))
# homogeneity chi2 (2xK) on the 5 archive days and on all 6
def homog(items):
    M=sum(m for m,n,_ in items);N=sum(n for m,n,_ in items);pbar=M/N;c2=0
    for m,n,_ in items:
        e=n*pbar;c2+=(m-e)**2/e+((n-m)-(n-e))**2/(n-e)
    return c2,len(items)-1
arch=[v for k,v in days.items() if 'partial' not in k]
c2,df=homog(arch);print('  homogeneity of 130 share across 5 archive days: chi2=%.2f df=%d p=%.3f'%(c2,df,sf(c2,df)))
c2,df=homog(list(days.values()));print('  across 6 days incl partial 09-03: chi2=%.2f df=%d p=%.3f'%(c2,df,sf(c2,df)))
# trend test: Cochran-Armitage-ish linear regression of share on day index (archive 5)
xs=list(range(5));ys=[m/n for m,n,_ in arch];ws=[n for _,n,_ in arch]
xbar=sum(w*x for w,x in zip(ws,xs))/sum(ws);ybar=sum(w*y for w,y in zip(ws,ys))/sum(ws)
b=sum(w*(x-xbar)*(y-ybar) for w,x,y in zip(ws,xs,ys))/sum(w*(x-xbar)**2 for w,x in zip(ws,xs))
seb=math.sqrt(ybar*(1-ybar)/sum(w*(x-xbar)**2 for w,x in zip(ws,xs)))
print('  linear trend of 130 share per day: slope %.5f/day, z=%.2f (share 1/30=%.4f)'%(b,b/seb,1/30))
# first-half vs second-half of retained window (independent split of same data)
mid=now-84*3600;h=[[0,0],[0,0]]
for tx in sn:
    sk=tx.get('skills') or {}
    if sk.get('attack') is None: continue
    i=ts(tx['sold_at'])>=mid;h[i][1]+=1;h[i][0]+=sk['attack']==130
print('  retained window halves: first %d/%d x%.2f, second %d/%d x%.2f; 2x2 chi2 p=%.3f'%(h[0][0],h[0][1],h[0][0]/h[0][1]*30,h[1][0],h[1][1],h[1][0]/h[1][1]*30,sf(*homog([(h[0][0],h[0][1],0),(h[1][0],h[1][1],0)]))))
# 4. max-cell z for all items where every roll sells (Epic+ armour) and Epic weapons, all tx
print('\nmax-cell of band, all 7d tx, per item (Epic/Legendary/Mythic):')
TIERS=['basic','reinforced','advanced','elite','legendary','mythic']
res={}
for code,cat in p['categories'].items():
    t=TIERS.index(cat['tier'])+1
    if t<4: continue
    slot=cat['slot']
    if slot=='weapon':
        (a0,a1),(c0,c1)=ev_ref.WEAPON_STATS[t-1]
        ac=collections.Counter();cc=collections.Counter()
        for tx in cat['transactions']:
            sk=tx.get('skills') or {}
            if sk.get('attack') is None: continue
            ac[sk['attack']]+=1;cc[sk['criticalChance']]+=1
        A_=[ac[a] for a in range(a0,a1+1)];C_=[cc[c] for c in range(c0,c1+1)]
        o,e,z,x=zmax(A_);o2,e2,z2,x2=zmax(C_);o3,e3,z3,x3=zmax(A_[::-1])
        print('  %-8s n=%5d attack max %4d exp %6.1f x%.2f z=%5.2f | attack min x%.2f z=%5.2f | crit max %4d exp %6.1f x%.2f z=%5.2f'%(code,sum(A_),o,e,x,z,x3,z3,o2,e2,x2,z2))
        res[code]={'att_x':x,'att_z':z,'crit_x':x2,'crit_z':z2}
    else:
        cnt=collections.Counter()
        for tx in cat['transactions']:
            sk=tx.get('skills') or {}
            if not sk: continue
            v=list(sk.values())[0];cnt[v]+=1
        space=ev_ref.roll_space(slot,t);vals=[int(k) for k in space]
        cs=[cnt[v] for v in vals]
        o,e,z,x=zmax(cs);o3,e3,z3,x3=zmax(cs[::-1])
        print('  %-8s n=%5d max %4d exp %6.1f x%.2f z=%5.2f | min x%.2f z=%5.2f | counts %s'%(code,sum(cs),o,e,x,z,x3,z3,cs))
        res[code]={'x':x,'z':z,'min_x':x3,'min_z':z3}
json.dump(res,open('r1_maxcells.json','w'),indent=1)
