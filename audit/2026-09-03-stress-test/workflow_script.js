export const meta = {
  name: 'warera-stress-test',
  description: 'Adversarial audit of the WarEra calculator and collector: 8 investigators, a refuter per substantive finding, a completeness critic',
  phases: [
    { title: 'Investigate', detail: 'one investigator per dimension, each runs code against the snapshot and the page' },
    { title: 'Verify', detail: 'an adversarial refuter re-runs every substantive finding' },
    { title: 'Critic', detail: 'what did the sweep miss' },
  ],
}

const AUDIT = '/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit'
const PRE = `Read ${AUDIT}/README.md first and treat every fact in it as established (cite it, do not re-derive it). ` +
  `Work only inside ${AUDIT}/<your-dimension>/ (create it); never modify anything under /home/user. ` +
  `The network is locked (every WarEra host and GitHub Pages return 403); never request or use an API key. ` +
  `Python 3.11 stdlib only unless you check a module imports; Node 22 with Playwright at /opt/node22/lib/node_modules/playwright. ` +
  `Verify before you assert: every number you report must come from a script you ran, saved in your directory, with the command in the finding's reproduction field. ` +
  `Rank findings by whether they change a number or a verdict a user acts on. Prefer five findings that can be acted on over thirty that cannot. ` +
  `Your final output is data for an orchestrator, not prose for the user: be dense and concrete, include the exact figures and the counterfactual figures. ` +
  `If the brief's claim holds, say so plainly and why; agreeing is fine when the evidence supports it, but you must have tried to break it first.\n\n`

const FINDINGS = {
  type: 'object', required: ['dimension', 'claim_verdicts', 'findings', 'scripts'],
  properties: {
    dimension: { type: 'string' },
    claim_verdicts: { type: 'array', items: { type: 'object', required: ['claim', 'verdict', 'reason'], properties: {
      claim: { type: 'string' }, verdict: { type: 'string', enum: ['holds', 'holds-with-caveat', 'wrong', 'unverifiable'] }, reason: { type: 'string' } } } },
    findings: { type: 'array', items: { type: 'object',
      required: ['id', 'title', 'severity', 'summary', 'evidence', 'reproduction', 'proposed_change', 'what_to_measure', 'confidence'],
      properties: {
        id: { type: 'string' }, title: { type: 'string' },
        severity: { type: 'string', enum: ['changes-a-number', 'changes-a-verdict', 'robustness', 'nit'] },
        summary: { type: 'string', description: 'one paragraph: the defect or the confirmation, with the number it changes and by how much' },
        evidence: { type: 'string', description: 'the figures and code lines that establish it' },
        reproduction: { type: 'string', description: 'exact commands / script paths that reproduce the figures' },
        proposed_change: { type: 'string' }, what_to_measure: { type: 'string' },
        confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
        code_refs: { type: 'array', items: { type: 'string' } } } } },
    scripts: { type: 'array', items: { type: 'string' }, description: 'paths of scripts you wrote' },
    notes: { type: 'string' },
  } }

const VERDICT = {
  type: 'object', required: ['refuted', 'confidence', 'reasoning', 'corrected'],
  properties: {
    refuted: { type: 'boolean', description: 'true if the finding is wrong, overstated, or could not be reproduced' },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
    reasoning: { type: 'string', description: 'what you ran, what you found, where the finding stands or falls' },
    corrected: { type: 'string', description: 'the corrected statement of the finding with corrected numbers, or the confirmation with your independently reproduced numbers' },
    severity_override: { type: 'string', enum: ['changes-a-number', 'changes-a-verdict', 'robustness', 'nit', ''] },
  } }

const CRITIC = {
  type: 'object', required: ['missing', 'overall'],
  properties: {
    missing: { type: 'array', items: { type: 'object', required: ['angle', 'why', 'how'], properties: { angle: { type: 'string' }, why: { type: 'string' }, how: { type: 'string' } } } },
    contradictions: { type: 'array', items: { type: 'string' } },
    overall: { type: 'string' },
  } }

