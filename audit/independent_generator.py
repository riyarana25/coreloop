"""An INDEPENDENT scenario generator for validating the temporal classifier.

Written to differ from coreloop/lifecycle.py on purpose:
  - 4 different OEMs with different windows, posting days, grace, deduction caps, dispute windows
  - a different parts catalogue with TWO-hop supersession chains (the classifier only follows one hop)
  - credits post on OEM STATEMENT CYCLES plus a heavy-tailed (log-normal) processing delay, not a
    uniform grace-window delay
  - extra failure modes the classifier was not built around: cores lost in transit, legitimate
    OEM rejections (not recoverable), and larger rounding noise on a minority of clean credits
It is the same author as the classifier, so it is independent in design, not in authorship.
It emits `Life` objects so the same observation machinery (information gating) applies.
"""
import math
import random

from coreloop.lifecycle import Life
from coreloop.models import OEMPolicy, Part

IND_POLICIES = {
    "OEM-W": OEMPolicy("OEM-W", 20, 2, 7, 2, 0.20, 90, 38.0),
    "OEM-X": OEMPolicy("OEM-X", 28, 5, 30, 7, 0.35, 60, 70.0),
    "OEM-Y": OEMPolicy("OEM-Y", 45, 3, 14, 4, 0.15, 45, 52.0),
    "OEM-Z": OEMPolicy("OEM-Z", 60, 6, 21, 5, 0.30, 120, 95.0),
}
CYCLE = {"OEM-W": 7, "OEM-X": 30, "OEM-Y": 14, "OEM-Z": 7}   # statement cycle length, days

_P = [
    ("W-100", "OEM-W", 300.0, "W-099"), ("W-099", "OEM-W", 220.0, "W-090"), ("W-090", "OEM-W", 150.0, None),
    ("W-210", "OEM-W", 95.0, None),
    ("X-500", "OEM-X", 640.0, "X-480"), ("X-480", "OEM-X", 500.0, "X-455"), ("X-455", "OEM-X", 410.0, None),
    ("X-610", "OEM-X", 240.0, None),
    ("Y-77", "OEM-Y", 180.0, "Y-70"), ("Y-70", "OEM-Y", 130.0, None), ("Y-81", "OEM-Y", 55.0, None),
    ("Z-9001", "OEM-Z", 880.0, "Z-8800"), ("Z-8800", "OEM-Z", 700.0, "Z-8100"), ("Z-8100", "OEM-Z", 560.0, None),
    ("Z-9150", "OEM-Z", 320.0, None), ("Z-9300", "OEM-Z", 110.0, None),
]
IND_PARTS = {p[0]: Part(*p) for p in _P}
_SUPER = {p.supersedes for p in IND_PARTS.values() if p.supersedes}
IND_ACTIVE = sorted(pn for pn in IND_PARTS if pn not in _SUPER)

# truth classes
RATES = [("never_shipped", 0.03), ("shipped_late", 0.05), ("credit_missing", 0.05), ("wrong_number", 0.03),
         ("excess_deduction", 0.03), ("lost_in_transit", 0.02), ("legit_rejection", 0.02),
         ("slow_credit", 0.03)]
RECOVERABLE = ("credit_missing", "wrong_number", "excess_deduction", "lost_in_transit")


def _draw(rng):
    r, acc = rng.random(), 0.0
    for name, p in RATES:
        acc += p
        if r < acc:
            return name
    return "clean"


def _chain(part_no, hops):
    p = IND_PARTS[part_no]
    for _ in range(hops):
        if p.supersedes is None:
            return None
        p = IND_PARTS[p.supersedes]
    return p


def _statement_day(oem, day):
    c = CYCLE[oem]
    off = (ord(oem[-1]) * 3) % c
    return day + ((off - day) % c)


def make_independent_lives(seed, n_cores=500, removal_span=150, damaged_share=0.20):
    rng = random.Random(10_000_019 * seed + 17)
    lives = []
    for cid in range(n_cores):
        part = IND_PARTS[rng.choice(IND_ACTIVE)]
        pol = IND_POLICIES[part.oem]
        removed = rng.randrange(0, removal_span)
        cond = "damaged" if rng.random() < damaged_share else "good"
        truth = _draw(rng)
        if truth == "wrong_number" and part.supersedes is None:
            truth = "clean"
        deadline = removed + pol.window_days - pol.transit_days
        span = max(1, deadline - removed)
        if truth == "never_shipped":
            ship = None
        elif truth == "shipped_late":
            ship = deadline + rng.randint(1, 15)
        else:
            ship = removed + rng.randint(1, span)
        recv = ship + pol.transit_days if ship is not None else None
        if truth == "lost_in_transit":
            recv = None
        due = credit_day = amount = cpart = None
        on_time = ship is not None and ship <= deadline
        if on_time and recv is not None:
            due = recv + pol.posting_days
            if truth != "credit_missing":
                stmt = _statement_day(part.oem, due)
                proc = int(round(math.exp(rng.gauss(0.0, 1.0))))          # median 1 day, heavy tail
                credit_day = stmt + proc
                if truth == "slow_credit":
                    credit_day += rng.randint(10, 40)
                value = part.core_value
                cpart = part.part_no
                d = 0.0
                if cond == "damaged":
                    d = pol.max_damage_deduction if rng.random() < 0.15 else rng.uniform(0.05, pol.max_damage_deduction)
                noise = rng.uniform(-0.99, 0.99) if rng.random() < 0.95 else rng.uniform(-2.5, 2.5)
                if truth == "wrong_number":
                    hops = 1 if rng.random() < 0.6 or _chain(part.part_no, 2) is None else 2
                    old = _chain(part.part_no, hops)
                    value, cpart = old.core_value, old.part_no
                    amount = round(value * (1 - d) + noise, 2)
                elif truth == "excess_deduction":
                    x = rng.uniform(pol.max_damage_deduction + 0.08, 0.6) if cond == "damaged" else rng.uniform(0.12, 0.5)
                    amount = round(value * (1 - x) + noise, 2)
                elif truth == "legit_rejection":
                    amount = 0.0
                else:
                    amount = round(value * (1 - d) + noise, 2)
        lives.append(Life(cid, 9000 + cid // 2, part.part_no, part.oem, removed, cond, truth, deadline,
                          ship, recv, due, credit_day, amount, cpart))
    return lives
