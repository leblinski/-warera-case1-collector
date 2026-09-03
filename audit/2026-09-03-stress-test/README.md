# Audit briefing: WarEra price calculator + Case I collector

You are one of several investigators stress-testing two repos. Everything here has been
verified by the orchestrator; build on it rather than re-deriving it, and cite it when useful.

## Repos (read-only for you: do NOT modify anything under /home/user)

- Calculator: `/home/user/WarEra-Selling-Price-Calc/test60.html` (7,460 lines). CSS lines
  12–2707, HTML body 2709–3327, one IIFE of ES5 JS at lines 3328–7459. No build, no deps.
  Served from GitHub Pages; fetches collector files from
  `https://leblinski.github.io/-warera-case1-collector/{index.json,summary.json,commodities.json,prices/<code>.json}`.
- Collector: `/home/user/-warera-case1-collector/collector.py` (850 lines),
  `tests/test_collector.py` (41 tests, all pass with `python -m unittest discover -s tests`),
  `config/case1_items.json`, `README.md`, `.github/workflows/collect.yml`.
  Committed rolling cache: `data/warera_case1_market.json` (36 MB, schema 4,
  generated_at 2026-09-03T15:30:50Z, 126,800 retained sales, oldest 2026-08-29T00:31Z).
  Daily archives `data/archive/2026-08-29..09-02.json` (write-once whole UTC days).
  Git history has 50 commits, each a snapshot of the rolling cache (~15 min apart today).

## Key code locations in test60.html (line numbers)

- Constants: `WEAPON_STATS` 3359, `STAT_RANGES` 3367, `RARITY_BANDS` 3943, `SCRAP_YIELDS` 4142,
  `CRAFT_SLOT_WEIGHT` 4224, `CASE_TIER_ODDS` 4227, `CRAFT_STEEL` 4228, `THIN_SALES=5` 5383,
  `sortMin={abs:0.10,pct:0,join:'both'}` 4415. Tax input default 1 (line 2814).
- Economics: `craftRollSpace` 4244, `bookLevels` 4259, `bookPanel` 4274, `craftRollKey` 4307,
  `craftSlotValue` 4316, `craftExpected` 4346, `sortNeed` 4437, `sortRolls` 4445,
  `fillQuiet` 4496 (neighbour fill), `cutRule` 4515, `craftDismantle` 4569 (= yield × scraps best_bid,
  0 if no bid), `craftBook` 4576, `craftWalk` 4585, `paintCraft` 4619, simulators
  `simPick/craftRollTable/simDraw/simOpenOne/simRun/craftSimRun` 4756–5022, `paintCase` 5024,
  `paintSort` 5191, `sortDetail` 5395 (thin marker `x.n<THIN_SALES`), `paintCutCard` 5447.
- Data plumbing: `paintDataStamp` 5481, `refreshCollector` 5513, `loadCraftData` 5568,
  `collectorFile/loadIndex/loadSummary/loadBooks` 5614–5624, live Gateway merge
  `liveRow/fetchLiveSales/saleKey/mergeSales/loadShard/shardSales` 5637–5710,
  `getMarketTransactions` 6009, `rarityRanges/tiersForPrice` 3945–3997, `factsFor/rollNeighbours` 3456–3513,
  `scrapPriceFor/paintScrap/loadScrapPrice` 4145–4213 (Price-tab dismantle floor).
- Price-tab "Trends" model (separate pricing engine): `recencyWeight` 5750, `median/robustFilter/
  weightedQuantileBy/dispersion` 5767–5793, `nearestWorse/nearbyBetter/weaponScore` 5804–5842,
  `singleModel` 5889, `weaponModel` 5947, `downwardRepriceGate` 5868, `renderModel` 6221,
  `opportunityDepthBands` 6064.

## Collector schema the page consumes (schema_version 4)

Per item `categories[code].rolls[roll_key]` = `{exact_roll:{skills:{...}}, primary_24h, fallback_48h,
retained_window:{count,median,median_time_to_sell_seconds}, retained_window_hours:168,
selected_window_hours:24|48, selected:<primary or fallback>, low_sample:bool}` where each
window is `{count, median, recency_weighted_price, weighted_median, min, max,
median_time_to_sell_seconds}` (all null except count=0 when empty). `selected` = primary_24h if
its count ≥ MIN_PRIMARY_COMPS=3 else fallback_48h. Comps exclude: non-full-condition, non-single,
invalid roll/price, and `stale_listing` (time_to_sell > MAX_TIME_ON_MARKET_HOURS=48).
Commodities `case1/scraps/steel`: `{price, order_book:{buy_orders,sell_orders,best_bid,best_ask}}`.
Shard sale rows: `[unit_price, sold_at_epoch_s(int, floor), time_to_sell_s|null, roll_index]`.
The page reads `selected.median/count/min/max/median_time_to_sell_seconds`, `fallback_48h.count/min/max`,
`retained_window.*`, `exact_roll.skills`, `commodities.scraps.best_bid` (index.json) and
`commodities[code].order_book` (commodities.json). It never checks `schema_version`.

## Established facts (all reproduced by the orchestrator; cite freely)

- Full roll space = 1,810 rolls (weapons 100/50/100/150/300/800; armour bands per STAT_RANGES).
  Snapshot: 1,295 rolls seen in 7 days, 1,040 with a `selected.median`, 458 of those with
  count < 5, 255 quiet (retained only). Coverage by item: knife 46/100, gun 50/50, rifle 100/100,
  sniper 150/150, tank 284/300, jet 110/800; all armour fully covered except mythic slots.
