"""One fixed post-hoc audit. No API, training, parameter search, or primary-result edits."""

from __future__ import annotations
import collections
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from agent import TICKERS, coverage_cap, finite
from scoring import metrics, endpoint_times
from replay_baselines import load_price_snapshots, round_return

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = ("full", "no_news", "no_risk")
EXPLORATORY = ("news_score_zero", "risk_exposure_only")


def economic_pair(action):
    if action["action"] == "F":
        return None
    return (
        (action["stock1"], action["stock2"])
        if action["action"] == "LS"
        else (action["stock2"], action["stock1"])
    )


def return_metrics(rows):
    return metrics([r["return"] for r in rows], [r["action"] for r in rows])


def frequency(counter):
    total = sum(counter.values())
    return {
        "count": total,
        "unique": len(counter),
        "counts": dict(counter.most_common()),
        "top_share": max(counter.values()) / total if total else None,
        "hhi": sum((v / total) ** 2 for v in counter.values()) if total else None,
    }


def summary(rows):
    m = return_metrics(rows)
    group = {}
    for key, pred in (
        ("daily", lambda r: r["round_id"][:10]),
        ("phase", lambda r: "I" if r["round"] <= 12 else "II"),
    ):
        groups = collections.defaultdict(list)
        for r in rows:
            groups[pred(r)].append(r)
        group[key] = {
            k: {
                "rounds": [r["round"] for r in rs],
                **return_metrics(rs),
                "log_return_contribution": sum(math.log1p(r["return"]) for r in rs),
            }
            for k, rs in groups.items()
        }
    active = [r for r in rows if r["action"] != "F"]
    wealth = 1 + m["cr"]
    influences = []
    for r in active:
        without = wealth / (1 + r["return"]) - 1
        influences.append(
            {
                "round": r["round"],
                "round_id": r["round_id"],
                "pair": economic_pair(r),
                "return": r["return"],
                "cr_if_replaced_by_F": without,
                "terminal_cr_delta_vs_without": m["cr"] - without,
            }
        )
    pairs = collections.Counter("/".join(economic_pair(r)) for r in active)
    long = collections.Counter(economic_pair(r)[0] for r in active)
    short = collections.Counter(economic_pair(r)[1] for r in active)
    ordered = sorted(influences, key=lambda r: r["return"])
    group.update(
        metrics=m,
        active_trade_sensitivity=influences,
        leave_one_active_trade_out_cr_range=[
            min(x["cr_if_replaced_by_F"] for x in influences),
            max(x["cr_if_replaced_by_F"] for x in influences),
        ]
        if influences
        else None,
        worst_trade=ordered[0] if ordered else None,
        best_trade=ordered[-1] if ordered else None,
        concentration={
            "economic_pairs": frequency(pairs),
            "long_tickers": frequency(long),
            "short_tickers": frequency(short),
        },
        winning_count=sum(r["return"] > 0 for r in rows),
        losing_count=sum(r["return"] < 0 for r in rows),
        flat_count=sum(r["action"] == "F" for r in rows),
    )
    assert (
        abs(
            sum(v["log_return_contribution"] for v in group["daily"].values())
            - math.log1p(m["cr"])
        )
        < 1e-12
    )
    return group


def posthoc_action(full, kind, cfg):
    action = {"stock1": "NVDA", "stock2": "GOOG", "action": "F"}
    if full.get("annotation_error"):
        return action
    eligible = [t for t in TICKERS if full["details"][t]["eligible"]]
    scores = {
        t: (
            cfg["momentum_weight"] * full["details"][t]["momentum"]
            if kind == "news_score_zero"
            else full["details"][t]["score"]
        )
        for t in eligible
    }
    order = sorted(eligible, key=lambda t: (-scores[t], TICKERS.index(t)))
    minimum = cfg["minimum_eligible"] if kind == "news_score_zero" else 2
    if len(order) < minimum:
        return action
    i, j = order[0], order[-1]
    action.update(stock1=i, stock2=j)
    if kind == "news_score_zero" and scores[i] - scores[j] < cfg["minimum_score_gap"]:
        return action
    action["action"] = "LS"
    return action


