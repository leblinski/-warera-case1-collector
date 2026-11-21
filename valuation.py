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
# How much better than the plain window a fitted model has to be before it is used. The
# fit is the more complex claim and the one a reader cannot check by opening the market,
# so it earns its place or it does not get it. Most of the bake-off's margins are hundredths
# of a point - noise that a second week of data would reverse - and on gloves and boots
# those coin flips were handing the fit an item it loses by a full point on an independent
# seven-day grading. Jets clear this bar at 4.10% against 5.66% and nothing else comes close.
FIT_MARGIN = 0.9


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


def score(history, days, window, k, end=None):
    """Average absolute error predicting the SCORE_DAYS before `end` from the days before each."""
    end = len(days) if end is None else end
    errors = []
    for i in range(max(1, end - SCORE_DAYS), end):
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


def window_cell(history, days, key, upto=None):
    """The cell the plain window reads: this roll on the newest of the last two days it traded."""
    end = len(days) if upto is None else upto
    for day in reversed(days[max(0, end - 2):end]):
        cell = history[day]["cells"].get(key)
        if cell and cell[1]:
            return cell
    return None


# Sales a roll needs since midnight UTC before today's median alone prices it. Below this the
# last 24 hours do instead. Replayed hourly over 82 days of the archive, every roll graded on
# what it sold for in the six hours after: since-midnight alone erred 2.03% (weighted by
# sales) because just after midnight it prices off one or two sales; the last 24 hours alone
# erred 2.13% because it lags a price moving during the day; switching at 10 sales erred
# 1.92%. The threshold was chosen on the first 41 days and that result is the last 41, which
# the choice never saw - better on 35 of them. The gain is in Common to Rare and the early
# UTC hours; Epic to Mythic come out level.
TODAY_MIN_SALES = 10


def evidence_cell(history, days, key, last24=None, today=None):
    """The cell a window price is read from.

    Today's sales once there are TODAY_MIN_SALES of them, else the last 24 hours, else the
    newest of the last two days held. Without `last24` it is the plain calendar rule -
    today, else yesterday - which is how the window is scored on stored days.
    """
    if last24 is not None:
        own = history[today]["cells"].get(key) if today in history else None
        if own and own[1] and own[0] >= TODAY_MIN_SALES:
            return own
        recent = last24.get(key)
        if recent and recent[1]:
            return recent
    return window_cell(history, days, key)


def window_price(history, days, key, upto=None):
    """What the plain window says: this roll's own median yesterday, or the day before.

    The method every consumer used before the fit existed - no pooling, no neighbours, no
    normalisation. It is the thing to beat, not a strawman: where a roll trades several
    times a day its own recent median is hard to improve on, and the fit's smoothing only
    adds lag. Carried here so an item can choose it on the evidence.
    """
    cell = window_cell(history, days, key, upto)
    return cell[1] if cell else None


def score_window(history, days, end=None):
    """The plain window, graded exactly as a fitted model is: predict a day, unseen."""
    end = len(days) if end is None else end
    errors = []
    for i in range(max(1, end - SCORE_DAYS), end):
        for key, row in history[days[i]]["cells"].items():
            want = window_price(history, days, key, upto=i)
            if want is None or not row[1]:
                continue
            errors.append(abs(want - row[1]) / row[1])
    if not errors:
        return None
    errors.sort()
    return {"avg_pct": round(statistics.mean(errors) * 100, 3),
            "tail_pct": round(statistics.mean(errors[int(len(errors) * 0.9):]) * 100, 3),
            "n": len(errors)}


