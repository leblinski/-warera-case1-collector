"""Read-only WarEra Case I market collector. Python 3.11+, standard library only."""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
import statistics
import sys
import tempfile
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parent
GATEWAY = "https://gateway.warerastats.io/trpc"
OFFICIAL = "https://api2.warera.io/trpc"
COMMODITIES = {"case1": "Case I", "scraps": "Scrap", "steel": "Steel"}
SCHEMA_VERSION = 5

# How long retained transactions live in the rolling output. The source only exposes a short
# rolling window, so depth accumulates forward: a fresh cache reaches RETENTION_HOURS only
# after running for that long. Distinct from COMPS_WINDOW_HOURS below.
RETENTION_HOURS = 168
# The price-comparison windows. These size the published roll statistics and are deliberately
# narrower than retention: stale sales make poor comparables, but the retained rows remain
# available to consumers that want to widen the window themselves.
COMPS_WINDOW_HOURS = 48
PRIMARY_HOURS = 24
# Both windows above filter on when a sale CLOSED. That is not enough on its own: a listing
# created months ago clears today and lands inside the 24h window carrying the price it was
# posted at. When the game moved its legal price brackets on 2026-08-29, three months of
# knife listings pinned at 1.80 kept clearing against a market whose fresh listings were
# selling at 2.50, and the published median tracked the backlog rather than the market. A
# sale that sat this long was priced under conditions that no longer hold, so it is not a
# comparable. Raw sale rows keep everything; only the statistics apply this.
MAX_TIME_ON_MARKET_HOURS = COMPS_WINDOW_HOURS
# Every incremental run re-reads this far past its checkpoint to catch delayed ingestion.
# The upstream gateway scrapes every 5 seconds, so this is ~350x the expected delay;
# full_rescan_interval_hours is the real backstop.
OVERLAP_HOURS = 0.5
FULL_RESCAN_HOURS = 6
# How deep the periodic backstop re-reads. It exists to recover records that arrived late
# and the overlap missed, not to rebuild the cache: the retained week accumulates forward
# and re-paging it costs about 62 pages per hour of history, so the full window is several
# thousand pages and cannot complete in one run. Six times the incremental overlap is far
# beyond the upstream scrape delay of five seconds.
BACKSTOP_HOURS = 3
# How deep a cache with no history of its own tries to go on its first run. Paging the whole
# retention window in one go cannot be done inside the page budget - the shared stream runs
# about eleven pages an hour, so 168h is roughly 1,800 pages against a limit of 1,000 - and a
# fresh cache that tries it exhausts the budget, errors, keeps last_success_at unset, fails
# --require-healthy, and does the same again on the next run for ever. Depth is meant to
# accumulate forward anyway, so the first run takes a bite it can finish and the window grows
# from there.
INITIAL_DEPTH_HOURS = 48
RECENCY_HALF_LIFE_HOURS = 12
MIN_PRIMARY_COMPS = 3

# Fields taken straight from the API. Everything else on a record is recomputed from these by
# derive_transaction(), so the rolling cache stores only these and rehydrates on read: a
# derived field that is never written can never drift from the values it came from.
PRIMITIVE_FIELDS = ("id", "item_code", "sold_at", "seller_id", "buyer_id", "offer_created_at",
                    "money", "quantity", "skills", "stats", "state", "max_state")
# item_code is omitted on disk because a record already lives under its category's key.
STORED_FIELDS = tuple(field for field in PRIMITIVE_FIELDS if field != "item_code")


class CollectionError(Exception):
    pass


class ApiError(CollectionError):
    def __init__(self, message, status=None, retry_after=0):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


def utcnow():
    return datetime.now(timezone.utc)


def stamp(value):
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_time(value):
    if not isinstance(value, str):
        raise CollectionError("Missing or invalid timestamp")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CollectionError("Invalid ISO timestamp") from exc
    if result.tzinfo is None:
        raise CollectionError("Timestamp has no timezone")
    return result.astimezone(timezone.utc)


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) else None


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def categories():
    rows = json.loads((ROOT / "config/case1_items.json").read_text(encoding="utf-8"))
    codes = [row["item_code"] for row in rows]
    expected = {"knife", "gun", "rifle", "sniper", "tank", "jet"}
    expected.update(f"{slot}{tier}" for slot in ("boots", "helmet", "gloves", "chest", "pants") for tier in range(1, 7))
    if len(codes) != 36 or set(codes) != expected:
        raise CollectionError("Case I manifest must contain exactly the 36 expected categories")
    return rows


def unwrap(body):
    if isinstance(body, list) and len(body) == 1:
        body = body[0]
    if not isinstance(body, dict):
        raise ApiError("Invalid tRPC response envelope")
    if "error" in body:
        error = body["error"]
        error = error.get("json", error) if isinstance(error, dict) else {}
        details = error.get("data", {})
        status = details.get("httpStatus") if isinstance(details, dict) else None
        raise ApiError(f"tRPC request failed (HTTP {status or 'unknown'})", status)
    try:
        payload = body["result"]["data"]
    except (KeyError, TypeError) as exc:
        raise ApiError("Missing result.data in tRPC response") from exc
    if isinstance(payload, dict) and "json" in payload and set(payload) <= {"json", "meta"}:
        payload = payload["json"]
    return payload


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ApiError("API redirect refused to protect the API key", code)


