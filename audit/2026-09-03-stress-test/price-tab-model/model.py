"""Pure-Python mirror of test60.html's Price-tab Trends engine (lines 5750-5990, 6009).

Usage: python3 model.py --item knife --roll attack=40,criticalChance=5 --floor 4.2 [--age 48h] [--mode quick|patient] [--deep] [--now ISO]
Default `now` = the shard's generated_at, which is what the Playwright run freezes Date.now to.
"""
import json, math, sys, argparse, datetime

PUBLIC = '/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/public'
WEAPON_CRIT_WEIGHT = 4.15
WEAPON_STATS = [((21, 40), (1, 5)), ((51, 60), (6, 10)), ((71, 90), (11, 15)), ((101, 130), (16, 20)),
                ((141, 170), (26, 35)), ((221, 300), (41, 50))]
STAT_RANGES = {
    'helmet': ('criticalDamages', [(1, 15), (16, 30), (31, 50), (71, 90), (91, 110), (121, 150)]),
    'boots': ('dodge', [(1, 5), (6, 10), (11, 15), (21, 25), (31, 40), (51, 60)]),
    'chest': ('armor', [(1, 5), (6, 10), (11, 15), (21, 30), (36, 50), (56, 70)]),
    'pants': ('armor', [(1, 5), (6, 10), (11, 15), (21, 30), (36, 50), (56, 70)]),
    'gloves': ('precision', [(1, 5), (6, 10), (11, 15), (21, 25), (31, 40), (51, 60)]),
}
TIER_OF_RARITY = {'common': 1, 'uncommon': 2, 'rare': 3, 'epic': 4, 'legendary': 5, 'mythic': 6}
MAX_HISTORY_HOURS = 168
MIN_WINDOW_ROWS = 5


def parse_iso(s):
    return datetime.datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp() * 1000


def round3(n):
    # JS: Math.round((n+EPSILON)*1000)/1000 ; Math.round rounds half up toward +inf
    x = (n + sys.float_info.epsilon) * 1000
    return math.floor(x + 0.5) / 1000


def load_shard(code):
    s = json.load(open(f'{PUBLIC}/prices/{code}.json'))
    rolls = s['rolls']
    sales = []
    for i, row in enumerate(s['sales']):
        sold = row[1] * 1000
        sales.append({'_id': f'{code}:{i}', 'money': row[0], 'createdAt': sold,
                      'offerCreatedAt': None if row[2] is None else sold - row[2] * 1000,
                      'skills': rolls[row[3]]['skills']})
    s['_sales'] = sales
    return s


class State:
    def __init__(self, shard, rolls, floor, age=None, mode='quick', higher_cheaper=False, now=None):
        self.slot = shard['slot']
        self.tier = TIER_OF_RARITY[shard['rarity']]
        self.rolls = rolls
        self.floor = round3(floor)
        self.age = age
        self.mode = mode
        self.higherCheaper = higher_cheaper
        self.now = now if now is not None else parse_iso(shard['generated_at'])

    def rollSpecs(self):
        if self.slot == 'weapon':
            w = WEAPON_STATS[self.tier - 1]
            return [('attack', w[0]), ('criticalChance', w[1])]
        key, tiers = STAT_RANGES[self.slot]
        return [(key, tiers[self.tier - 1])]

    def initialTargetHours(self):
        return ([4, 4, 6, 8, 12, 18] if self.slot == 'weapon' else [4, 4, 6, 8, 12, 24])[self.tier - 1]

    def deepTargetHours(self):
        return ([24, 24, 36, 48, 96, 120] if self.slot == 'weapon' else [24, 24, 36, 72, 120, 144])[self.tier - 1]

    def validAge(self):
        return self.age is not None and self.age >= 0


def recencyWeight(age):
    if age is None: return .4
    if age <= 3: return 1.12
    if age <= 6: return 1
    if age <= 12: return .88
    if age <= 24: return .72
    if age <= 48: return .52
    if age <= 72: return .38
    if age <= 120: return .27
    return .20


def median(nums):
    if not nums: return None
    a = sorted(nums); m = len(a) // 2
    return a[m] if len(a) % 2 else (a[m - 1] + a[m]) / 2