const DIMS = [
  { key: 'ev-arithmetic', prompt: PRE + `Dimension: ev-arithmetic. Claims 1 and 3 of the brief (case EV +4.3%, the bar as a threshold). Hypotheses to test, each with numbers:
(a) The tax model. money is on the seller's typed grid (README). The Sort/Craft/Cases tabs net median*(1-tax); the Price tab's flip maths nets the typed figure and charges the buyer typed*(1+tax) (flipCheckCore 4116, entryForDisplayed 3926, paintScrap 4154 which divides the scrap floor by (1+tax)). Enumerate every place the page applies tax, state the model each implies, and quantify what changes if the seller actually nets the typed price: case gross/edge (use ev_ref.Model with tax=0 as the 'seller nets typed' case), craft rows, and the number of Sort verdicts that flip (rolls with median*0.99 <= need < median), by tier. Do the same for the Price-tab dismantle floor formula versus craftDismantle. Do not decide which model the game uses (you cannot); make the inconsistency and its size the finding.
(b) The scrap side. craftDismantle = yield*best_bid with no walk and no tax; the case card walks the ask book for the cost but not the bid book for the scraps. From commodities.json quantify: bid depth at best bid and within 1%, scraps produced by 100 and 1,000 opened cases at the tier odds and the break shares, and whether the walk would move the figure. Sensitivity: d(edge)/d(scrap bid), the scrap bid at which the case edge is zero, and d(edge)/d(case ask).
(c) Coverage handling. craftExpected renormalises over slots with data; paintCase adds nothing for a tier with none. With ev_ref, remove one slot at a time and one tier at a time and report how the case figure moves; then judge whether 'assumed to price like the rest' is the right default for the knife (46/100 rolls priced, 18.6% of all case outcomes) - compare the priced knife rolls' medians against what fillQuiet would say about the unpriced ones.
(d) Claim 3. Show the bar is a threshold, not a cost: the EV moves 3.6848 -> 3.6781 for a 0.10 bar; then compute the alternative 'bar as a per-listing cost' EV (subtract 0.10 per listed piece) and state which model matches what a person sorting loot actually experiences. Check sortNeed with join='either' and a pct bar for any non-monotone or paradoxical case (e.g. pct bar with dis=0 when the bid is missing). Re-derive the comment at line 4410 ('21.5 listings per 100 cases into dismantles, gives up 1.13 gold') from the snapshot.
(e) The 'free money' sanity argument (nobody takes an edge on a 3,500-deep book). Give it a quantitative treatment: daily sale volume per tier and per item from the snapshot, how many cases per day an opener could sell into that volume before being X% of it (X = 10, 25, 50), the variance figure (sd 7.06, ~12,100 cases), capital lockup and listing labour; conclude whether the argument can distinguish +4% from +9%.
(f) Bracket the EV with alternative price definitions from the shards (prices/<code>.json sale rows): selected median (page), 25th percentile of the last 48h, min, last sale, and a 'what actually clears fast' price (median of sales that sold within 30 minutes). Report the case edge under each.
Return findings with the counterfactual numbers, and a verdict on claims 1 and 3.` },

  { key: 'roll-odds-selection', prompt: PRE + `Dimension: roll-odds-selection. Claim 2 (every roll equal weight) and the selection-bias and time-to-sell doubts in the brief. Hypotheses:
(a) Are case/craft draws uniform within a band? Sale counts per roll are flat only where every roll gets listed (README). Extend this: for every item compute counts per roll (7-day retained), a chi-square-style dispersion statistic against uniform, and separate the items where the Sort tab says every roll sells (Epic+, and check the exact set from ev_ref) from the rest. Quantify the excess at the band maximum where it exists (sniper attack 130, gun attack 60, crit maxima) and say whether it is consistent with uniform draws plus listing selection, or needs a non-uniform RNG. State what a case-opening log would have to record to settle it.
(b) The removed 'as traded' weighting: reproduce +9.47% with ev_ref weighting='as_traded' and decompose which items drive the gap (knife 40/5 at 4.329 with 600 of 1,712 knife sales at attack 40, etc.). Was removing it right, and did it carry information: is there any roll where trade frequency is informative about the draw (e.g. the Epic max-roll excess)?
(c) Unpriced rolls are excluded from the mean, so 'untraded rolls price like traded ones'. For each item list the unpriced rolls, what fillQuiet's neighbour rule says for each, and recompute the case EV under three assumptions for unpriced rolls: worth scrap; worth the nearest-worse priced neighbour's value; as the page assumes. Report the three case edges. The knife and the tank matter; the jet does not (0.0001 odds) but report it.
(d) Selection bias of completed sales. Every price is a sale. Bound the effect: (1) refine the 15,354 flip estimate with stricter matching (same item, same roll, buyer of an earlier sale is the seller of a later one, restricted to items with roll spaces >= 50 to limit collisions); report the share of volume that is flipper resale, by tier, and whether flip resales price differently from first sales (median ratio per roll). (2) For flip pairs the time_to_sell is the flipper's relist, not the original listing: quantify how the reported 'sells in' changes if flips are excluded. (3) The survivorship problem: 'sells in N minutes' is conditional on selling inside the window; using the time-to-sell distribution of sales priced at or above the roll median, estimate what share of listings at the median price would still be unsold after 24h and 48h, and translate that into a plausible haircut on the case EV (unsold pieces are broken for scrap instead). Be explicit that this is a bound, and show the sensitivity.
(e) Check 'sells in 8 min' (the brief) against the collector's median_time_to_sell_seconds: which population produces 8 minutes, and what does the median look like for sales at <= the roll median versus above it, per tier.
Return findings and a verdict on claim 2 and on the two doubts (selection bias, time-to-sell).` },

  { key: 'estimator-thin', prompt: PRE + `Dimension: estimator-thin. Claims 4 (the median is the right listing price; no better estimator) and 6 (thin-evidence marker at 5). Use the shards in ${AUDIT}/../public/prices/*.json (rows [unit_price, sold_at_epoch_s, time_to_sell_s, roll_index]) and/or the raw snapshot.
(a) Reproduce the brief's split test: 45,000 sales over 561 rolls, asking at the upper quartile earns +0.68% and takes 6x longer to clear (47 vs 8 min). Choose a roll-count threshold that yields about 561 rolls, compare sales priced at >= Q3 against those at the median (price uplift, median time-to-sell), and report your numbers and the threshold. If you cannot reproduce them, say what you get and why the figure may differ.
(b) Out-of-sample estimator comparison. For each roll with enough history, use rolling origins T inside the 7-day window: estimate from sales before T, score against sales in (T, T+24h]. Estimators: plain 48h median; the collector's selected (24h median if >=3 else 48h); recency-weighted median (12h half-life); recency-weighted mean; 20% trimmed mean; last-3 median; Q25; Q75; retained 7-day median. Losses: relative MAE, signed bias, and a 'would it have sold' proxy (share of subsequent sales at or above the estimate). Report a table. Say whether any estimator beats the plain median by more than noise.
(c) The 24h/48h switch at MIN_PRIMARY_COMPS=3: on rolls where both windows are populated, does the 24h median predict the next day's sales better than the 48h median? Report.
(d) Claim 6. For rolls with >= 30 sales in 48h, subsample n = 1..10 sales and measure the subsample median's relative error against the full median (median absolute and 90th percentile), as a function of n; where does the curve flatten, and is 5 the right cut? Also: the thin count is selected.count (a 24h window when >= 3), so a roll with 3 sales in 24h and 12 in 48h is marked thin; count how many rolls are marked thin that have >= 5 in 48h, and how many unmarked rolls have a 48h min-max range wider than 10% of the median (which is the thing the marker is standing in for). Compare treatments: binary marker, showing the count, showing the range (rollFacts already shows min-max on the Price tab), or a confidence band.
(e) For thin rolls, does the retained 7-day median predict next-day sales better than the thin 48h median? Report, since the Sort/Cases could use it as a fallback.
Return findings with tables, and verdicts on claims 4 and 6.` },

  { key: 'neighbour-fill', prompt: PRE + `Dimension: neighbour-fill. Claim 5: for rolls with no recent sale, the nearest worse roll of the same kind (same crit band for weapons) settles sell-or-break; claimed 97.2% held-one-out over 1,167 rolls, 100% knife, 93% rifle; the neighbour price is a true lower bound only ~2/3 of the time; so it is used for the verdict, never the price.
(a) Reproduce. Implement fillQuiet (test60.html 4496) exactly in Python over the snapshot: roll space per craftRollSpace, verdict = median*0.99 > need(t) with need = 18-tier scrap value + 0.10 (ev_ref has need/dismantle), neighbour = nearest lower attack (same crit) or lower stat that has a price or a retained-window median. Held-one-out: for every roll with a selected median, hide it, find its neighbour, compare verdicts. Report accuracy overall, per tier, per slot, per true class (sell/break), the confusion matrix, and the majority-class base rate so 97.2% is judged against something. The current snapshot has 1,040 priced rolls, not 1,167; report yours.
(b) Reproduce the '2/3 lower bound' figure: share of priced rolls whose median is >= the neighbour's median, and the distribution of the neighbour's relative price error.
(c) Alternatives, same protocol: nearest neighbour either direction; for weapons the same attack at the next crit down; linear interpolation between the nearest priced rolls; and the retained-window verdict (fillQuiet uses wide.price for rolls that have one). On rolls that have both a selected median and a retained median, report verdict agreement and, where they disagree, which one the next 24h of sales vindicates.
(d) The verdict-only split: quantify what a neighbour price would cost if shown (relative error distribution) versus what showing nothing costs (share of the roll space with no price on the Sort tab), and say whether a marked neighbour price would be better than a dash.
(e) Code checks: sortHeat (5316, 5337) uses wide.price*0.99 with a hard-coded tax instead of taxMul; cutRule (4515) ignores neighbour verdicts (only x.net != null) while sortDetail shows them - is the cut line consistent with the roll list; paintCutCard counts; fillQuiet's handling of rolls with wide (verdict from the week median, no from); the bar sweep interaction. Verify each claim in the code before reporting it.
Return findings and a verdict on claim 5.` },

  { key: 'seam-robustness', prompt: PRE + `Dimension: seam-robustness. The collector -> page contract. Use ${AUDIT}/harness.js (withPage with overrides) to feed the page broken or degraded collector files and read what it shows. First enumerate every collector field the page reads and whether it is guarded. Then test at least these, reporting for each what the user sees and whether a WRONG NUMBER is shown WITHOUT A WARNING (that is the severity axis):
(a) index.json 404 with summary/commodities fine; (b) commodities.json 404; (c) summary.json 404; (d) scraps order_book with empty buy_orders and best_bid null (hypothesis: craftDismantle returns 0 so every roll 'sells', the case EV becomes the pure sale mean, and nothing says so - measure the case figure); (e) case1 sell_orders empty; (f) a category missing from summary (delete knife); (g) a tier with zero coverage (delete all six Mythic categories' rolls); (h) status 'degraded' plus generated_at 26 hours old - what the data strip says and whether the tabs still quote numbers; (i) schema_version 5 with 'selected' renamed to 'chosen' - silent failure?; (j) selected.median null but count > 0; (k) median_time_to_sell_seconds missing; (l) exact_roll missing on some rolls; (m) index.json scraps best_bid 0.30 while commodities.json best_bid stays 0.225 (the Price tab's dismantle floor reads index.json via loadScrapPrice, the Sort/Craft/Cases read commodities.json via craftBook: two sources for one number - show the two floors disagreeing on screen); (n) tax input set to 0, blank, -5, 100; (o) the Price tab's hard-coded 0.218 scrap fallback (paintScrap 4155) when index.json fails - what floor does it print and is it labelled; (p) commodities.json present but order_book missing on scraps (only price present).
Also read paintDataStamp/scheduleAutoRefresh/refreshCollector (5481-5567) and collectorFile caching for a stale-data path that keeps quoting old numbers; and note that the page never checks schema_version. Write one node script per case under your directory. Rank the cases by silent-wrong-number first.` },

  { key: 'collector-correctness', prompt: PRE + `Dimension: collector-correctness. Read /home/user/-warera-case1-collector/collector.py end to end adversarially, run its tests, and write targeted extra tests in your own directory (import collector via sys.path; never edit the repo). Check at least:
(a) collect_market stop logic (315-404): the stream is newest-first; reached_known flips true on the first known id; the incremental stop needs oldest < checkpoint - 0.5h. Construct a scenario where sales are missed (delayed ingestion older than the overlap; a run that failed mid-way; min(checkpoints) with a mix; a category whose last_success_at is None; the backstop at 3h with a collector that was down 5h). Also max_pages=1000 versus ~62 pages/hour: can a fresh cache ever reach history_complete on the retention boundary, and what does history_complete mean in the committed snapshot (check stop_reason/pages_fetched/full_scan in the JSON and in git history: git -C /home/user/-warera-case1-collector log -p is available; use git show <sha>:data/warera_case1_market.json | python3 - to read old snapshots without checking out).
(b) summarize (407): weighted median picks the first price whose cumulative weight >= half - is that the lower or upper median for ties/even weights; recency_weighted_price; median_time_to_sell_seconds is computed after stale_listing filtering, so it is censored at 48h - quantify the censoring by tier from raw rows (share dropped and the median with/without). Also the primary/fallback windows use sold_at >= now-24h inclusive boundaries; fine or not.
(c) The stale filter direction (README: it lowers medians slightly; 1,218 of 1,284 excluded sales were at/above the median). Confirm independently and reason about the failure mode it was built for (a bracket move) versus steady state; propose what to measure.
(d) validate (769): the tamper check recomputes aggregate() with 1e-12 tolerance; migrate; the archive merge in publish (record != existing rewrites a day file when anything differs - can a day file be rewritten after being 'write-once'? sales arriving late for a completed day; ids unique across days?), atomic_write, collect_commodities retention, normalize_book quantity filter, Client throttle/retry/redirect, NoRedirect.
(e) The workflow (.github/workflows/collect.yml): --max-seconds 600 inside a 14-minute job; continue-on-error then commit of a valid partial; the push to main racing a human push; the hourly cron fallback; the 15-min claim vs the page's COLLECTOR_CADENCE_MS and the README's '10 minutes'. Also the probe workflow.
(f) shard_rows/epoch uses int(timestamp) (floor) while the page keys live rows with Math.round(ms/1000) (saleKey 5670): confirm from code, and estimate from the ms distribution of sold_at in the snapshot how often a live row would fail to dedupe against its shard copy.
(g) Anything else you find. Report each as a finding with a reproduction (your test file and the command).` },

  { key: 'price-tab-model', prompt: PRE + `Dimension: price-tab-model. The Price tab is the thing done every time, and its Trends engine (singleModel 5889, weaponModel 5947, recencyWeight 5750, robustFilter 5771, weightedQuantileBy 5779, nearestWorse/nearbyBetter 5804-5812, weaponScore 5825 with WEAPON_CRIT_WEIGHT=4.15 and weaponCritAdjustment, velocity 5843-5856, downwardRepriceGate 5868, renderModel 6221, opportunityDepthBands 6064, getMarketTransactions 6009) is a separate pricing model from the Sort tab's median. Questions:
(a) What number does a user act on? Trace renderModel: directPrice (floor - 0.001) versus histTarget (weighted quantile at 0.55 quick / 0.70 patient) and the 'higher' branch. Use the harness to run one full analysis (type a price in #price, pin a rarity via #rarityBtns, pick a slot and roll, click #analyseBtn, read #resultText/#miniTarget/#trendMiniPrice/#confidence/#debug) for three cases: a Common knife 40/5 with a floor below the median, an Epic boots 25 with a floor above the median, a Legendary tank roll. Confirm each printed figure against your own computation from the shard rows.
(b) Is the 55th/70th percentile consistent with the brief's claim that the median is the right ask? Quantify weightedQuantile(exact, 0.55) versus the plain median across rolls with enough sales (relative difference distribution), and what recencyWeight's step table does versus the collector's 12h half-life.
(c) robustFilter: log-MAD 3.5 with a 0.12 floor - how many sales does it drop per roll, and does it ever drop the true clearing price (e.g. a bracket move)?
(d) WEAPON_CRIT_WEIGHT=4.15 and weaponCritAdjustment: where would they come from? Fit sale price ~ a + b*attack + c*crit per weapon (pure-Python least squares on the shard rows) and report the implied crit weight per tier; say whether a single constant across tiers is defensible.
(e) velocity ('sales / hour' on screen): from the code it is a recency-weighted count divided by coverage hours; compute it for a typical roll and compare with the true sales/hour from the shard; is the label honest? Then opportunityDepthBands and the SAFE/LESS SAFE/RISKY bands.
(f) Live merge seam: saleKey uses Math.round(ms/1000); shard rows are floor seconds; live Gateway rows carry ms - so a live row with ms >= 500 fails to dedupe against its shard copy. Confirm from code and estimate the rate from sold_at ms in the snapshot. Also liveRow, mergeSales ordering, the 'gap between sources' logic, and analyticsRead/Write localStorage cache.
(g) Tier inference from price: rarityRanges/tiersForPrice (3945-3997) use fallback_48h min/max across every roll of a tier; compute from summary.json the six ranges, their overlaps, and which typed prices are ambiguous; e.g. a knife 40/5 at 4.329 - what rarity does the page infer, and is 'higher tier wins' right given volumes. Check the RARITY_BANDS fallback against the observed ranges.
Report findings with what a user would be told wrongly and by how much.` },

  { key: 'js-numerics-sims', prompt: PRE + `Dimension: js-numerics-sims. Numerical and simulator soundness of test60.html.
(a) Simulators versus the card. simDraw (4789) draws a slot by CRAFT_SLOT_WEIGHT then a roll uniformly among priced rolls; a slot with no table returns net 0 and 'unpriced'. craftExpected renormalises over slots with data. Replicate simDraw in Python (Monte Carlo, 1e6 draws per tier) and compare its mean to the card's per-tier net from ev_ref; report any tier where the simulator's long-run answer is not the card's (Mythic coverage 180/880; Legendary tank 284/300). Also simRun's 'Expected' line uses caseEdge*n; check simPick's boundary (r<=0) and Math.random bias.
(b) paintCase variance (5057): between-tier only. Compute the full per-case sd including within-tier roll dispersion (from ev_ref slot rows) and the 'cases before profit reliably beats the swing' figure under both; check the formula (2*sd/edge)^2 and the wording (it is where the edge equals two standard errors).
(c) Order books: bookLevels (float keys via object), bookPanel 'taken' marking for the ask side only, craftWalk thin handling (remainder priced at the deepest of 100 visible orders - a floor, since deeper orders exist), craft cost for a batch walks the book but resale does not. Quantify the missing price impact with the snapshot: daily sale volume per item versus what 100 cases/day of opening would add, and the scraps a sorter dumps versus bid depth.
(d) The BigInt core: dec/decStr/toThousandths/taxFrac/undercutEntry/entryForDisplayed (3890-3934) and flipCheckCore (4116). Write a node brute-force check over displayed prices 0.001..50.000 step 0.001 and tax in {0, 0.5, 1, 2.5, 5, 12.5}: assert typed*(1+tax) rounded to 3 decimals is strictly below the displayed price (undercut) and that typed+0.001 would not also satisfy (minimality); same for the non-beat conversion (nearest typed that displays as the target), and for flipCheckCore's s3 (the smallest second offer worth flipping to). Report any failures with examples. Also extractNumber's locale handling (1.234,56 vs 1,234.56).
(e) sortHowOften/sortGold/'Per 1,000' (5176-5186, 4460-4483): each = tier odds x slot weight / space; keep/drop only count priced rolls, so keep+drop < slot share and the 'break the rest' row is built from drop only; check with the Uncommon figures on screen (Gun none, Helmet 30+ 2.8 per 1,000, Chest 10+ 8.4, break the rest 289) whether the column is per 1,000 cases and whether the unpriced rolls' share silently vanishes.
(f) Float accumulation: is anything here at risk (sums of ~1,800 terms of magnitude 1-400)? Say so briefly and move on unless you find a real one.
(g) Anything else numerically wrong on the page. Report each finding with an example input and the wrong output.` },
]

