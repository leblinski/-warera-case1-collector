"""Shared loader for the estimator-thin audit. Reads the published shards
(../public/prices/*.json, rows [unit_price, sold_at_epoch_s, time_to_sell_s|null, roll_index])
and applies the collector's stale-listing rule (time_to_sell > 48h excluded from statistics)."""
import json, glob, os, statistics, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PUBLIC = os.path.normpath(os.path.join(HERE, '..', '..', 'public'))
STALE_S = 48 * 3600
H = 3600

def now_epoch():
    idx = json.load(open(os.path.join(PUBLIC, 'index.json')))
    t = idx['generated_at'].replace('Z', '+00:00')
    return int(datetime.datetime.fromisoformat(t).timestamp())

def load(drop_stale=True):
    """Return dict (item_code, roll_index) -> sorted list of (t, price, tts), plus meta per item."""
    rolls = {}
    meta = {}
    for f in sorted(glob.glob(os.path.join(PUBLIC, 'prices', '*.json'))):
        d = json.load(open(f))
        code = d['item_code']
        meta[code] = {'tier': d['tier'], 'slot': d['slot'], 'rolls': d['rolls'], 'summary': d['summary']}
        for p, t, tts, ri in d['sales']:
            if drop_stale and tts is not None and tts > STALE_S:
                continue
            rolls.setdefault((code, ri), []).append((t, p, tts))
    for k in rolls:
        rolls[k].sort()
    return rolls, meta

def median(xs):
    return statistics.median(xs)

def quantile(xs, q):
    """Inclusive (type 7) quantile, same as numpy default."""
    s = sorted(xs)
    n = len(s)
    if n == 1:
        return s[0]
    pos = (n - 1) * q
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)

def weighted_median(prices, weights):
    """Collector's definition (summarize()): first price, ascending, whose cumulative weight >= half."""
    half = sum(weights) / 2
    c = 0.0
    for p, w in sorted(zip(prices, weights)):
        c += w
        if c >= half:
            return p
    return prices[-1]

def trimmed_mean(xs, frac_each_side=0.2):
    s = sorted(xs)
    k = int(len(s) * frac_each_side)
    core = s[k:len(s) - k] if len(s) - 2 * k > 0 else s
    return sum(core) / len(core)
