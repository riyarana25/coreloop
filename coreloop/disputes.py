"""Dispute work-queue: which credits to chase on which day, given limited staff time.

Every credit finding has an expected value (amount x chance of winning), an effort
in minutes, and a dispute deadline. Staff have a daily minute budget. The queue is
an exact assignment solved with CP-SAT (verified against brute force in tests).
Win probabilities and effort minutes are ASSUMPTIONS, not measured values.
"""
from ortools.sat.python import cp_model

# kind -> (effort minutes, probability a dispute succeeds). Assumptions.
DISPUTE_PARAMS = {
    "credit_missing": (10, 0.85),
    "wrong_number": (15, 0.80),
    "excess_deduction": (20, 0.60),
}


def effort(f):
    return DISPUTE_PARAMS[f.kind][0]


def expected_value(f):
    return round(f.amount * DISPUTE_PARAMS[f.kind][1], 2)


def _eligible(findings):
    return [f for f in findings if f.kind in DISPUTE_PARAMS and f.recoverable]


def plan_queue(findings, daily_minutes=120, horizon=10, time_limit=10.0):
    """Return ({day_offset: [findings]}, total_expected_value). Day 0 is audit day."""
    items = _eligible(findings)
    m = cp_model.CpModel()
    x = {}
    for i, f in enumerate(items):
        for t in range(min(horizon, f.days_left + 1)):
            x[i, t] = m.NewBoolVar(f"x{i}_{t}")
        if any((i, t) in x for t in range(horizon)):
            m.Add(sum(x[i, t] for t in range(horizon) if (i, t) in x) <= 1)
    for t in range(horizon):
        terms = [effort(items[i]) * x[i, t] for i in range(len(items)) if (i, t) in x]
        if terms:
            m.Add(sum(terms) <= daily_minutes)
    # value in cents, x100 so that "earlier is better" tie-break (-t) never changes totals
    m.Maximize(sum((int(round(expected_value(items[i]) * 100)) * 100 - t) * v
                   for (i, t), v in x.items()))
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = time_limit
    s.parameters.num_workers = 1
    s.parameters.random_seed = 7
    status = s.Solve(m)
    plan = {}
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for (i, t), v in x.items():
            if s.Value(v):
                plan.setdefault(t, []).append(items[i])
    total = round(sum(expected_value(f) for fs in plan.values() for f in fs), 2)
    return plan, total


def greedy_queue(findings, daily_minutes=120, horizon=10, order="amount"):
    """Baselines. order='amount': biggest dollars first; order='expiry': soonest deadline first."""
    items = _eligible(findings)
    key = (lambda f: -f.amount) if order == "amount" else (lambda f: (f.days_left, -f.amount))
    items.sort(key=key)
    used = [0] * horizon
    plan = {}
    for f in items:
        for t in range(min(horizon, f.days_left + 1)):
            if used[t] + effort(f) <= daily_minutes:
                used[t] += effort(f)
                plan.setdefault(t, []).append(f)
                break
    total = round(sum(expected_value(f) for fs in plan.values() for f in fs), 2)
    return plan, total


def draft_dispute(f, ledger):
    """Deterministic dispute text built only from ledger facts (an LLM may polish it later)."""
    c = next(c for c in ledger.cores if c.core_id == f.core_id)
    pol = ledger.policies[c.oem]
    ev = f.evidence
    lines = [
        f"To: {c.oem} Core Returns / Credits Desk",
        f"Subject: Core credit dispute - RO {c.ro_id}, part {c.part_no}",
        "",
        f"Part {c.part_no} was removed on day {c.removed_day} (condition recorded: {c.condition}) "
        f"and shipped on day {c.shipped_day}, inside the {pol.window_days}-day return window. "
        f"The OEM received it on day {c.received_day}.",
    ]
    if f.kind == "credit_missing":
        lines.append(f"No credit has posted. It was due by day {ev['credit_due']} "
                     f"(+{pol.grace_days} grace days). Amount owed: ${ev['expected']:.2f}.")
    elif f.kind == "wrong_number":
        lines.append(f"A credit of ${ev['received']:.2f} posted against superseded part number "
                     f"{ev['credit_part_no']}. The part returned was {c.part_no}. "
                     f"Entitled credit is ${ev['expected']:.2f}; shortfall ${f.amount:.2f}.")
    else:
        lines.append(f"A credit of ${ev['received']:.2f} posted. Policy allows a deduction of at most "
                     f"{pol.max_damage_deduction:.0%} for damage; entitled credit is "
                     f"${ev['expected']:.2f}. Shortfall ${f.amount:.2f}.")
    lines.append(f"Please correct the credit. Dispute deadline: {f.days_left} days from audit day.")
    return "\n".join(lines)
