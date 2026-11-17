"""Generate an immutable local recommendation only. Never submits to the organizer."""

import argparse
import hashlib
import json
import pathlib
import shutil
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from agent import ROOT, annotate, decide
from experiment import read_news
from replay_baselines import load_price_snapshots


def select_session_history(snapshots, current, session_start):
    if current.utcoffset() is None or session_start.utcoffset() is None:
        raise ValueError("Session timestamps must include a timezone")
    if session_start > current:
        raise ValueError("Session starts after the requested release")
    previous = max((t for t in snapshots if session_start <= t < current), default=None)
    return previous, snapshots[previous] if previous else {}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--round-id", required=True)
    p.add_argument(
        "--schedule", type=pathlib.Path, default=ROOT / "sources/live-state-latest.json"
    )
    p.add_argument(
        "--session-start",
        help="Official first release timestamp for this live session (with timezone)",
    )
    args = p.parse_args()
    if not args.schedule.exists():
        raise SystemExit(
            "No current official schedule. Refresh it; never infer a final deadline."
        )
    state = json.loads(args.schedule.read_text())
    schedule = state.get("release_schedule", [])
    matching = [r for r in schedule if r["round_id"] == args.round_id]
    if len(matching) != 1:
        raise SystemExit(
            "Round absent/ambiguous in current official schedule; no recommendation issued."
        )
    release = matching[0]
    now = datetime.now(timezone.utc)
    start = datetime.fromisoformat(release["timestamp"])
    due = datetime.fromisoformat(release["action_due"])
    if not start <= now < due:
        raise SystemExit(
            "Outside the verified decision window; no recommendation issued."
        )
    if not args.session_start:
        raise SystemExit(
            "Explicit --session-start required; do not use stale prices from the October session."
        )
    try:
        session_start = datetime.fromisoformat(args.session_start)
        if session_start.utcoffset() is None or session_start > start:
            raise ValueError("Invalid session start")
        if not any(
            datetime.fromisoformat(r["timestamp"]) == session_start for r in schedule
        ):
            raise ValueError("Session start absent from official schedule")
    except ValueError as exc:
        raise SystemExit(str(exc))
    folder = ROOT / "logs/live" / args.round_id.replace(":", "-")
    folder.mkdir(parents=True, exist_ok=True)
    final = folder / "recommendation.json"
    if final.exists():
        print(final.read_text())
        return
    cfg = json.loads((ROOT / "preregistration.json").read_text())
    expected = (ROOT / "preregistration.sha256").read_text().split()[0]
    if (
        hashlib.sha256((ROOT / "preregistration.json").read_bytes()).hexdigest()
        != expected
    ):
        raise SystemExit("Configuration differs from frozen checksum")
    snapshots = load_price_snapshots(ROOT)
    prices = snapshots.get(start)
    if prices is None:
        raise SystemExit("Current price file not available")
    previous, old = select_session_history(snapshots, start, session_start)
    news = read_news(release)
    source = ROOT / "data/raw" / args.round_id.replace(":", "-")
    files = {}
    for kind in ("price", "news"):
        f = source / (kind + ".parquet")
        files[kind] = hashlib.sha256(f.read_bytes()).hexdigest()
        shutil.copy2(f, folder / f.name)
    error = None
    try:
        anns, digest = annotate(news, cfg, args.round_id)
    except Exception as exc:
        anns, digest = {}, None
        error = {"type": type(exc).__name__, "message": str(exc)}
    action = decide(prices, old, news, anns, cfg)
    if error:
        action.update(action="F", reason="Annotation failed; fail-closed policy.")
    now = datetime.now(timezone.utc)
    if now >= due:
        raise SystemExit(
            "Deadline passed during inference; no valid recommendation issued."
        )
    action.update(
        round_id=args.round_id,
        generated_utc=now.isoformat(),
        deadline_new_york=due.isoformat(),
        deadline_beijing=due.astimezone(ZoneInfo("Asia/Shanghai")).isoformat(),
        input_sha256=files,
        request_sha256=digest,
        annotation_error=error,
        session_start=session_start.isoformat(),
        history_reference_timestamp=previous.isoformat() if previous else None,
        history_age_hours=(start - previous).total_seconds() / 3600
        if previous
        else None,
        momentum_initialization="within_session_previous_release"
        if previous
        else "first_session_observation_zero",
        submission_status="USER_MUST_SUBMIT_MANUALLY",
    )
    with final.open("x") as f:
        json.dump(action, f, indent=2)
    card = f"{cfg['team']} | {action['stock1']} | {action['stock2']} | {action['action']}\n{action['reason']}\nDeadline Beijing: {action['deadline_beijing']}\nUSER MANUAL SUBMISSION REQUIRED\n"
    (folder / "action_card.txt").write_text(card)
    print(card)


if __name__ == "__main__":
    main()
