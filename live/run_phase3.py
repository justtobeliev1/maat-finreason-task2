"""Unattended Phase III runner (2 November 2026): fetch each release, decide, submit, keep receipts.

Deployed rule: momentum-routed (variant "no_news"), the declared live policy. The decision comes from
the frozen agent.decide() in vendor/agent.py with the frozen vendor/preregistration.json; momentum uses
only prices from earlier releases of this session, so round 1 is F.

The portal is driven exactly as its own page does: GET /status, then POST /submissions with the team
token returned by the first accepted submission (kept in a 0600 file). One submission per round; a
round with a receipt is never submitted again.

  .venv/bin/python run_phase3.py              # live, all six rounds
  .venv/bin/python run_phase3.py --dry-run    # everything except the POST
"""

import argparse
import hashlib
import io
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "vendor"))
from agent import TICKERS, decide  # noqa: E402

STATE_URL = "https://carolyn-jiang.github.io/Market-Neutral-Hedging-live-trading/phrase3-live-state.json"
PORTAL = "https://finreason-task2-receipts.carolyn1010011010.workers.dev"
DATA = (
    "https://hf-mirror.com/datasets/CarolynJiang/Market-Neutral-Hedging-live-trading/resolve/main/data/",
    "https://huggingface.co/datasets/CarolynJiang/Market-Neutral-Hedging-live-trading/resolve/main/data/",
)
PHASE_ID = "phrase-iii-2026-11-02"
TEAM = "FinProbeBench"
TOKEN_FILE = pathlib.Path(os.environ.get("MAAT_PORTAL_TOKEN_FILE", str(HERE / ".portal_token.json")))  # released copy; see README
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36"
BJ = timezone(timedelta(hours=8))
NODES = ["09:30", "10:30", "11:30", "12:30", "13:30", "14:30", "15:30", "16:00"]


def builtin_schedule():
    """Same construction as the official app.js, used only if the state file cannot be read."""
    ts = [f"2026-11-02T{t}:00-05:00" for t in NODES]
    out = []
    for i in range(6):
        out.append({
            "round": i + 1,
            "round_id": "2026-11-02_" + NODES[i],
            "timestamp": ts[i],
            "action_due": (datetime.fromisoformat(ts[i + 1]) - timedelta(minutes=5)).isoformat(),
            "entry_at": ts[i + 1],
            "exit_at": ts[i + 2],
        })
    return out