def robustFilter(items):
    if len(items) < 5: return list(items)
    prices = [it['money'] for it in items if it['money'] and it['money'] > 0]
    med = median(prices)
    if not med: return list(items)
    dev = [abs(math.log(p / med)) for p in prices]
    mad = median(dev) or 0
    thr = max(.12, mad * 3.5)
    return [it for it in items if it['money'] and abs(math.log(it['money'] / med)) <= thr]


def weightedQuantileBy(items, q, wfn):
    rows = []
    for it in items:
        p = it['money']; w = wfn(it)
        if p is not None and w > 0 and math.isfinite(w): rows.append((p, w))
    if not rows: return None
    rows.sort(key=lambda r: r[0])
    total = 0.0
    for r in rows: total += r[1]
    target = total * max(0, min(1, q)); acc = 0.0
    for p, w in rows:
        acc += w
        if acc >= target: return p
    return rows[-1][0]


def dispersion(items):
    if len(items) < 3: return None
    p = sorted(it['money'] for it in items); med = median(p)
    q1 = p[int((len(p) - 1) * .25)]; q3 = p[int((len(p) - 1) * .75)]
    return max(0, (q3 - q1) / med) if med else None


def qnum(a, q):
    a = sorted(x for x in a if x is not None and math.isfinite(x))
    if not a: return None
    pos = (len(a) - 1) * q; lo = math.floor(pos); hi = math.ceil(pos)
    return a[lo] if lo == hi else a[lo] + (a[hi] - a[lo]) * (pos - lo)


def soldHours(it):
    a = it['offerCreatedAt']; b = it['createdAt']
    if a is None or b < a: return None
    return (b - a) / 3600000


