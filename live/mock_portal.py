"""Local stand-in for the receipt portal and the data host, for rehearsing run_phase3.py.

Serves /status, /submissions (one per team per round, token required after the first) and
/data/<folder>/<name>.parquet, which appears only `delay` seconds after each round's release.
"""
import json, pathlib, sys, time, uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SCHED = json.loads(pathlib.Path(sys.argv[1]).read_text())
RAW = pathlib.Path(sys.argv[2])
DELAY = float(sys.argv[3])
PUBLISH = {r["round_id"]: datetime.fromisoformat(r["mock_publish"]) for r in SCHED}
tokens, accepted = {}, {}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, obj=None, raw=None, ctype="application/json"):
        body = raw if raw is not None else json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.end_headers(); self.wfile.write(body)

    def open_round(self):
        now = datetime.now(timezone.utc)
        for r in SCHED:
            if PUBLISH[r["round_id"]].timestamp() + DELAY <= now.timestamp() < datetime.fromisoformat(r["action_due"]).timestamp():
                return r
        return None

    def do_GET(self):
        if self.path.startswith("/status"):
            r = self.open_round()
            return self.send(200, {"round_id": r and r["round_id"], "deadline": r and r["action_due"], "mode": "live", "session_id": "live"})
        if self.path.startswith("/data/"):
            folder, name = self.path.split("/")[2:4]
            rid = folder[:-3].replace("_", " ").replace("-", ":")  # 2026-10-23_09-30_NY -> compare below
            for r in SCHED:
                if r["round_id"].replace(":", "-") + "_NY" == folder:
                    if time.time() < PUBLISH[r["round_id"]].timestamp() + DELAY:
                        return self.send(404, {"error": "not yet"})
                    p = RAW / folder[:-3] / name
                    return self.send(200, raw=p.read_bytes(), ctype="application/octet-stream")
            return self.send(404, {"error": "unknown"})
        self.send(404, {})

    def do_POST(self):
        b = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        r = self.open_round()
        if not r or b["round_id"] != r["round_id"]:
            return self.send(409, {"accepted": False, "detail": "round not open"})
        team = b["team_name"].lower()
        if team in tokens and self.headers.get("X-Team-Token") != tokens[team]:
            return self.send(403, {"accepted": False, "detail": "team token required"})
        if (team, b["round_id"]) in accepted:
            return self.send(409, {"accepted": False, "detail": "already submitted"})
        rid = "rcpt-" + uuid.uuid4().hex[:8]
        accepted[(team, b["round_id"])] = b
        out = {"accepted": True, "receipt_id": rid, "accepted_at": datetime.now(timezone.utc).isoformat()}
        if team not in tokens:
            tokens[team] = out["team_token"] = uuid.uuid4().hex
        print("MOCK ACCEPTED", b, flush=True)
        self.send(200, out)


ThreadingHTTPServer(("127.0.0.1", 8765), H).serve_forever()