class Runner:
    def __init__(self, args):
        self.args = args
        self.out = pathlib.Path(args.out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.cfg = json.loads((HERE / "vendor/preregistration.json").read_text())
        self.portal = args.portal.rstrip("/")
        self.data = tuple(args.data) if args.data else DATA
        self.token_file = pathlib.Path(args.token_file)

    # ------------------------------------------------------------------ utilities
    def log(self, msg, **kw):
        now = datetime.now(BJ).strftime("%m-%d %H:%M:%S")
        line = json.dumps({"bj": now, "msg": msg, **kw}, ensure_ascii=False, default=str)
        print(line, flush=True)
        with open(self.out / "run.log", "a") as f:
            f.write(line + "\n")

    def now(self):
        return datetime.now(timezone.utc)

    def http(self, url, data=None, headers=None, timeout=30):
        h = {"User-Agent": UA, "Cache-Control": "no-store"}
        h.update(headers or {})
        req = urllib.request.Request(url, data=data, headers=h, method="POST" if data is not None else "GET")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()

    def sleep_until(self, t, step=20):
        while self.now() < t:
            time.sleep(min(step, max(1, (t - self.now()).total_seconds())))

    # ------------------------------------------------------------------ schedule
    def schedule(self):
        if self.args.schedule_file:
            return json.loads(pathlib.Path(self.args.schedule_file).read_text())
        try:
            _, body = self.http(STATE_URL + "?t=" + str(int(time.time())))
            state = json.loads(body)
            (self.out / "phrase3-live-state.json").write_bytes(body)
            if state.get("phase_id") != PHASE_ID or state.get("total_rounds") != 6:
                raise ValueError("unexpected phase state")
            sched = state["release_schedule"]
            if [r["round_id"] for r in sched] != [r["round_id"] for r in builtin_schedule()]:
                raise ValueError("schedule differs from the published construction")
            return sched
        except Exception as exc:  # the published construction is fixed; fall back to it
            self.log("state file unavailable, using built-in schedule", error=str(exc))
            return builtin_schedule()

    # ------------------------------------------------------------------ data
    def folder(self, rid):
        return rid.replace(":", "-") + "_NY"

    def fetch(self, rid, name):
        for base in self.data:
            url = f"{base}{self.folder(rid)}/{name}.parquet"
            try:
                status, body = self.http(url, timeout=60)
                if status == 200 and body[:4] == b"PAR1":
                    return body, url
            except urllib.error.HTTPError as exc:
                if exc.code not in (404, 401):
                    self.log("data fetch error", url=url, code=exc.code)
            except Exception as exc:
                self.log("data fetch error", url=url, error=str(exc))
        return None, None

    def load_prices(self, body, release):
        frame = pd.read_parquet(io.BytesIO(body))
        if frame["ticker"].duplicated().any() or set(frame["ticker"]) != set(TICKERS):
            raise ValueError("price file must have the ten tickers once each")
        prices = {}
        for row in frame.to_dict("records"):
            if datetime.fromisoformat(str(row["timestamp"])) != datetime.fromisoformat(release["timestamp"]):
                raise ValueError("price timestamp differs from the release")
            ok = row.get("status") == "available" and pd.notna(row["price"]) and float(row["price"]) > 0
            prices[str(row["ticker"])] = float(row["price"]) if ok else None
        return prices

    def wait_for_data(self, release, deadline):
        rid = release["round_id"]
        rdir = self.out / self.folder(rid)
        rdir.mkdir(exist_ok=True)
        cached = rdir / "price.parquet"
        if cached.exists():
            return self.load_prices(cached.read_bytes(), release)
        while self.now() < deadline:
            body, url = self.fetch(rid, "price")
            if body:
                prices = self.load_prices(body, release)
                cached.write_bytes(body)
                news, nurl = self.fetch(rid, "news")
                if news:
                    (rdir / "news.parquet").write_bytes(news)
                (rdir / "fetch.json").write_text(json.dumps({
                    "price_url": url, "price_sha256": hashlib.sha256(body).hexdigest(),
                    "news_url": nurl, "news_sha256": hashlib.sha256(news).hexdigest() if news else None,
                    "fetched_utc": self.now().isoformat()}, indent=2))
                return prices
            time.sleep(self.args.poll)
        return None

    # ------------------------------------------------------------------ portal
    def token(self, namespace):
        if self.token_file.exists():
            return json.loads(self.token_file.read_text()).get(f"{namespace}.{TEAM.lower()}")
        return None

    def save_token(self, namespace, token):
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        data = json.loads(self.token_file.read_text()) if self.token_file.exists() else {}
        data[f"{namespace}.{TEAM.lower()}"] = token
        self.token_file.write_text(json.dumps(data, indent=2))
        os.chmod(self.token_file, 0o600)

    def status(self):
        _, body = self.http(self.portal + "/status?t=" + str(int(time.time())))
        return json.loads(body)

    def wait_for_open_round(self, rid, deadline):
        while self.now() < deadline:
            try:
                s = self.status()
                if s.get("round_id") and "".join(filter(str.isdigit, s["round_id"])) == "".join(filter(str.isdigit, rid)):
                    return s
                self.log("portal not yet open for this round", want=rid, status=s)
            except Exception as exc:
                self.log("portal status error", error=str(exc))
            time.sleep(self.args.poll)
        return None

    def submit(self, release, action, deadline):
        rid = release["round_id"]
        rdir = self.out / self.folder(rid)
        receipt = rdir / "receipt.json"
        if receipt.exists():
            self.log("receipt already present, not submitting again", round=rid)
            return
        s = self.wait_for_open_round(rid, deadline)
        if s is None:
            self.log("PORTAL NEVER OPENED THIS ROUND; nothing submitted", round=rid)
            return
        if s.get("mode") != "live" and not self.args.allow_rehearsal:
            self.log("portal is not in live mode; nothing submitted", status=s)
            return
        namespace = s.get("session_id") or "live"
        body = {"team_name": TEAM, "stock1": action["stock1"], "stock2": action["stock2"],
                "action": action["action"], "round_id": s["round_id"]}  # as the portal page sends it
        if self.args.dry_run:
            self.log("DRY RUN: would POST", body=body, has_token=bool(self.token(namespace)))
            return
        headers = {"Content-Type": "application/json", "Origin": self.portal, "Referer": self.portal + "/"}
        tok = self.token(namespace)
        if tok:
            headers["X-Team-Token"] = tok
        while self.now() < deadline:
            try:
                status, raw = self.http(self.portal + "/submissions", data=json.dumps(body).encode(), headers=headers)
                resp = json.loads(raw)
            except urllib.error.HTTPError as exc:
                raw = exc.read()
                self.log("SUBMISSION REJECTED", round=rid, code=exc.code, body=raw.decode(errors="replace"))
                (rdir / "rejection.json").write_bytes(raw)
                return
            except Exception as exc:  # network: the portal accepts one per round, so a retry cannot double-submit
                self.log("submission network error, retrying", error=str(exc))
                time.sleep(15)
                continue
            if not resp.get("accepted"):
                self.log("SUBMISSION NOT ACCEPTED", round=rid, response=resp)
                (rdir / "rejection.json").write_text(json.dumps(resp, indent=2))
                return
            if resp.get("team_token"):
                self.save_token(namespace, resp.pop("team_token"))
            receipt.write_text(json.dumps({"request": body, "response": resp}, indent=2))
            self.log("ACCEPTED", round=rid, receipt=resp.get("receipt_id"), at=resp.get("accepted_at"), body=body)
            return
        self.log("deadline passed during submission; nothing accepted", round=rid)

    # ------------------------------------------------------------------ main loop
    def run(self):
        sched = self.schedule()
        self.log("schedule", rounds=[(r["round_id"], datetime.fromisoformat(r["action_due"]).astimezone(BJ).strftime("%m-%d %H:%M")) for r in sched])
        previous = {}
        for release in sched:
            rid = release["round_id"]
            if self.args.only and rid not in self.args.only:
                continue
            published = datetime.fromisoformat(release["timestamp"])
            due = datetime.fromisoformat(release["action_due"])
            margin = due - timedelta(seconds=self.args.margin)
            if self.now() > margin:
                self.log("round already past its deadline, skipping", round=rid)
                rdir = self.out / self.folder(rid)
                if (rdir / "price.parquet").exists():
                    previous = self.load_prices((rdir / "price.parquet").read_bytes(), release)
                continue
            self.log("waiting for release", round=rid, release_bj=published.astimezone(BJ).strftime("%H:%M"))
            self.sleep_until(published)
            prices = self.wait_for_data(release, margin)
            if prices is None:
                self.log("NO DATA BEFORE DEADLINE; round left unsubmitted (counts as F)", round=rid)
                previous = {}
                continue
            action = decide(prices, previous, [], {}, self.cfg, variant="no_news")
            action.update(round=release["round"], round_id=rid, policy="momentum-routed (no_news), declared v2")
            rdir = self.out / self.folder(rid)
            (rdir / "decision.json").write_text(json.dumps(action, indent=2))
            self.log("decision", round=rid, stock1=action["stock1"], stock2=action["stock2"],
                     action=action["action"], reason=action["reason"])
            self.submit(release, action, margin)
            previous = prices
        self.log("session finished")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--allow-rehearsal", action="store_true")
    p.add_argument("--only", nargs="*")
    p.add_argument("--out", default=str(HERE / "phase3"))
    p.add_argument("--portal", default=PORTAL)
    p.add_argument("--data", nargs="*")
    p.add_argument("--schedule-file")
    p.add_argument("--token-file", default=str(TOKEN_FILE))
    p.add_argument("--poll", type=float, default=30)
    p.add_argument("--margin", type=float, default=90, help="stop trying this many seconds before the due time")
    Runner(p.parse_args()).run()


if __name__ == "__main__":
    main()
