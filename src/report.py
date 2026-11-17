import json
import csv
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from agent import ROOT

plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans"]
plt.rcParams["svg.fonttype"] = "none"
plt.rcParams["font.size"] = 9
plt.rcParams["axes.spines.right"] = False
plt.rcParams["axes.spines.top"] = False
plt.rcParams["axes.linewidth"] = 1
plt.rcParams["legend.frameon"] = False
base = json.loads((ROOT / "results/baseline_replay.json").read_text())
ours = json.loads((ROOT / "results/agent_results.json").read_text())
methods = [(b["name"], b["public_common_intervals"]) for b in base["baselines"]]
methods += [(b["method"], b["public_common_intervals"]) for b in ours["methods"]]
lines = [
    r"\begin{table}[t]",
    r"\centering",
    r"\caption{Retrospective results on the same 37 observable intervals (rounds 1--10 and 13--39). CR and MDD are computed after excluding the four unavailable intervals, not on the complete 41-round account. Win rates count positive returns; flat rounds are not wins.}",
    r"\label{tab:replay}",
    r"\setlength{\tabcolsep}{3pt}",
    r"\scriptsize",
    r"\begin{tabular}{lrrrrr}",
    r"\hline",
    r"Method & CR (\%) & MDD (\%) & Win/all & Win/active & Trades \\",
    r"\hline",
]
names = {
    "FinMem baseline": "FinMem",
    "Moira baseline": "Moira",
    "Codex baseline": "Codex",
    "FinProbeBench full": "FinProbeBench",
    "FinProbeBench no_news": "w/o news",
    "FinProbeBench no_risk": "w/o risk",
}
for name, m in methods:
    lines.append(
        f"{names[name]} & {100 * m['cr']:.3f} & {100 * m['max_drawdown']:.3f} & {100 * m['win_rate_all_settled']:.1f}\\% & {100 * m['win_rate_active']:.1f}\\% & {m['active_settled_count']}/37 "
        + r"\\"
    )
lines += [r"\hline", r"\end{tabular}", r"\end{table}"]
(ROOT / "paper/figures").mkdir(parents=True, exist_ok=True)
(ROOT / "paper/results_table.tex").write_text("\n".join(lines) + "\n")
series = {}
rows = list(csv.DictReader((ROOT / "results/baseline_replay_rounds.csv").open()))
common = set(ours["common_rounds"])
for name, _ in methods[:3]:
    series[name] = [
        float(r["return"])
        for r in rows
        if r["baseline"] == name and int(r["round"]) in common
    ]
rows2 = list(csv.DictReader((ROOT / "results/agent_rounds.csv").open()))
for variant in ["full", "no_news", "no_risk"]:
    series["FinProbeBench " + variant] = [
        float(r["return"])
        for r in rows2
        if r["method"] == variant and int(r["round"]) in common
    ]
fig, axes = plt.subplots(1, 2, figsize=(7.05, 2.55), layout="constrained")
colors = {
    "FinMem baseline": "#54826A",
    "Moira baseline": "#A88B4E",
    "Codex baseline": "#8A8C91",
    "FinProbeBench full": "#325B9A",
    "FinProbeBench no_news": "#54826A",
    "FinProbeBench no_risk": "#B27576",
}
for ax, names_plot, title in [
    (axes[0], list(series)[:3] + ["FinProbeBench full"], "a  Baseline comparison"),
    (
        axes[1],
        ["FinProbeBench full", "FinProbeBench no_news", "FinProbeBench no_risk"],
        "b  Fixed ablations",
    ),
]:
    for name in names_plot:
        y = np.r_[0.0, (np.cumprod(1 + np.array(series[name])) - 1) * 100]
        ax.plot(
            np.arange(38),
            y,
            label=names[name],
            color=colors[name],
            lw=1.6,
            ls="-" if name == "FinProbeBench full" else "--",
        )
    ax.axhline(0, color="#bbb", lw=0.6)
    ax.grid(axis="y", color="#eee", lw=0.5)
    ax.set_title(title, loc="left", fontsize=10)
    ax.set_xlabel("Observable interval index")
    ax.set_ylabel("Compounded return (%)")
    ax.legend(fontsize=7, loc="best")
    ax.set_xlim(0, 37)
for ext in ["pdf", "svg", "png"]:
    fig.savefig(ROOT / ("paper/figures/common_intervals." + ext), dpi=220)
plt.close(fig)
usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0}
for f in (ROOT / "logs/llm").glob("*/response-*.json"):
    d = json.loads(f.read_text())
    usage["calls"] += 1
    for k in ["prompt_tokens", "completion_tokens", "total_tokens"]:
        usage[k] += d.get("usage", {}).get(k, 0)
(ROOT / "results/api_usage.json").write_text(json.dumps(usage, indent=2))
