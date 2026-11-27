"""All business logic behind the demo UI. The UI only calls these functions and draws the results.

World state = (synthetic lives from seed) + (operator decisions from SQLite) + (simulated clock).
Everything the classifier and planner see goes through observe(life, today): no hidden fields.
Hidden draws (staff outcome, dispute win, cash lag) are used ONLY to resolve what happens after a
decision, exactly as in the benchmark simulator; they never reach a classifier or planner.
"""
from dataclasses import dataclass, field
from functools import lru_cache
from types import SimpleNamespace

from audit.temporal_credit_classifier import (ACTION, AT_RISK, CLOSED, PENDING, PostingHistory, assess)
from coreloop.catalog import PARTS, POLICIES
from coreloop.disputes import DISPUTE_PARAMS, plan_queue
from coreloop.lifecycle import make_lives, observe, reship
from coreloop.models import entitlement, next_business_day, prev_business_day, ship_by
from coreloop.shipping import TRANSIT_DELAY_PROBS, _expected_miss, _window, min_ship_days
from shipping.freight_cost_model import CORE_WEIGHT_LB, FreightParams, plan_freight

DECISION_LAG = 7      # ASSUMPTION: days for an OEM to rule on a submitted dispute
CREDIT_KINDS = tuple(DISPUTE_PARAMS)
DAILY_MINUTES = 120   # ASSUMPTION: staff minutes per day available for disputes


@lru_cache(maxsize=8)
def _lives(seed, n_cores):
    return make_lives(seed, n_cores=n_cores, removal_span=180)


@dataclass
class World:
    today: int
    lives: list
    cores: dict                      # core_id -> observed Core (today)
    assessments: dict                # core_id -> Assessment
    history: PostingHistory
    ship_overrides: dict
    submitted: dict = field(default_factory=dict)    # core_id -> day submitted
    decisions: list = field(default_factory=list)


def build_world(seed, n_cores, today, decisions):
    lives = list(_lives(seed, n_cores))
    by_id = {l.core_id: i for i, l in enumerate(lives)}
    ship_overrides, submitted = {}, {}
    for d in decisions:
        if d["day"] > today:
            continue
        if d["action"] == "approve" and d["kind"] == "ship_by":
            ship_overrides[d["core_id"]] = next_business_day(d["day"])
        elif d["action"] == "approve" and d["kind"] in CREDIT_KINDS:
            submitted[d["core_id"]] = d["day"]
    for cid, day in ship_overrides.items():
        i = by_id[cid]
        lives[i] = reship(lives[i], day, POLICIES)
    hist = PostingHistory()
    for l in lives:
        if l.credit_day is not None and l.credit_day <= today and l.due is not None:
            hist.add(l.oem, l.credit_day - l.due, l.due)
    cores, ass = {}, {}
    for l in lives:
        if l.removed_day > today:
            continue
        c = observe(l, today)
        cores[l.core_id] = c
        ass[l.core_id] = assess(c, today, PARTS, POLICIES, hist, today + 1)
    return World(today, lives, cores, ass, hist, ship_overrides, submitted, decisions)


# ---------------------------------------------------------------- overview / inventory
def overview(w):
    a = w.assessments.values()
    open_ = [x for x in a if x.state != CLOSED]
    missed = [x for x in a if x.kind == "window_missed"]
    return {
        "today": w.today,
        "cores_in_system": len(w.cores),
        "open_cores": len(open_),
        "action_required": sum(x.state == ACTION for x in a),
        "at_risk": sum(x.state == AT_RISK for x in a),
        "pending": sum(x.state == PENDING for x in a),
        "deposits_open": round(sum(x.amount for x in open_), 2),
        "deposits_action": round(sum(x.amount for x in a if x.state == ACTION), 2),
        "deposits_at_risk": round(sum(x.amount for x in a if x.state == AT_RISK), 2),
        "windows_missed": len(missed),
        "deposits_forfeited": round(sum(x.amount for x in missed), 2),
        "disputes_submitted": len(w.submitted),
    }


def inventory_rows(w):
    rows = []
    for cid, a in w.assessments.items():
        c = w.cores[cid]
        pol = POLICIES[c.oem]
        sb = ship_by(c, pol)
        rows.append({"core_id": cid, "part": c.part_no, "oem": c.oem, "condition": c.condition,
                     "removed_day": c.removed_day, "ship_by_day": sb, "days_to_ship_by": sb - w.today,
                     "shipped_day": c.shipped_day, "received_day": c.received_day,
                     "credit": c.credit_amount, "state": a.state, "kind": a.kind,
                     "amount": a.amount, "why": a.reason})
    return rows


# ---------------------------------------------------------------- shipping
def _unshipped(w):
    return [c for cid, c in w.cores.items() if c.shipped_day is None
            and w.assessments[cid].kind != "window_missed" and w.assessments[cid].state != CLOSED]