def retry_delay(header):
    try:
        return max(0, float(header))
    except (TypeError, ValueError):
        try:
            return max(0, (parsedate_to_datetime(header) - utcnow()).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return 0


class Client:
    """One shared rate limiter for workers and retries; never logs the API key."""
    def __init__(self, base_url=GATEWAY, api_key=None, interval=0.5, max_seconds=600):
        if base_url not in (GATEWAY, OFFICIAL):
            raise CollectionError("Only the official API and WarEraStats Gateway are supported")
        self.base_url = base_url
        self.api_key = api_key
        self.interval = interval
        self.deadline = time.monotonic() + max_seconds
        self.lock = threading.Lock()
        self.next_request = 0.0
        self.cooldown_until = 0.0
        self.requests = 0

    def _throttle(self):
        while True:
            with self.lock:
                now = time.monotonic()
                target = max(self.next_request, self.cooldown_until, now)
                if target >= self.deadline:
                    raise ApiError("Run time budget reached; retry on the next scheduled run")
                delay = target - now
                if delay <= 0:
                    self.next_request = now + self.interval
                    self.requests += 1
                    return
            time.sleep(min(delay, 1))

    def call(self, procedure, params=None):
        url = self.base_url + "/" + procedure + "?" + urlencode({"input": canonical(params or {})})
        headers = {"Accept": "application/json", "User-Agent": "warera-case1-collector/1.0 (Supported by warerastats.io)"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        for attempt in range(4):
            self._throttle()
            try:
                remaining = self.deadline - time.monotonic()
                with build_opener(NoRedirect()).open(Request(url, headers=headers), timeout=max(0.1, min(30, remaining))) as response:
                    return unwrap(json.load(response))
            except HTTPError as exc:
                reason = " (valid WARERA_API_KEY required)" if exc.code in (401, 403) else ""
                failure = ApiError(f"{procedure}: HTTP {exc.code}{reason}", exc.code, retry_delay(exc.headers.get("Retry-After")))
                exc.close()
            except ApiError as exc:
                failure = exc
            except (URLError, TimeoutError, OSError) as exc:
                failure = ApiError(f"{procedure}: network request failed ({type(exc).__name__})", 503)
            except (ValueError, TypeError) as exc:
                raise ApiError(f"{procedure}: invalid JSON response") from exc
            if failure.status not in (408, 429, 500, 502, 503, 504) or attempt == 3:
                raise failure
            delay = max(2 ** attempt, failure.retry_after)
            with self.lock:
                self.cooldown_until = max(self.cooldown_until, time.monotonic() + delay)
        raise AssertionError("Unreachable retry state")


def roll_of(transaction):
    """Rebuild the exact roll from a record. roll_key is its canonical JSON form."""
    fields = ((key, transaction.get(key)) for key in ("skills", "stats"))
    return {key: value for key, value in fields if isinstance(value, dict) and value}


def derive_transaction(base):
    """Recompute every derived field from the primitive fields of a record.

    Both normalize_transaction() and validate() go through this, so a stored record can be
    re-derived and checked without retaining a copy of the original API payload.
    """
    exact_roll = roll_of(base)
    numeric_roll = bool(exact_roll) and all(number(v) is not None for fields in exact_roll.values() for v in fields.values())
    state = number(base.get("state"))
    max_state = number(base.get("max_state"))
    full_condition = state is not None and max_state is not None and max_state > 0 and state == max_state
    ratio = state / max_state if state is not None and max_state is not None and max_state > 0 else None
    money = number(base.get("money"))
    quantity = number(base.get("quantity"))
    unit_price = money / quantity if money is not None and quantity is not None and quantity > 0 else None
    issues = []
    if not numeric_roll:
        issues.append("missing_or_invalid_exact_roll")
    if ratio is None or not 0 <= ratio <= 1:
        issues.append("missing_or_invalid_condition")
    if unit_price is None or unit_price <= 0:
        issues.append("missing_or_invalid_price")
    if quantity != 1:
        issues.append("non_single_equipment_quantity")
    offer_time = base.get("offer_created_at")
    time_to_sell = None
    if offer_time is not None:
        try:
            time_to_sell = (parse_time(base["sold_at"]) - parse_time(offer_time)).total_seconds()
            if time_to_sell < 0:
                time_to_sell = None
                issues.append("offer_after_sale")
        except CollectionError:
            issues.append("invalid_offer_timestamp")
    return {
        **{key: copy.deepcopy(base.get(key)) for key in PRIMITIVE_FIELDS},
        "time_to_sell_seconds": time_to_sell, "unit_price": unit_price,
        "condition_ratio": ratio, "full_condition": full_condition,
        "roll_key": canonical(exact_roll) if numeric_roll else None,
        "eligible_for_comps": full_condition and numeric_roll and unit_price is not None and unit_price > 0 and quantity == 1,
        "quality_issues": issues,
    }


def pack_transaction(transaction):
    """Project a record down to what is written to disk. Absent values are omitted."""
    return {field: transaction[field] for field in STORED_FIELDS if transaction.get(field) is not None}


def unpack_transaction(row, item_code):
    if not isinstance(row, dict):
        raise CollectionError("Stored transaction is not an object")
    return derive_transaction({**row, "item_code": item_code})


def normalize_transaction(raw, item_code):
    if not isinstance(raw, dict):
        raise CollectionError("Transaction is not an object")
    txid = raw.get("_id", raw.get("id"))
    if not isinstance(txid, str) or not txid:
        raise CollectionError("Transaction has no stable ID")
    if raw.get("transactionType") != "itemMarket" or raw.get("itemCode") != item_code:
        raise CollectionError("Transaction filter mismatch; refusing cross-category data")
    sold = parse_time(raw.get("createdAt"))
    equipment = raw.get("item")
    equipment = equipment if isinstance(equipment, dict) else {}
    code = equipment.get("code", equipment.get("itemCode"))
    if code is not None and code != item_code:
        raise CollectionError("Equipment code does not match its transaction")
    # The original payload and the full equipment object are deliberately not retained: every
    # field either survives below or is recomputed by derive_transaction() from what does.
    return derive_transaction({
        "id": txid, "item_code": item_code, "sold_at": stamp(sold),
        "seller_id": raw.get("sellerId"), "buyer_id": raw.get("buyerId"),
        "offer_created_at": raw.get("offerCreatedAt"),
        "money": number(raw.get("money")),
        "quantity": number(raw.get("quantity", equipment.get("quantity", 1))),
        "skills": equipment.get("skills"), "stats": equipment.get("stats"),
        "state": number(equipment.get("state")),
        "max_state": number(equipment.get("maxState", equipment.get("max_state"))),
    })


def page_data(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise CollectionError("Transaction page must have an items array")
    if "nextCursor" not in payload:
        raise CollectionError("Transaction page has no pagination metadata")
    cursor = payload["nextCursor"]
    if cursor is not None and not isinstance(cursor, str):
        raise CollectionError("Invalid nextCursor")
    if payload.get("hasMore") and not cursor:
        raise CollectionError("Page claims more records but has no cursor")
    if not payload["items"] and cursor:
        raise CollectionError("Empty page with a cursor; coverage cannot be trusted")
    return payload["items"], cursor


def collect_market(client, manifest, previous, now, max_pages=1000):
    """Scan itemMarket once, then distribute exact records across Case I codes."""
    cutoff = now - timedelta(hours=RETENTION_HOURS)
    codes = [cat["item_code"] for cat in manifest]
    old = {code: previous.get(code, {}) for code in codes}
    kept = {code: {row["id"]: unpack_transaction(row, code) for row in old[code].get("transactions", [])
                   if cutoff <= parse_time(row["sold_at"]) <= now} for code in codes}
    known = {txid for rows in kept.values() for txid in rows}
    checkpoints = [row.get("last_success_at") for row in old.values()]
    checkpoint = min(checkpoints, key=parse_time) if all(checkpoints) else None
    # A cache that has never reached the boundary has to page all the way there. A cache
    # that already has must not: re-reading the whole retention window every six hours is
    # what made the scan unable to finish inside any sane time budget.
    never_complete = any(not row.get("history_complete") for row in old.values())
    periodic = any(not row.get("last_full_scan_at")
                   or parse_time(row["last_full_scan_at"]) <= now - timedelta(hours=FULL_RESCAN_HOURS)
                   for row in old.values())
    full_scan = never_complete or periodic
    initial = never_complete and checkpoint is None
    deep_floor = (max(cutoff, now - timedelta(hours=INITIAL_DEPTH_HOURS)) if initial
                  else cutoff if never_complete
                  else max(cutoff, now - timedelta(hours=BACKSTOP_HOURS)))
    overlap_cutoff = max(cutoff, parse_time(checkpoint) - timedelta(hours=OVERLAP_HOURS)) if checkpoint else cutoff
    # The backstop is a ceiling on work, never a reason to skip history. Stopping three hours
    # back while the last success is four hours back leaves that hour unfetched, and the
    # checkpoint then moves past it, so the sales in the gap are gone from the cache and the
    # archive alike. Whichever floor is older wins.
    if checkpoint and not never_complete:
        deep_floor = min(deep_floor, overlap_cutoff)
    complete_stops = ("retention_boundary", "end_of_history",
                      f"initial_depth_{INITIAL_DEPTH_HOURS:g}h")
    cursor = None
    seen_cursors = set()
    pages = 0
    stop = None
    error = None
    reached_known = False
    try:
        for _ in range(max_pages):
            params = {"transactionType": "itemMarket", "limit": 100}
            if cursor:
                params["cursor"] = cursor
            raw_rows, next_cursor = page_data(client.call("transaction.getPaginatedTransactions", params))
            pages += 1
            if any(not isinstance(raw, dict) or raw.get("transactionType") != "itemMarket" for raw in raw_rows):
                raise CollectionError("Market stream returned a different transaction type")
            dates = [parse_time(raw.get("createdAt")) for raw in raw_rows]
            if any(date > now + timedelta(minutes=5) for date in dates):
                raise CollectionError("Transaction timestamp too far in the future")
            for raw, date in zip(raw_rows, dates):
                code = raw.get("itemCode")
                if not isinstance(code, str) or not code:
                    raise CollectionError("Market transaction has no item code")
                if code not in kept:
                    continue
                row = normalize_transaction(raw, code)
                reached_known = reached_known or row["id"] in known
                if cutoff <= date <= now:
                    kept[code][row["id"]] = row
            oldest = min(dates) if dates else None
            if pages % 10 == 0:
                print(f"Market history: {pages} pages, {sum(map(len, kept.values()))} Case I sales retained", flush=True)
            # Gateway sorts by whole seconds. Walk past the boundary second.
            if oldest is not None and oldest < cutoff - timedelta(seconds=1):
                stop = "retention_boundary"
            elif not next_cursor:
                stop = "end_of_history"
            elif full_scan and oldest is not None and oldest < deep_floor - timedelta(seconds=1):
                stop = (f"initial_depth_{INITIAL_DEPTH_HOURS:g}h" if initial
                        else f"backstop_{BACKSTOP_HOURS:g}h")
            elif not full_scan and reached_known and oldest is not None and oldest < overlap_cutoff - timedelta(seconds=1):
                stop = f"known_history_with_{OVERLAP_HOURS:g}h_overlap"
            if stop:
                break
            if next_cursor in seen_cursors:
                raise CollectionError("Repeated pagination cursor")
            seen_cursors.add(next_cursor)
            cursor = next_cursor
        if not stop:
            raise CollectionError(f"Reached {max_pages} pages before covering the history window")
    except CollectionError as exc:
        error = str(exc)
    results = {}
    for category in manifest:
        code = category["item_code"]
        rows = sorted(kept[code].values(), key=lambda tx: (tx["sold_at"], tx["id"]), reverse=True)
        result = {
            **category, "status": "error" if error else "ok", "error": error,
            "attempted_at": stamp(now), "last_success_at": old[code].get("last_success_at") if error else stamp(now),
            "last_full_scan_at": old[code].get("last_full_scan_at") if error or not full_scan else stamp(now),
            # Reaching the depth this run set out to reach is what completes the history,
            # whether that was the retention boundary or the first run's initial bite.
            "history_complete": bool(old[code].get("history_complete"))
                                if error or stop not in complete_stops else True,
            "pages_fetched": pages, "stop_reason": stop, "full_scan": full_scan,
            "new_transaction_count": len(set(kept[code]) - known), "transaction_count": len(rows),
            "quality_issue_count": sum(bool(tx["quality_issues"]) for tx in rows),
            "transactions": [pack_transaction(tx) for tx in rows],
        }
        result["rolls"] = aggregate(rows, now)
        results[code] = result
    if error:
        print(f"Market history incomplete: {error}", flush=True)
    return results


def summarize(rows, now, timed=None):
    """`rows` price the roll; `timed` times it, and the two are not the same set.

    A sale off a listing that sat longer than the comps window is a poor comparable, so it
    is kept out of the price. Keeping it out of the time to sell as well was a mistake in
    one direction only: the filter drops slow sales and nothing else, so every roll it
    touched came out looking quicker than it is. On this cache it touched 298 of 1,072
    priced rolls, and the uncensored median was higher on all 298 of them - it cannot be
    otherwise. Forty rolls more than doubled, and the knife at attack 24, crit 5 published
    1.1 minutes against a true 2.6 days, which is the roll nobody wants reading as the
    fastest thing on the board.

    So the price keeps its filter and the clock does not."""
    timed = rows if timed is None else timed
    if not rows:
        return {"count": 0, "median": None, "recency_weighted_price": None, "weighted_median": None,
                "min": None, "max": None, "median_time_to_sell_seconds": None, "stale_excluded": 0}
    prices = [row["unit_price"] for row in rows]
    half_life = RECENCY_HALF_LIFE_HOURS * 3600
    weights = [2 ** (-max(0, (now - parse_time(row["sold_at"])).total_seconds()) / half_life) for row in rows]
    halfway = sum(weights) / 2
    cumulative = 0.0
    weighted_median = None
    for price, weight in sorted(zip(prices, weights)):
        cumulative += weight
        if cumulative >= halfway:
            weighted_median = price
            break
    durations = [row["time_to_sell_seconds"] for row in timed if row["time_to_sell_seconds"] is not None]
    return {"count": len(rows), "median": statistics.median(prices),
            "recency_weighted_price": sum(p * w for p, w in zip(prices, weights)) / sum(weights),
            "weighted_median": weighted_median, "min": min(prices), "max": max(prices),
            "median_time_to_sell_seconds": statistics.median(durations) if durations else None,
            # Sales the clock counted and the price ignored, so a reader can see how much of
            # the timing rests on listings the price would not trust. Named to stay clear of
            # the guard that keeps sale rows out of the on-load bundle.
            "stale_excluded": len(timed) - len(rows)}


def stale_listing(tx, max_hours=MAX_TIME_ON_MARKET_HOURS):
    """A sale off a listing that sat longer than the comps window. Its price was set under
    conditions the window is meant to exclude, whatever day it happened to clear on. An
    unknown time on market is not evidence of staleness, so it stays."""
    seconds = tx["time_to_sell_seconds"]
    return seconds is not None and seconds > max_hours * 3600


def retained_summary(rows, now, timed=None):
    """Wide enough to show a roll trades, not to price against, so it carries only what
    answers that. Recency weighting, spread and the rest are what the narrow windows are for,
    and repeating them here would cost every reader half again the download for fields the
    question does not use."""
    full = summarize(rows, now, timed)
    return {key: full[key] for key in ("count", "median", "median_time_to_sell_seconds", "stale_excluded")}


def aggregate(transactions, now, min_primary_comps=MIN_PRIMARY_COMPS):
    """Roll statistics at three widths: 24h, 48h, and everything retained.

    The comparison windows are narrower than retention on purpose - stale sales make poor
    comparables. But a roll is roughly one percent of its slot, so at 48h most of them are
    silent on any given day, and a consumer cannot tell "nobody wants this" from "none traded
    since Tuesday". The retained window answers that: it is too wide to price against, and
    exactly wide enough to show the roll does trade.

    It stays out of `selected` deliberately. Pricing against week-old sales would be a
    silent substitution; reporting them beside the empty window is an informed one.
    """
    groups = defaultdict(list)
    wide = defaultdict(list)
    # The same rows without the staleness filter, kept only to time the roll.
    groups_timed = defaultdict(list)
    wide_timed = defaultdict(list)
    for tx in transactions:
        if not tx["eligible_for_comps"]:
            continue
        sold = parse_time(tx["sold_at"])
        if not now - timedelta(hours=RETENTION_HOURS) <= sold <= now:
            continue
        recent_enough = sold >= now - timedelta(hours=COMPS_WINDOW_HOURS)
        wide_timed[tx["roll_key"]].append(tx)
        if recent_enough:
            groups_timed[tx["roll_key"]].append(tx)
        if stale_listing(tx):
            continue
        wide[tx["roll_key"]].append(tx)
        if recent_enough:
            groups[tx["roll_key"]].append(tx)
    rolls = {}
    for key, retained in sorted(wide.items()):
        rows = groups.get(key, [])
        rows_timed = groups_timed.get(key, [])
        cut = now - timedelta(hours=PRIMARY_HOURS)
        recent = [row for row in rows if parse_time(row["sold_at"]) >= cut]
        recent_timed = [row for row in rows_timed if parse_time(row["sold_at"]) >= cut]
        primary = summarize(recent, now, recent_timed)
        fallback = summarize(rows, now, rows_timed)
        use_primary = len(recent) >= min_primary_comps
        rolls[key] = {"exact_roll": roll_of(retained[0]), "primary_24h": primary, "fallback_48h": fallback,
                      "retained_window": retained_summary(retained, now, wide_timed.get(key, [])),
                      "retained_window_hours": RETENTION_HOURS,
                      "selected_window_hours": PRIMARY_HOURS if use_primary else COMPS_WINDOW_HOURS,
                      "selected": primary if use_primary else fallback,
                      "low_sample": (primary if use_primary else fallback)["count"] < min_primary_comps}
    return rolls


def normalize_prices(payload):
    if isinstance(payload, list):
        payload = {row.get("itemCode"): row for row in payload if isinstance(row, dict)}
    if not isinstance(payload, dict):
        raise CollectionError("Prices payload must be an object or array")
    return payload


def normalize_book(payload, code):
    if isinstance(payload, dict) and "buyOrders" in payload and "sellOrders" in payload:
        buys, sells = payload["buyOrders"], payload["sellOrders"]
    else:
        rows = payload if isinstance(payload, list) else payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise CollectionError("Unrecognized order book schema")
        buys, sells = [], []
        for row in rows:
            side = row.get("type", row.get("orderType")) if isinstance(row, dict) else None
            if side not in ("buy", "sell"):
                raise CollectionError("Order has no valid buy/sell side")
            (buys if side == "buy" else sells).append(row)
    if not isinstance(buys, list) or not isinstance(sells, list):
        raise CollectionError("Order book sides must be arrays")
    for row in buys + sells:
        if not isinstance(row, dict) or row.get("itemCode", code) != code:
            raise CollectionError("Order book item code mismatch")
        if number(row.get("price")) is None or row["price"] <= 0 or number(row.get("quantity")) is None or row["quantity"] < 0:
            raise CollectionError("Invalid order price or quantity")
    buys = sorted((r for r in buys if r["quantity"] > 0), key=lambda r: r["price"], reverse=True)
    sells = sorted((r for r in sells if r["quantity"] > 0), key=lambda r: r["price"])
    return {"buy_orders": buys, "sell_orders": sells,
            "best_bid": buys[0]["price"] if buys else None,
            "best_ask": sells[0]["price"] if sells else None, "raw": payload}


def collect_commodities(client, previous, now):
    try:
        prices = normalize_prices(client.call("itemTrading.getPrices"))
        price_error = None
    except CollectionError as exc:
        prices, price_error = {}, str(exc)
    result = {}
    for code, name in COMMODITIES.items():
        old = copy.deepcopy(previous.get(code, {}))
        row = {**old, "item_code": code, "name": name, "attempted_at": stamp(now), "errors": []}
        try:
            if price_error:
                raise CollectionError(price_error)
            raw = prices.get(code)
            price = number(raw.get("price")) if isinstance(raw, dict) else number(raw)
            if price is None or price <= 0:
                raise CollectionError(f"Missing or invalid price for {code}")
            row.update(price=price, price_raw=raw, price_fetched_at=stamp(now), price_status="ok")
        except CollectionError as exc:
            row["price_status"] = "error"
            row["errors"].append(str(exc))
        try:
            book = normalize_book(client.call("tradingOrder.getTopOrders", {"itemCode": code, "limit": 100}), code)
            row.update(order_book=book, book_fetched_at=stamp(now), book_status="ok")
        except CollectionError as exc:
            row["book_status"] = "error"
            row["errors"].append(str(exc))
        row["status"] = "error" if row["errors"] else "ok"
        # Retention applies to commodity observations too; never resurrect old prices.
        for time_key, value_keys in (("price_fetched_at", ("price", "price_raw")), ("book_fetched_at", ("order_book",))):
            if row.get(time_key) and parse_time(row[time_key]) < now - timedelta(hours=RETENTION_HOURS):
                for key in value_keys:
                    row.pop(key, None)
                row.pop(time_key, None)
        result[code] = row
    return result


def collect(client, previous=None, now=None, max_pages=1000):
    # Use the exact precision written to JSON so weighted summaries recompute identically.
    now = parse_time(stamp(now or utcnow()))
    previous = previous or {}
    manifest = categories()
    commodities = collect_commodities(client, previous.get("commodities", {}), now)
    results = collect_market(client, manifest, previous.get("categories", {}), now, max_pages)
    for code, row in results.items():
        print(f"{code}: {row['status']}, {row['transaction_count']} cached, {row['pages_fetched']} shared pages", flush=True)
    for code, row in commodities.items():
        if row["errors"]:
            print(f"{code}: {'; '.join(row['errors'])}", flush=True)
    failed = [code for code, row in results.items() if row["status"] != "ok"]
    failed_inputs = [code for code, row in commodities.items() if row["status"] != "ok"]
    quality_issues = sum(row["quality_issue_count"] for row in results.values())
    status = "ok" if not failed and not failed_inputs and not quality_issues else "degraded"
    return {
        "schema_version": SCHEMA_VERSION, "generated_at": stamp(now),
        "updated_at": stamp(now) if status == "ok" else previous.get("updated_at"),
        "status": status, "source": {"base_url": client.base_url, "attribution": "Supported by warerastats.io", "read_only": True},
        "policy": {"retention_hours": RETENTION_HOURS, "comps_window_hours": COMPS_WINDOW_HOURS,
                   "max_time_on_market_hours": MAX_TIME_ON_MARKET_HOURS,
                   "primary_hours": PRIMARY_HOURS, "min_primary_comps": MIN_PRIMARY_COMPS,
                   "full_condition_only": True, "recency_half_life_hours": RECENCY_HALF_LIFE_HOURS,
                   "incremental_overlap_hours": OVERLAP_HOURS, "full_rescan_interval_hours": FULL_RESCAN_HOURS,
                   "backstop_hours": BACKSTOP_HOURS,
                   "scan_mode": "shared_itemMarket_stream"},
        "health": {"category_count": 36, "categories_ok": 36 - len(failed), "failed_categories": failed,
                   "failed_commodities": failed_inputs, "quality_issue_count": quality_issues,
                   "request_count": client.requests, "transaction_count": sum(row["transaction_count"] for row in results.values())},
        "commodities": commodities, "categories": {cat["item_code"]: results[cat["item_code"]] for cat in manifest},
    }


def epoch(value):
    return int(parse_time(value).timestamp())


def shard_rows(code, category):
    """Compact sale rows for one item: [unit_price, sold_at, time_to_sell, roll_index].

    The roll index covers every roll seen in the retained window, which is wider than the
    comparison window, so a consumer can recompute statistics over more history than the
    published summaries use.
    """
    rows, keys = [], {}
    for stored in category["transactions"]:
        tx = unpack_transaction(stored, code)
        if not tx["eligible_for_comps"]:
            continue
        index = keys.setdefault(tx["roll_key"], len(keys))
        duration = tx["time_to_sell_seconds"]
        rows.append([tx["unit_price"], epoch(tx["sold_at"]),
                     None if duration is None else int(duration), index])
    rows.sort(key=lambda row: (row[1], row[0], row[3]))
    return rows, [json.loads(key) for key in keys]


def build_shard(code, category, payload):
    rows, rolls = shard_rows(code, category)
    return {"item_code": code, "name": category["name"], "tier": category["tier"],
            "rarity": category["rarity"], "slot": category["slot"],
            "generated_at": payload["generated_at"], "status": category["status"],
            "last_success_at": category["last_success_at"],
            "coverage_start": min((row[1] for row in rows), default=None),
            "rolls": rolls, "summary": category["rolls"], "sales": rows}


def build_summary(payload):
    """Every item's roll statistics with no sale rows: one small fetch answers any price."""
    return {"schema_version": SCHEMA_VERSION, "generated_at": payload["generated_at"],
            "updated_at": payload["updated_at"], "status": payload["status"],
            "policy": payload["policy"],
            "commodities": {code: {key: value for key, value in row.items() if key not in ("order_book", "price_raw")}
                            for code, row in payload["commodities"].items()},
            "categories": {code: {"name": row["name"], "tier": row["tier"], "rarity": row["rarity"],
                                  "slot": row["slot"], "status": row["status"],
                                  "last_success_at": row["last_success_at"],
                                  "transaction_count": row["transaction_count"], "rolls": row["rolls"]}
                           for code, row in payload["categories"].items()}}


def build_index(payload):
    return {"schema_version": SCHEMA_VERSION, "generated_at": payload["generated_at"],
            "updated_at": payload["updated_at"], "status": payload["status"],
            "source": payload["source"], "policy": payload["policy"], "health": payload["health"],
            "commodities": {code: {"price": row.get("price"), "status": row["status"],
                                   "best_bid": (row.get("order_book") or {}).get("best_bid"),
                                   "best_ask": (row.get("order_book") or {}).get("best_ask")}
                            for code, row in payload["commodities"].items()},
            "items": {code: {"status": row["status"], "transaction_count": row["transaction_count"],
                             "roll_count": len(row["rolls"]), "last_success_at": row["last_success_at"]}
                      for code, row in payload["categories"].items()}}


def build_commodities(payload):
    """Full order books for the input commodities, fetched on demand rather than on load.

    A crafting cost is what the book actually charges for the quantity being bought, not the
    best ask repeated, so a consumer needs the depth to walk it.
    """
    return {"schema_version": SCHEMA_VERSION, "generated_at": payload["generated_at"],
            "status": payload["status"],
            "commodities": {code: {"item_code": code, "name": row["name"], "status": row["status"],
                                   "price": row.get("price"),
                                   "price_fetched_at": row.get("price_fetched_at"),
                                   "book_fetched_at": row.get("book_fetched_at"),
                                   "order_book": {key: value
                                                  for key, value in (row.get("order_book") or {}).items()
                                                  if key != "raw"}}
                            for code, row in payload["commodities"].items()}}


def build_archive(payload, now):
    """Group retained sales into whole UTC days. Today is still accumulating and is skipped,
    so a day file is written once and then never changes again."""
    today = now.date()
    days = defaultdict(list)
    for code, category in payload["categories"].items():
        for stored in category["transactions"]:
            day = parse_time(stored["sold_at"]).date()
            if day < today:
                days[day.isoformat()].append({**stored, "item_code": code})
    for rows in days.values():
        rows.sort(key=lambda row: (row["sold_at"], row["id"]))
    return days


def book_ladder(order_book):
    """Both sides of a book as [price, quantity] rungs, best first, aggregated by price."""
    def side(orders, best_first_high):
        levels = {}
        for order in orders or []:
            price = number(order.get("price"))
            quantity = number(order.get("quantity"))
            if price is None or quantity is None or price <= 0 or quantity <= 0:
                continue
            key = round(price, 3)
            levels[key] = levels.get(key, 0) + quantity
        return [[key, round(levels[key])] for key in sorted(levels, reverse=best_first_high)]
    return {"b": side((order_book or {}).get("buy_orders"), True),
            "a": side((order_book or {}).get("sell_orders"), False)}


def book_snapshot(payload):
    """One line of depth for every commodity that reported a book this run.

    Prices are an outcome; a book is intent, and the collector was throwing the intent away
    every fifteen minutes. Whether the support under a price is building or eroding, whether
    a wall has rested there for an hour or a week, whether a level that held last Tuesday
    holds again - none of it can be answered from a single snapshot, and none of it can be
    recovered later. So the capture starts now and the reading of it can come whenever.

    Full depth rather than the top few rungs, because the question that prompted this was how
    far down the book a buyer could reasonably rest, and that is exactly what a trimmed
    ladder throws away. It costs almost nothing to keep everything: aggregating raw orders
    into price levels turns 200 orders into about 70 rungs, so a snapshot is 1.6 KB and a
    day of them 0.15 MB, against a repository already growing 5.5 MB a day."""
    books = {}
    for code, row in (payload.get("commodities") or {}).items():
        if row.get("status") != "ok" or "order_book" not in row:
            continue
        ladder = book_ladder(row["order_book"])
        if ladder["b"] or ladder["a"]:
            books[code] = ladder
    return {"t": payload["generated_at"], **books} if books else None


def append_book_history(payload, books_dir, now):
    """One file a day of newline-delimited snapshots, appended in place.

    Newline-delimited so a run appends rather than rewriting the day, which is what keeps
    the git cost to the bytes actually added. Re-running for a timestamp already recorded
    replaces that line rather than doubling it, so a re-run is not a second sample."""
    snapshot = book_snapshot(payload)
    if snapshot is None:
        return 0
    path = Path(books_dir) / f"{now.date().isoformat()}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                if json.loads(line).get("t") == snapshot["t"]:
                    continue
            except ValueError:
                raise CollectionError("Book history file holds a line that is not JSON")
            lines.append(line)
    lines.append(json.dumps(snapshot, ensure_ascii=False, allow_nan=False, separators=(",", ":")))
    lines.sort(key=lambda line: json.loads(line)["t"])
    atomic_text(path, "\n".join(lines) + "\n")
    return 1


def publish(payload, public_dir, archive_dir, now):
    """Write the consumer-facing artifacts. These are served, not committed; only the
    archive is durable, which is what keeps repository growth flat."""
    public_dir, archive_dir = Path(public_dir), Path(archive_dir)
    atomic_write(public_dir / "index.json", build_index(payload))
    atomic_write(public_dir / "summary.json", build_summary(payload))
    atomic_write(public_dir / "commodities.json", build_commodities(payload))
    written = 3
    for code, category in payload["categories"].items():
        atomic_write(public_dir / "prices" / f"{code}.json", build_shard(code, category, payload))
        written += 1
    for day, rows in build_archive(payload, now).items():
        target = archive_dir / f"{day}.json"
        existing = json.loads(target.read_text(encoding="utf-8")) if target.exists() else None
        merged = {row["id"]: row for row in (existing or {}).get("sales", [])}
        merged.update({row["id"]: row for row in rows})
        record = {"schema_version": SCHEMA_VERSION, "date": day, "sale_count": len(merged),
                  "sales": sorted(merged.values(), key=lambda row: (row["sold_at"], row["id"]))}
        if record != existing:
            atomic_write(target, record)
            written += 1
    return written


def atomic_write(path, payload):
    atomic_text(path, json.dumps(payload, ensure_ascii=False, allow_nan=False,
                                 separators=(",", ":")) + "\n")


def atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False) as handle:
            temp_name = handle.name
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def summaries_match(actual, expected):
    """Allow only tiny platform math differences in derived floating summaries."""
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(summaries_match(actual[k], expected[k]) for k in actual)
    if isinstance(actual, float) or isinstance(expected, float):
        return number(actual) is not None and number(expected) is not None and math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
    return actual == expected


def migrate(payload):
    """Upgrade an older cache in place so a format change never forces a full refetch.

    Schema 1 stored `raw`, `equipment` and `exact_roll` alongside the fields they duplicated.
    Every primitive field schema 2 needs is already present, so each record re-derives locally.

    Every version since has changed what aggregate() returns - schema 3 dropped sales off
    long-standing listings, schema 4 added the retained window, schema 5 stopped letting the
    staleness filter censor the time to sell. validate() recomputes those
    summaries as a tamper check, so any change to aggregate() leaves older caches failing it,
    and the collector rejects its own cache on load and cannot run at all. That is not a
    special case to handle once: it is what every future change to aggregate() will do. So
    the summaries are always rebuilt from the retained rows, which no such change touches,
    rather than the retention window being refetched.
    """
    version = payload.get("schema_version")
    if version == SCHEMA_VERSION:
        return payload
    if version not in range(1, SCHEMA_VERSION):
        raise CollectionError(f"Cannot migrate cache schema version {version!r}")
    if version == 1:
        for category in payload.get("categories", {}).values():
            category["transactions"] = [pack_transaction(tx) for tx in category.get("transactions", [])]
    generated_at = payload.get("generated_at")
    if generated_at:
        now = parse_time(generated_at)
        for code, category in payload.get("categories", {}).items():
            rows = [unpack_transaction(row, code) for row in category.get("transactions", [])]
            category["rolls"] = aggregate(rows, now)
    payload["schema_version"] = SCHEMA_VERSION
    print(f"Migrated cache from schema {version} to {SCHEMA_VERSION}", flush=True)
    return payload


def validate(payload, require_healthy=False, current_time=None):
    expected = {row["item_code"] for row in categories()}
    if payload.get("schema_version") != SCHEMA_VERSION or set(payload.get("categories", {})) != expected:
        raise CollectionError("Invalid schema version or incomplete category manifest")
    now = parse_time(payload.get("generated_at"))
    cutoff = now - timedelta(hours=RETENTION_HOURS)
    seen = set()
    for code, category in payload["categories"].items():
        stored = category["transactions"]
        if category["transaction_count"] != len(stored):
            raise CollectionError("Transaction count mismatch")
        rows = []
        for row in stored:
            if set(row) - set(STORED_FIELDS):
                raise CollectionError("Stored transaction carries unexpected fields")
            if row["id"] in seen or not cutoff <= parse_time(row["sold_at"]) <= now:
                raise CollectionError("Duplicate, misplaced, or expired transaction")
            seen.add(row["id"])
            rows.append(unpack_transaction(row, code))
        if category["quality_issue_count"] != sum(bool(tx["quality_issues"]) for tx in rows):
            raise CollectionError("Quality issue count does not match the retained transactions")
        if not summaries_match(aggregate(rows, now), category["rolls"]):
            raise CollectionError("Roll summaries do not match retained transactions")
    if set(payload.get("commodities", {})) != set(COMMODITIES):
        raise CollectionError("Missing commodity coverage")
    if require_healthy:
        if payload.get("status") != "ok" or payload.get("updated_at") != payload["generated_at"]:
            raise CollectionError("Collector is degraded; inspect health and category errors")
        if abs(((current_time or utcnow()) - now).total_seconds()) > 45 * 60:
            raise CollectionError("Output is older than 45 minutes or its clock is incorrect")
        if any(row["status"] != "ok" or not row["history_complete"] for row in payload["categories"].values()):
            raise CollectionError("Incomplete equipment history")
        for row in payload["commodities"].values():
            if row["status"] != "ok" or number(row.get("price")) is None or "order_book" not in row:
                raise CollectionError("Incomplete commodity prices/order books")
    return len(seen)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data/warera_case1_market.json")
    parser.add_argument("--public-dir", type=Path, default=ROOT / "public",
                        help="Consumer-facing index/summary/price shards; served, not committed")
    parser.add_argument("--books-dir", type=Path, default=ROOT / "data/books",
                        help="Where the daily order-book history is appended.")
    parser.add_argument("--archive-dir", type=Path, default=ROOT / "data/archive",
                        help="Write-once daily sale files; the durable history")
    parser.add_argument("--base-url", choices=(GATEWAY, OFFICIAL), default=GATEWAY)
    parser.add_argument("--max-pages", type=int, default=1000)
    parser.add_argument("--max-seconds", type=int, default=600)
    parser.add_argument("--validate", action="store_true", help="Validate existing JSON without network calls")
    parser.add_argument("--require-healthy", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.max_pages < 1 or args.max_seconds < 1:
            raise CollectionError("Page and time limits must be positive")
        if args.validate:
            count = validate(migrate(json.loads(args.output.read_text(encoding="utf-8"))), args.require_healthy)
            print(f"Validated all 36 categories and {count} transactions")
            return 0
        api_key = os.environ.get("WARERA_API_KEY", "").strip()
        if not api_key:
            raise CollectionError("WARERA_API_KEY is missing. Add the repository Actions secret or set it locally. No market cache was changed.")
        previous = None
        if args.output.exists():
            previous = migrate(json.loads(args.output.read_text(encoding="utf-8")))
            validate(previous)
            if previous["source"]["base_url"] != args.base_url:
                for category in previous["categories"].values():
                    category["history_complete"] = False
        client = Client(args.base_url, api_key, max_seconds=args.max_seconds)
        output = collect(client, previous, max_pages=args.max_pages)
        validate(output)
        atomic_write(args.output, output)
        files = publish(output, args.public_dir, args.archive_dir, parse_time(output["generated_at"]))
        books = append_book_history(output, args.books_dir, parse_time(output["generated_at"]))
        print(f"Saved {output['health']['transaction_count']} transactions and {files} published files"
              f"{' plus a book snapshot' if books else ''}; status={output['status']}")
        return 0 if output["status"] == "ok" else 1
    except (CollectionError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Collector failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
