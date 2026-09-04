import json,glob,statistics,datetime
exec(open('indep.py').read().split('def ev(')[0])  # reuse loaders/constants
tier=lambda code: WEAP.index(code)+1 if code in WEAP else int(code[-1])
nf=0
for defn in ('p25_48','min48','last','fast30'):
    out=[]
    for t in range(1,7):
        rs=[]
        for code,d in rolls.items():
            if tier(code)!=t: continue
            for k,r in d.items():
                pr=[x[1] for x in r]; med=statistics.median(pr)
                if defn=='p25_48': v=Q(pr,0.25)
                elif defn=='min48': v=min(pr)
                elif defn=='last': v=max(r)[1]
                else:
                    f=[x[1] for x in r if x[2] is not None and x[2]<=1800]; v=statistics.median(f) if f else None
                if v is None: continue
                rs.append(v/med)
        out.append('t%d %.3f(n%d)'%(t,statistics.fmean(rs),len(rs)))
        if defn=='fast30': nf+=len(rs)
    print(defn,' '.join(out))
print('rolls with a fast sale',nf)
