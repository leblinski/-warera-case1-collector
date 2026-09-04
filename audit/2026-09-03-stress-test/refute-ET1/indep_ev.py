import sys,json
sys.path.insert(0,'/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit')
import ev_ref
snap=json.load(open('/home/user/-warera-case1-collector/data/warera_case1_market.json'))
class Scaled(ev_ref.Model):
    f=1.0
    def price_of(self,row):
        p=super().price_of(row); return None if p is None else p*self.f
def edge(f,est='median'):
    m=Scaled(snap,tax=1.0,bar_abs=0.10,estimator=est); m.f=f; return m.case(1)
b=edge(1.0); print('baseline gross %.4f edge %+.4f pct %+.2f%% ask %.2f'%(b['gross'],b['edge'],b['pct'],b['gross']-b['edge']))
for est in ['weighted_median','recency_mean','retained_median','min']:
    c=edge(1.0,est); print('%-16s gross %.4f edge %+.4f pct %+.2f%%'%(est,c['gross'],c['edge'],c['pct']))
for f in [0.999,0.99,0.95,0.92,0.915,0.91,0.90]:
    c=edge(f); print('scale %.3f gross %.4f edge %+.4f pct %+.2f%%'%(f,c['gross'],c['edge'],c['pct']))
lo,hi=0.85,1.0
for _ in range(40):
    mid=(lo+hi)/2
    if edge(mid)['edge']>0: hi=mid
    else: lo=mid
print('crossing f=%.4f  -> medians overstate by %.2f%%'%(hi,(1/hi-1)*100))
# also with weighted_median as the estimator
lo,hi=0.85,1.0
for _ in range(40):
    mid=(lo+hi)/2
    if edge(mid,'weighted_median')['edge']>0: hi=mid
    else: lo=mid
print('crossing (weighted_median) f=%.4f -> %.2f%%'%(hi,(1/hi-1)*100))
