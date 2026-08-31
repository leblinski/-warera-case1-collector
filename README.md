# WarEra Case I collector

Standalone, read-only collector for the 36 Case I equipment categories. It writes
`data/warera_case1_market.json` and updates it through GitHub Actions every 15 minutes.
Supported by [warerastats.io](https://warerastats.io/).

## Setup

1. Add a valid WarEra API key as the repository Actions secret `WARERA_API_KEY`:
   [repository secrets](https://github.com/leblinski/-warera-case1-collector/settings/secrets/actions).
   Use an API key issued through your WarEra account, never a session cookie or password.
   Do not commit the key or paste it into source files.
2. Push the project to `main`. Changes to the collector, config, tests, or workflow
   automatically start collection. You can also select **Run workflow** under
   [Actions](https://github.com/leblinski/-warera-case1-collector/actions).
3. A successful run commits the rolling JSON to `main`. The workflow's job requests
   `contents: write`; repository rules must permit its bot to update `main`.

The workflow uses `*/15 * * * *` in UTC, a manual trigger, one serialized collection
job, Python 3.12, and no third-party Python dependencies. GitHub scheduled runs can
be delayed; this is a requested cadence, not a guaranteed delivery time. GitHub may
disable public-repository schedules after 60 days without repository activity.

## Local usage

Python 3.11 or newer is required. Set `WARERA_API_KEY` in your environment without
saving it in the repository, then run:

```sh
python -m unittest discover -s tests -v
python collector.py
python collector.py --validate --require-healthy
```

The default source is `https://gateway.warerastats.io/trpc`. Both the Gateway and
the official transaction API require an API key for the required data. To explicitly
use the official source instead:

```sh
python collector.py --base-url https://api2.warera.io/trpc
```

Changing sources forces another full history scan; cursors are never shared between
sources. `--output PATH`, `--max-pages N`, and `--max-seconds N`
are available. Use a separate output path for experiments. Missing keys and corrupt
existing caches cause a nonzero exit without overwriting the cache.

## Collected data

`config/case1_items.json` lists six tiers with one weapon plus boots, helmet,
gloves, chest and pants in each tier:

| Tier | API rarity | Weapon | Armour suffix |
| --- | --- | --- | --- |
| Basic | common | knife | 1 |
| Reinforced | uncommon | gun | 2 |
| Advanced | rare | rifle | 3 |
| Elite | epic | sniper | 4 |
| Legendary | legendary | tank | 5 |
| Mythic | mythic | jet | 6 |

One shared market scan uses `transactionType=itemMarket`, `limit=100`, and the
returned `nextCursor`. It distributes records by exact `itemCode` into all 36
categories, ignoring equipment outside Case I. This avoids 36 separate filtered
history queries. Category `pages_fetched` counts shared pages, not extra requests
per category. Prices and order books are collected before the market scan so a
slow history request cannot starve commodity collection.

The first run scans back at least 48
hours, or to the source's end of history. Incremental runs revisit one hour before
the previous successful checkpoint to capture delayed ingestion. A full scan runs
at least every six hours. Delays beyond the overlap are recovered on that full
scan, provided the source still exposes them within the rolling 48-hour window.

Each cached sale includes:

- Stable transaction ID, sale timestamp, seller/buyer IDs, total money and quantity.
- Full original transaction in `raw`, plus its original equipment object.
- Exact `skills` and `stats`, with separate roll keys; no rounded/bucketed rolls.
- Equipment `state`, `max_state`, condition ratio and full-condition flag.
- Offer timestamp and time-to-sell when available. Missing durations stay null.

Only single equipment sales with known 100% condition, valid exact stats, and a
positive price enter comparisons. Used equipment remains in the raw cache. Missing
stats/condition are flagged and excluded; they are never assumed to be full condition.
Raw transactions are retained exactly as JSON values; transport whitespace is not
preserved. Unknown fields remain available for auditing.

Per exact roll, `primary_24h` and `fallback_48h` contain sample count, median,
12-hour half-life recency-weighted mean, weighted median, min/max, and median
time-to-sell. Three or more recent sales select the 24-hour window; fewer select
the full 48-hour window and flag low sample size when still below three. These
statistics describe completed sales, not guaranteed executable prices, net proceeds,
or a full case-profit/EV model. There is no interpolation between rolls.

Commodity coverage is `case1` (Case I), `scraps` (Scrap), and `steel` (Steel).
It includes current reference prices, up to 100 orders on each side when returned
by the source, best bid/ask, timestamps, and raw order-book responses. Empty sides
have null best prices. The live API's `buyOrders` and `sellOrders` structure is
handled explicitly.

## Output health and failure safety

- `generated_at` is the run's observation cutoff; `updated_at` advances only when
  every category and commodity succeeds with no recorded data-quality issues.
- `status` is `ok` or `degraded`. `health` lists failed categories/commodities and
  sample counts. Each category/commodity also carries its own status and timestamps.
- Individual failures retain valid cached data, prune observations older than 48
  hours, and never advance the failed category's successful checkpoint. A failed
  initial backfill cannot cause an incremental run to skip missing pages.
- Repeated cursors, page/time caps, malformed response schemas, authentication
  errors and wrong-category records produce explicit failures, not empty success.
- One shared limiter caps requests at approximately 120/minute, below the Gateway's
  documented 200/minute limit. Retries honor HTTP `Retry-After`; 401/403 are not retried.
- Writes use a temporary file followed by atomic replacement. Before replacement,
  validation recomputes roll statistics and checks IDs, age limits, raw/normalized
  consistency, and all 36 category keys.
- The workflow commits valid partial results and then fails visibly if collection
  was degraded. An invalid cache is never committed. An artifact is retained for
  two days when a JSON file exists. Code tests never use a real API key.

The 48-hour limit applies to the current JSON's transactions and commodity
observations. Git commit history retains older snapshots; this is not a historical
data deletion policy. The collector cannot guarantee the upstream Gateway's
database is complete; `history_complete` means pagination reached the requested
boundary or the source reported its end of history. Sparse categories may have
zero trades even when fetched successfully.

## Validation and provenance

This version was reconstructed from the requirements in the referenced conversation.
The original `warera-case1-collector.zip` was not available through the conversation
handoff, so an identical original directory structure could not be verified.

On 2026-08-31, the live official game config confirmed all 36 codes and rarities.
Public commodity price/order-book calls succeeded. The first authenticated Actions
run retrieved live equipment sales but exposed slow category-filtered queries and
a timestamp-precision mismatch in summary validation. The collector now scans the
shared market stream and uses the serialized timestamp precision throughout.
The [first successful live run](https://github.com/leblinski/-warera-case1-collector/actions/runs/33374184973)
collected 43,535 sales across all 36 categories, plus all three commodity prices
and order books, with zero data-quality issues. Its JSON was committed to `main`.
The [next successful run](https://github.com/leblinski/-warera-case1-collector/actions/runs/33374990632)
validated the rolling update: 43,616 retained sales, 208 new IDs, and 127 expired
IDs removed, using 18 API requests. Both runs completed on 2026-08-31.
All 28 local tests pass. Validation permits a relative/absolute tolerance of
1e-12 for derived floating summaries because Windows and Linux can differ by one
last decimal place. Original transactions, equipment, exact roll values, counts,
and timestamps remain checked without that floating-summary tolerance.
Check the latest Actions run and JSON health fields for ongoing collection status.

Sources checked for protocol/schema compatibility:

- [Gateway documentation](https://gateway.warerastats.io/)
- [Gateway authentication and routing source](https://github.com/Hattorius/War-Era-Gateway/blob/main/cmd/gateway/main.go)
- [Gateway transaction pagination source](https://github.com/Hattorius/War-Era-Gateway/blob/main/internal/database/models/transaction.go)
- [Python client transaction model](https://github.com/WarEraProjects/api-client-py/blob/main/warera/models/transaction.py)
- [Python client equipment model](https://github.com/WarEraProjects/api-client-py/blob/main/warera/models/inventory.py)
- [GitHub schedule behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