def plan_shipments(w, buffer_days=1, delay_days=0, fp=None):
    """Minimum-shipment plan for every unshipped core. delay_days>0 = the counterfactual 'wait'."""
    fp = fp or FreightParams()
    earliest = next_business_day(w.today + delay_days)
    sched, lost, intervals_by_oem = {}, [], {}
    for c in _unshipped(w):
        pol = POLICIES[c.oem]
        _lo, hi = _window(c, pol, buffer_days)
        lo = max(_lo, earliest)
        if hi < lo:
            hi = prev_business_day(ship_by(c, pol))      # buffer cannot fit: use the unbuffered last day
        if hi < lo:
            lost.append(c)
            continue
        intervals_by_oem.setdefault(c.oem, []).append((lo, hi, c.core_id))
    for oem, ivs in intervals_by_oem.items():
        for day, ids in min_ship_days(ivs).items():
            sched[(oem, day)] = ids
    by_id = {c.core_id: c for c in _unshipped(w)}
    fr = plan_freight(sched, by_id, fp) if sched else {"freight": 0.0, "loads": 0, "cores": 0, "total_lb": 0, "utilisation": 0.0}
    exp_loss = 0.0
    for (oem, day), ids in sched.items():
        for cid in ids:
            c = by_id[cid]
            exp_loss += entitlement(c, PARTS[c.part_no], POLICIES[oem]) * _expected_miss(c, POLICIES[oem], day)
    lost_value = sum(entitlement(c, PARTS[c.part_no], POLICIES[c.oem]) for c in lost)
    return {"schedule": sched, "events": len(sched), "freight": fr["freight"], "loads": fr["loads"],
            "cores_planned": fr["cores"], "cores_lost": len(lost), "value_lost": round(lost_value, 2),
            "expected_delay_loss": round(exp_loss, 2), "lost_cores": [c.core_id for c in lost],
            "cores_by_id": by_id}


def counterfactual_wait(w, wait_days=1, buffer_days=1):
    base = plan_shipments(w, buffer_days, 0)
    wait = plan_shipments(w, buffer_days, wait_days)
    keys = ("events", "freight", "cores_lost", "value_lost", "expected_delay_loss", "loads")
    return {"base": {k: base[k] for k in keys}, "wait": {k: wait[k] for k in keys},
            "newly_lost": sorted(set(wait["lost_cores"]) - set(base["lost_cores"])),
            "delta": {k: round(wait[k] - base[k], 2) for k in keys}}


def ship_today_alerts(w):
    """Unshipped cores the classifier says to ship today."""
    return [a for a in w.assessments.values() if a.track == "shipping" and a.state == ACTION]


# ---------------------------------------------------------------- credit monitoring
def credit_rows(w):
    """Credit and transit cases that need attention (not healthy, not already closed)."""
    rows = []
    for cid, a in w.assessments.items():
        if a.track in ("credit", "transit") and a.state != CLOSED and a.kind != "ok":
            rows.append({"core_id": cid, "oem": w.cores[cid].oem, "track": a.track, "state": a.state, "kind": a.kind,
                         "amount": a.amount, "days_left": a.days_left, "why": a.reason})
    return rows


def posting_history_summary(w):
    out = []
    for oem in POLICIES:
        tail = w.history.normal_delay(oem, POLICIES[oem].grace_days, w.today)
        out.append({"oem": oem, "settled_credits": w.history.n(oem),
                    "normal_delay_days": tail, "grace_days": POLICIES[oem].grace_days})
    return out


# ---------------------------------------------------------------- disputes
def dispute_queue(w, daily_minutes=DAILY_MINUTES):
    """ACTION credit findings not yet decided, ordered by the exact CP-SAT assignment."""
    decided = {d["core_id"] for d in w.decisions if d["action"] in ("approve", "dismiss")
               or (d["action"] == "defer" and d["defer_until"] and d["defer_until"] > w.today)}
    items = []
    for cid, a in w.assessments.items():
        if a.track == "credit" and a.state == ACTION and a.kind in CREDIT_KINDS and cid not in decided:
            items.append(SimpleNamespace(core_id=cid, kind=a.kind, amount=a.amount, days_left=max(0, a.days_left or 0),
                                         recoverable=True, evidence=a.evidence, why=a.reason))
    plan, total = plan_queue(items, daily_minutes=daily_minutes, horizon=10, time_limit=5.0) if items else ({}, 0.0)
    planned_day = {f.core_id: t for t, fs in plan.items() for f in fs}
    rows = []
    for f in items:
        pw = DISPUTE_PARAMS[f.kind]
        rows.append({"core_id": f.core_id, "kind": f.kind, "amount": f.amount, "days_left": f.days_left,
                     "effort_min": pw[0], "win_probability": pw[1], "expected_value": round(f.amount * pw[1], 2),
                     "suggested_day_offset": planned_day.get(f.core_id), "why": f.why})
    rows.sort(key=lambda r: (r["suggested_day_offset"] is None, r["suggested_day_offset"] or 0, -r["expected_value"]))
    return rows, total


