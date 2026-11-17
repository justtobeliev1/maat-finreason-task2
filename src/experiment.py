"""Single frozen retrospective run; all execution occurs on the laboratory server."""

import argparse
import csv
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import pandas as pd
from agent import ROOT, TICKERS, SYSTEM, annotate, decide
from scoring import metrics, endpoint_times
from replay_baselines import load_price_snapshots, round_return


def read_news(release):
    folder = ROOT / "data/raw" / release["round_id"].replace(":", "-")
    frame = pd.read_parquet(folder / "news.parquet")
    if frame["ticker"].duplicated().any() or set(frame["ticker"]) != set(TICKERS):
        raise ValueError("News must have ten unique eligible tickers")
    out = []
    for row in frame.to_dict("records"):
        if datetime.fromisoformat(str(row["timestamp"])) != datetime.fromisoformat(
            release["timestamp"]
        ):
            raise ValueError("News release timestamp mismatch")
        if datetime.fromisoformat(str(row["window_end"])) > datetime.fromisoformat(
            release["timestamp"]
        ):
            raise ValueError("Future news window")
        out.append(
            {
                "ticker": str(row["ticker"]),
                "summary": str(row["summary"]) if pd.notna(row["summary"]) else "",
                "news_count": int(row["news_count"])
                if pd.notna(row["news_count"])
                else 0,
                "coverage_status": str(row["coverage_status"]),
            }
        )
    return sorted(out, key=lambda n: TICKERS.index(n["ticker"]))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--workers", type=int, default=4)
    args = p.parse_args()
    cfg = json.loads((ROOT / "preregistration.json").read_text())
    cfg_hash = hashlib.sha256((ROOT / "preregistration.json").read_bytes()).hexdigest()
    expected = (ROOT / "preregistration.sha256").read_text().split()[0]
    if cfg_hash != expected:
        raise ValueError("Frozen configuration checksum differs")
    state = json.loads((ROOT / "sources/live-state.json").read_text())
    schedule = state["release_schedule"]
    snapshots = load_price_snapshots(ROOT)
    if len(snapshots) != 41:
        raise RuntimeError("41 released price snapshots required")
    news_all = {r["round_id"]: read_news(r) for r in schedule}
    manifest = []
    for path in sorted((ROOT / "data/raw").glob("*/*.parquet")):
        manifest.append(
            {
                "path": str(path.relative_to(ROOT)),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
            }
        )
    (ROOT / "results/data_manifest.json").write_text(json.dumps(manifest, indent=2))
    (ROOT / "logs/frozen_prompt.txt").write_text(SYSTEM)
    (ROOT / "results/run_metadata.json").write_text(
        json.dumps(
            {
                "server_host": __import__("socket").gethostname(),
                "started_utc": datetime.now(timezone.utc).isoformat(),
                "config_sha256": cfg_hash,
                "prompt_sha256": hashlib.sha256(SYSTEM.encode()).hexdigest(),
                "python": __import__("sys").version,
                "variants": cfg["variants"],
                "parameter_search": False,
            },
            indent=2,
        )
    )
    annotations = {}

    def process(release):
        rid = release["round_id"]
        try:
            anns, digest = annotate(news_all[rid], cfg, rid)
            return rid, anns, digest, None
        except Exception as exc:
            return rid, {}, None, {"type": type(exc).__name__, "message": str(exc)}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(process, r) for r in schedule]
        for future in as_completed(futures):
            rid, anns, digest, error = future.result()
            annotations[rid] = (anns, digest, error)
            print(
                json.dumps(
                    {"release": rid, "annotation_ok": error is None, "error": error}
                ),
                flush=True,
            )
    common = [
        r["round"] for r in schedule if all(t in snapshots for t in endpoint_times(r))
    ]
    decisions = {v: [] for v in cfg["variants"]}
    previous_prices = {}
    for release in schedule:
        rid = release["round_id"]
        now = datetime.fromisoformat(release["timestamp"])
        prices = snapshots[now]
        anns, digest, error = annotations[rid]
        file_hashes = {
            m["path"]: m["sha256"]
            for m in manifest
            if rid.replace(":", "-") in m["path"]
        }
        for variant in cfg["variants"]:
            action = decide(prices, previous_prices, news_all[rid], anns, cfg, variant)
            action.update(
                round=release["round"],
                round_id=rid,
                request_sha256=digest,
                input_file_hashes=file_hashes,
                config_sha256=cfg_hash,
                annotation_error=error,
            )
            if error and variant != "no_news":
                action.update(
                    action="F",
                    reason="Annotation failed; deterministic fail-closed policy.",
                )
            decisions[variant].append(action)
            directory = ROOT / "logs/decisions" / variant
            directory.mkdir(parents=True, exist_ok=True)
            (directory / (rid.replace(":", "-") + ".json")).write_text(
                json.dumps(action, indent=2)
            )
        previous_prices = prices
    results = {
        "common_rounds": common,
        "common_count": len(common),
        "scope": "Compound only common observable intervals; not an estimate of complete 41-round CR.",
        "annotation_failures": [rid for rid, (_, _, err) in annotations.items() if err],
        "methods": [],
    }
    output_rows = []
    for variant, acts in decisions.items():
        returns = [round_return(r, a, snapshots) for r, a in zip(schedule, acts)]
        chosen = [
            (r, a) for i, (r, a) in enumerate(zip(returns, acts), 1) if i in common
        ]
        values = [r for r, a in chosen]
        actions = [a["action"] for r, a in chosen]
        results["methods"].append(
            {
                "method": "FinProbeBench " + variant,
                "public_common_intervals": metrics(values, actions),
                "all_scorable_including_flat_without_prices": metrics(
                    returns, [a["action"] for a in acts]
                ),
                "unscorable_rounds": [i for i, r in enumerate(returns, 1) if r is None],
                "flat_all_41": sum(a["action"] == "F" for a in acts),
            }
        )
        for release, action, rr in zip(schedule, acts, returns):
            output_rows.append(
                {
                    "method": variant,
                    "round": release["round"],
                    "round_id": release["round_id"],
                    "stock1": action["stock1"],
                    "stock2": action["stock2"],
                    "action": action["action"],
                    "return": rr,
                    "common_interval": release["round"] in common,
                    "reason": action["reason"],
                }
            )
    (ROOT / "results/agent_results.json").write_text(json.dumps(results, indent=2))
    with (ROOT / "results/agent_rounds.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(output_rows[0]))
        w.writeheader()
        w.writerows(output_rows)
    print(json.dumps(results, indent=2), flush=True)


if __name__ == "__main__":
    main()