const refutePrompt = (d, f) => PRE + `You are an adversarial refuter. Another investigator (dimension: ${d.key}) reported this finding:\n\n${JSON.stringify(f, null, 1)}\n\n` +
  `Your job is to REFUTE it. Re-run its reproduction (the scripts are under ${AUDIT}/${d.key}/ or wherever the reproduction field says). Re-read the cited code lines in test60.html or collector.py yourself and check that the code does what the finding says. Check the arithmetic independently (write your own short script; do not trust theirs). Ask: is the number right, is the mechanism right, does it actually change what a user is told, is the severity right, is the proposed change sound. ` +
  `Default to refuted=true if you cannot reproduce it or the mechanism does not hold. If it stands, give your independently reproduced numbers in 'corrected'. If it stands but the numbers or severity are off, refuted=false with the corrected statement. Be specific and short.`

const results = await pipeline(
  DIMS,
  d => agent(d.prompt, { label: 'investigate:' + d.key, phase: 'Investigate', schema: FINDINGS, effort: 'high' }),
  async (res, d) => {
    if (!res) { log('investigator ' + d.key + ' returned nothing'); return null }
    const substantive = (res.findings || []).filter(f => f.severity !== 'nit')
    const nits = (res.findings || []).filter(f => f.severity === 'nit').map(f => ({ ...f, verdict: null }))
    log(d.key + ': ' + substantive.length + ' substantive findings to verify, ' + nits.length + ' nits')
    const verified = await parallel(substantive.map(f => () =>
      agent(refutePrompt(d, f), { label: 'refute:' + d.key + ':' + f.id, phase: 'Verify', schema: VERDICT, effort: f.severity === 'robustness' ? 'medium' : 'high' })
        .then(v => ({ ...f, verdict: v }))))
    return { dimension: d.key, claim_verdicts: res.claim_verdicts, notes: res.notes, scripts: res.scripts,
             findings: [...verified.filter(Boolean), ...nits] }
  })