def main():
    cfg = json.loads((ROOT / "preregistration.json").read_text())
    state = json.loads((ROOT / "sources/live-state.json").read_text())
    schedule = state["release_schedule"]
    snapshots = load_price_snapshots(ROOT)
    common = [
        r["round"] for r in schedule if all(t in snapshots for t in endpoint_times(r))
    ]
    assert len(common) == 37
    source_paths = [
        ROOT / "preregistration.json",
        ROOT / "preregistration.sha256",
        ROOT / "sources/live-state.json",
        ROOT / "results/agent_results.json",
        ROOT / "results/agent_rounds.csv",
        ROOT / "results/baseline_replay.json",
        ROOT / "results/baseline_replay_rounds.csv",
    ]
    source_paths += sorted((ROOT / "logs/decisions").glob("*/*.json")) + sorted(
        (ROOT / "data/raw").glob("*/*.parquet")
    )
    before = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in source_paths
    }
    original_csv = {
        (r["method"], int(r["round"])): r
        for r in csv.DictReader((ROOT / "results/agent_rounds.csv").open())
    }
    decisions = {v: {} for v in VARIANTS}
    rows = {v: [] for v in (*VARIANTS, *EXPLORATORY)}
    abstentions = collections.defaultdict(collections.Counter)
    overlap = collections.Counter()
    waterfall = collections.Counter()
    partial = collections.Counter()
    per_release = []
    time_flags = []
    gap_rows = []
    bar_offsets = collections.Counter()
    status_counts = collections.Counter()
    price_basis = collections.Counter()
    previous = None
    previous_prices = {}
    momentum_checked = 0
    momentum_mismatch = []
    clipped = []
    raw_inputs = {}
    for release in schedule:
        rid = release["round_id"]
        number = release["round"]
        now = datetime.fromisoformat(release["timestamp"])
        folder = ROOT / "data/raw" / rid.replace(":", "-")
        price = pd.read_parquet(folder / "price.parquet")
        news = pd.read_parquet(folder / "news.parquet")
        if (
            len(price) != 10
            or set(price["ticker"]) != set(TICKERS)
            or price["ticker"].duplicated().any()
        ):
            time_flags.append({"round": number, "flag": "price_universe_or_duplicate"})
        if (
            len(news) != 10
            or set(news["ticker"]) != set(TICKERS)
            or news["ticker"].duplicated().any()
        ):
            time_flags.append({"round": number, "flag": "news_universe_or_duplicate"})
        for p in price.to_dict("records"):
            stamp = datetime.fromisoformat(str(p["timestamp"]))
            bar = datetime.fromisoformat(str(p["bar_start"]))
            status_counts[str(p["status"])] += 1
            price_basis[str(p["price_basis"])] += 1
            bar_offsets[str((bar - now).total_seconds())] += 1
            if stamp != now:
                time_flags.append(
                    {
                        "round": number,
                        "ticker": p["ticker"],
                        "flag": "price_timestamp_differs_from_release",
                    }
                )
            if bar > now:
                time_flags.append(
                    {
                        "round": number,
                        "ticker": p["ticker"],
                        "flag": "bar_start_after_release",
                    }
                )
            val = p["price"]
            valid = finite(val) and val > 0
            if (p["status"] == "available") != valid:
                time_flags.append(
                    {
                        "round": number,
                        "ticker": p["ticker"],
                        "flag": "status_price_validity_disagrees",
                    }
                )
        news_by = {r["ticker"]: r for r in news.to_dict("records")}
        for n in news_by.values():
            if datetime.fromisoformat(str(n["timestamp"])) != now:
                time_flags.append(
                    {
                        "round": number,
                        "ticker": n["ticker"],
                        "flag": "news_timestamp_differs_from_release",
                    }
                )
            if datetime.fromisoformat(str(n["window_end"])) != datetime.fromisoformat(
                release["window_end"]
            ):
                time_flags.append(
                    {
                        "round": number,
                        "ticker": n["ticker"],
                        "flag": "news_window_end_differs_from_schedule",
                    }
                )
            if datetime.fromisoformat(str(n["window_start"])) != datetime.fromisoformat(
                release["window_start"]
            ):
                time_flags.append(
                    {
                        "round": number,
                        "ticker": n["ticker"],
                        "flag": "news_window_start_differs_from_schedule",
                    }
                )
        for v in VARIANTS:
            action = json.loads(
                (
                    ROOT / "logs/decisions" / v / (rid.replace(":", "-") + ".json")
                ).read_text()
            )
            decisions[v][number] = action
            rr = round_return(release, action, snapshots)
            c = original_csv[v, number]
            recorded = None if not c["return"] else float(c["return"])
            assert (recorded is None) == (rr is None)
            assert rr is None or abs(rr - recorded) < 1e-12
            rows[v].append(
                {
                    "method": v,
                    "round": number,
                    "round_id": rid,
                    "stock1": action["stock1"],
                    "stock2": action["stock2"],
                    "action": action["action"],
                    "return": rr,
                    "common": number in common,
                }
            )
        full = decisions["full"][number]
        eligible = sum(d["eligible"] for d in full["details"].values())
        if full["action"] == "F":
            if full.get("annotation_error"):
                reason = "api_failure"
            elif eligible < cfg["minimum_eligible"]:
                reason = "fewer_than_six_eligible"
            elif full.get("score_gap", -1) < cfg["minimum_score_gap"]:
                reason = "score_gap_below_0.35"
            else:
                raise AssertionError("Unexplained F")
            abstentions["all_41"][reason] += 1
            if number in common:
                abstentions["common_37"][reason] += 1
        else:
            reason = "active"
        raw_inputs[number] = {}
        for t in TICKERS:
            n = news_by[t]
            d = full["details"][t]
            cap = coverage_cap(n["coverage_status"])
            p = snapshots[now].get(t)
            summary_present = pd.notna(n["summary"]) and bool(str(n["summary"]).strip())
            count_positive = pd.notna(n["news_count"]) and n["news_count"] > 0
            price_ok = finite(p) and p > 0
            failed = {
                "invalid_current_price": not price_ok,
                "unrecognized_coverage": cap <= 0,
                "absent_summary": not summary_present,
                "nonpositive_or_missing_news_count": not count_positive,
                "capped_confidence_below_0.35": d["confidence"]
                < cfg["minimum_confidence"],
            }
            for key, bad in failed.items():
                overlap[key] += int(bad)
            first = next((key for key, bad in failed.items() if bad), "eligible")
            waterfall[first] += 1
            assert (first == "eligible") == d["eligible"]
            partial["observations"] += 1
            partial["partial"] += int(
                str(n["coverage_status"]).lower().startswith("partial")
            )
            partial[str(n["coverage_status"])] += 1
            old = previous_prices.get(t)
            raw = (
                (p / old - 1) / cfg["momentum_scale"]
                if price_ok and finite(old) and old > 0
                else 0.0
            )
            expected = max(-1.0, min(1.0, raw))
            momentum_checked += 1
            if abs(expected - d["momentum"]) > 1e-12:
                momentum_mismatch.append(
                    {
                        "round": number,
                        "ticker": t,
                        "expected": expected,
                        "actual": d["momentum"],
                    }
                )
            if abs(raw) >= 1:
                clipped.append(
                    {
                        "round": number,
                        "ticker": t,
                        "raw_scaled_move": raw,
                        "elapsed_hours": (now - previous).total_seconds() / 3600
                        if previous
                        else None,
                    }
                )
            raw_inputs[number][t] = {
                "failed": failed,
                "news_count": int(n["news_count"])
                if pd.notna(n["news_count"])
                else None,
                "confidence": d["confidence"],
                "score": d["score"],
                "momentum": d["momentum"],
            }
        gap = None if previous is None else (now - previous).total_seconds() / 3600
        overnight = previous is not None and now.date() != previous.date()
        weekend = previous is not None and (now.date() - previous.date()).days >= 3
        gap_rows.append(
            {
                "round": number,
                "round_id": rid,
                "release_to_entry_hours": (
                    datetime.fromisoformat(release["entry_at"]) - now
                ).total_seconds()
                / 3600,
                "holding_hours": (
                    datetime.fromisoformat(release["exit_at"])
                    - datetime.fromisoformat(release["entry_at"])
                ).total_seconds()
                / 3600,
                "previous_release": previous.isoformat() if previous else None,
                "hours": gap,
                "overnight": overnight,
                "weekend_or_long_calendar_gap": weekend,
                "note": "First release uses zero momentum"
                if previous is None
                else None,
            }
        )
        per_release.append(
            {
                "round": number,
                "round_id": rid,
                "eligible_count": eligible,
                "action": full["action"],
                "F_reason": reason,
                "entry_at": release["entry_at"],
                "exit_at": release["exit_at"],
                "score_gap": full.get("score_gap"),
                "full_pair": economic_pair(full),
                "full_return": rows["full"][-1]["return"],
                "common": number in common,
                "ticker_exclusion_counts": dict(
                    collections.Counter(
                        key
                        for t in TICKERS
                        for key, bad in raw_inputs[number][t]["failed"].items()
                        if bad
                    )
                ),
            }
        )
        for kind in EXPLORATORY:
            action = posthoc_action(full, kind, cfg)
            if kind == "risk_exposure_only" and full["action"] != "F":
                assert economic_pair(action) == economic_pair(full)
            rr = round_return(release, action, snapshots)
            rows[kind].append(
                {
                    "method": kind,
                    "round": number,
                    "round_id": rid,
                    "stock1": action["stock1"],
                    "stock2": action["stock2"],
                    "action": action["action"],
                    "return": rr,
                    "common": number in common,
                }
            )
        previous = now
        previous_prices = snapshots[now]
    common_rows = {v: [r for r in rs if r["common"]] for v, rs in rows.items()}
    result = {
        "status": "post_hoc_exploratory_no_api_no_parameter_search",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "host": __import__("socket").gethostname(),
        "design_sha256": hashlib.sha256(
            (ROOT / "results/diagnostics_design.md").read_bytes()
        ).hexdigest(),
        "common_rounds": common,
        "original_method_results": {v: summary(common_rows[v]) for v in VARIANTS},
        "eligibility_audit": {
            "full_F_reason_counts": {k: dict(v) for k, v in abstentions.items()},
            "overlapping_failed_criteria_410_stock_releases": dict(overlap),
            "disjoint_exclusion_waterfall_410_stock_releases": dict(waterfall),
            "coverage": {
                "partial_count": partial["partial"],
                "total_count": partial["observations"],
                "partial_proportion": partial["partial"] / partial["observations"],
                "labels": {
                    k: v
                    for k, v in partial.items()
                    if k not in ("partial", "observations")
                },
            },
            "per_release": per_release,
        },
        "temporal_audit": {
            "price_rows_checked": 410,
            "news_rows_checked": 410,
            "price_status_counts": dict(status_counts),
            "price_basis_counts": dict(price_basis),
            "bar_start_minus_release_seconds_counts": dict(bar_offsets),
            "flags": time_flags,
            "momentum_feature_count_checked": momentum_checked,
            "momentum_mismatches": momentum_mismatch,
            "momentum_saturated_stock_releases": clipped,
            "elapsed_previous_release": gap_rows,
            "limitation": "News metadata validate window boundaries only; article publication provenance not independently verified. Hosted model historical knowledge is uncontrolled.",
        },
        "paired_behavior": {},
        "exploratory_controlled_diagnostics": {
            v: {
                **summary(common_rows[v]),
                "unscorable_rounds": [
                    r["round"] for r in rows[v] if r["return"] is None
                ],
            }
            for v in EXPLORATORY
        },
        "interpretation_limits": [
            "Retrospective, post-hoc descriptive analysis; no causal identification, parameter selection, or held-out performance claim.",
            "Same 37 observed intervals omit four terminal intervals; no continuous 41-round account reconstruction.",
            "No_news renormalizes momentum from 0.3 to 1 and changes eligibility; no_risk removes confidence eligibility in addition to exposure gates.",
            "Leave-one-out changes only one realized return to F, holding all other actions fixed; not a deployable adaptive rule.",
            "Risk_exposure_only reconstructs ranked pair when cached full F pair is a placeholder, retaining full confidence eligibility.",
        ],
    }
    for variant in (*VARIANTS[1:], *EXPLORATORY):
        pairs = list(zip(common_rows["full"], common_rows[variant]))
        both = [(a, b) for a, b in pairs if a["action"] != "F" and b["action"] != "F"]
        conditional = {}
        for label, active in (("full_active", True), ("full_F", False)):
            chosen = [(a, b) for a, b in pairs if (a["action"] != "F") == active]
            conditional[label] = {
                "rounds": [a["round"] for a, b in chosen],
                "count": len(chosen),
                "full": return_metrics([a for a, b in chosen]),
                "other": return_metrics([b for a, b in chosen]),
                "sum_per_interval_return_difference_other_minus_full": sum(
                    b["return"] - a["return"] for a, b in chosen
                ),
            }
        result["paired_behavior"][variant] = {
            "both_active_count": len(both),
            "economic_pair_direction_equal_both_active_count": sum(
                economic_pair(a) == economic_pair(b) for a, b in both
            ),
            "economic_pair_direction_equal_both_active_rate": sum(
                economic_pair(a) == economic_pair(b) for a, b in both
            )
            / len(both)
            if both
            else None,
            "same_active_or_F_state_count": sum(
                (a["action"] != "F") == (b["action"] != "F") for a, b in pairs
            ),
            "same_economic_position_including_joint_F_count": sum(
                economic_pair(a) == economic_pair(b) for a, b in pairs
            ),
            "denominator_common_intervals": 37,
            "conditional": conditional,
        }
    for scope in ("all_41", "common_37"):
        for label in ("api_failure", "fewer_than_six_eligible", "score_gap_below_0.35"):
            result["eligibility_audit"]["full_F_reason_counts"][scope].setdefault(
                label, 0
            )
    result["interpretation_findings"] = [
        "The main common-set profit changes sign after removing its single largest gain (round 5); this is sensitivity evidence, not a significance test.",
        "All stock-release coverage fields are partial, so the sample cannot distinguish partial from complete coverage performance or validate the confidence cap.",
        "No current-price or summary absence occurs; 29 zero-news-count stock releases and 128 additional low-confidence observations account for exclusion. This evaluates an availability/confidence policy, not missing-price resilience in realized returns.",
        "The original no_news gain is mostly on intervals where full abstains, but it changes score scale, eligibility and selected pairs. Neither raw difference identifies a causal news effect.",
        "The controlled news-zero diagnostic also changes pair rankings and gap-induced exposure even with eligibility/scale retained; it is a descriptive component sensitivity only.",
        "The original no_risk and confidence-preserving risk_exposure_only diagnostics differ in extra-interval outcome, showing confidence-related pair changes matter and preventing attribution solely to abstention.",
        "Momentum compares 1h,2h,18h and90h observations with one scale. Correct implementation does not make these heterogeneous horizons economically comparable.",
        "The 340 one-minute-earlier bar_start values are consistent with completed-minute bars, not future observations; price_basis counts are retained.",
    ]
    result["notable_round_cases"] = [
        {**p, "ticker_details": raw_inputs[p["round"]]}
        for p in per_release
        if p["round"]
        in sorted(
            set(
                [
                    r["round"]
                    for v in VARIANTS
                    for r in (
                        result["original_method_results"][v]["best_trade"],
                        result["original_method_results"][v]["worst_trade"],
                    )
                ]
                + [1, 2, 11, 13]
            )
        )
    ]
    after = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in source_paths
    }
    assert before == after, "Primary source changed while diagnostics ran"
    result["source_files_unchanged_count"] = len(before)
    result["source_sha256"] = before
    (ROOT / "results/diagnostics.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    with (ROOT / "results/diagnostics_rounds.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows["full"][0]))
        writer.writeheader()
        writer.writerows(r for rs in rows.values() for r in rs)
    lines = [
        "# Post-hoc diagnostic audit",
        "",
        "Exploratory interpretation only. No API calls, parameter search, or changes to primary results.",
        "",
        "All returns below use the common 37 observable intervals, unless stated otherwise.",
        "",
        "## Primary sensitivity and concentration",
        "",
        "| Method | CR % | MDD % | Active | Leave-one-active-out CR range % | Top pair share | Pair HHI |",
        "|---|---:|---:|---:|---|---:|---:|",
    ]
    for v, s in result["original_method_results"].items():
        m = s["metrics"]
        low, high = s["leave_one_active_trade_out_cr_range"]
        conc = s["concentration"]["economic_pairs"]
        lines.append(
            f"| {v} | {100 * m['cr']:.6f} | {100 * m['max_drawdown']:.6f} | {m['active_settled_count']} | {100 * low:.6f} to {100 * high:.6f} | {conc['top_share']:.3f} | {conc['hhi']:.3f} |"
        )
        lines.extend(
            [
                "",
                f"{v}: best round {s['best_trade']['round']} ({s['best_trade']['pair']}) {100 * s['best_trade']['return']:+.4f}%; worst round {s['worst_trade']['round']} ({s['worst_trade']['pair']}) {100 * s['worst_trade']['return']:+.4f}%.",
                "",
                f"Daily metrics: `{json.dumps(s['daily'])}`",
                "",
                f"Phase metrics: `{json.dumps(s['phase'])}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Evidence and temporal audit",
            "",
            f"F reasons: `{json.dumps(result['eligibility_audit']['full_F_reason_counts'])}`.",
            "",
            f"Overlapping failed per-stock criteria: `{json.dumps(dict(overlap))}`.",
            "",
            f"Disjoint waterfall: `{json.dumps(dict(waterfall))}`.",
            "",
            f"Partial coverage: {partial['partial']}/{partial['observations']} = {partial['partial'] / partial['observations']:.2%}.",
            "",
            f"All 410 price and 410 news rows checked. Temporal/status flags: {len(time_flags)}. Momentum mismatches: {len(momentum_mismatch)}/{momentum_checked}. Saturated momentum observations: {len(clipped)}.",
            "",
            f"Bar-start minus release seconds: `{json.dumps(dict(bar_offsets))}`.",
            "",
            f"Cross-date momentum references: {sum(r['overnight'] for r in gap_rows)}; weekend/long calendar gaps: {sum(r['weekend_or_long_calendar_gap'] for r in gap_rows)}. Details retained in JSON.",
            "",
            "## Pair and exposure diagnostics",
            "",
        ]
    )
    for v, b in result["paired_behavior"].items():
        lines.extend(
            [
                f"{v}: economic pair/direction equal {b['economic_pair_direction_equal_both_active_count']}/{b['both_active_count']} when both active; same economic position including joint F {b['same_economic_position_including_joint_F_count']}/37.",
                "",
            ]
        )
        for label, c in b["conditional"].items():
            lines.append(
                f"- {label} ({c['count']} intervals): full conditional CR {100 * c['full']['cr']:.6f}%, {v} conditional CR {100 * c['other']['cr']:.6f}%."
            )
        lines.append("")
    lines.extend(
        [
            "## Controlled post-hoc calculations",
            "",
            "Definitions were written in diagnostics_design.md before this one diagnostic run. They are not replacement main policies.",
            "",
        ]
    )
    for v, s in result["exploratory_controlled_diagnostics"].items():
        m = s["metrics"]
        lines.append(
            f"- {v}: common CR {100 * m['cr']:.6f}%, MDD {100 * m['max_drawdown']:.6f}%, active {m['active_settled_count']}/37; unresolved rounds {s['unscorable_rounds']}."
        )
    lines.extend(
        ["", "## Evidence-backed findings", ""]
        + ["- " + t for t in result["interpretation_findings"]]
        + ["", "## Interpretation boundaries", ""]
        + ["- " + t for t in result["interpretation_limits"]]
        + [
            "",
            f"All {len(before)} input/source files had identical hashes before and after the diagnostic run.",
        ]
    )
    (ROOT / "results/diagnostics.md").write_text("\n".join(lines) + "\n")
    print(
        json.dumps(
            {
                "original": {
                    k: {
                        "metrics": v["metrics"],
                        "loto_range": v["leave_one_active_trade_out_cr_range"],
                        "best": v["best_trade"],
                        "worst": v["worst_trade"],
                    }
                    for k, v in result["original_method_results"].items()
                },
                "F_reasons": result["eligibility_audit"]["full_F_reason_counts"],
                "coverage": result["eligibility_audit"]["coverage"],
                "exclusions": dict(overlap),
                "temporal_flags": time_flags,
                "momentum_mismatches": momentum_mismatch,
                "controls": {
                    k: v["metrics"]
                    for k, v in result["exploratory_controlled_diagnostics"].items()
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
