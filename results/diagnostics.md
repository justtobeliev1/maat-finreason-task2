# Post-hoc diagnostic audit

Exploratory interpretation only. No API calls, parameter search, or changes to primary results.

All returns below use the common 37 observable intervals, unless stated otherwise.

## Primary sensitivity and concentration

| Method | CR % | MDD % | Active | Leave-one-active-out CR range % | Top pair share | Pair HHI |
|---|---:|---:|---:|---|---:|---:|
| full | 0.296809 | 1.981109 | 18 | -1.015538 to 1.385158 | 0.167 | 0.093 |

full: best round 5 (('WMT', 'AAPL')) +1.3258%; worst round 23 (('AMZN', 'AMD')) -1.0735%.

Daily metrics: `{"2026-10-14": {"rounds": [1, 2, 3, 4, 5, 6], "cr": 0.01325811364474827, "max_drawdown": 0.0, "win_rate_all_settled": 0.16666666666666666, "win_rate_active": 1.0, "settled_count": 6, "active_settled_count": 1, "unscorable_count": 0, "sharpe_unannualized_ddof1": 0.40824829046386296, "scope": "all_rounds", "log_return_contribution": 0.013170994039000598}, "2026-10-15": {"rounds": [7, 8, 9, 10], "cr": -0.008455251596366176, "max_drawdown": 0.00985901499691788, "win_rate_all_settled": 0.25, "win_rate_active": 0.3333333333333333, "settled_count": 4, "active_settled_count": 3, "unscorable_count": 0, "sharpe_unannualized_ddof1": -0.47620376060843156, "scope": "all_rounds", "log_return_contribution": -0.008491200014852124}, "2026-10-19": {"rounds": [13, 14, 15, 16, 17, 18], "cr": 8.480901729335244e-06, "max_drawdown": 0.00641994404457269, "win_rate_all_settled": 0.3333333333333333, "win_rate_active": 0.5, "settled_count": 6, "active_settled_count": 4, "unscorable_count": 0, "sharpe_unannualized_ddof1": 0.00237441432328735, "scope": "all_rounds", "log_return_contribution": 8.480865766620667e-06}, "2026-10-20": {"rounds": [19, 20, 21, 22, 23, 24], "cr": -0.0066476116479294856, "max_drawdown": 0.010734791869557503, "win_rate_all_settled": 0.3333333333333333, "win_rate_active": 0.6666666666666666, "settled_count": 6, "active_settled_count": 3, "unscorable_count": 0, "sharpe_unannualized_ddof1": -0.2269927911789446, "scope": "all_rounds", "log_return_contribution": -0.006669805430017034}, "2026-10-21": {"rounds": [25, 26, 27, 28, 29, 30], "cr": -0.004845657236785539, "max_drawdown": 0.004845657236785539, "win_rate_all_settled": 0.0, "win_rate_active": 0.0, "settled_count": 6, "active_settled_count": 2, "unscorable_count": 0, "sharpe_unannualized_ddof1": -0.620805908390419, "scope": "all_rounds", "log_return_contribution": -0.0048574354981628974}, "2026-10-22": {"rounds": [31, 32, 33, 34, 35, 36], "cr": 0.007856185408762872, "max_drawdown": 0.0, "win_rate_all_settled": 0.3333333333333333, "win_rate_active": 1.0, "settled_count": 6, "active_settled_count": 2, "unscorable_count": 0, "sharpe_unannualized_ddof1": 0.44861071924444457, "scope": "all_rounds", "log_return_contribution": 0.007825486264794656}, "2026-10-23": {"rounds": [37, 38, 39], "cr": 0.0019791301946963102, "max_drawdown": 0.007363956653701265, "win_rate_all_settled": 0.6666666666666666, "win_rate_active": 0.6666666666666666, "settled_count": 3, "active_settled_count": 3, "unscorable_count": 0, "sharpe_unannualized_ddof1": 0.08965174573692566, "scope": "all_rounds", "log_return_contribution": 0.0019771742967583084}}`

Phase metrics: `{"I": {"rounds": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], "cr": 0.00469076136182256, "max_drawdown": 0.00985901499691788, "win_rate_all_settled": 0.2, "win_rate_active": 0.5, "settled_count": 10, "active_settled_count": 4, "unscorable_count": 0, "sharpe_unannualized_ddof1": 0.09110637792395752, "scope": "all_rounds", "log_return_contribution": 0.004679794024148475}, "II": {"rounds": [13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39], "cr": -0.001714627844068728, "max_drawdown": 0.015528431984434876, "win_rate_all_settled": 0.2962962962962963, "win_rate_active": 0.5714285714285714, "settled_count": 27, "active_settled_count": 14, "unscorable_count": 0, "sharpe_unannualized_ddof1": -0.013625006347770214, "scope": "all_rounds", "log_return_contribution": -0.0017160995008603445}}`

