"""Full core lifecycles and information-gated observation.

`Life` holds a core's complete timeline under the dealership's ordinary (manual) process, plus
latent random draws used ONLY by the outcome simulator. `observe(life, t)` returns what a
system could actually see on day t. Everything after t is hidden, which is what lets the
simulator hand every audit policy only information available at that moment.

make_ledger() in generator.py is now a thin wrapper (lives -> observe at one audit day) and is
checked against saved hashes of the pre-refactor ledgers (tests/test_refactor_parity.py).
"""
import random
from dataclasses import dataclass, replace
from typing import Optional

from .catalog import ACTIVE_PARTS, PARTS, POLICIES
from .models import Core

TOL = 1.0

LEAK_RATES = {
    "never_shipped": 0.04,
    "shipped_late": 0.06,
    "credit_missing": 0.05,
    "wrong_number": 0.03,
    "excess_deduction": 0.04,
    "slow_credit": 0.03,
}


@dataclass
class Life:
    core_id: int
    ro_id: int
    part_no: str
    oem: str
    removed_day: int
    condition: str
    leak: str                       # latent: what the ordinary process does wrong (or "none")
    deadline: int                   # last ship day that still arrives inside the window
    ship_day: Optional[int]
    recv_day: Optional[int]
    due: Optional[int]              # day the credit is nominally due (receipt + posting days)
    credit_day: Optional[int]
    credit_amount: Optional[float]
    credit_part_no: Optional[str]
    # latent draws for the outcome simulator (separate RNG stream, never seen by policies)
    u_ship: float = 0.0             # does staff act on a ship alert
    u_submit: float = 0.0           # does staff submit a flagged dispute
    u_win: float = 0.0              # is a submitted dispute approved
    cash_lag: int = 20              # days from approval to cash
    clean_delay: int = 0            # posting delay if the core is shipped cleanly after intervention
    clean_amount: float = 0.0


def _draw_leak(rng, part, scale, rates=None):
    r = rng.random()
    acc = 0.0
    for name, p in (rates or LEAK_RATES).items():
        acc += p * scale
        if r < acc:
            if name == "wrong_number" and part.supersedes is None:
                return "none"
            return name
    return "none"


def _credit(rng, part, cond, leak, pol):
    noise = rng.uniform(-0.5, 0.5)
    if leak == "wrong_number":
        old = PARTS[part.supersedes]
        d = rng.uniform(0.10, pol.max_damage_deduction) if cond == "damaged" else 0.0
        return round(old.core_value * (1 - d) + noise, 2), old.part_no
    if leak == "excess_deduction":
        if cond == "damaged":
            x = rng.uniform(pol.max_damage_deduction + 0.10, 0.60)
        else:
            x = rng.uniform(0.15, 0.50)
        return round(part.core_value * (1 - x) + noise, 2), part.part_no
    d = rng.uniform(0.10, pol.max_damage_deduction) if cond == "damaged" else 0.0
    return round(part.core_value * (1 - d) + noise, 2), part.part_no


