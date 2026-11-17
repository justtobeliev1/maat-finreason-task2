"""Check: vendor decide() reproduces every archived momentum-routed (no_news) October decision."""
import csv, json, pathlib, sys
import pandas as pd
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "vendor"))
from agent import decide
root = HERE.parent  # repository root
cfg = json.loads((HERE / "vendor/preregistration.json").read_text())
want = {r["round_id"]: r for r in csv.DictReader(open(root / "results/agent_rounds.csv")) if r["method"] == "no_news"}
prev, bad = {}, 0
for d in sorted((root / "data/raw").iterdir()):
    f = pd.read_parquet(d / "price.parquet")
    prices = {r["ticker"]: (float(r["price"]) if r["status"] == "available" else None) for r in f.to_dict("records")}
    rid = d.name[:13] + ":" + d.name[14:]
    a = decide(prices, prev, [], {}, cfg, variant="no_news")
    w = want[rid]
    same = (a["stock1"], a["stock2"], a["action"]) == (w["stock1"], w["stock2"], w["action"])
    bad += not same
    if not same: print("MISMATCH", rid, a["stock1"], a["stock2"], a["action"], "vs", w["stock1"], w["stock2"], w["action"])
    prev = prices
print(f"{len(want)} archived rounds, {bad} mismatches")
