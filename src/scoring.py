"""Official equal-dollar pair arithmetic; missing active endpoints are never zeroed."""

from __future__ import annotations
import math
from datetime import datetime
from typing import Iterable, Mapping

TICKERS = ("NVDA", "GOOG", "META", "MSFT", "JPM", "AMZN", "AAPL", "AMD", "WMT", "TSLA")


def valid_price(value):
    try:
        return math.isfinite(float(value)) and float(value) > 0
    except (TypeError, ValueError):
        return False


def pair_return(
    stock1: str,
    stock2: str,
    action: str,
    entry: Mapping[str, float],
    exit: Mapping[str, float],
):
    """Return None for an unscorable active trade, and zero for F."""
    if stock1 not in TICKERS or stock2 not in TICKERS or stock1 == stock2:
        raise ValueError("Two distinct eligible tickers are required")
    if action not in ("LS", "SL", "F"):
        raise ValueError("Action must be LS, SL, or F")
    if action == "F":
        return 0.0
    values = (entry.get(stock1), entry.get(stock2), exit.get(stock1), exit.get(stock2))
    if not all(valid_price(x) for x in values):
        return None
    a, b, c, d = map(float, values)
    result = 0.5 * ((c / a - 1.0) - (d / b - 1.0))
    return result if action == "LS" else -result


def endpoint_times(release):
    """Use organizer schedule, never release-to-next-release as the scored interval."""
    published = datetime.fromisoformat(release["timestamp"])
    due = datetime.fromisoformat(release["action_due"])
    entry = datetime.fromisoformat(release["entry_at"])
    exit = datetime.fromisoformat(release["exit_at"])
    if not published < due < entry < exit:
        raise ValueError("Invalid release/deadline/execution ordering")
    return entry, exit


def metrics(returns: Iterable[float | None], actions: Iterable[str] | None = None):
    """Metrics over available settled returns only; disclose excluded rounds separately.

    When gaps occur, CR/MDD describe the observed-interval sequence, not the full
    account trajectory. Win rate counts strictly positive returns; F is not a win.
    """
    returns = list(returns)
    actions = list(actions) if actions is not None else ["LS"] * len(returns)
    if len(actions) != len(returns):
        raise ValueError("Returns/actions lengths differ")
    observed = [(float(r), a) for r, a in zip(returns, actions) if r is not None]
    if any(not math.isfinite(r) or r <= -1 for r, _ in observed):
        raise ValueError("Non-finite return or exhausted equity")
    wealth = peak = 1.0
    mdd = 0.0
    for r, _ in observed:
        wealth *= 1 + r
        peak = max(peak, wealth)
        mdd = max(mdd, 1 - wealth / peak)
    active = [(r, a) for r, a in observed if a != "F"]
    vals = [r for r, _ in observed]
    mean = sum(vals) / len(vals) if vals else None
    sd = (
        (sum((r - mean) ** 2 for r in vals) / (len(vals) - 1)) ** 0.5
        if len(vals) > 1
        else None
    )
    return {
        "cr": wealth - 1 if observed else None,
        "max_drawdown": mdd if observed else None,
        "win_rate_all_settled": sum(r > 0 for r, _ in observed) / len(observed)
        if observed
        else None,
        "win_rate_active": sum(r > 0 for r, _ in active) / len(active)
        if active
        else None,
        "settled_count": len(observed),
        "active_settled_count": len(active),
        "unscorable_count": sum(r is None for r in returns),
        "sharpe_unannualized_ddof1": mean / sd if sd else None,
        "scope": "all_rounds"
        if all(r is not None for r in returns)
        else "observed_intervals_only_gaps_excluded",
    }
