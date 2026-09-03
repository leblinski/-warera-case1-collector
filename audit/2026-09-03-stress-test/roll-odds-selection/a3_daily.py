"""(a) cont.: is the Epic max-roll excess stable across independent whole-day archives?"""
import json, glob, collections, statistics, math
out={}
for f in sorted(glob.glob('/home/user/-warera-case1-collector/data/archive/*.json')):
    a=json.load(open(f));d=a['date'];out[d]={}
    line=[]
    for code,(a0,a1),(c0,c1) in [('sniper',(101,130),(16,20)),('tank',(141,170),(26,35)),('gun',(51,60),(6,10)),('rifle',(71,90),(11,15))]:
        att=collections.Counter();crit=collections.Counter()
        for s in a['sales']:
            if s.get('item_code')!=code:continue
            sk=s.get('skills') or {}
            if sk.get('attack') is None:continue
            att[sk['attack']]+=1;crit[sk['criticalChance']]+=1
        n=sum(att.values());rest=[att[x] for x in range(a0,a1)];mx=att[a1]
        crest=[crit[x] for x in range(c0,c1)];cmx=crit[c1]
        ea=statistics.mean(rest);ec=statistics.mean(crest)
        out[d][code]={'n':n,'att_max':mx,'att_rest_mean':ea,'att_excess':mx/ea if ea else None,'att_sigma':(mx-ea)/math.sqrt(ea) if ea else None,'crit_max':cmx,'crit_rest_mean':ec,'crit_excess':cmx/ec if ec else None,'att_min':att[a0]}
        line.append('%s n=%d att%d %d vs %.0f (x%.2f, %.1fs; min x%.2f) crit%d %d vs %.0f (x%.2f)'%(code,n,a1,mx,ea,mx/ea,(mx-ea)/math.sqrt(ea),att[a0]/ea,c1,cmx,ec,cmx/ec))
    print(d,' | '.join(line))
# pooled sniper across days
tot=sum(out[d]['sniper']['att_max'] for d in out);rest=sum(out[d]['sniper']['att_rest_mean'] for d in out)
print('sniper pooled 5 days: att130 %d vs rest-mean %.0f -> x%.3f, %.1f sigma; crit20 x%.3f'%(tot,rest,tot/rest,(tot-rest)/math.sqrt(rest),sum(out[d]['sniper']['crit_max'] for d in out)/sum(out[d]['sniper']['crit_rest_mean'] for d in out)))
json.dump(out,open('a3_daily.json','w'),indent=1)
