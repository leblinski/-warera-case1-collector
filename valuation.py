"""Pricing equipment by its roll, from more history than a week.

The published per-roll medians answer well where an item trades thickly and badly where it
does not, and the gap is enormous: mythic boots have ten rolls and seven sales a day in
each, while a jet has eight hundred rolls, a fifth of them touched in a day and most of
those by a single sale. The same method cannot serve both.

Three things here that the medians do not do.

A roll is priced from its neighbours as well as itself. For a two stat item the neighbours
are the rolls sharing its critical chance, because that is how the market shops: filtered
to a crit, then along attack looking for a price. Measured on jets, a point of attack is
worth 0.78 gold at crit 41 and 4.39 at crit 50 - five and a half times - so a single
surface across both stats is the wrong shape, and fitting one line per crit is the right
one. Armour has a single stat and gets a single line.

Every sale is expressed against its own day's level before it is used, and today's level is
put back at the end. Without that, old sales drag a stale price in with their shape: on
jets at thirty days it is the difference between 6.99% and 5.39% average error.

How much history, and how much weight the neighbours get, are measured per item rather than
chosen. Jets want sixty days; mythic gloves want one, because they moved 24% in a fortnight
and a ten day window is four times worse than a one day window on them. Nothing but a
walk-forward score can know that, and it changes as the market does.
"""
from __future__ import annotations

import json
import statistics
from datetime import date

WINDOWS = (1, 2, 3, 7, 14, 30, 60)
SHRINKAGE = (0.25, 0.5, 1.0, 2.0)
SCORE_DAYS = 5          # how many recent days a candidate is judged on
MIN_CELL = 3            # sales at a roll before it is trusted on its own
MIN_PEERS = 5           # sales in a crit bucket before it beats the whole item


def roll_key(skills):
    """A roll as a stable string: {"attack": 280, "criticalChance": 47} -> "attack=280;criticalChance=47"."""
    return ";".join(f"{k}={skills[k]}" for k in sorted(skills))


def parse_roll(key):
    out = {}
    for part in key.split(";"):
        if not part:
            continue
        name, _, value = part.partition("=")
        try:
            out[name] = int(value)
        except ValueError:
            out[name] = value
    return out


def aggregate(sales):
    """One day of one item's sales, as cells: roll -> [count, median price, median seconds].

    Aggregating by day and roll is what makes sixty days affordable to keep and to read. It
    loses the spread within a cell on one day, which no part of the fit asks for.
    """
    cells = {}
    for key, price, seconds in sales:
        cells.setdefault(key, [[], []])[0].append(price)
        if seconds is not None:
            cells[key][1].append(seconds)
    out = {}
    for key, (prices, seconds) in cells.items():
        out[key] = [len(prices), round(statistics.median(prices), 4),
                    int(statistics.median(seconds)) if seconds else None]
    return out


def day_level(cells):
    """The item's price level on a day: the median cell median, weighted by nothing.

    Weighting by count would let one busy roll speak for the day, and a day's level is meant
    to say where the whole item sat, not where its most traded roll did.
    """
    values = [row[1] for row in cells.values() if row[1] is not None]
    return round(statistics.median(values), 4) if values else None


def _stat_names(cells):
    names = set()
    for key in cells:
        names.update(parse_roll(key))
    return sorted(names)


def _line(points):
    """Least squares through (x, y), returning a callable. None if it cannot be drawn."""
    n = len(points)
    if n < 2:
        return None
    mx = sum(p[0] for p in points) / n
    my = sum(p[1] for p in points) / n
    sxx = sum((p[0] - mx) ** 2 for p in points)
    if not sxx:
        return lambda x: my
    b = sum((p[0] - mx) * (p[1] - my) for p in points) / sxx
    return lambda x: my + b * (x - mx)


def build(window_days, k):
    """A model over a list of (day, cells) in time order, newest last, prices normalised."""
    pooled, last_seen = {}, {}
    for day, cells in window_days:
        for key, row in cells.items():
            slot = pooled.setdefault(key, [0, 0.0, []])
            slot[0] += row[0]
            slot[1] += row[1] * row[0]
            if row[2] is not None:
                slot[2].append(row[2])
            last_seen[key] = day
            # Age is not weighted - a roll's standing against its item's own level holds
            # across the window, measured at 2.2% drift over thirty days against 2.2%
            # within a few days. It is published so a reader can see how thin the evidence
            # under a price is, which a sale count alone does not say.
    cells = {key: [n, total / n, (statistics.median(secs) if secs else None)]
             for key, (n, total, secs) in pooled.items() if n}
    if not cells:
        return None
    names = _stat_names(cells)
    main = names[-1] if len(names) == 1 else [n for n in names if n != "criticalChance"]
    main = main[0] if isinstance(main, list) and main else (main if isinstance(main, str) else names[0])
    buckets = {}
    for key, row in cells.items():
        roll = parse_roll(key)
        buckets.setdefault(roll.get("criticalChance"), []).append((roll.get(main), row[1], row[0]))
    lines = {}
    for bucket, points in buckets.items():
        weighted = [(x, y) for x, y, n in points for _ in range(min(n, 20)) if x is not None]
        if len(weighted) >= MIN_PEERS:
            lines[bucket] = _line(weighted)
    whole = _line([(x, y) for points in buckets.values() for x, y, n in points
                   for _ in range(min(n, 20)) if x is not None])
    return {"cells": cells, "main": main, "lines": lines, "whole": whole, "k": k,
            "last_seen": last_seen}


