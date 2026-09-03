"""Counterfactual: if every roll's selected median were corrected by the out-of-sample next-day
bias measured per tier (b_oos.py, 24h horizon, all roll-origins), what happens to the page's
case EV?  Uses ../ev_ref.py (mirrors the page).  Also: rwmed / selected in place of the median."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import ev_ref
SNAP = '/home/user/-warera-case1-collector/data/warera_case1_market.json'
snap = json.load(open(SNAP))
# signed bias of med48 vs next-day sales, % (from b_oos.out, per-tier tables)
BIAS = {1: 4.33, 2: 2.54, 3: 0.86, 4: 0.39, 5: -0.08, 6: -0.27}
BIAS_SEL = {1: 3.80, 2: 2.58, 3: 1.13, 4: 0.52, 5: -0.01, 6: -0.32}
class Corrected(ev_ref.Model):
    def __init__(self, snap, bias, **kw):
        super().__init__(snap, **kw); self.bias = bias; self._t = None
    def slot_value(self, slot, t):
        self._t = t; return super().slot_value(slot, t)
    def price_of(self, row):
        p = super().price_of(row)
        return None if p is None else p / (1 + self.bias[self._t] / 100)
base = ev_ref.Model(snap, tax=1.0, bar_abs=0.10).case(1)
print('baseline (median):        gross %.4f edge %+.4f pct %+.2f%%' % (base['gross'], base['edge'], base['pct']))
for label, b in [('med48 bias-corrected', BIAS), ('selected bias-corrected', BIAS_SEL),
                 ('uniform -0.68%', {t: 0.68 for t in range(1, 7)}), ('uniform -1.37% (6h-horizon bias)', {t: 1.37 for t in range(1, 7)})]:
    c = Corrected(snap, b, tax=1.0, bar_abs=0.10).case(1)
    print('%-32s gross %.4f edge %+.4f pct %+.2f%%  per-tier net: %s' % (label, c['gross'], c['edge'], c['pct'],
          ' '.join('%.3f' % p['net'] if p else '-' for p in c['parts'])))
for est in ['weighted_median', 'recency_mean', 'retained_median']:
    c = ev_ref.Model(snap, tax=1.0, bar_abs=0.10, estimator=est).case(1)
    print('%-32s gross %.4f edge %+.4f pct %+.2f%%' % (est, c['gross'], c['edge'], c['pct']))
# how far can the median be wrong before the case verdict flips? scale all medians by f
lo, hi = 0.90, 1.0
for _ in range(30):
    mid = (lo + hi) / 2
    c = Corrected(snap, {t: (1 / mid - 1) * 100 for t in range(1, 7)}, tax=1.0, bar_abs=0.10).case(1)
    if c['edge'] > 0: hi = mid
    else: lo = mid
print('case edge crosses 0 when every median is scaled by %.4f (i.e. medians overstate next-day prices by %.2f%%)' % (hi, (1 / hi - 1) * 100))