def fit(history):
    """Choose what prices this item - the plain window, or a fitted one - on its own record.

    Searching windows inside the fit could only ever pick the least-bad fit; it had no way
    to say "do not fit this one". Measured over seven graded days the plain window beat the
    fit on every mythic armour slot (gloves 3.45% against 4.96%) and lost to it on jets
    (6.08% against 4.47%), which is the same split the history always showed: ten rolls
    trading five times a day each need no help, eight hundred rolls sharing a fifth of a
    sale each do. So the window is a candidate like any other and the item picks.

    A fitted model is built either way. Where the window wins it still prices only the
    rolls that traded, and the fit fills the rest - better than the tier average that
    stood in for them before.

    History is {day: {"cells": {...}, "level": float}}, any number of days.
    """
    days = sorted(d for d in history if history[d].get("level"))
    if len(days) < 3:
        return None
    # Hyperparameters are chosen on days earlier than the ones the two methods are then
    # judged on. Without that the comparison is rigged: the fit picks its best of
    # twenty-eight candidates against the very days it is scored on and the window, which
    # has nothing to choose, gets one shot. On gloves that flattered the fit from 3.58%
    # to 2.71% - enough to hand it a bake-off it actually loses.
    pick_end = len(days) - SCORE_DAYS if len(days) >= 2 * SCORE_DAYS else None
    best = None
    for window in WINDOWS:
        if window > len(days):
            continue
        for k in SHRINKAGE:
            got = score(history, days, window, k, end=pick_end)
            if got and (best is None or got["avg_pct"] < best[2]["avg_pct"]):
                best = (window, k, got)
    if best is None:
        return None
    window, k, chosen_on = best
    # Both judged on the same held-out days, each with one shot. Note what this does not
    # hold out: the choice between them is made on these same days, so the published
    # accuracy is the winner's score on the days that picked it, and reads a little better
    # than the method will do next. Deciding on earlier days instead was tried and replayed
    # over fourteen days: the honest choice priced worse (2.80% average next-day error
    # against 2.69%, the plain yesterday-median baseline 2.80%), because five-day-old
    # evidence is staler than the bias it removes. So the decision stays where it prices
    # best, and readers are told what the number is rather than that it is held out.
    accuracy = score(history, days, window, k) if pick_end else chosen_on
    plain = score_window(history, days)
    # A tie goes to the window: it is the simpler claim and the one a reader can check by
    # opening the market.
    # Strictly better, by the margin. Equal scores - including two methods that are both
    # exactly right - are a tie, and a tie goes to the window.
    source = "fit" if (not plain or accuracy["avg_pct"] < plain["avg_pct"] * FIT_MARGIN) else "window"
    recent = [(d, history[d]["cells"]) for d in days[-window:]]
    normalised = [(d, {key: [row[0], row[1] / history[d]["level"], row[2]]
                       for key, row in cells.items()}) for d, cells in recent]
    model = build(normalised, k)
    if not model:
        return None
    level = statistics.median([history[d]["level"] for d in days[-2:]])
    return {"window_days": window, "k": k, "source": source,
            "accuracy": plain if source == "window" else accuracy,
            "fit_accuracy": accuracy, "window_accuracy": plain,
            "level": round(level, 4), "days_available": len(days), "as_of": days[-1],
            "model": model, "days": days}


# A stat value at the edge of an item's range has to carry at least this share of the item's
# sales to widen it. Seventy days hold a handful of sales outside every band - six rifle
# sales at a Common crit, one Uncommon boot at a Common dodge - and the grid is a product of
# ranges, so one stray sale doubled the sniper to 300 rolls. Real edge values carry percents.
EDGE_SHARE = 0.002
# How far back a roll the item's own model cannot price is filled from.
FILL_DAYS = 7


def grid(model, counts=None):
    """Every roll the item has been seen in, filled out across the range of its stats.

    `counts` is {roll: sales} over the history held. Without it the range is read off the
    model's own cells, which for a one-day fit is whatever has traded since midnight UTC:
    at 07:30 the top and bottom Mythic glove rolls had not sold yet and were dropped from
    the feed outright, and just after midnight gloves4 was down to a single roll.
    """
    counts = counts if counts else {key: cell[0] for key, cell in model["cells"].items()}
    rolls = [(parse_roll(key), n) for key, n in counts.items()]
    if not rolls:
        return []
    total = sum(n for _, n in rolls) or 1
    names = sorted({name for r, _ in rolls for name in r})
    spans = {}
    for name in names:
        by_value = {}
        for r, n in rolls:
            if name in r:
                by_value[r[name]] = by_value.get(r[name], 0) + n
        seen = sorted(by_value)
        if not seen or not all(isinstance(v, int) for v in seen):
            return [roll_key(r) for r, _ in rolls]
        # Trim strays off the ends only; a gap inside the range is still filled.
        while len(seen) > 1 and by_value[seen[0]] < EDGE_SHARE * total:
            seen.pop(0)
        while len(seen) > 1 and by_value[seen[-1]] < EDGE_SHARE * total:
            seen.pop()
        spans[name] = range(seen[0], seen[-1] + 1)
    out = [{}]
    for name in names:
        out = [dict(base, **{name: v}) for base in out for v in spans[name]]
        if len(out) > 5000:
            return [roll_key(r) for r, _ in rolls]
    return [roll_key(r) for r in out]


