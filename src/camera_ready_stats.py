"""Camera-ready statistics: uncertainty intervals and the gate-isolation diagnostics.

Computed only from archived decision records (which hold every stock's sentiment, capped
confidence, momentum, score and eligibility under each variant) and the public price snapshots.
No language-model call is made and nothing under logs/ or data/ is modified.

Outputs
  results/camera_ready_stats.json   all numbers, with the inputs they were computed from
  results/camera_ready_macros.tex   the same numbers as LaTeX macros for the paper

Before writing anything the script reproduces the published replay numbers (CR and active
intervals of the three variants on the 37 common intervals, the record counts and agreement
rates of the analyst table, the news-zero diagnostic) and reports every mismatch, so a
definitional difference cannot pass silently. Use --strict to stop on a mismatch.

  python src/camera_ready_stats.py                      # run from inside the repository
  python -I camera_ready_stats.py --root ARCHIVE/FinProbeBench --data-root DATA_DIR \
      --results-root OUT_DIR --out camera_ready_stats.json --macros camera_ready_macros.tex --strict
  python src/camera_ready_stats.py --schedule PATH ...  # explicit October schedule file(s)
"""

import argparse
import glob
import json
import math
import pathlib
import re
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
TICKERS = ("NVDA", "GOOG", "META", "MSFT", "JPM", "AMZN", "AAPL", "AMD", "WMT", "TSLA")
VARIANTS = ("full", "no_news", "no_risk")
NY = ZoneInfo("America/New_York")
SEED = 20261119
REPS = 20000
BLOCKS = (3, 5)
NEWS_W, MOM_W, MIN_ELIG, MIN_GAP = 0.7, 0.3, 6, 0.35

# Values printed in the submitted paper; used only to check that the definitions match.
PAPER = {
    "n_rounds": 41, "n_common": 37,
    "cr": {"full": 0.30, "no_news": 4.96, "no_risk": 0.32},
    "active": {"full": 18, "no_news": 36, "no_risk": 37},
    "news_records": 277, "news_agree": 46.9, "mom_records": 267, "mom_agree": 50.9,
    "news_zero_cr": -1.86,
}

RID = re.compile(r"(20\d\d)-(\d\d)-(\d\d)[_T ](\d\d)[-:](\d\d)")


# ---------------------------------------------------------------- helpers
def rid_of(*texts):
    for t in texts:
        m = RID.search(str(t or ""))
        if m:
            y, mo, d, h, mi = m.groups()
            return f"{y}-{mo}-{d}_{h}:{mi}"
    return None


def utc(ts):
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize(NY)
    return t.tz_convert("UTC").to_pydatetime()


def sign(x):
    return (x > 0) - (x < 0)


def pct(x, nd=2):
    return round(100.0 * x, nd)


def compound(r):
    return float(np.prod(1.0 + np.asarray(r, float)) - 1.0)