const clean = results.filter(Boolean)
phase('Critic')
const digest = clean.map(r => ({ dimension: r.dimension, claim_verdicts: r.claim_verdicts,
  findings: r.findings.map(f => ({ id: f.id, title: f.title, severity: f.severity, summary: f.summary,
    refuted: f.verdict ? f.verdict.refuted : null, corrected: f.verdict ? f.verdict.corrected : null })) }))
const critic = await agent(PRE + `You are the completeness critic. Eight investigators audited the two repos; here is the digest of their findings and the refuters' verdicts:\n\n${JSON.stringify(digest, null, 1)}\n\n` +
  `Read the brief at /root/.claude/uploads/d4b26fab-cdf4-573a-8269-c661bf06e643/7d263eff-HANDOVER.md. Then answer: what did the sweep miss? Which of the six claims or the 'things I happen to know' got no real test? Which findings contradict each other? Is there a load-bearing assumption nobody attacked (e.g. that the game's tax is paid the way the page assumes, that scraps sell at the bid, that the case odds are right, that a piece sold at the median is a piece you could have sold at the median)? Which finding, if true, most changes what a user is told, and did it get a strong enough test? Look at the actual data and code where a quick check settles it. Return concrete angles with how to test each, not generalities.`,
  { label: 'critic', phase: 'Critic', schema: CRITIC, effort: 'high' })

return { results: clean, critic }