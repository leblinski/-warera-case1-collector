"""(d) Where does WEAPON_CRIT_WEIGHT=4.15 come from? Least-squares fit price ~ a + b*attack + c*crit per
weapon from the shard rows (pure Python normal equations). Run: python3 d_critfit.py"""
import json, math
from model import load_shard, median, PUBLIC, WEAPON_STATS

WEAPONS = ['knife', 'gun', 'rifle', 'sniper', 'tank', 'jet']


def solve(A, y):
    """Least squares via normal equations, Gaussian elimination. A: list of rows."""
    k = len(A[0])
    N = [[sum(A[i][r] * A[i][c] for i in range(len(A))) for c in range(k)] for r in range(k)]
    b = [sum(A[i][r] * y[i] for i in range(len(A))) for r in range(k)]
    M = [N[r][:] + [b[r]] for r in range(k)]
    for col in range(k):
        piv = max(range(col, k), key=lambda r: abs(M[r][col]))
        M[col], M[piv] = M[piv], M[col]
        if abs(M[col][col]) < 1e-12: return None
        for r in range(k):
            if r == col: continue
            f = M[r][col] / M[col][col]
            for c in range(col, k + 1): M[r][c] -= f * M[col][c]
    return [M[r][k] / M[r][r] for r in range(k)]


def r2(A, y, beta):
    yhat = [sum(a * b for a, b in zip(row, beta)) for row in A]
    ybar = sum(y) / len(y)
    ss_res = sum((yi - yh) ** 2 for yi, yh in zip(y, yhat)); ss_tot = sum((yi - ybar) ** 2 for yi in y)
    return 1 - ss_res / ss_tot if ss_tot else float('nan')


def fit(rows, label, with_dummies=False, tier=None):
    if len(rows) < 6: print(f'  {label}: n={len(rows)} too few'); return None
    (amin, amax), (cmin, cmax) = WEAPON_STATS[tier - 1]
    A, y = [], []
    for a, c, p, w in rows:
        r = [1.0, a, c]
        if with_dummies: r += [1.0 if c <= cmin else 0.0, 1.0 if c >= cmax else 0.0]
        A.append([x * math.sqrt(w) for x in r]); y.append(p * math.sqrt(w))
    beta = solve(A, y)
    if beta is None: print(f'  {label}: singular'); return None
    ratio = beta[2] / beta[1] if abs(beta[1]) > 1e-12 else float('nan')
    extra = ''
    if with_dummies:
        extra = f' d_min={beta[3]:+.3f} d_max={beta[4]:+.3f} (in price units; in attack units: {beta[3]/beta[1]:+.2f} / {beta[4]/beta[1]:+.2f})'
    print(f'  {label}: n={len(rows)} a={beta[0]:.3f} b_attack={beta[1]:.4f} c_crit={beta[2]:.4f} -> crit/attack={ratio:.2f}  R2={r2(A,y,beta):.3f}{extra}')
    return ratio


print('WEAPON_CRIT_WEIGHT in page = 4.15 attack-points per crit point; weaponCritAdjustment: -2 at band min, +3 at band max, linear -1.2..+1.2 between')
now = None
for i, code in enumerate(WEAPONS):
    tier = i + 1
    shard = load_shard(code)
    gen = shard['generated_at']
    import datetime
    now_ms = datetime.datetime.fromisoformat(gen.replace('Z', '+00:00')).timestamp() * 1000
    allrows = [(it['skills']['attack'], it['skills']['criticalChance'], it['money'], 1.0) for it in shard['_sales']]
    r48 = [(it['skills']['attack'], it['skills']['criticalChance'], it['money'], 1.0) for it in shard['_sales'] if now_ms - it['createdAt'] <= 48 * 3600000]
    # per-roll medians, weighted by count
    byroll = {}
    for a, c, p, w in allrows: byroll.setdefault((a, c), []).append(p)
    medrows = [(a, c, median(ps), len(ps)) for (a, c), ps in byroll.items()]
    (amin, amax), (cmin, cmax) = WEAPON_STATS[tier - 1]
    print(f'\n== {code} (tier {tier}) attack {amin}-{amax} crit {cmin}-{cmax}; sales={len(allrows)} rolls seen={len(byroll)}')
    fit(allrows, 'all 168h sales, linear', tier=tier)
    fit(r48, '48h sales, linear', tier=tier)
    fit(medrows, 'per-roll medians (weight=count), linear', tier=tier)
    fit(medrows, 'per-roll medians + min/max crit dummies', with_dummies=True, tier=tier)
    # exclude the top-attack and top-crit cliffs (the "not broken" rolls) to see the interior slope
    interior = [r for r in medrows if amin < r[0] < amax and cmin < r[1] < cmax]
    fit(interior, 'interior rolls only (no band edges), medians', tier=tier)
    # log-price fit: elasticities
    logrows = [(a, c, math.log(p), w) for a, c, p, w in medrows]
    fit(logrows, 'log(price) per-roll medians', tier=tier)
    # what the page's score implies vs the market: for each pair of rolls, does the score order agree with median order?
    from model import Model, State
    st = State(shard, {'attack': amin, 'criticalChance': cmin}, 1.0); M = Model(st)
    scored = [(M.weaponScore({'attack': a, 'criticalChance': c}), m, n) for a, c, m, n in medrows if n >= 5]
    agree = disagree = 0
    for x in range(len(scored)):
        for yy in range(x + 1, len(scored)):
            s1, m1, _ = scored[x]; s2, m2, _ = scored[yy]
            if abs(s1 - s2) < 1e-9 or abs(m1 - m2) < 1e-9: continue
            if (s1 - s2) * (m1 - m2) > 0: agree += 1
            else: disagree += 1
    print(f'  score-vs-median pairwise order agreement (rolls n>=5): {agree}/{agree+disagree} = {agree/max(1,agree+disagree):.2f}')
    # cliff: how much of the price is the "max attack" premium
    top = [m for a, c, m, n in medrows if a == amax]; rest = [m for a, c, m, n in medrows if a != amax]
    if top and rest: print(f'  median price at attack={amax}: {median(top):.3f} vs other attacks: {median(rest):.3f}')
    topc = [m for a, c, m, n in medrows if c == cmax]; restc = [m for a, c, m, n in medrows if c != cmax]
    if topc and restc: print(f'  median price at crit={cmax}: {median(topc):.3f} vs other crits: {median(restc):.3f}')