class Model:
    def __init__(self, st):
        self.st = st

    def saleAge(self, it):
        return max(0, (self.st.now - it['createdAt']) / 3600000)

    def weightedQuantile(self, items, q):
        return weightedQuantileBy(items, q, lambda it: recencyWeight(self.saleAge(it)))

    def exactMatch(self, it):
        return all(it['skills'].get(k) == self.st.rolls[k] for k, _ in self.st.rollSpecs())

    def statValue(self, it):
        if self.st.slot == 'weapon': return None
        key = self.st.rollSpecs()[0][0]
        v = it['skills'].get(key)
        return v if isinstance(v, (int, float)) else None

    def singleStatTarget(self):
        return None if self.st.slot == 'weapon' else self.st.rolls[self.st.rollSpecs()[0][0]]

    def maxSingleStat(self):
        return None if self.st.slot == 'weapon' else self.st.rollSpecs()[0][1][1]

    def hasPossibleBetterRoll(self):
        a = self.singleStatTarget(); b = self.maxSingleStat()
        return a is not None and b is not None and a < b

    def nearestWorse(self, sales):
        t = self.singleStatTarget()
        vals = [v for v in (self.statValue(it) for it in sales) if v is not None and v < t]
        if not vals: return []
        best = max(vals)
        return robustFilter([it for it in sales if self.statValue(it) == best])

    def nearbyBetter(self, sales):
        t = self.singleStatTarget()
        return robustFilter([it for it in sales if (self.statValue(it) is not None and t < self.statValue(it) <= t + 5)])

    def cheapBetterPattern(self, better, reference):
        t = self.singleStatTarget()
        cheap = [it for it in better if it['money'] < reference - .0005]
        if not cheap: return {'count': 0, 'price': None}
        price = weightedQuantileBy(cheap, .55, lambda it: recencyWeight(self.saleAge(it)) / (max(1, self.statValue(it) - t) ** 2))
        return {'count': len(cheap), 'price': price}

    def weaponCritAdjustment(self, c):
        mn, mx = WEAPON_STATS[self.st.tier - 1][1]
        if c <= mn: return -2
        if c >= mx: return 3
        return ((c - mn) / (mx - mn) - .5) * 2.4

    def weaponScore(self, skills):
        a = skills.get('attack'); c = skills.get('criticalChance')
        if a is None or c is None: return None
        return a + c * WEAPON_CRIT_WEIGHT + self.weaponCritAdjustment(c)

    def weaponRelation(self, it):
        c = it['skills'].get('criticalChance'); mine = self.st.rolls['criticalChance']
        return 'same' if c == mine else ('higher' if c > mine else 'lower')

    def weaponComparables(self, sales):
        target = self.weaponScore(self.st.rolls)
        rows = []
        for it in sales:
            s = self.weaponScore(it['skills']); rel = self.weaponRelation(it)
            if s is None: continue
            rows.append((0 if rel == 'same' else (1 if rel == 'higher' else 2), abs(s - target), self.saleAge(it), it))
        rows.sort(key=lambda r: (r[0], r[1], r[2]))
        return robustFilter([r[3] for r in rows[:12]])

    def velocityForSingle(self, sales, coverage):
        t = self.singleStatTarget(); s = 0.0
        for it in sales:
            v = self.statValue(it)
            if v is None: continue
            d = abs(v - t)
            if d > 5: continue
            s += recencyWeight(self.saleAge(it)) / (1 + d)
        return s / max(.25, coverage)

    def velocityForWeapon(self, items, coverage):
        t = self.weaponScore(self.st.rolls); s = 0.0
        for it in items:
            sc = self.weaponScore(it['skills'])
            if sc is None: continue
            d = abs(sc - t); rel = self.weaponRelation(it); pref = 1 if rel == 'same' else (.8 if rel == 'higher' else .55)
            s += recencyWeight(self.saleAge(it)) * pref / (1 + d)
        return s / max(.25, coverage)

    def floorSignal(self, exposure):
        if exposure is None: return ('unknown', 'floor age not supplied')
        if exposure >= 2: return ('stale', 'stale floor')
        if exposure >= .65: return ('watch', 'watch floor')
        return ('fresh', 'fresh floor')

    def quantileForMode(self):
        return .55 if self.st.mode == 'quick' else .70

    def underFloor(self):
        return round3(max(.001, self.st.floor - .001))

    def gate(self, score, exposure):
        rare = self.st.tier >= 5
        ageKnown = self.st.validAge() and exposure is not None
        veryStale = ageKnown and exposure >= 3.0
        confident = score >= 55
        return {'rare': rare, 'ageKnown': ageKnown, 'veryStale': veryStale, 'confident': confident,
                'allowed': rare and veryStale and confident}

    def getMarketTransactions(self, shard, deep=False):
        target = min(MAX_HISTORY_HOURS, self.st.deepTargetHours() if deep else self.st.initialTargetHours())
        allrows = sorted(shard['_sales'], key=lambda it: -it['createdAt'])
        cut = self.st.now - target * 3600000
        items = [it for it in allrows if it['createdAt'] >= cut]
        widened = len(items) < MIN_WINDOW_ROWS and len(allrows) > len(items)
        if widened: items = list(allrows)
        oldest = min((it['createdAt'] for it in items), default=None)
        coverage = 0 if oldest is None else min(MAX_HISTORY_HOURS, max(0, (self.st.now - oldest) / 3600000))
        return items, {'coverageHours': coverage, 'targetHours': target, 'deep': deep, 'partial': False, 'widened': widened,
                       'downloaded': len(allrows), 'marketRows': len(items)}

    def analyse_sales(self, shard, deep=False):
        items, meta = self.getMarketTransactions(shard, deep)
        maxAge = min(MAX_HISTORY_HOURS, max(meta['targetHours'], meta['coverageHours']))
        sales = [it for it in items if it['money'] > 0 and self.saleAge(it) <= maxAge + .05]
        return sales, meta

    def singleModel(self, sales, meta):
        st = self.st
        coverage = max(.25, meta['coverageHours'])
        exact = robustFilter([it for it in sales if self.exactMatch(it)]); worse = self.nearestWorse(sales)
        better = self.nearbyBetter(sales) if self.hasPossibleBetterRoll() else []
        velocity = self.velocityForSingle(sales, coverage)
        exposure = velocity * st.age if st.validAge() else None
        signal = self.floorSignal(exposure)
        q = self.quantileForMode()
        exactTarget = self.weightedQuantile(exact, q) if exact else None
        worseTarget = self.weightedQuantile(worse, .60 if st.mode == 'quick' else .72) if len(worse) >= 3 else None
        if len(exact) >= 3: hist, source = exactTarget, 'exact'
        elif exact:
            hist = exactTarget
            if worseTarget is not None: hist = max(hist, worseTarget)
            source = 'sparse exact + nearest worse'
        elif worseTarget is not None: hist, source = worseTarget, 'nearest worse'
        else: hist, source = self.underFloor(), 'live floor'
        primary = exact if exact else worse; disp = dispersion(primary); score = 0
        score += min(22, 22 * (coverage / max(1, st.initialTargetHours())))
        score += 40 if len(exact) >= 6 else (32 if len(exact) >= 3 else (20 if len(exact) == 2 else (12 if len(exact) == 1 else 0)))
        if len(exact) < 3 and len(worse) >= 6: score += 20
        elif len(exact) < 3 and len(worse) >= 3: score += 13
        if disp is not None: score += 12 if disp <= .06 else (7 if disp <= .12 else 2)
        if meta['deep']: score += 5
        if meta['partial']: score -= 12
        pressure = self.cheapBetterPattern(better, max(st.floor, hist or 0))
        stale = signal[0] == 'stale'
        if st.higherCheaper and not stale: score -= 4
        score = max(0, min(100, math.floor(score + 0.5)))
        gate = self.gate(score, exposure)
        pressureNeeded = 3 if st.higherCheaper else 4
        pressureActive = gate['allowed'] and pressure['count'] >= pressureNeeded and pressure['price'] is not None
        higher = hist > st.floor + .0005 and score >= 70 and not stale and not pressureActive
        direct = self.underFloor(); strategy = 'minimum-undercut'
        if not higher and gate['allowed']:
            if hist < direct: direct = round3(hist); strategy = 'rare-stale-history'
            if pressureActive and pressure['price'] < direct:
                direct = round3(min(direct, pressure['price'])); strategy = 'rare-stale-better-pressure'
        return {'kind': 'single', 'selected': (exact if exact else worse)[:12], 'exact': exact, 'worse': worse, 'better': better,
                'histTarget': round3(hist), 'source': source, 'velocity': velocity, 'exposure': exposure, 'signal': signal,
                'confidenceScore': score, 'confidence': 'High' if score >= 70 else ('Medium' if score >= 45 else 'Low'),
                'higher': higher, 'directPrice': direct, 'pressure': pressure, 'pressureActive': pressureActive,
                'strategy': strategy, 'gate': gate, 'exactTarget': exactTarget, 'worseTarget': worseTarget}

    def weaponModel(self, sales, meta):
        st = self.st
        coverage = max(.25, meta['coverageHours']); comp = self.weaponComparables(sales)
        velocity = self.velocityForWeapon(comp, coverage)
        exposure = velocity * st.age if st.validAge() else None
        signal = self.floorSignal(exposure)
        target = self.weaponScore(st.rolls)

        def w(it):
            d = abs(self.weaponScore(it['skills']) - target); rel = self.weaponRelation(it)
            pref = 1 if rel == 'same' else (.8 if rel == 'higher' else .55)
            return recencyWeight(self.saleAge(it)) * pref / (1 + d)
        hist = weightedQuantileBy(comp, self.quantileForMode(), w)
        if hist is None: hist = self.underFloor()
        disp = dispersion(comp); score = 0
        score += min(25, 25 * (coverage / max(1, st.initialTargetHours())))
        score += 38 if len(comp) >= 10 else (30 if len(comp) >= 6 else (18 if len(comp) >= 3 else 5))
        same = sum(1 for it in comp if self.weaponRelation(it) == 'same')
        if same >= 3: score += 12
        if disp is not None: score += 12 if disp <= .06 else (7 if disp <= .12 else 2)
        if meta['deep']: score += 5
        if meta['partial']: score -= 12
        score = max(0, min(100, math.floor(score + 0.5)))
        gate = self.gate(score, exposure)
        higher = hist > st.floor + .0005 and score >= 70 and signal[0] != 'stale'
        direct = self.underFloor(); strategy = 'minimum-undercut'
        if not higher and gate['allowed'] and hist < direct:
            direct = round3(hist); strategy = 'rare-stale-history'
        return {'kind': 'weapon', 'selected': comp, 'histTarget': round3(hist), 'source': 'score comparables', 'velocity': velocity,
                'exposure': exposure, 'signal': signal, 'confidenceScore': score,
                'confidence': 'High' if score >= 70 else ('Medium' if score >= 45 else 'Low'),
                'higher': higher, 'directPrice': direct, 'strategy': strategy, 'gate': gate, 'same': same, 'disp': disp}

    def build(self, sales, meta):
        return self.weaponModel(sales, meta) if self.st.slot == 'weapon' else self.singleModel(sales, meta)

    def opportunityDepthBands(self, m):
        st = self.st
        sample = [it for it in m['selected'] if soldHours(it) is not None]
        t = m['histTarget']; f = st.floor
        lo, hi = min(f, t), max(f, t); pad = max(1, (hi - lo) * .75)
        near = [it for it in sample if lo - pad <= it['money'] <= hi + pad]
        src = near if len(near) >= 3 else sample
        durations = [h for h in (soldHours(it) for it in src) if h is not None and 0 < h <= 168]
        velocity = max(0, m['velocity'])
        cycle = qnum(durations, .5) if durations else (1 / velocity if velocity > 0 else st.initialTargetHours())
        cycle = max(.25, min(168, cycle or st.initialTargetHours()))
        spc = max(.1, velocity * cycle)
        totalSafe = max(1, math.floor(spc + .5)); totalCaution = max(totalSafe + 1, math.ceil(spc * 3))
        safe = max(0, totalSafe - 1); caution = max(safe + 1, totalCaution - 1)
        return {'velocity': velocity, 'cycleHours': cycle, 'durationCount': len(durations), 'safeMax': safe, 'cautionMax': caution}