| no_news | 4.964479 | 3.605746 | 36 | 1.415830 to 7.391371 | 0.111 | 0.056 |

no_news: best round 30 (('TSLA', 'META')) +3.4991%; worst round 5 (('AMD', 'GOOG')) -2.2599%.

Daily metrics: `{"2026-10-14": {"rounds": [1, 2, 3, 4, 5, 6], "cr": -0.007566394571820845, "max_drawdown": 0.02653383136726517, "win_rate_all_settled": 0.5, "win_rate_active": 0.6, "settled_count": 6, "active_settled_count": 5, "unscorable_count": 0, "sharpe_unannualized_ddof1": -0.10252348736856957, "scope": "all_rounds", "log_return_contribution": -0.007595164952474431}, "2026-10-15": {"rounds": [7, 8, 9, 10], "cr": -0.0034301366891773544, "max_drawdown": 0.009783217209536788, "win_rate_all_settled": 0.5, "win_rate_active": 0.5, "settled_count": 4, "active_settled_count": 4, "unscorable_count": 0, "sharpe_unannualized_ddof1": -0.11817326727602752, "scope": "all_rounds", "log_return_contribution": -0.003436033095545163}, "2026-10-19": {"rounds": [13, 14, 15, 16, 17, 18], "cr": 0.019619138265593028, "max_drawdown": 0.004800969222694906, "win_rate_all_settled": 0.5, "win_rate_active": 0.5, "settled_count": 6, "active_settled_count": 6, "unscorable_count": 0, "sharpe_unannualized_ddof1": 0.416911599568404, "scope": "all_rounds", "log_return_contribution": 0.019429163710073773}, "2026-10-20": {"rounds": [19, 20, 21, 22, 23, 24], "cr": 0.012798936451551501, "max_drawdown": 0.0007110226280355736, "win_rate_all_settled": 0.8333333333333334, "win_rate_active": 0.8333333333333334, "settled_count": 6, "active_settled_count": 6, "unscorable_count": 0, "sharpe_unannualized_ddof1": 1.2384369745868582, "scope": "all_rounds", "log_return_contribution": 0.01271772230014574}, "2026-10-21": {"rounds": [25, 26, 27, 28, 29, 30], "cr": 0.029563875382645488, "max_drawdown": 0.008426697737762279, "win_rate_all_settled": 0.6666666666666666, "win_rate_active": 0.6666666666666666, "settled_count": 6, "active_settled_count": 6, "unscorable_count": 0, "sharpe_unannualized_ddof1": 0.3269863480893207, "scope": "all_rounds", "log_return_contribution": 0.029135290614557684}, "2026-10-22": {"rounds": [31, 32, 33, 34, 35, 36], "cr": 0.0024455313632312237, "max_drawdown": 0.007930819458282667, "win_rate_all_settled": 0.5, "win_rate_active": 0.5, "settled_count": 6, "active_settled_count": 6, "unscorable_count": 0, "sharpe_unannualized_ddof1": 0.06210258969041519, "scope": "all_rounds", "log_return_contribution": 0.0024425459177501423}, "2026-10-23": {"rounds": [37, 38, 39], "cr": -0.004232724880796179, "max_drawdown": 0.007363956653701265, "win_rate_all_settled": 0.6666666666666666, "win_rate_active": 0.6666666666666666, "settled_count": 3, "active_settled_count": 3, "unscorable_count": 0, "sharpe_unannualized_ddof1": -0.27187053434632485, "scope": "all_rounds", "log_return_contribution": -0.004241708219049029}}`

Phase metrics: `{"I": {"rounds": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], "cr": -0.010970577493372713, "max_drawdown": 0.03605746234113483, "win_rate_all_settled": 0.5, "win_rate_active": 0.5555555555555556, "settled_count": 10, "active_settled_count": 9, "unscorable_count": 0, "sharpe_unannualized_ddof1": -0.10941786394413343, "scope": "all_rounds", "log_return_contribution": -0.011031198048019596}, "II": {"rounds": [13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39], "cr": 0.06128773413628963, "max_drawdown": 0.015236373901264644, "win_rate_all_settled": 0.6296296296296297, "win_rate_active": 0.6296296296296297, "settled_count": 27, "active_settled_count": 27, "unscorable_count": 0, "sharpe_unannualized_ddof1": 0.2638529031033792, "scope": "all_rounds", "log_return_contribution": 0.05948301432347831}}`

