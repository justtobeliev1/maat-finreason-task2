"""Replay public actions at public execution snapshots, with explicit missing-data gaps."""

from __future__ import annotations
import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET
import pandas as pd
from scoring import pair_return, metrics, endpoint_times, valid_price


def load_price_snapshots(root: Path):
    snapshots = {}
    files = sorted((root / "data/raw").glob("*/price.parquet"))
    for path in files:
        frame = pd.read_parquet(path)
        required = {"ticker", "timestamp", "price", "status"}
        if not required <= set(frame.columns):
            raise ValueError(f"Unexpected price schema: {path}")
        for row in frame.to_dict("records"):
            timestamp = datetime.fromisoformat(str(row["timestamp"]))
            prices = snapshots.setdefault(timestamp, {})
            ticker = str(row["ticker"])
            if ticker in prices:
                raise ValueError(f"Duplicate ticker/timestamp: {ticker}/{timestamp}")
            prices[ticker] = (
                float(row["price"])
                if row["status"] == "available" and valid_price(row["price"])
                else None
            )
    return snapshots


def round_return(release, action, snapshots):
    entry, exit = endpoint_times(release)
    return pair_return(
        action["stock1"],
        action["stock2"],
        action["action"],
        snapshots.get(entry, {}),
        snapshots.get(exit, {}),
    )


