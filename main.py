"""Release-day Twitch CCU forecaster (make.fun: gta6-twitch-ccu-forecast-01).

Model, in one paragraph: a launch day's viewer curve has a fairly stable
*shape* once you divide out its scale. For every past launch bundled in the
case (the comparables), I take the 24 hourly prints of its own release day
and express each hour as a log-ratio to that launch's hour-1 print. The
target launch's hour-1 print is known, so the comparables' log-ratios,
hour by hour, form an empirical predictive distribution for the target's
remaining hours — but not all comparables deserve an equal vote. Each one
is weighted by how closely its *pre-release* trajectory (the twelve hours
before its day began, again as log-ratios to its own hour 1) matches the
target's pre-release trajectory: launches that were gathering viewers in
the same pattern before daybreak tend to unfold alike after it. The
forecast quantile at level tau for hour h is then p1 * exp(weighted
tau-quantile of the comparable log-ratios at h), so the spread is exactly
how much similar real launches actually deviated, per hour — honest
calibration, not fixed padding. One hedge: in the mid-day hours (5–14),
comparable trajectories diverge the most (unlock timing differs), so
there the shape forecast is blended halfway toward the persistence
baseline (flat level, random-walk spread) in log space; the opening dip
(hours 2–4) and the evening climb (15–24) are consistent enough across
launches to trust the shape fully.

The grader runs this file once per case (`python3 -P -s /bot/main.py`,
standard library only, offline). Input/output follow the case contract:
read every *.in in $MAKEFUN_INPUT_DIR (else /input), write one
<id>.out per case to $MAKEFUN_OUTPUT_DIR (else /output), each holding
{"hours": [{"hour": h, "q": [q05, q25, q50, q75, q95]} for h in 2..24]}.
Everything below is plain deterministic arithmetic on sorted lists: two
runs on the same input produce byte-identical output.
"""

import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# The grader's -P leaves this file's directory off sys.path; put it back
# first so sibling modules would import (this entry is a single file, but
# the line keeps the layout standard).
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# Fallback spread (the persistence baseline's), used only if a case ships
# too few usable comparables to pool.
FALLBACK_Z = [-1.645, -0.674, 0.0, 0.674, 1.645]
FALLBACK_SIGMA = 0.15
MIN_COMPARABLES = 5
# Pre-release similarity kernel: bandwidth (in RMS log units) and the
# floor every comparable keeps, so no launch is ever fully ignored.
KERNEL_BANDWIDTH = 0.3
KERNEL_FLOOR = 0.15
# Weight for a comparable whose pre-release curve cannot be compared
# (too few shared hours): a neutral mid value.
DEFAULT_WEIGHT = 0.65
PRE_HOURS = 12
# Mid-day hedge: hours 5..14 blend the shape forecast halfway (in log
# space) toward the persistence baseline; other hours trust it fully.
MID_DAY_BLEND = 0.5
MID_DAY_HOURS = range(5, 15)


def parse_ts(text):
    """Parse an ISO-8601 'Z' timestamp into an aware datetime."""
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def round2(x):
    """Round to 2 decimals, half up; whole numbers come back as ints."""
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if float(value).is_integer() else value


def points_map(rows):
    """Map exact hour timestamps to positive viewer counts from raw rows."""
    pts = {}
    for row in rows or []:
        viewers = row.get("viewers")
        if viewers is None or viewers <= 0:
            continue
        try:
            pts[parse_ts(row["from"])] = float(viewers)
        except (KeyError, TypeError, ValueError):
            continue
    return pts


def pre_curve(pts, start, log_anchor):
    """{hours before start: log-ratio to the hour-1 print}, 1..PRE_HOURS."""
    out = {}
    for t in range(1, PRE_HOURS + 1):
        v = pts.get(start - timedelta(hours=t))
        if v is not None:
            out[t] = math.log(v) - log_anchor
    return out


