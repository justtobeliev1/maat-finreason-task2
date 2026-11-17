# Maat: an evidence-gated news–price agent for market-neutral hedging

English | [中文](README.zh.md)

Code, configuration and archived records for **Maat**, the system of team **FinProbeBench** for
[FinReason Cup 2026](https://the-finai.github.io/IEEE-bigdata-cup/) Task 2 (Market-Neutral Hedging).
It accompanies the Working Notes paper
*Maat at FinReason Cup 2026 Task 2: An Evidence-Gated News–Price Agent for Market-Neutral Hedging*.

In every round the task asks for an equal-dollar long–short position in two of ten large-cap stocks,
or no position. A language-model analyst turns each release's news summaries into validated
per-stock evidence (sentiment, confidence, event type, reason); a deterministic branch computes price
momentum; coverage-aware eligibility, breadth and separation gates decide whether to trade; and a
deployment policy, declared and hashed before the live session, selects the scoring rule. Three
variants were frozen before any of their returns was computed: news-led (`full`), momentum-routed
(`no_news`, deployed live) and ungated (`no_risk`).

| | Result |
|---|---|
| October replay, 37 public intervals, news-led | CR 0.30%, 18 active intervals |
| October replay, momentum-routed | CR 4.96%, 36 active intervals |
| Live session, 2 November 2026, momentum-routed | CR 2.33% over six rounds, first in the Phase III ranking (organizer-reported) |

## What is included

| Path | Content |
|---|---|
| `prompt/system_prompt.txt` | the analyst's system prompt, verbatim (also `SYSTEM` in `src/agent.py`) |
| `preregistration.json`, `preregistration.sha256` | frozen model, temperature, weights and thresholds |
| `live_policy.json`, `live_policy.sha256` | live deployment policy (v2), declared and hashed on 1 November 2026, SHA-256 `6142a54f4a2866115c2c2890511942793adc61a13163f5996368aeaeb6a930ce` (*to be added*, see below) |
| `src/agent.py` | analyst request, response validation, cache, and the decision function `decide()` |
| `src/experiment.py`, `src/scoring.py` | replay of the three frozen variants; Eq. (1), endpoint times and metrics |
| `src/replay_baselines.py` | the organizers' baselines with the same evaluator; the chart conversion is used only for the consistency check |
| `src/diagnostics.py`, `src/semantic_audit.py` | post-hoc diagnostics (gates, news-zero, concentration) and the descriptive signal audit |
| `src/report.py` | Table II, Fig. 2 and token usage |
| `src/live.py` | local live helper (recommendation only, no submission code), version of 1 November 2026 |
| `src/prepare_data.py` | arranges the downloaded dataset as `data/raw/<release>/` |
| `src/camera_ready_stats.py` | bootstrap intervals, tests and gate-isolation diagnostics of the final paper |
| `logs/llm/<sha256>/` | every analyst call: `request.json` (exact request body), `response-1.json` (raw provider response), `validated.json`, `metadata.json` |
| `logs/decisions/{full,no_news,no_risk}/` | one record per release and variant: every stock's evidence, eligibility, score, the action and its reason |
| `logs/live/phase3_post/` | post-session records of all three variants on the six live releases (*to be added*, see below) |
| `live/` | the unattended runner that submitted the six live actions, its rehearsal portal, and its records (`phase3/`: decision, download hashes and portal receipt per round, run log) |
| `results/` | per-round actions and returns, baseline replay, diagnostics, signal audit and token usage behind the paper's tables; `camera_ready_stats.json` and `camera_ready_macros.tex` hold every interval, test and diagnostic added in the final version |
| `tests/` | unit tests of the scoring, the decision function, the live history rule and the cached replay |

Request bodies contain only the payload; no credential or HTTP header was ever stored.

### To be added

Three items are kept on our laboratory server and will be added to this repository when it is accessible again:
`live_policy.json` with `live_policy.sha256` (the declared live policy, SHA-256 `6142a54f4a2866115c2c2890511942793adc61a13163f5996368aeaeb6a930ce`),
the post-session records of the three variants on the six live releases (`logs/live/phase3_post/`),
and the script that computes the per-event breakdown of Table III (`src/paper_extras.py`).
Everything else in the paper can be recomputed from the files already here.

## Data

The organizers' price and news files are **not** included. Download them from the public dataset
[CarolynJiang/Market-Neutral-Hedging-live-trading](https://huggingface.co/datasets/CarolynJiang/Market-Neutral-Hedging-live-trading)
and arrange them for the replay:

```bash
pip install huggingface_hub pandas pyarrow numpy matplotlib
huggingface-cli download CarolynJiang/Market-Neutral-Hedging-live-trading \
    --repo-type dataset --local-dir data/hf
python src/prepare_data.py          # data/raw/<YYYY-MM-DD_HH-MM>/{price,news}.parquet
```

The scripts also read the organizers' October live state, `sources/live-state.json` (release schedule
with entry and exit times, and the baselines' published actions), and the baselines' return chart,
`sources/return-paths.svg`, both published on the organizers' live-trading page
(<https://carolyn-jiang.github.io/Market-Neutral-Hedging-live-trading/>); they are not redistributed here.
The SHA-256 of every downloaded live file is in `live/phase3/*/fetch.json`, and that of every October
file in `results/data_manifest.json`.

## Reproducing the paper without model calls

The analyst cache is keyed by the SHA-256 of the exact request body. With the data in place, the
replay rebuilds each request, finds it under `logs/llm/`, and reuses the stored annotation, so no
call is made and no key is needed. Run from the repository root:

```bash
python src/experiment.py            # replay of the three variants -> results/agent_rounds.csv
python src/replay_baselines.py      # organizers' baselines with the same evaluator
python src/diagnostics.py           # where-the-return-comes-from diagnostics
python src/semantic_audit.py        # descriptive signal audit
python src/report.py                # Table II, Fig. 2, token usage
python src/camera_ready_stats.py --strict   # intervals, tests, fixed-pool comparison
python -m unittest discover -s tests
python live/test_decide.py          # vendored decide() reproduces all 41 momentum-routed decisions
```

`camera_ready_stats.py` first reproduces the published replay numbers and lists any mismatch.
Python 3.10 or later with `numpy`, `pandas` and `pyarrow` (`matplotlib` for `src/report.py`).

## Integrity of the frozen files

```bash
sha256sum preregistration.json        # live_policy.json once added
cat preregistration.sha256
```

## Changes from the deployed files

Two lines differ from the files that ran in the replay and the live session, so that no local path or credential location is
published: `src/agent.py` (and its vendored copy `live/vendor/agent.py`) reads the API key from the
environment variable `MAAT_API_KEY` instead of a file on our server, and `live/run_phase3.py` keeps
the portal's team token in the file named by `MAAT_PORTAL_TOKEN_FILE`. The prompt, the validator
and `decide()` are unchanged; `live/test_decide.py` uses repository-relative paths.
`src/report.py` omits the final part of the deployed file, which wrote an internal run report with
server paths, and creates its output directory itself. `src/camera_ready_stats.py` is the final
statistics script; its `--root`, `--data-root` and `--results-root` options let it run on a copy of
the archive outside the repository.

## Citation

```bibtex
@inproceedings{finprobebench2026maat,
  title     = {Maat at {FinReason Cup 2026} Task 2: An Evidence-Gated News--Price Agent for Market-Neutral Hedging},
  author    = {Cao, Run and Kuang, Ziyan and Xie, Qianqian},
  booktitle = {2026 IEEE International Conference on Big Data (BigData), FinReason Cup Working Notes},
  year      = {2026}
}
```

## License

The code is released under the MIT License (see `LICENSE`). The news summaries quoted inside the
archived request bodies come from the organizers' dataset and remain under its terms.