def read_svg_curves(path: Path, state):
    """Recover approximate public CR only for cross-checks, never for pricing gaps.

    The SVG stores y to 0.01 px. Its exact zero line and three exact final CRs
    identify the admissible linear scale. The intersection propagates rounding
    uncertainty, avoiding any claim that plotted coordinates are exact prices.
    """
    if not path.exists():
        return {}, {"available": False}
    nodes = list(ET.parse(path).getroot())
    names = {
        "Codex(gpt-5.3-codex) · Baseline": "Codex baseline",
        "FinMem(gpt-4.1-mini) · Baseline": "FinMem baseline",
        "Moira(gpt-4.1-mini) · Baseline": "Moira baseline",
    }
    paths = {}
    previous = None
    for node in nodes:
        if node.tag.endswith("polyline"):
            previous = [float(p.split(",")[1]) for p in node.attrib["points"].split()]
        elif node.tag.endswith("text") and node.text in names and previous:
            paths[names[node.text]] = previous
    zero = None
    for node in nodes:
        if node.tag.endswith("path") and node.attrib.get("stroke") == "#aaa":
            zero = float(node.attrib["d"].split(" ")[1].split("H")[0])
    if zero is None or len(paths) != 3:
        return {}, {"available": False, "reason": "Unexpected SVG structure"}
    lower, upper = 0.0, float("inf")
    official = {r["team_name"]: r["cumulative_return"] for r in state["rows"]}
    for name, ys in paths.items():
        cr = official[name]
        bounds = sorted(
            ((zero - ys[-1] - 0.005000001) / cr, (zero - ys[-1] + 0.005000001) / cr)
        )
        lower, upper = max(lower, bounds[0]), min(upper, bounds[1])
    if lower > upper or lower <= 0:
        return {}, {"available": False, "reason": "SVG calibration inconsistent"}
    scale = (lower + upper) / 2
    curves = {}
    for name, ys in paths.items():
        if len(ys) != 42:
            raise ValueError("Expected starting equity plus 41 SVG points")
        intervals = []
        for y in ys:
            vals = [
                (zero - y + eps) / s
                for eps in (-0.005000001, 0.005000001)
                for s in (lower, upper)
            ]
            intervals.append((min(vals), max(vals)))
        curves[name] = {
            "cr_midpoints": [(zero - y) / scale for y in ys],
            "cr_intervals": intervals,
        }
    return curves, {
        "available": True,
        "coordinate_rounding_px": 0.01,
        "scale_px_per_unit_cr_interval": [lower, upper],
        "zero_y_px": zero,
        "use": "Approximate consistency check only; not a substitute for unpublished endpoint prices",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = p.parse_args()
    root = args.root
    state = json.loads((root / "sources/live-state.json").read_text())
    snapshots = load_price_snapshots(root)
    if len(snapshots) != 41:
        raise RuntimeError(
            f"Expected all 41 released snapshots, found {len(snapshots)}; wait for transfer"
        )
    curves, calibration = read_svg_curves(root / "sources/return-paths.svg", state)
    result = {
        "official_state_updated_at": state["updated_at"],
        "price_snapshot_count": len(snapshots),
        "formula": "LS=0.5*(exit1/entry1-1)-0.5*(exit2/entry2-1); SL=-LS; F=0; equity*=1+r",
        "timing": "entry_at and exit_at from official release_schedule; never decision release prices",
        "svg_calibration": calibration,
        "baselines": [],
        "full_41_price_based_reproduction": False,
        "limitation": "Public release data omit four terminal valuation snapshots; do not substitute flat returns or SVG-derived prices.",
    }
    records = []
    schedule = state["release_schedule"]
    common_rounds = [
        r["round"] for r in schedule if all(t in snapshots for t in endpoint_times(r))
    ]
    result["common_public_price_rounds"] = common_rounds
    for baseline in state["rows"]:
        if not baseline["is_baseline"]:
            continue
        name = baseline["team_name"]
        returns, actions = [], []
        mismatches = []
        curve = curves.get(name)
        for release, action in zip(schedule, baseline["steps"]):
            if release["round"] != action["step"]:
                raise ValueError("Step/schedule mismatch")
            rr = round_return(release, action, snapshots)
            returns.append(rr)
            actions.append(action["action"])
            entry, exit = endpoint_times(release)
            row = {
                "baseline": name,
                "round": action["step"],
                "round_id": release["round_id"],
                **{k: action[k] for k in ("stock1", "stock2", "action")},
                "entry_at": release["entry_at"],
                "exit_at": release["exit_at"],
                "return": rr,
                "entry_snapshot_public": entry in snapshots,
                "exit_snapshot_public": exit in snapshots,
                "svg_return_approx": None,
                "svg_return_lower": None,
                "svg_return_upper": None,
                "svg_check_pass": None,
            }
            if curve and rr is not None:
                step = action["step"]
                a0, a1 = curve["cr_intervals"][step - 1]
                b0, b1 = curve["cr_intervals"][step]
                lo, hi = (1 + b0) / (1 + a1) - 1, (1 + b1) / (1 + a0) - 1
                row["svg_return_approx"] = (1 + curve["cr_midpoints"][step]) / (
                    1 + curve["cr_midpoints"][step - 1]
                ) - 1
                row["svg_return_lower"], row["svg_return_upper"] = lo, hi
                row["svg_check_pass"] = lo - 1e-12 <= rr <= hi + 1e-12
                if not row["svg_check_pass"]:
                    mismatches.append(step)
            records.append(row)
        common_returns = [r for i, r in enumerate(returns, 1) if i in common_rounds]
        common_actions = [a for i, a in enumerate(actions, 1) if i in common_rounds]
        result["baselines"].append(
            {
                "name": name,
                "official_full_41": {
                    k: baseline[k]
                    for k in ("cumulative_return", "max_drawdown", "sharpe_ratio")
                },
                "public_common_intervals": {
                    **metrics(common_returns, common_actions),
                    "rounds": common_rounds,
                    "scope": "same_common_public_price_intervals_for_all_methods",
                },
                "all_scorable_including_flat_without_prices": metrics(returns, actions),
                "unscorable_rounds": [i for i, r in enumerate(returns, 1) if r is None],
                "svg_checked_round_count": sum(
                    r["baseline"] == name and r["svg_check_pass"] is not None
                    for r in records
                ),
                "svg_mismatch_rounds": mismatches,
            }
        )
    (root / "results").mkdir(exist_ok=True)
    (root / "results/baseline_replay.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    with (root / "results/baseline_replay_rounds.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(records[0]))
        w.writeheader()
        w.writerows(records)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