def price(model, key):
    """What one roll is worth, relative to the level the model was fitted on."""
    if not model:
        return None
    cell = model["cells"].get(key)
    if cell and cell[0] >= MIN_CELL:
        return cell[1]
    roll = parse_roll(key)
    line = model["lines"].get(roll.get("criticalChance")) or model["whole"]
    x = roll.get(model["main"])
    if line is None or x is None:
        return cell[1] if cell else None
    surface = line(x)
    if not cell:
        return surface
    n, own = cell[0], cell[1]
    return (n * own + model["k"] * surface) / (n + model["k"])


def score(history, days, window, k):
    """Average absolute error predicting each of the last days from the ones before it."""
    errors = []
    for i in range(max(1, len(days) - SCORE_DAYS), len(days)):
        past = [(d, history[d]["cells"]) for d in days[max(0, i - window):i]
                if history[d]["level"]]
        if not past:
            continue
        normalised = [(d, {key: [row[0], row[1] / history[d]["level"], row[2]]
                           for key, row in cells.items()}) for d, cells in past]
        model = build(normalised, k)
        if not model:
            continue
        level = statistics.median([history[d]["level"] for d, _ in past[-2:]])
        for key, row in history[days[i]]["cells"].items():
            want = price(model, key)
            if want is None or not row[1]:
                continue
            errors.append(abs(want * level - row[1]) / row[1])
    if not errors:
        return None
    errors.sort()
    return {"avg_pct": round(100 * sum(errors) / len(errors), 3),
            "tail_pct": round(100 * statistics.mean(errors[int(len(errors) * 0.9):]), 3),
            "n": len(errors)}


def fit(history):
    """Choose the window and the shrinkage this item's own history argues for, then fit.

    History is {day: {"cells": {...}, "level": float}}, any number of days.
    """
    days = sorted(d for d in history if history[d].get("level"))
    if len(days) < 3:
        return None
    best = None
    for window in WINDOWS:
        if window > len(days):
            continue
        for k in SHRINKAGE:
            got = score(history, days, window, k)
            if got and (best is None or got["avg_pct"] < best[2]["avg_pct"]):
                best = (window, k, got)
    if best is None:
        return None
    window, k, accuracy = best
    recent = [(d, history[d]["cells"]) for d in days[-window:]]
    normalised = [(d, {key: [row[0], row[1] / history[d]["level"], row[2]]
                       for key, row in cells.items()}) for d, cells in recent]
    model = build(normalised, k)
    if not model:
        return None
    level = statistics.median([history[d]["level"] for d in days[-2:]])
    return {"window_days": window, "k": k, "accuracy": accuracy, "level": round(level, 4),
            "days_available": len(days), "as_of": days[-1], "model": model}


def grid(model):
    """Every roll the item has been seen in, filled out across the range of its stats."""
    rolls = [parse_roll(key) for key in model["cells"]]
    if not rolls:
        return []
    names = sorted({n for r in rolls for n in r})
    spans = {}
    for name in names:
        seen = sorted({r[name] for r in rolls if name in r})
        if not seen or not all(isinstance(v, int) for v in seen):
            return [roll_key(r) for r in rolls]
        spans[name] = range(min(seen), max(seen) + 1)
    out = [{}]
    for name in names:
        out = [dict(base, **{name: v}) for base in out for v in spans[name]]
        if len(out) > 5000:
            return [roll_key(r) for r in rolls]
    return [roll_key(r) for r in out]


def _as_date(value):
    """A stored day as a date, or None if it is missing or not one."""
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def value_item(history):
    """The published block: what every roll is worth, and how well the method is doing."""
    fitted = fit(history)
    if not fitted:
        return None
    model, level = fitted["model"], fitted["level"]
    last_seen, rolls = model["last_seen"], {}
    end = _as_date(fitted["as_of"])
    for key in grid(model):
        relative = price(model, key)
        if relative is None:
            continue
        cell = model["cells"].get(key)
        # How old the evidence is, in days, or null for a roll read off the curve alone.
        # A price with no sales under it and one with forty are both just a number without
        # this, and they are not the same claim.
        seen = _as_date(last_seen.get(key))
        rolls[key] = {"price": round(relative * level, 3),
                      "sales": cell[0] if cell else 0,
                      "last_seen_days": (end - seen).days if end and seen else None,
                      "hours_to_sell": (round(cell[2] / 3600, 2)
                                        if cell and cell[2] is not None else None)}
    return {"window_days": fitted["window_days"], "k": fitted["k"],
            "days_available": fitted["days_available"], "as_of": fitted["as_of"],
            "level": level, "accuracy": fitted["accuracy"],
            "priced_rolls": len(rolls),
            "traded_rolls": sum(1 for r in rolls.values() if r["sales"]),
            "rolls": rolls}
