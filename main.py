"""Forecast GTA VI launch-day Twitch viewers, hour by hour, from past launches.

Idea: no single past launch looks like GTA VI, but the *shape* of a big
console launch day is shared. Every comparable launch in the case file
records one hourly viewers series for its own release day. For each
forecast hour h we look at how that hour compared with the same launch's
first hour, in log space, across all usable comparables, and take the
middle of that distribution as our median and its spread as our width:

    log viewers(h) - log viewers(1)  ~  median_h  +/-  spread_h

    q_tau(h) = p1 * exp(median_h + z_tau * spread_h)

where p1 is this case's hour-1 print and z_tau is the standard normal
quantile at the scored level. The median is robust to the odd launch
whose hour 1 was a freak spike or a dead hour, and the interquartile
range gives an honest, data-driven width per hour instead of a guessed
random-walk sigma.

Which comparables count as usable:
  * their unlock note must carry "Tier: comparable" (early-access
    contaminated launches and weak / free-to-play ones are left out,
    because their release-day shape is not a clean launch day);
  * they must have a full 24-hour release day in the file;
  * their hour-1 viewers must be at least 5000 -- launches whose first
    hour was nearly empty (a few hundred viewers) have ratios in the
    hundreds and would swamp the shape of a launch like this one, whose
    first hour already holds the UK midnight crowd;
  * the target game itself is never in its own pool.

If the pool is too thin for an hour, that hour falls back to the plain
persistence forecast (stay at hour 1, widening like a random walk),
so the program always writes a valid file.

Only the standard library is used. No network, no randomness, no clock:
the same case file always produces the same bytes.
"""

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]

# Smallest hour-1 crowd a comparable must have to join the pool.
MIN_FIRST_HOUR = 5000
# An hour needs at least this many log-ratios before we trust its median.
MIN_RATIOS = 4
# Keep the fitted centre inside a sane band even if the data is wild.
MEDIAN_LOW, MEDIAN_HIGH = -2.0, 3.5
# Floor / cap on the per-hour log spread (the IQR-implied sigma).
SPREAD_LOW, SPREAD_HIGH = 0.25, 1.2
# Fallback random-walk sigma, used only when the pool is too thin.
FALLBACK_SIGMA = 0.15


def _parse_time(text):
    """ISO-8601 UTC timestamp -> aware datetime, or None if unreadable."""
    if not isinstance(text, str):
        return None
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def _tier_of(comparable):
    """The tier tag inside a comparable's unlock note, e.g. 'comparable'."""
    note = comparable.get("unlock") or ""
    marker = "Tier:"
    at = note.find(marker)
    if at < 0:
        return ""
    rest = note[at + len(marker):].strip()
    return rest.split(".")[0].split(",")[0].strip().lower()


def _release_day_hours(comparable):
    """{hour 1..24: viewers} for the comparable's release UTC day.

    Returns an empty dict when the day cannot be lined up cleanly.
    """
    start = _parse_time(comparable.get("day_start"))
    if start is None:
        return {}
    day = {}
    for row in comparable.get("hourly") or []:
        moment = _parse_time(row.get("from"))
        viewers = row.get("viewers")
        if moment is None or not isinstance(viewers, (int, float)):
            continue
        offset = (moment - start).total_seconds() / 3600.0
        if offset == int(offset) and 0 <= offset < 24 and viewers > 0:
            day[int(offset) + 1] = float(viewers)
    return day


def _median(values):
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _quartile(values, which):
    """Nearest-rank quartile (which = 0.25 or 0.75) of a sorted list."""
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(which * len(ordered))))
    return ordered[index]


def fit_shape(case):
    """Per-hour (median log-ratio, spread) fitted from the case's pool.

    Hours with too little data get None and are handled by the fallback.
    """
    target_name = (case.get("game") or {}).get("name") or ""
    ratios = {hour: [] for hour in range(2, 25)}
    for comparable in case.get("comparables") or []:
        if _tier_of(comparable) != "comparable":
            continue
        if comparable.get("name") == target_name:
            continue
        day = _release_day_hours(comparable)
        if len(day) < 24:
            continue
        first = day.get(1)
        if not first or first < MIN_FIRST_HOUR:
            continue
        for hour in range(2, 25):
            viewers = day.get(hour)
            if viewers:
                ratios[hour].append(math.log(viewers / first))
    shape = {}
    for hour in range(2, 25):
        sample = ratios[hour]
        if len(sample) < MIN_RATIOS:
            shape[hour] = None
            continue
        centre = _median(sample)
        centre = max(MEDIAN_LOW, min(MEDIAN_HIGH, centre))
        width = (_quartile(sample, 0.75) - _quartile(sample, 0.25)) / 1.349
        width = max(SPREAD_LOW, min(SPREAD_HIGH, width))
        shape[hour] = (centre, width)
    return shape


def _round2(value):
    """Round to 2 decimals, half up, returning an int for whole numbers."""
    scaled = value * 100.0
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    rounded = whole / 100.0
    return int(rounded) if float(rounded).is_integer() else rounded


def _quantiles(p1, hour, shape):
    """The five forecast quantiles for one hour, non-decreasing, in range."""
    fitted = shape.get(hour)
    if fitted is None:
        centre, width = 0.0, FALLBACK_SIGMA * math.sqrt(hour - 1)
    else:
        centre, width = fitted
    out = []
    previous = 0.0
    for z in Z:
        value = p1 * math.exp(centre + z * width)
        value = max(1.0, min(1_000_000_000.0, value))
        value = _round2(value)
        if value < previous:
            value = previous
        out.append(value)
        previous = value
    return out


def forecast_case(case, name):
    if list(case.get("levels") or []) != LEVELS:
        raise ValueError(f"{name} asks for levels {case.get('levels')}, not {LEVELS}")
    known = case.get("known") or []
    first = next((row for row in known if row.get("hour") == 1), None)
    if first is None:
        raise ValueError(f"{name} has no hour-1 print")
    p1 = max(1.0, float(first.get("viewers") or 1))
    shape = fit_shape(case)
    rows = case.get("forecast") or []
    if not rows:
        # A case that names no hours still gets the full day 2..24.
        rows = [{"hour": hour} for hour in range(2, 25)]
    hours = [
        {"hour": row["hour"], "q": _quantiles(p1, row["hour"], shape)}
        for row in rows
    ]
    hours.sort(key=lambda row: row["hour"])
    return {"hours": hours}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        text = json.dumps(forecast, separators=(",", ":")) + "\n"
        (OUTPUT_DIR / f"{path.stem}.out").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