def run(item, rolls, floor, age=None, mode='quick', deep=False, now=None, higher_cheaper=False):
    shard = load_shard(item)
    st = State(shard, rolls, floor, age, mode, higher_cheaper, now)
    M = Model(st)
    sales, meta = M.analyse_sales(shard, deep)
    m = M.build(sales, meta)
    return shard, st, M, sales, meta, m


def parse_age(s):
    if s is None: return None
    s = s.strip().lower()
    if s.replace('.', '', 1).isdigit(): return float(s)
    import re
    tot = 0
    for v, u in re.findall(r'(\d+(?:\.\d+)?)\s*(d|h|m)', s):
        tot += float(v) * {'d': 24, 'h': 1, 'm': 1 / 60}[u]
    return tot


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--item', required=True); ap.add_argument('--roll', required=True)
    ap.add_argument('--floor', type=float, required=True); ap.add_argument('--age'); ap.add_argument('--mode', default='quick')
    ap.add_argument('--deep', action='store_true'); ap.add_argument('--now'); ap.add_argument('--higher-cheaper', action='store_true')
    a = ap.parse_args()
    rolls = {k: int(v) for k, v in (kv.split('=') for kv in a.roll.split(','))}
    shard, st, M, sales, meta, m = run(a.item, rolls, a.floor, parse_age(a.age), a.mode, a.deep,
                                       parse_iso(a.now) if a.now else None, a.higher_cheaper)
    out = {k: v for k, v in m.items() if k not in ('selected', 'exact', 'worse', 'better')}
    out['n_sales_window'] = len(sales); out['meta'] = meta
    if m['kind'] == 'single':
        out['n_exact'] = len(m['exact']); out['n_worse'] = len(m['worse']); out['n_better'] = len(m['better'])
        exact_prices = sorted(it['money'] for it in m['exact'])
        out['exact_plain_median'] = median(exact_prices)
    else:
        out['n_comp'] = len(m['selected']); out['comp'] = [(it['money'], it['skills'], round(M.saleAge(it), 2)) for it in m['selected']]
    out['bands'] = M.opportunityDepthBands(m)
    print(json.dumps(out, indent=1, default=str))
