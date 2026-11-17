# Post-hoc diagnostic design

This diagnostic was specified after the fixed primary and ablation returns were observed. It is exploratory explanation, not a new preregistered main strategy, parameter search, or evidence of causal effects. No model API is called. Existing configuration, cached annotations, primary decisions, and historical results remain unchanged.

## Population and accounting

Use all 41 releases for input/abstention audits. Return comparisons use the same 37 public-price intervals (1–10,13–39), with missing nonflat endpoint returns left unresolved. Group daily and phase returns by the decision release date, not execution date. Compound within each group; group log-return contributions add to the common-set log return. Contributions do not reconstruct the continuous missing four intervals.

For each primary variant, report daily/phase metrics, each active common trade's return and exact terminal-CR delta if that trade were replaced with F, leave-one-active-trade-out CR range, largest gain/loss, and economic long/short pair and ticker concentration (HHI and top share). Leave-one-out fixes all other decisions and is a sensitivity calculation, not a feasible adaptive policy.

## Eligibility and abstention

Classify full F decisions in precedence order: API annotation failure, fewer than six eligible stocks, score gap below 0.35. Count each per-ticker failed criterion separately (overlapping counts) and additionally a disjoint exclusion waterfall: invalid current price, unrecognized coverage, absent summary, nonpositive retrieved-news count, capped confidence below 0.35. Do not interpret count zero as proof of no real-world news. Report the partial-coverage proportion over all 410 observations and missingness separately.

## Paired behavioral comparisons

For full vs each original ablation, distinguish action agreement including F; exact economic pair/direction agreement conditional on both active; full-active and full-F conditional returns for every variant on identical intervals. Report per-interval differences, not causal treatment effects. In particular no_news changes score scaling and eligibility, while no_risk changes eligibility and exposure.

## Time audit

For all price rows, check timestamp equals its release, bar_start is not later than the release, status/positive finite values agree, duplicates and universe coverage. For all news rows, check timestamp/window endpoints against the schedule. Report observed previous-release elapsed hours, overnight and weekend gaps, momentum saturation, and whether cached momentum equals the fixed formula. News sources lack individually verifiable article publication times; endpoint checks cannot certify article-level provenance.

## Two controlled, post-hoc diagnostics (one fixed run)

1. `news_score_zero`: use the exact full-policy eligible pool (all confidence/coverage/current-price rules retained); replace score by 0.3 times momentum; retain minimum-six and gap>=0.35 gates and deterministic universe tie order.
2. `risk_exposure_only`: retain the exact full-policy eligible pool, fused scores, and ranked extreme pair; remove only minimum-six and gap gates, requiring at least two eligible stocks. Full cached F outputs caused by insufficient breadth contain placeholder NVDA/GOOG rather than an economically selected pair. For those rounds only, reconstruct the full ranking's highest/lowest eligible stocks, avoiding trading the placeholders. Full active pairs never change. This tests gate-related exposure with the confidence filter held fixed, not the broader original no_risk definition.

Both diagnostics use only original cached contemporaneous features; original failed annotations force F. Report full set and matched active/flat subsets, with missing valuations unresolved. Do not select a replacement main strategy from these outcomes.