def draft_dispute(w, core_id):
    c, a = w.cores[core_id], w.assessments[core_id]
    pol, ev = POLICIES[c.oem], a.evidence
    lines = [f"To: {c.oem} Core Returns / Credits Desk",
             f"Subject: Core credit dispute - RO {c.ro_id}, part {c.part_no}", "",
             f"Part {c.part_no} was removed on day {c.removed_day} (condition recorded: {c.condition}) and shipped on day "
             f"{c.shipped_day}, inside the {pol.window_days}-day return window. The OEM received it on day {c.received_day}."]
    if a.kind == "credit_missing":
        lines.append(f"No credit has posted. It was due by day {ev['credit_due']} (+{pol.grace_days} grace days). "
                     f"Amount owed: ${a.amount:.2f}.")
    elif a.kind == "wrong_number":
        lines.append(f"A credit of ${ev['received_credit']:.2f} posted against superseded part number {ev['credit_part_no']}. "
                     f"Entitled credit is ${ev['expected_credit']:.2f}; shortfall ${a.amount:.2f}.")
    else:
        lines.append(f"A credit of ${ev['received_credit']:.2f} posted. Policy allows a deduction of at most "
                     f"{pol.max_damage_deduction:.0%}; entitled credit is ${ev['expected_credit']:.2f}. Shortfall ${a.amount:.2f}.")
    lines.append(f"Dispute deadline: day {ev['dispute_deadline']}.")
    return "\n".join(lines)


def dispute_outcomes(w):
    """Resolve submitted disputes with the hidden draws (simulation only). Returns list of dicts."""
    lives = {l.core_id: l for l in w.lives}
    out = []
    for cid, day in w.submitted.items():
        l = lives[cid]
        a_kind = next((d["kind"] for d in w.decisions if d["core_id"] == cid and d["action"] == "approve"), None)
        p = DISPUTE_PARAMS.get(a_kind, (0, 0))[1]
        ruling_day = day + DECISION_LAG
        won = l.u_win < p
        cash_day = ruling_day + l.cash_lag
        amount = next((d.get("amount", 0.0) for d in w.decisions if d["core_id"] == cid and d["action"] == "approve"), 0.0)
        status = "submitted" if w.today < ruling_day else (
            ("approved" if w.today < cash_day else "cash received") if won else "rejected")
        out.append({"core_id": cid, "kind": a_kind, "submitted_day": day, "ruling_day": ruling_day,
                    "cash_day": cash_day if won else None, "status": status, "_won": won})
    return out


# ---------------------------------------------------------------- operator actions (persisted by caller)
def decide(store, w, core_id, kind, action, defer_days=3, note=""):
    day = w.today
    if action == "approve" and any(d["core_id"] == core_id and d["kind"] == kind and d["action"] == "approve"
                                   for d in store.decisions()):
        return                      # idempotent: a double click must not submit twice
    until = day + defer_days if action == "defer" else None
    store.add_decision(core_id, kind, action, day, until, note)
    if action == "approve" and kind == "ship_by":
        store.log(day, "ship_now", f"shipment released for core {core_id} on day {next_business_day(day)}", core_id)
    elif action == "approve":
        store.log(day, "dispute_submitted", f"{kind} dispute submitted for core {core_id}", core_id)
    elif action == "defer":
        store.log(day, "deferred", f"{kind} deferred until day {until}", core_id)
    else:
        store.log(day, "dismissed", f"{kind} dismissed", core_id)


def advance(store, days):
    t = store.get("today") + days
    store.set("today", t)
    store.log(t, "clock", f"advanced {days} day(s)")
    return t


def reconcile_audit_events(store, w):
    """Write outcome events to the trail once (idempotent)."""
    seen = {(r["core_id"], r["event"]) for r in store.trail(10_000)}
    for o in dispute_outcomes(w):
        ev = {"approved": "dispute_approved", "rejected": "dispute_rejected", "cash received": "cash_received"}.get(o["status"])
        if ev and (o["core_id"], ev) not in seen:
            store.log(w.today, ev, f"simulated outcome ({o['kind']}); ruling day {o['ruling_day']}", o["core_id"])


# ---------------------------------------------------------------- audit-frequency simulator
def frequency_experiment(n_seeds=8, window_scale=1.0, audit_adherence=1.0, follow_dispute=0.85, n_cores=300):
    """Live (small) run of the benchmark simulator. Returns {policy: {metric: mean}}. SYNTHETIC."""
    from coreloop.lifecycle import scale_windows
    from simulation.engine import POLICIES_UNDER_TEST, Params, simulate
    params = Params(audit_adherence=audit_adherence, follow_dispute=follow_dispute)
    pol = scale_windows(POLICIES, window_scale) if window_scale != 1.0 else POLICIES
    acc = {s.name: {} for s in POLICIES_UNDER_TEST}
    for seed in range(n_seeds):
        lives = make_lives(9000 + seed, n_cores=n_cores, policies=pol)
        for spec in POLICIES_UNDER_TEST:
            r = simulate(lives, pol, spec, params, seed=seed)
            for k in ("total_loss", "staff_minutes", "net_benefit", "operating_cost"):
                acc[spec.name].setdefault(k, []).append(r[k])
    out = {n: {k: sum(v) / len(v) for k, v in d.items()} for n, d in acc.items()}
    for d in out.values():
        d["staff_hours"] = d.pop("staff_minutes") / 60.0
    return out


def load_benchmark(path):
    import json
    with open(path) as f:
        return json.load(f)
