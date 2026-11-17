"""Post-hoc input/signal audit. No strategy modification, search, or API calls."""

import hashlib
import json
from collections import Counter
import numpy as np
import pandas as pd
from agent import ROOT, TICKERS
from replay_baselines import load_price_snapshots
from scoring import endpoint_times

state = json.loads((ROOT / "sources/live-state.json").read_text())
snaps = load_price_snapshots(ROOT)
samples = []
ics = []
repetition = []
prior_links = {}
events = Counter()
conf = []
sent = []
missing = Counter()
for rel in state["release_schedule"]:
    rid = rel["round_id"]
    folder = ROOT / "data/raw" / rid.replace(":", "-")
    news = pd.read_parquet(folder / "news.parquet").to_dict("records")
    decision = json.loads(
        (ROOT / "logs/decisions/full" / (rid.replace(":", "-") + ".json")).read_text()
    )
    entry, exit = endpoint_times(rel)
    ret = {}
    if entry in snaps and exit in snaps:
        ret = {
            t: snaps[exit][t] / snaps[entry][t] - 1
            for t in TICKERS
            if snaps[exit].get(t) and snaps[entry].get(t)
        }
    for row in news:
        t = row["ticker"]
        ann = decision["details"][t]
        links = set(str(x) for x in row.get("source_links", []) if str(x))
        previous = prior_links.get(t, set())
        if previous and links:
            repetition.append(
                {
                    "round": rel["round"],
                    "ticker": t,
                    "current_links": len(links),
                    "previous_links": len(previous),
                    "shared_links": len(links & previous),
                    "fraction_current_seen_in_previous": len(links & previous)
                    / len(links),
                }
            )
        prior_links[t] = links
        events[ann["event"]] += 1
        conf.append(ann["confidence"])
        sent.append(ann["sentiment"])
        if not row["summary"]:
            missing["empty_summary"] += 1
        samples.append(
            {
                "round": rel["round"],
                "round_id": rid,
                "ticker": t,
                "summary": row["summary"],
                "news_count": int(row["news_count"]),
                "coverage_status": row["coverage_status"],
                "sentiment": ann["sentiment"],
                "confidence_capped": ann["confidence"],
                "event": ann["event"],
                "annotation_reason": ann["reason"],
                "hash": hashlib.sha256((rid + "|" + t).encode()).hexdigest(),
            }
        )
    if len(ret) >= 6:
        r = pd.Series(ret)
        item = {"round": rel["round"], "n": len(ret)}
        for field in ["sentiment", "momentum", "score"]:
            x = pd.Series({t: decision["details"][t][field] for t in ret})
            item[field + "_spearman"] = (
                float(x.rank().corr(r.rank()))
                if x.nunique() > 1 and r.nunique() > 1
                else None
            )
        n = pd.Series(
            {
                t: decision["details"][t]["sentiment"]
                * decision["details"][t]["confidence"]
                for t in ret
            }
        )
        item["news_component_spearman"] = (
            float(n.rank().corr(r.rank()))
            if n.nunique() > 1 and r.nunique() > 1
            else None
        )
        ics.append(item)
selected = sorted(samples, key=lambda x: x["hash"])[:24]
result = {
    "status": "post_hoc_descriptive_audit_not_model_selection",
    "annotation_count": len(samples),
    "event_counts": dict(events),
    "sentiment_counts": {
        "positive": sum(x > 0 for x in sent),
        "negative": sum(x < 0 for x in sent),
        "zero": sum(x == 0 for x in sent),
    },
    "capped_confidence_mean": float(np.mean(conf)),
    "partial_coverage_count": sum(
        str(x["coverage_status"]).startswith("partial") for x in samples
    ),
    "news_source_overlap": {
        "comparisons": len(repetition),
        "mean_fraction_current_seen_in_previous": float(
            np.mean([r["fraction_current_seen_in_previous"] for r in repetition])
        ),
        "comparisons_over_half_overlap": sum(
            r["fraction_current_seen_in_previous"] > 0.5 for r in repetition
        ),
        "note": "Repeated URLs across stated news windows indicate non-independent observed source sets; publication times are unavailable, so this audit cannot establish a leakage violation.",
    },
    "cross_sectional_rank_diagnostics": {},
    "per_round_rank_diagnostics": ics,
    "qualitative_sample": {
        "selection": "24 lowest SHA256(round_id|ticker), independent of return and model annotation",
        "records": selected,
    },
    "limitations": [
        "Per-stock returns share time and factor exposures; observations are not independent.",
        "Rank correlation is descriptive, post hoc and not used for threshold/model selection.",
        "LLM confidence is not a calibrated profit probability; do not interpret it as one.",
        "The quantitative audit tests alignment with later returns, not factual truth of original summaries.",
        "Qualitative annotation review is assistant-generated and is not independent human ground truth.",
    ],
}
for k in [
    "sentiment_spearman",
    "news_component_spearman",
    "momentum_spearman",
    "score_spearman",
]:
    vals = [x[k] for x in ics if x[k] is not None]
    result["cross_sectional_rank_diagnostics"][k] = {
        "rounds": len(vals),
        "mean": float(np.mean(vals)),
        "median": float(np.median(vals)),
        "positive_round_fraction": sum(x > 0 for x in vals) / len(vals),
    }
(ROOT / "results/semantic_audit.json").write_text(
    json.dumps(result, indent=2, ensure_ascii=False)
)
(ROOT / "results/news_source_overlap.json").write_text(json.dumps(repetition, indent=2))
print(
    json.dumps(
        {
            k: v
            for k, v in result.items()
            if k not in ["qualitative_sample", "per_round_rank_diagnostics"]
        },
        indent=2,
        ensure_ascii=False,
    )
)
print("\nQUALITATIVE SAMPLE\n" + json.dumps(selected, indent=2, ensure_ascii=False))
