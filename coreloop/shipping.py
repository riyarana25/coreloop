"""Deadline-aware core shipment batching.

Each core must leave on a business day in [removed+1, ship_by]. One shipment per
(OEM, day) costs a fixed freight amount. Choosing the fewest shipping days so
every core is covered is a minimum point-stabbing problem; sorting by latest
allowed day and shipping on that day is provably optimal (tested against brute
force). Because each OEM has one fixed window, the rule only needs cores that
are already in the bin, so it can run live without knowing the future.

`buffer_days` ships earlier than the last safe day to absorb carrier delays.
"""
from dataclasses import dataclass, field

from .models import (is_business_day, next_business_day, prev_business_day, ship_by)

# Assumed chance that a shipment arrives d extra days late (editable assumption).
TRANSIT_DELAY_PROBS = {0: 0.80, 1: 0.12, 2: 0.06, 3: 0.02}


@dataclass
class ShipResult:
    policy: str
    shipments: int
    freight: float
    missed: int                  # cores that cannot arrive inside the window even with no delay
    expected_missed: float       # including random carrier delay
    schedule: dict = field(default_factory=dict)   # (oem, day) -> [core_id]


def _window(core, pol, buffer_days):
    lo = next_business_day(core.removed_day + 1)
    hi = prev_business_day(ship_by(core, pol) - buffer_days)
    if hi < lo:  # window too short for the buffer: use the unbuffered last day
        hi = prev_business_day(ship_by(core, pol))
    return lo, hi


def min_ship_days(intervals):
    """Minimum point stabbing on (lo, hi, key) triples. Returns {day: [keys]}."""
    points = {}
    last = None
    for lo, hi, key in sorted(intervals, key=lambda t: (t[1], t[0])):
        if last is not None and lo <= last <= hi:
            points[last].append(key)
        else:
            last = hi
            points[last] = [key]
    return points


def _expected_miss(core, pol, ship_day):
    margin = (core.removed_day + pol.window_days) - (ship_day + pol.transit_days)
    if margin < 0:
        return 1.0
    return sum(p for extra, p in TRANSIT_DELAY_PROBS.items() if extra > margin)


def _finish(name, assignment, cores, ledger):
    """assignment: {core_id: ship_day}."""
    by_id = {c.core_id: c for c in cores}
    sched, missed, exp_missed = {}, 0, 0.0
    for cid, day in assignment.items():
        c = by_id[cid]
        pol = ledger.policies[c.oem]
        sched.setdefault((c.oem, day), []).append(cid)
        if day > ship_by(c, pol):
            missed += 1
        exp_missed += _expected_miss(c, pol, day)
    freight = sum(ledger.policies[oem].freight_cost for (oem, _d) in sched)
    return ShipResult(name, len(sched), freight, missed, round(exp_missed, 2), sched)


def run_policy(name, cores, ledger, buffer_days=0):
    assignment = {}
    if name == "ship_each":
        for c in cores:
            assignment[c.core_id] = next_business_day(c.removed_day + 1)
    elif name == "weekly_friday":
        for c in cores:
            d = c.removed_day + 1
            d += (4 - d % 7) % 7
            assignment[c.core_id] = d
    elif name == "last_safe_day":     # basic deadline rule: each core ships alone on its last safe day
        for c in cores:
            lo, hi = _window(c, ledger.policies[c.oem], buffer_days)
            assignment[c.core_id] = max(lo, hi)
    elif name == "coreloop":
        for oem in sorted({c.oem for c in cores}):
            pol = ledger.policies[oem]
            ivs = []
            for c in cores:
                if c.oem != oem:
                    continue
                lo, hi = _window(c, pol, buffer_days)
                if hi < lo:               # cannot be saved: ship ASAP and count as missed
                    assignment[c.core_id] = lo
                else:
                    ivs.append((lo, hi, c.core_id))
            for day, ids in min_ship_days(ivs).items():
                for cid in ids:
                    assignment[cid] = day
    else:
        raise ValueError(name)
    label = name if name not in ("coreloop", "last_safe_day") else f"{name}(buffer={buffer_days})"
    return _finish(label, assignment, cores, ledger)


def compare(ledger, buffers=(0, 1, 2, 3)):
    """Re-plan shipping for every core in the ledger under each policy."""
    cores = ledger.cores
    res = [run_policy("ship_each", cores, ledger), run_policy("weekly_friday", cores, ledger)]
    res += [run_policy("coreloop", cores, ledger, buffer_days=b) for b in buffers]
    return res