- Reference EV (`ev_ref.py`, mirrors the page exactly; the page under Playwright renders the
  identical figures): scraps best_bid 0.225, case best ask 3.55, **case gross 3.6781, edge +0.1281
  = +3.61%**, sd 7.06. Per tier net: 1.5806 / 4.0556 / 13.4718 / 50.809 / 137.775 / 379.827;
  broken share 13% / 99% / 64% / 0% / 3% / 9%. Craft rows: −47.9% / −45.3% / −28.7% / +1.6% /
  +0.8% / −0.9%. The brief's 3.7114 vs 3.558 (+4.3%) was an earlier snapshot.
- Bar sweep (abs bar → gross): 0→3.6848, 0.1→3.6781, 0.5→3.5784, 1→3.5514, 1000→3.3010; monotone.
  Pure scrap floor = 0.225 × Σ odds×yield = 3.3010.
- Weighting/estimator sensitivity at bar 0.10: even-median +3.61%; "as traded" (weight by
  fallback_48h.count) +9.47%; weighted_median +3.49%; recency mean +3.02%; min −1.94%.
- `money` is on the seller's 3-decimal typed grid: 900 of 126,800 values (0.71%) are
  unreachable as round3(typed×1.01) (half-up), 437 (0.34%) half-even; the skip residues match
  50+101k exactly (e.g. 1.868, 2.474, 2.777). If money were the tax-inflated displayed price the
  count would be ~0. The Price tab's flip maths (`flipCheckCore` 4116, `entryForDisplayed` 3926)
  assumes displayed = typed×(1+tax) and profit = typed − displayed_buy, i.e. the seller nets the
  typed figure; the Sort/Craft/Cases tabs net median×(1−tax). One of these is a double count.
- Sale counts per roll (7-day retained): flat across the band only where every roll is listed
  (Epic+: boots4 1754/1816/1613/1569/1693; sniper attack 499–609 per value; tank flat), and
  skewed toward the top roll exactly where low rolls are told to be broken (boots1 161/162/186/
  288/728; knife attack 40 = 600 of 1,712; gun attack 60 = 1083 vs ~760; helmet3 130→477).
  Small excess at the band maximum even at Epic (sniper 130: 609 vs ~530; gun crit 10 +18%).
- Stale-listing filter: excludes 1,448 of 46,508 sales in the 48h window (3.1%; basic 5.7%,
  mythic 8.0%). 1,218 of the 1,284 excluded sales on affected rolls were priced at/above the
  filtered median: the filter lowers roll medians slightly (median change −0.02%, mean −0.17%,
  10th pct −0.59%).
- Time to sell (all retained): median 20 min, p75 2.1h, p90 12h, p95 28h, p99 7.5d, 3.4% > 48h.
  By tier median: basic 70 min, reinforced 1.3 min, advanced 21, elite 23, legendary 79, mythic 212.
- 15,354 sales (12%) have a seller who was earlier the buyer of the same roll of the same item
  (an upper-ish bound on flips; false positives likely on 5-roll items).
- Every retained sale has offer_created_at, quantity 1, state 100/100.
- The page's Uncommon (tier 2) value equals scrap (99% broken): the Uncommon market clears at
  ~4.05–4.1 against a scrap value of 4.05, in ~1 minute median — effectively a dismantler's bid.

## Tools in this directory (`/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit`)

- `ev_ref.py`: `Model(snap, tax, bar_abs, bar_pct, join, estimator, weighting, scrap_bid)` with
  `.case(n)`, `.craft_expected(t)`, `.slot_value(slot,t)`; `craft_walk(book, qty)`; `roll_space`,
  `roll_key`. Run `python3 ev_ref.py --tax 1 --bar 0.1`.
- `harness.js`: Playwright. `const {withPage,text,dumpAll}=require('./harness')`;
  `withPage({publicDir, tab, overrides:{'index.json': obj | {__status:404}}, localStorage:{...}, now:ms}, async (page, {log, requests}) => {...})`.
  All collector URLs are answered from `publicDir` (default `../public`, generated from the
  committed snapshot with `collector.publish`); every other host returns 403 like the proxy.
  `node harness.js` dumps the Cases/Craft/Sort figures. The JS is inside an IIFE: drive the DOM
  (`#tabBar [data-tab=cases]`, `#caseVerdict`, `#caseDetail`, `#caseRows`, `#craftRows`,
  `#sortRows`, `#sortPick [data-sorttier=N]`, `.cut-row.tap` to open a slot, `#sortMin`,
  `#tax`, `#price`, `#rarityBtns [data-tier=N]`, `#slotGrid [data-slot=x]`, `#rollGrid [data-roll=v]`,
  `#analyseBtn`, `#rollFacts`, `#dataStamp`) and read rendered text.
- To publish shards from a modified snapshot: `python3 -c "import json,collector as c; p=json.load(open(SNAP)); c.publish(p,OUT_PUBLIC,OUT_ARCHIVE,c.parse_time(p['generated_at']))"`
  run from the collector repo dir (add it to `sys.path`).
- Python 3.11 (stdlib only; no numpy/pandas — check with `python3 -c "import numpy"` before assuming),
  Node 22, Playwright at `/opt/node22/lib/node_modules/playwright`, Chromium preinstalled.

## Rules

- Network is locked: every WarEra host and leblinski.github.io return 403 at the proxy. Do not curl.
- Never request, print, or use an API key. There is none available and none is needed.
- Verify before you assert: run code, quote numbers with the command that produced them. Put
  every script you write under `audit/<your-dimension>/` so it can be re-run.
- Rank by whether a finding changes a number or a verdict a user acts on. A rounding nit and a
  systematically wrong EV are not the same finding. Say what you would measure to know a fix worked.
- Your final output is data for the orchestrator, not prose for the user. Be concrete and dense.