def weighted_quantile(pairs, tau):
    """tau-quantile of (value, weight) pairs, linear interpolation.

    Walks the samples in value order accumulating weight; the quantile is
    where the accumulated weight crosses tau * total, interpolated
    between the bracketing samples.
    """
    ordered = sorted(pairs)
    total = sum(w for _, w in ordered)
    if total <= 0:
        return ordered[len(ordered) // 2][0]
    target = tau * total
    cum = 0.0
    prev_v, prev_c = ordered[0][0], 0.0
    for v, w in ordered:
        cum += w
        if cum >= target:
            if cum == prev_c:
                return v
            frac = (target - prev_c) / (cum - prev_c)
            return prev_v + (v - prev_v) * frac
        prev_v, prev_c = v, cum
    return ordered[-1][0]


def comparable_data(case):
    """Per comparable: ({hour: log-ratio to its hour 1}, similarity weight).

    The weight compares the comparable's pre-release curve with the
    target's (from the case's history_hourly and known hour 1): a
    Gaussian kernel on the RMS distance over the shared pre-hours, on
    top of a floor. Comparables without a release-day anchor are dropped;
    ones whose pre-curve cannot be compared get a neutral weight.
    """
    first = next((k for k in case.get("known") or [] if k.get("hour") == 1), None)
    p1 = max(1.0, float(first["viewers"])) if first and first.get("viewers") else 1.0
    try:
        start = parse_ts(case["day_start"])
    except (KeyError, TypeError, ValueError):
        return p1, []
    target_pre = pre_curve(points_map(case.get("history_hourly")), start, math.log(p1))
    out = []
    for comp in case.get("comparables") or []:
        try:
            cs = parse_ts(comp["day_start"])
        except (KeyError, TypeError, ValueError):
            continue
        pts = points_map(comp.get("hourly"))
        anchor = pts.get(cs)
        if anchor is None:
            continue
        log_anchor = math.log(anchor)
        comp_pre = pre_curve(pts, cs, log_anchor)
        shared = [t for t in comp_pre if t in target_pre]
        if len(shared) >= 4 and target_pre:
            dist = math.sqrt(
                sum((comp_pre[t] - target_pre[t]) ** 2 for t in shared) / len(shared)
            )
            weight = KERNEL_FLOOR + math.exp(
                -(dist * dist) / (2 * KERNEL_BANDWIDTH * KERNEL_BANDWIDTH)
            )
        else:
            weight = DEFAULT_WEIGHT
        ratios = {}
        for h in range(2, 25):
            v = pts.get(cs + timedelta(hours=h - 1))
            if v is not None:
                ratios[h] = math.log(v) - log_anchor
        if ratios:
            out.append((ratios, weight))
    return p1, out


def forecast_case(case):
    p1, comps = comparable_data(case)
    hours_out = []
    for row in case["forecast"]:
        h = int(row["hour"])
        pairs = [(ratios[h], w) for ratios, w in comps if h in ratios]
        alpha = MID_DAY_BLEND if h in MID_DAY_HOURS else 1.0
        qs = []
        for i, tau in enumerate(LEVELS):
            base_log = FALLBACK_Z[i] * FALLBACK_SIGMA * math.sqrt(h - 1)
            if len(pairs) >= MIN_COMPARABLES:
                shape_log = weighted_quantile(pairs, tau)
            else:
                shape_log = base_log
            log_q = (1.0 - alpha) * base_log + alpha * shape_log
            qs.append(round2(p1 * math.exp(log_q)))
        # Guard the contract: positive, finite, non-decreasing.
        fixed = []
        prev = 0.0
        for q in qs:
            v = float(q)
            if not math.isfinite(v) or v <= 0:
                v = prev if prev > 0 else 1.0
            v = max(v, prev, 1e-9)
            fixed.append(int(v) if float(v).is_integer() else v)
            prev = v
        hours_out.append({"hour": h, "q": fixed})
    return {"hours": hours_out}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for in_path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(in_path.read_text(encoding="utf-8"))
        result = forecast_case(case)
        out_path = OUTPUT_DIR / (in_path.stem + ".out")
        out_path.write_text(json.dumps(result), encoding="utf-8")


if __name__ == "__main__":
    main()