def make_life(rng, cid, removal_span, damaged_share=0.15, leak_scale=1.0, policies=None,
              latent_seed=None, rates=None):
    """Same random-number consumption order as the original generator (parity-tested)."""
    policies = policies or POLICIES
    part = PARTS[rng.choice(ACTIVE_PARTS)]
    pol = policies[part.oem]
    removed = rng.randrange(0, removal_span)
    cond = "damaged" if rng.random() < damaged_share else "good"
    leak = _draw_leak(rng, part, leak_scale, rates)
    deadline = removed + pol.window_days - pol.transit_days

    if leak == "never_shipped":
        ship = None
    elif leak == "shipped_late":
        ship = deadline + rng.randint(1, 10)
    else:
        ship = removed + rng.randint(1, deadline - removed)

    recv = None if ship is None else ship + pol.transit_days
    on_time = ship is not None and ship <= deadline
    due = credit_day = credit_amount = credit_part = None
    if on_time:
        due = recv + pol.posting_days
        if leak != "credit_missing":
            if leak == "slow_credit":
                credit_day = due + pol.grace_days + rng.randint(1, 10)
            else:
                credit_day = due + rng.randint(0, pol.grace_days)
            credit_amount, credit_part = _credit(rng, part, cond, leak, pol)

    life = Life(cid, 5000 + cid // 2, part.part_no, part.oem, removed, cond, leak, deadline,
                ship, recv, due, credit_day, credit_amount, credit_part)
    if latent_seed is not None:
        lr = random.Random(latent_seed)
        life.u_ship, life.u_submit, life.u_win = lr.random(), lr.random(), lr.random()
        life.cash_lag = lr.randint(10, 30)
        life.clean_delay = lr.randint(0, pol.grace_days)
        d = lr.uniform(0.10, pol.max_damage_deduction) if cond == "damaged" else 0.0
        life.clean_amount = round(part.core_value * (1 - d) + lr.uniform(-0.5, 0.5), 2)
    return life


def scale_windows(policies, k):
    """Copy of the policy table with every return window multiplied by k (sensitivity runs)."""
    return {n: replace(p, window_days=int(round(p.window_days * k))) for n, p in policies.items()}


def reship(life, day, policies):
    """Return a copy of `life` shipped on `day` (an intervention). Keeps OEM-side behaviour."""
    pol = policies[life.oem]
    recv = day + pol.transit_days
    out = replace(life, ship_day=day, recv_day=recv)
    if day > life.deadline:                       # too late: the OEM will not credit it
        out.due = out.credit_day = out.credit_amount = out.credit_part_no = None
        return out
    out.due = recv + pol.posting_days
    if life.leak in ("never_shipped", "shipped_late"):     # ordinary clean credit afterwards
        out.credit_day = out.due + life.clean_delay
        out.credit_amount = life.clean_amount
        out.credit_part_no = life.part_no
        out.leak = "none"
    elif life.credit_day is not None:                       # same OEM behaviour, shifted in time
        out.credit_day = out.due + (life.credit_day - life.due)
    return out


def truth_at(life, t, policies=None):
    """What is actually wrong on day t (hidden label; used only for scoring)."""
    policies = policies or POLICIES
    pol = policies[life.oem]
    ship, deadline = life.ship_day, life.deadline
    on_time = ship is not None and ship <= deadline
    if (ship is None or ship > deadline) and t > deadline:
        return "window_missed"
    if on_time and ship <= t:
        late_enough = t > life.due + pol.grace_days
        if life.leak == "credit_missing" and late_enough:
            return "credit_missing"
        if life.leak == "slow_credit" and late_enough and life.credit_day > t:
            return "slow_credit"
        if life.leak in ("wrong_number", "excess_deduction") and life.credit_day <= t:
            return life.leak
    return "clean"


def observe(life, t, with_truth=False, policies=None):
    """The Core record as visible on day t. Never exposes latent fields."""
    visible_credit = life.credit_day is not None and life.credit_day <= t
    return Core(
        core_id=life.core_id, ro_id=life.ro_id, part_no=life.part_no, oem=life.oem,
        removed_day=life.removed_day, condition=life.condition,
        shipped_day=life.ship_day if (life.ship_day is not None and life.ship_day <= t) else None,
        received_day=life.recv_day if (life.recv_day is not None and life.recv_day <= t) else None,
        credit_amount=life.credit_amount if visible_credit else None,
        credit_part_no=life.credit_part_no if visible_credit else None,
        credit_day=life.credit_day if visible_credit else None,
        truth=truth_at(life, t, policies) if with_truth else "",
    )


def make_lives(seed, n_cores=600, removal_span=180, damaged_share=0.15, leak_scale=1.0,
               policies=None, rates=None):
    rng = random.Random(seed)
    return [make_life(rng, cid, removal_span, damaged_share, leak_scale, policies,
                      latent_seed=seed * 1_000_003 + cid, rates=rates) for cid in range(n_cores)]