def _as_date(value):
    """A stored day as a date, or None if it is missing or not one."""
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def value_item(history, last24=None, today=None):
    """The published block: what every roll is worth, and how well the method is doing.

    `last24` is this item's cells over the last 24 hours and `today` the current UTC date;
    given both, window prices follow evidence_cell's rule rather than the calendar day.
    """
    fitted = fit(history)
    if not fitted:
        return None
    model, level = fitted["model"], fitted["level"]
    rolls = {}
    end = _as_date(fitted["as_of"])
    use_window = fitted["source"] == "window"
    # When a roll last traded is read off every day held, not off the fit's own window.
    # A one-day fit only sees today, so a roll that sold four hundred times this season and
    # last sold yesterday came out as "never traded" - and was published that way beside a
    # price taken from yesterday's sale.
    last_seen, sold = {}, {}
    for day in fitted["days"]:
        for key, cell in history[day]["cells"].items():
            last_seen[key] = day
            sold[key] = sold.get(key, 0) + cell[0]
    from_window = 0
    filler = None
    for key in grid(model, counts=sold):
        relative = price(model, key)
        own = evidence_cell(history, fitted["days"], key, last24, today) if use_window else None
        # Just after midnight a one-day model holds a sale or two and cannot draw a line, so
        # a roll that last sold the day before yesterday had no price at all. The same fit
        # over the last week fills those, and only those.
        if relative is None and not own:
            if filler is None:
                recent = [d for d in fitted["days"][-FILL_DAYS:] if history[d]["level"]]
                filler = build([(d, {k: [row[0], row[1] / history[d]["level"], row[2]]
                                     for k, row in history[d]["cells"].items()})
                                for d in recent], fitted["k"]) or {}
            relative = price(filler, key) if filler else None
        # A roll the window can price does not need the fit to have an opinion: on a quiet
        # morning a one-day model has too few cells to draw a line at all.
        if relative is None and not own:
            continue
        # Where the window won, it prices the rolls it can and the fit fills the rest. The
        # window is the better estimate on a roll that trades daily and has nothing at all
        # to say about one that does not, so taking each where it is strongest beats
        # choosing one of them for the whole item. The count and time to sell go with the
        # price: a window price is that day's sales, a fitted one the fit's pooled cell.
        cell = own or model["cells"].get(key)
        if own:
            from_window += 1
        seen = _as_date(last_seen.get(key))
        rolls[key] = {"price": round(own[1] if own else relative * level, 3),
                      "from": "window" if own else "fit",
                      "sales": cell[0] if cell else 0,
                      "last_seen_days": (end - seen).days if end and seen else None,
                      "hours_to_sell": (round(cell[2] / 3600, 2)
                                        if cell and cell[2] is not None else None)}
    return {"window_days": fitted["window_days"], "k": fitted["k"],
            "source": fitted["source"],
            "fit_accuracy": fitted["fit_accuracy"], "window_accuracy": fitted["window_accuracy"],
            "days_available": fitted["days_available"], "as_of": fitted["as_of"],
            "level": level, "accuracy": fitted["accuracy"],
            "priced_rolls": len(rolls), "window_rolls": from_window,
            "traded_rolls": sum(1 for r in rolls.values() if r["sales"]),
            "rolls": rolls}