def betainc_reg(a, b, x):
    """Regularized incomplete beta I_x(a,b) (continued fraction, Numerical Recipes)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1 - x))
    if x > (a + 1) / (a + b + 2):
        return 1.0 - betainc_reg(b, a, 1 - x)
    f, c, d = 1.0, 1.0, 0.0
    for i in range(400):
        m = i // 2
        if i == 0:
            num = 1.0
        elif i % 2 == 0:
            num = m * (b - m) * x / ((a + 2 * m - 1) * (a + 2 * m))
        else:
            num = -(a + m) * (a + b + m) * x / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + num * d
        d = 1e-300 if abs(d) < 1e-300 else d
        d = 1.0 / d
        c = 1.0 + num / c
        c = 1e-300 if abs(c) < 1e-300 else c
        f *= c * d
        if abs(1.0 - c * d) < 1e-12:
            break
    return front * (f - 1.0) / a


def t_test(x):
    x = np.asarray(x, float)
    n = len(x)
    mean, sd = float(x.mean()), float(x.std(ddof=1))
    t = mean / (sd / math.sqrt(n))
    df = n - 1
    p = betainc_reg(df / 2.0, 0.5, df / (df + t * t))
    return {"n": n, "mean_pct": pct(mean, 3), "sd_pct": pct(sd, 3), "t": round(t, 3), "df": df, "p_two_sided": round(p, 4)}


# ---------------------------------------------------------------- bootstrap
def idx_iid(rng, n, reps):
    return rng.integers(0, n, size=(reps, n))


def idx_block(rng, n, reps, length):
    """Circular moving-block bootstrap indices for an ordered sequence of n units."""
    k = math.ceil(n / length)
    starts = rng.integers(0, n, size=(reps, k))
    idx = (starts[:, :, None] + np.arange(length)[None, None, :]) % n
    return idx.reshape(reps, k * length)[:, :n]


def schemes(n):
    out = {"cluster_iid": lambda rng: idx_iid(rng, n, REPS)}
    for L in BLOCKS:
        out[f"block{L}"] = (lambda L: (lambda rng: idx_block(rng, n, REPS, L)))(L)
    return out


def ci_p(boot, obs, null):
    """Percentile 95% interval and two-sided p-value of the shifted (null-centred) bootstrap."""
    lo, hi = np.percentile(boot, [2.5, 97.5])
    extreme = np.abs(boot - obs) >= abs(obs - null) - 1e-15
    p = (extreme.sum() + 1) / (len(boot) + 1)
    return float(lo), float(hi), float(p)


def boot_rate(num, den, null=0.5):
    """Pooled rate sum(num)/sum(den), resampling whole rounds (units)."""
    num, den = np.asarray(num, float), np.asarray(den, float)
    obs = num.sum() / den.sum()
    out = {"rate_pct": pct(obs, 1), "records": int(den.sum()), "units": int(len(den))}
    for name, draw in schemes(len(den)).items():
        idx = draw(np.random.default_rng(SEED))
        b = num[idx].sum(1) / np.maximum(den[idx].sum(1), 1)
        lo, hi, p = ci_p(b, obs, null)
        out[name] = {"ci95_pct": [pct(lo, 1), pct(hi, 1)], "p_vs_half": round(p, 4)}
    return out


def boot_mean(x, null=0.0):
    x = np.asarray(x, float)
    obs = float(x.mean())
    out = {"mean_pct": pct(obs, 3), "n": int(len(x))}
    for name, draw in schemes(len(x)).items():
        idx = draw(np.random.default_rng(SEED))
        lo, hi, p = ci_p(x[idx].mean(1), obs, null)
        out[name] = {"ci95_pct": [pct(lo, 3), pct(hi, 3)], "p_vs_zero": round(p, 4)}
    return out


def boot_cr(r, r_ref=None):
    """CR of an interval series (or CR difference to a paired reference series)."""
    r = np.asarray(r, float)
    ref = None if r_ref is None else np.asarray(r_ref, float)
    stat = lambda a, b: np.prod(1 + a, axis=-1) - 1 - (0 if b is None else np.prod(1 + b, axis=-1) - 1)
    obs = float(stat(r, ref))
    out = {"value_pct": pct(obs), "n": int(len(r))}
    for name, draw in schemes(len(r)).items():
        idx = draw(np.random.default_rng(SEED))
        b = stat(r[idx], None if ref is None else ref[idx])
        lo, hi, p = ci_p(b, obs, 0.0)
        out[name] = {"ci95_pct": [pct(lo), pct(hi)], "p_vs_zero": round(p, 4)}
    return out


# ---------------------------------------------------------------- inputs
def load_schedule(paths, rounds_csv):
    rows = []
    cands = list(paths)
    if not cands:
        pats = ["sources/**/*live-state*.json", "sources/**/*state*.json", "data/**/*schedule*.json",
                "data/**/*state*.json", "results/*schedule*.json"]
        for p in pats:
            cands += [c for c in sorted(glob.glob(str(ROOT / p), recursive=True)) if c not in cands]
    for path in cands:
        try:
            obj = json.loads(pathlib.Path(path).read_text())
        except Exception:
            continue
        sched = obj.get("release_schedule") if isinstance(obj, dict) else obj
        if not isinstance(sched, list):
            continue
        for r in sched:
            if isinstance(r, dict) and {"entry_at", "exit_at"} <= set(r) and str(rid_of(r.get("round_id"), r.get("timestamp")) or "").startswith("2026-10"):
                rows.append(r)
    if not rows and rounds_csv is not None and {"entry_at", "exit_at"} <= set(rounds_csv.columns):
        rows = rounds_csv.drop_duplicates("round_id").to_dict("records")
    sched = {}
    for r in rows:
        rid = rid_of(r.get("round_id"), r.get("timestamp"))
        sched[rid] = {"round_id": rid, "release": utc(r.get("timestamp") or rid.replace("_", " ")),
                      "entry": utc(r["entry_at"]), "exit": utc(r["exit_at"])}
    out = sorted(sched.values(), key=lambda r: r["release"])
    for i, r in enumerate(out, 1):
        r["round"] = i
    return out, cands


def load_prices(pattern, root=None):
    snaps = {}
    for f in sorted(glob.glob(str((root or ROOT) / pattern), recursive=True)):
        frame = pd.read_parquet(f)
        for row in frame.to_dict("records"):
            ok = str(row.get("status", "available")) == "available" and pd.notna(row.get("price")) and float(row["price"]) > 0
            snaps.setdefault(utc(row["timestamp"]), {})[str(row["ticker"])] = float(row["price"]) if ok else None
    return snaps


def find_decision(obj):
    if isinstance(obj, dict):
        if "details" in obj and "action" in obj:
            return obj
        for v in obj.values():
            d = find_decision(v)
            if d is not None:
                return d
    return None


def load_decisions(folder):
    out = {}
    for v in VARIANTS:
        for f in sorted(glob.glob(str(ROOT / folder / v / "*.json"))):
            obj = json.loads(pathlib.Path(f).read_text())
            dec = find_decision(obj)
            if dec is None:
                continue
            keys = [obj.get(k) for k in ("round_id", "release_id", "timestamp", "release")] if isinstance(obj, dict) else []
            keys += [dec.get(k) for k in ("round_id", "release_id", "timestamp")]
            rid = rid_of(*keys, pathlib.Path(f).stem)
            if rid:
                out.setdefault(v, {})[rid] = dec
    return out


# ---------------------------------------------------------------- decision helpers
def pair_return(u, s1, s2, action):
    if action == "F" or u is None:
        return 0.0
    r = 0.5 * (u[s1] - u[s2])
    return r if action == "LS" else -r


def rank_pair(scores, pool):
    order = sorted(pool, key=lambda t: (-scores[t], TICKERS.index(t)))
    return order[0], order[-1], scores[order[0]] - scores[order[-1]]


def gated(scores, pool):
    if len(pool) < MIN_ELIG:
        return "NVDA", "GOOG", "F"
    i, j, gap = rank_pair(scores, pool)
    return (i, j, "LS") if gap >= MIN_GAP else (i, j, "F")


# ---------------------------------------------------------------- main
def main():
    global ROOT
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT),
                    help="archive root (FinProbeBench/); relative --schedule/--decisions/--rounds-csv paths resolve here")
    ap.add_argument("--data-root", default=None,
                    help="directory holding data/raw/<release>/price.parquet (default: --root)")
    ap.add_argument("--results-root", default=None,
                    help="directory against which relative --out/--macros resolve (default: --root)")
    ap.add_argument("--schedule", nargs="*", default=[])
    ap.add_argument("--prices", default="data/raw/**/price.parquet")
    ap.add_argument("--decisions", default="logs/decisions")
    ap.add_argument("--rounds-csv", default="results/agent_rounds.csv")
    ap.add_argument("--out", default="results/camera_ready_stats.json")
    ap.add_argument("--macros", default="results/camera_ready_macros.tex")
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    ROOT = pathlib.Path(a.root).resolve()
    data_root = pathlib.Path(a.data_root).resolve() if a.data_root else ROOT
    out_root = pathlib.Path(a.results_root).resolve() if a.results_root else ROOT

    rc = ROOT / a.rounds_csv
    rounds_csv = pd.read_csv(rc) if rc.exists() else None
    sched, sched_files = load_schedule(a.schedule, rounds_csv)
    snaps = load_prices(a.prices, data_root)
    dec = load_decisions(a.decisions)
    issues = []
    if len(sched) != PAPER["n_rounds"]:
        issues.append(f"schedule has {len(sched)} October rounds, expected {PAPER['n_rounds']} (files tried: {sched_files[:6]})")
    for v in VARIANTS:
        miss = [r["round_id"] for r in sched if r["round_id"] not in dec.get(v, {})]
        if miss:
            issues.append(f"{v}: no decision record for {len(miss)} rounds, e.g. {miss[:3]}")

    # interval returns u_k on the common intervals
    U, common = {}, []
    for r in sched:
        e, x = snaps.get(r["entry"]), snaps.get(r["exit"])
        if not e or not x:
            continue
        u = {k: (x[k] / e[k] - 1) if e.get(k) and x.get(k) else None for k in TICKERS}
        U[r["round_id"]] = u
        common.append(r)
    if len(common) != PAPER["n_common"]:
        issues.append(f"{len(common)} common intervals, expected {PAPER['n_common']}")
    rids = [r["round_id"] for r in common]

    # replayed returns per variant, checked against the paper and agent_rounds.csv
    R, check = {}, {}
    for v in VARIANTS:
        R[v] = np.array([pair_return(U[q], dec[v][q]["stock1"], dec[v][q]["stock2"], dec[v][q]["action"]) if q in dec.get(v, {}) else 0.0 for q in rids])
        active = int(sum(1 for q in rids if q in dec.get(v, {}) and dec[v][q]["action"] != "F"))
        check[v] = {"cr_pct": pct(compound(R[v])), "active": active}
        if abs(check[v]["cr_pct"] - PAPER["cr"][v]) > 0.006 or active != PAPER["active"][v]:
            issues.append(f"{v}: CR {check[v]['cr_pct']} / active {active}, paper {PAPER['cr'][v]} / {PAPER['active'][v]}")
    if rounds_csv is not None and {"method", "round_id", "stock1", "stock2", "action"} <= set(rounds_csv.columns):
        bad = 0
        for row in rounds_csv.to_dict("records"):
            q, v = rid_of(row["round_id"]), row["method"]
            d = dec.get(v, {}).get(q)
            if d is not None and (d["stock1"], d["stock2"], d["action"]) != (row["stock1"], row["stock2"], row["action"]):
                bad += 1
        check["agent_rounds_csv_mismatches"] = bad
        if bad:
            issues.append(f"{bad} decision records differ from results/agent_rounds.csv")

    # ------------------------------------------------ (1) record-level sign agreement
    nv, av, nm, am = [], [], [], []
    for q in rids:
        u = U[q]
        valid = [k for k in TICKERS if u[k] is not None]
        mean = float(np.mean([u[k] for k in valid]))
        a1 = b1 = a2 = b2 = 0
        for k in valid:
            det = dec["full"][q]["details"][k]
            v_, m_ = float(det.get("sentiment") or 0), float(det.get("momentum") or 0)
            if v_ == 0:
                continue
            rel = sign(u[k] - mean)
            b1 += 1
            a1 += sign(v_) == rel
            if m_ != 0:
                b2 += 1
                a2 += sign(m_) == rel
        nv.append(b1); av.append(a1); nm.append(b2); am.append(a2)
    agree = {"news": boot_rate(av, nv), "momentum": boot_rate(am, nm),
             "definition": "full-variant records on the common intervals with nonzero (usable) sentiment; agreement = sign matches the sign of the stock's return minus the cross-sectional mean of the valid stocks; momentum on the subset with nonzero momentum; units = rounds"}
    for key, n_, r_ in (("news", "news_records", "news_agree"), ("momentum", "mom_records", "mom_agree")):
        if agree[key]["records"] != PAPER[n_] or abs(agree[key]["rate_pct"] - PAPER[r_]) > 0.05:
            issues.append(f"agreement {key}: {agree[key]['records']} records at {agree[key]['rate_pct']}%, paper {PAPER[n_]} at {PAPER[r_]}%")

    # ------------------------------------------------ (2) momentum-routed returns
    mom_trades = np.array([R["no_news"][i] for i, q in enumerate(rids) if dec["no_news"][q]["action"] != "F"])
    momentum = {
        "per_trade_t_test": t_test(mom_trades),
        "per_trade_mean_bootstrap": boot_mean(mom_trades),
        "cr_bootstrap": boot_cr(R["no_news"]),
        "cr_minus_news_led": boot_cr(R["no_news"], R["full"]),
        "cr_minus_ungated": boot_cr(R["no_news"], R["no_risk"]),
        "note": "one trade per round, so the round (cluster) bootstrap equals the iid trade bootstrap; block schemes resample consecutive intervals",
    }

    # ------------------------------------------------ (3) gate isolation
    def pool_of(q):
        return [k for k in TICKERS if dec["full"][q]["details"][k].get("eligible") and U[q][k] is not None]

    def comp(q, k):
        d = dec["full"][q]["details"][k]
        news = float(d.get("sentiment") or 0) * float(d.get("confidence") or 0)
        return news, float(d.get("momentum") or 0)

    # (3a) news term set to zero, news-led pool and gates re-applied
    zero = {}
    for label, w in (("weight_0.3", MOM_W), ("weight_1", 1.0)):
        rr, act, lost, gained = [], 0, 0, 0
        for q in rids:
            pool = pool_of(q)
            sc = {k: w * comp(q, k)[1] for k in pool}
            i, j, action = gated(sc, pool)
            rr.append(pair_return(U[q], i, j, action))
            act += action != "F"
            full_on = dec["full"][q]["action"] != "F"
            lost += full_on and action == "F"
            gained += (not full_on) and action != "F"
        zero[label] = {"cr_pct": pct(compound(rr)), "active": act,
                       "news_led_active_now_flat": lost, "news_led_flat_now_active": gained}
    zero["matches_paper"] = [k for k in ("weight_0.3", "weight_1") if abs(zero[k]["cr_pct"] - PAPER["news_zero_cr"]) <= 0.006]
    if not zero["matches_paper"]:
        issues.append(f"news-zero diagnostic does not reproduce {PAPER['news_zero_cr']}%: {zero}")

    # (3b) fixed eligible pool and fixed trade mask of the news-led agent; only the score differs
    mask = [q for q in rids if dec["full"][q]["action"] != "F"]
    fixed, series, same_pair = {}, {}, {}
    for label in ("news_only", "momentum_only", "fused"):
        rr = []
        for q in rids:
            if q not in mask:
                rr.append(0.0)
                continue
            pool = pool_of(q)
            n_, m_ = zip(*(comp(q, k) for k in pool))
            sc = dict(zip(pool, {"news_only": n_, "momentum_only": m_,
                                 "fused": [NEWS_W * x + MOM_W * y for x, y in zip(n_, m_)]}[label]))
            i, j, _ = rank_pair(sc, pool)
            rr.append(pair_return(U[q], i, j, "LS"))
            same_pair[label] = same_pair.get(label, 0) + ((i, j) == (dec["full"][q]["stock1"], dec["full"][q]["stock2"]))
        series[label] = np.array(rr)
        on = series[label][[rids.index(q) for q in mask]]
        fixed[label] = {"cr_pct": pct(compound(rr)), "wins": int((on > 0).sum()), "trades": len(mask),
                        "same_pair_as_news_led": same_pair[label]}
    if same_pair["fused"] != len(mask):
        issues.append(f"fused score reproduces {same_pair['fused']} of {len(mask)} news-led pairs")
    on_idx = [rids.index(q) for q in mask]
    fixed["fused_minus_momentum_only"] = {"cr": boot_cr(series["fused"][on_idx], series["momentum_only"][on_idx]),
                                          "mean": boot_mean(series["fused"][on_idx] - series["momentum_only"][on_idx])}
    fixed["fused_minus_news_only"] = {"cr": boot_cr(series["fused"][on_idx], series["news_only"][on_idx]),
                                      "mean": boot_mean(series["fused"][on_idx] - series["news_only"][on_idx])}
    fixed["definition"] = "news-led traded intervals and news-led eligible stocks held fixed; long the top and short the bottom of each score, ties by universe order; no gate re-applied"

    # (3c) live initialisation applied to the replay: flat at each trading day's first release
    first = {}
    for r in common:
        day = r["release"].astimezone(NY).date()
        first.setdefault(day, r["round_id"])
    firsts = set(first.values())
    rr = [0.0 if q in firsts else R["no_news"][i] for i, q in enumerate(rids)]
    live_init = {"first_release_intervals": len(firsts),
                 "momentum_routed_active_on_them": int(sum(dec["no_news"][q]["action"] != "F" for q in firsts)),
                 "cr_on_them_pct": pct(compound([R["no_news"][rids.index(q)] for q in firsts])),
                 "cr_flat_on_them_pct": pct(compound(rr)),
                 "active_flat_on_them": int(sum(dec["no_news"][q]["action"] != "F" for q in rids if q not in firsts))}

    out = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seed": SEED, "bootstrap_replicates": REPS, "block_lengths": list(BLOCKS),
        "inputs": {"schedule_files": [str(pathlib.Path(p).relative_to(ROOT)) if str(p).startswith(str(ROOT)) else str(p) for p in sched_files][:10], "prices": a.prices, "decisions": a.decisions,
                   "common_intervals": rids},
        "reproduction_check": check, "issues": issues,
        "sign_agreement": agree, "momentum_routed": momentum,
        "news_zero_diagnostic": zero, "fixed_pool_fixed_mask": fixed, "live_initialisation_on_replay": live_init,
    }
    (out_root / a.out).write_text(json.dumps(out, indent=2))

    def ci(d, key="cluster_iid", f=lambda x: x):
        lo, hi = d[key]["ci95_pct"]
        return f"[{f(lo)}, {f(hi)}]"

    def p(x):
        return "<0.001" if x < 0.001 else f"{x:.2f}" if x >= 0.01 else f"{x:.3f}"

    t = momentum["per_trade_t_test"]
    mac = {
        "crReps": "20{,}000", "crSeed": str(SEED),
        "crAgreeNews": f"{agree['news']['rate_pct']:.1f}", "crAgreeNewsCI": ci(agree["news"]),
        "crAgreeNewsP": p(agree["news"]["cluster_iid"]["p_vs_half"]),
        "crAgreeNewsBlockCI": ci(agree["news"], "block3"),
        "crAgreeMom": f"{agree['momentum']['rate_pct']:.1f}", "crAgreeMomCI": ci(agree["momentum"]),
        "crAgreeMomP": p(agree["momentum"]["cluster_iid"]["p_vs_half"]),
        "crAgreeMomBlockCI": ci(agree["momentum"], "block3"),
        "crAgreeNewsBlockFiveCI": ci(agree["news"], "block5"),
        "crAgreeNewsBlockFiveP": p(agree["news"]["block5"]["p_vs_half"]),
        "crAgreeMomBlockFiveCI": ci(agree["momentum"], "block5"),
        "crMomMean": f"{t['mean_pct']:.3f}", "crMomT": f"{t['t']:.2f}", "crMomTP": p(t["p_two_sided"]),
        "crMomMeanCI": ci(momentum["per_trade_mean_bootstrap"], "block3"),
        "crMomCRCI": ci(momentum["cr_bootstrap"], "block3"),
        "crMomMinusFull": f"{momentum['cr_minus_news_led']['value_pct']:.2f}",
        "crMomMinusFullCI": ci(momentum["cr_minus_news_led"], "block3"),
        "crMomMinusFullP": p(momentum["cr_minus_news_led"]["block3"]["p_vs_zero"]),
        "crZeroCR": f"{zero['weight_0.3']['cr_pct']:.2f}", "crZeroActive": str(zero["weight_0.3"]["active"]),
        "crZeroLost": str(zero["weight_0.3"]["news_led_active_now_flat"]),
        "crZeroGained": str(zero["weight_0.3"]["news_led_flat_now_active"]),
        "crFixNews": f"{fixed['news_only']['cr_pct']:.2f}", "crFixMom": f"{fixed['momentum_only']['cr_pct']:.2f}",
        "crFixFused": f"{fixed['fused']['cr_pct']:.2f}",
        "crFixFusedMinusMom": f"{fixed['fused_minus_momentum_only']['cr']['value_pct']:.2f}",
        "crFixFusedMinusMomCI": ci(fixed["fused_minus_momentum_only"]["cr"], "block3"),
        "crFixFusedMinusNews": f"{fixed['fused_minus_news_only']['cr']['value_pct']:.2f}",
        "crFixFusedMinusNewsCI": ci(fixed["fused_minus_news_only"]["cr"], "block3"),
        "crFixMomSame": str(fixed["momentum_only"]["same_pair_as_news_led"]),
        "crFixNewsSame": str(fixed["news_only"]["same_pair_as_news_led"]),
        "crFirstN": str(live_init["first_release_intervals"]), "crFirstCR": f"{live_init['cr_on_them_pct']:.2f}",
        "crFirstActive": str(live_init["momentum_routed_active_on_them"]),
        "crLiveInitCR": f"{live_init['cr_flat_on_them_pct']:.2f}", "crLiveInitActive": str(live_init["active_flat_on_them"]),
    }
    neg = lambda s: s.replace("-", "$-$") if s.startswith("-") or "[-" in s or ", -" in s else s
    lines = ["% generated by src/camera_ready_stats.py -- paste over the placeholder block in main.tex"]
    lines += [f"\\newcommand{{\\{k}}}{{{neg(v)}}}" for k, v in mac.items()]
    (out_root / a.macros).write_text("\n".join(lines) + "\n")

    print(json.dumps({"reproduction_check": check, "issues": issues, "macros": mac}, indent=2))
    if issues and a.strict:
        sys.exit(1)


if __name__ == "__main__":
    main()