| no_risk | 0.318522 | 4.170057 | 37 | -0.994110 to 1.407106 | 0.081 | 0.046 |

no_risk: best round 5 (('WMT', 'AAPL')) +1.3258%; worst round 23 (('AMZN', 'AMD')) -1.0735%.

Daily metrics: `{"2026-10-14": {"rounds": [1, 2, 3, 4, 5, 6], "cr": 0.010954361151845449, "max_drawdown": 0.006363292247285157, "win_rate_all_settled": 0.6666666666666666, "win_rate_active": 0.6666666666666666, "settled_count": 6, "active_settled_count": 6, "unscorable_count": 0, "sharpe_unannualized_ddof1": 0.2693567540036477, "scope": "all_rounds", "log_return_contribution": 0.010894796736349717}, "2026-10-15": {"rounds": [7, 8, 9, 10], "cr": -0.0067511531987192175, "max_drawdown": 0.00855543240418044, "win_rate_all_settled": 0.5, "win_rate_active": 0.5, "settled_count": 4, "active_settled_count": 4, "unscorable_count": 0, "sharpe_unannualized_ddof1": -0.32999044450688414, "scope": "all_rounds", "log_return_contribution": -0.006774045323812931}, "2026-10-19": {"rounds": [13, 14, 15, 16, 17, 18], "cr": -0.011870066212714692, "max_drawdown": 0.011870066212714692, "win_rate_all_settled": 0.3333333333333333, "win_rate_active": 0.3333333333333333, "settled_count": 6, "active_settled_count": 6, "unscorable_count": 0, "sharpe_unannualized_ddof1": -0.39072495138011326, "scope": "all_rounds", "log_return_contribution": -0.011941077950754525}, "2026-10-20": {"rounds": [19, 20, 21, 22, 23, 24], "cr": -0.008327094231303733, "max_drawdown": 0.012754717592301401, "win_rate_all_settled": 0.5, "win_rate_active": 0.5, "settled_count": 6, "active_settled_count": 6, "unscorable_count": 0, "sharpe_unannualized_ddof1": -0.28726093600528846, "scope": "all_rounds", "log_return_contribution": -0.008361958158849483}, "2026-10-21": {"rounds": [25, 26, 27, 28, 29, 30], "cr": 0.003457396073256458, "max_drawdown": 0.010272516730160053, "win_rate_all_settled": 0.5, "win_rate_active": 0.5, "settled_count": 6, "active_settled_count": 6, "unscorable_count": 0, "sharpe_unannualized_ddof1": 0.08404231359340131, "scope": "all_rounds", "log_return_contribution": 0.003451433019924878}, "2026-10-22": {"rounds": [31, 32, 33, 34, 35, 36], "cr": 0.013023646518624865, "max_drawdown": 0.008077557412101366, "win_rate_all_settled": 0.8333333333333334, "win_rate_active": 0.8333333333333334, "settled_count": 6, "active_settled_count": 6, "unscorable_count": 0, "sharpe_unannualized_ddof1": 0.36166747235183594, "scope": "all_rounds", "log_return_contribution": 0.012939568052961174}, "2026-10-23": {"rounds": [37, 38, 39], "cr": 0.0029758566829154454, "max_drawdown": 0.007363956653701265, "win_rate_all_settled": 0.6666666666666666, "win_rate_active": 0.6666666666666666, "settled_count": 3, "active_settled_count": 3, "unscorable_count": 0, "sharpe_unannualized_ddof1": 0.13478198176860254, "scope": "all_rounds", "log_return_contribution": 0.0029714375863114373}}`

Phase metrics: `{"I": {"rounds": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], "cr": 0.0041292533827961275, "max_drawdown": 0.014864283934775901, "win_rate_all_settled": 0.6, "win_rate_active": 0.6, "settled_count": 10, "active_settled_count": 10, "unscorable_count": 0, "sharpe_unannualized_ddof1": 0.06979933933761523, "scope": "all_rounds", "log_return_contribution": 0.004120751412536787}, "II": {"rounds": [13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39], "cr": -0.0009401552272867431, "max_drawdown": 0.029008266428846574, "win_rate_all_settled": 0.5555555555555556, "win_rate_active": 0.5555555555555556, "settled_count": 27, "active_settled_count": 27, "unscorable_count": 0, "sharpe_unannualized_ddof1": -0.003303286616457408, "scope": "all_rounds", "log_return_contribution": -0.0009405974504065199}}`

## Evidence and temporal audit

F reasons: `{"all_41": {"score_gap_below_0.35": 7, "fewer_than_six_eligible": 15, "api_failure": 0}, "common_37": {"score_gap_below_0.35": 6, "fewer_than_six_eligible": 13, "api_failure": 0}}`.

Overlapping failed per-stock criteria: `{"invalid_current_price": 0, "unrecognized_coverage": 0, "absent_summary": 0, "nonpositive_or_missing_news_count": 29, "capped_confidence_below_0.35": 157}`.

Disjoint waterfall: `{"eligible": 253, "capped_confidence_below_0.35": 128, "nonpositive_or_missing_news_count": 29}`.

Partial coverage: 410/410 = 100.00%.

All 410 price and 410 news rows checked. Temporal/status flags: 0. Momentum mismatches: 0/410. Saturated momentum observations: 74.

Bar-start minus release seconds: `{"0.0": 70, "-60.0": 340}`.

Cross-date momentum references: 6; weekend/long calendar gaps: 1. Details retained in JSON.

## Pair and exposure diagnostics

no_news: economic pair/direction equal 2/18 when both active; same economic position including joint F 3/37.

- full_active (18 intervals): full conditional CR 0.296809%, no_news conditional CR 0.147216%.
- full_F (19 intervals): full conditional CR 0.000000%, no_news conditional CR 4.810182%.

no_risk: economic pair/direction equal 12/18 when both active; same economic position including joint F 12/37.

- full_active (18 intervals): full conditional CR 0.296809%, no_risk conditional CR 0.618274%.
- full_F (19 intervals): full conditional CR 0.000000%, no_risk conditional CR -0.297910%.

news_score_zero: economic pair/direction equal 6/16 when both active; same economic position including joint F 25/37.

- full_active (18 intervals): full conditional CR 0.296809%, news_score_zero conditional CR -1.857588%.
- full_F (19 intervals): full conditional CR 0.000000%, news_score_zero conditional CR 0.000000%.

risk_exposure_only: economic pair/direction equal 18/18 when both active; same economic position including joint F 19/37.

- full_active (18 intervals): full conditional CR 0.296809%, risk_exposure_only conditional CR 0.296809%.
- full_F (19 intervals): full conditional CR 0.000000%, risk_exposure_only conditional CR 0.301215%.

## Controlled post-hoc calculations

Definitions were written in diagnostics_design.md before this one diagnostic run. They are not replacement main policies.

- news_score_zero: common CR -1.857588%, MDD 3.747012%, active 16/37; unresolved rounds [11].
- risk_exposure_only: common CR 0.598918%, MDD 3.105830%, active 36/37; unresolved rounds [11, 12, 40, 41].

## Evidence-backed findings

- The main common-set profit changes sign after removing its single largest gain (round 5); this is sensitivity evidence, not a significance test.
- All stock-release coverage fields are partial, so the sample cannot distinguish partial from complete coverage performance or validate the confidence cap.
- No current-price or summary absence occurs; 29 zero-news-count stock releases and 128 additional low-confidence observations account for exclusion. This evaluates an availability/confidence policy, not missing-price resilience in realized returns.
- The original no_news gain is mostly on intervals where full abstains, but it changes score scale, eligibility and selected pairs. Neither raw difference identifies a causal news effect.
- The controlled news-zero diagnostic also changes pair rankings and gap-induced exposure even with eligibility/scale retained; it is a descriptive component sensitivity only.
- The original no_risk and confidence-preserving risk_exposure_only diagnostics differ in extra-interval outcome, showing confidence-related pair changes matter and preventing attribution solely to abstention.
- Momentum compares 1h,2h,18h and90h observations with one scale. Correct implementation does not make these heterogeneous horizons economically comparable.
- The 340 one-minute-earlier bar_start values are consistent with completed-minute bars, not future observations; price_basis counts are retained.

## Interpretation boundaries

- Retrospective, post-hoc descriptive analysis; no causal identification, parameter selection, or held-out performance claim.
- Same 37 observed intervals omit four terminal intervals; no continuous 41-round account reconstruction.
- No_news renormalizes momentum from 0.3 to 1 and changes eligibility; no_risk removes confidence eligibility in addition to exposure gates.
- Leave-one-out changes only one realized return to F, holding all other actions fixed; not a deployable adaptive rule.
- Risk_exposure_only reconstructs ranked pair when cached full F pair is a placeholder, retaining full confidence eligibility.

All 212 input/source files had identical hashes before and after the diagnostic run.
