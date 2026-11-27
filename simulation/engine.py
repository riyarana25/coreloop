"""Day-by-day dealership simulator for comparing audit policies on IDENTICAL ledgers.

A policy decides on which days it looks at the ledger. On each look it sees only what is
observable that day (`observe(life, t)`), runs the same temporal classifier as every other
policy, and acts. Policies differ ONLY in `period` (how often they look) and whether the looking
is automated. Nothing else is tuned per policy.

Outcome stages are modelled separately and never collapsed:
    flagged -> submitted (staff follow-through) -> approved (win probability) -> cash received (lag)
A flagged discrepancy is not a dispute, a dispute is not an approved credit, and an approved credit is
not cash until its lag has elapsed.

All parameters are assumptions (see benchmark/audit_frequency_methodology.md).
"""
import random
from collections import Counter, defaultdict
from dataclasses import dataclass

from audit.temporal_credit_classifier import ACTION, CLOSED, PostingHistory, assess
from coreloop.catalog import PARTS
from coreloop.disputes import DISPUTE_PARAMS
from coreloop.lifecycle import reship
from coreloop.lifecycle import observe
from coreloop.models import entitlement, next_business_day

CREDIT_KINDS = ("credit_missing", "wrong_number", "excess_deduction")


@dataclass
class Params:
    follow_ship: float = 0.85        # chance staff act on a "ship now" alert
    follow_dispute: float = 0.85     # chance staff submit a flagged dispute
    p_win_scale: float = 1.0         # multiplies per-kind win probabilities
    wage_per_hour: float = 35.0
    audit_base_min: float = 90.0     # human audit: fixed setup/reading time
    audit_per_open_min: float = 0.5  # human audit: minutes per open core reviewed
    triage_min: float = 4.0          # automated monitoring: minutes to triage one alert
    ship_event_min: float = 10.0
    ship_per_core_min: float = 1.0
    software_cost_per_month: float = 200.0   # automated monitoring only
    freight_scale: float = 1.0
    audit_adherence: float = 1.0     # chance a scheduled HUMAN audit really happens (1.0 = best case)
    horizon: int = 400               # long enough that every core's lifecycle has resolved


@dataclass(frozen=True)
class PolicySpec:
    name: str
    period: int | None               # None = never audit; 1 = every day
    automated: bool = False          # True = event-driven software; humans only triage alerts


POLICIES_UNDER_TEST = [
    PolicySpec("N: no auditing (reference)", None),
    PolicySpec("A: every 90 days", 90),
    PolicySpec("B: every 30 days", 30),
    PolicySpec("C: every 7 days", 7),
    PolicySpec("D: event-driven continuous", 1, automated=True),
]


def _audit_days(spec, seed, horizon):
    if spec.period is None:
        return []
    off = random.Random(seed * 7919 + spec.period).randrange(spec.period) if spec.period > 1 else 0
    return list(range(off + (spec.period if spec.period > 1 else 0), horizon + 1, spec.period))


def simulate(lives, policies, spec, params, seed=0):
    n = len(lives)
    cur = list(lives)
    order = sorted(range(n), key=lambda i: lives[i].removed_day)
    ptr, active = 0, []
    hist = PostingHistory()
    events = defaultdict(list)
    for i, l in enumerate(lives):
        if l.credit_day is not None:
            events[l.credit_day].append(i)

    days = _audit_days(spec, seed, params.horizon)
    day_set = set(days)
    next_after = {}
    for a, b in zip(days, days[1:] + [days[-1] + spec.period if days else 0]):
        next_after[a] = b

    st = Counter()
    minutes = Counter()
    alerted = set()
    flagged = {}                    # core -> (day, kind)
    recovered = {}                  # core -> (amount, cash_day)
    submitted = {}
    interventions = defaultdict(set)

    for t in range(params.horizon + 1):
        for i in events.pop(t, ()):
            l = cur[i]
            if l.credit_day == t and l.due is not None:
                hist.add(l.oem, t - l.due, l.due)    # a credit became visible today
        while ptr < n and lives[order[ptr]].removed_day <= t:
            active.append(order[ptr])
            ptr += 1
        if t not in day_set:
            continue
        nxt = next_after[t]
        if (not spec.automated and params.audit_adherence < 1.0
                and random.Random(seed * 104729 + spec.period * 1009 + t).random() >= params.audit_adherence):
            continue                                   # the audit was planned but skipped
        if not spec.automated:
            minutes["audit_review"] += params.audit_base_min + params.audit_per_open_min * len(active)

        still = []
        for i in active:
            core = observe(cur[i], t)
            a = assess(core, t, PARTS, policies, hist, nxt)
            if a.state == CLOSED:
                continue
            if a.state != ACTION:
                still.append(i)
                continue
            if a.kind == "ship_by":
                if (i, "ship") not in alerted:
                    alerted.add((i, "ship"))
                    st["ship_alerts"] += 1
                    if spec.automated:
                        minutes["triage"] += params.triage_min
                    manual_ok = lives[i].ship_day is not None and lives[i].ship_day <= lives[i].deadline
                    if manual_ok:
                        st["ship_alerts_unnecessary"] += 1   # it would have shipped on time anyway
                day = next_business_day(t)
                if cur[i].ship_day == day:
                    still.append(i)
                    continue                            # already scheduled for that day
                if cur[i].u_ship < params.follow_ship:
                    if day <= cur[i].deadline:
                        oem = cur[i].oem
                        # one box per OEM: everything of that OEM still in the bin goes with it
                        for j in active:
                            c = cur[j]
                            if (c.oem == oem and c.removed_day <= t and c.deadline >= day
                                    and (c.ship_day is None or c.ship_day > day)):
                                cur[j] = reship(c, day, policies)
                                interventions[(oem, day)].add(j)
                                st["ship_acted"] += 1
                                if cur[j].credit_day is not None:
                                    events[cur[j].credit_day].append(j)
                    else:
                        st["ship_acted_too_late"] += 1
                still.append(i)
                continue
            if a.kind not in CREDIT_KINDS:
                still.append(i)                     # e.g. carrier trace: informational here
                continue
            # credit discrepancy needing action
            flagged[i] = (t, a.kind)
            st["credit_alerts"] += 1
            if spec.automated:
                minutes["triage"] += params.triage_min
            if cur[i].u_submit < params.follow_dispute and a.days_left >= 0:
                submitted[i] = t
                st["disputes_submitted"] += 1
                minutes["disputes"] += DISPUTE_PARAMS[a.kind][0]
                real = cur[i].leak in CREDIT_KINDS
                if real and cur[i].u_win < DISPUTE_PARAMS[a.kind][1] * params.p_win_scale:
                    recovered[i] = (a.amount, t + cur[i].cash_lag)
        active = still

    for oem_day, ids in interventions.items():
        minutes["ship_events"] += params.ship_event_min + params.ship_per_core_min * len(ids)
    freight = sum(policies[oem].freight_cost for (oem, _d) in interventions) * params.freight_scale

    # ---- final accounting --------------------------------------------------
    loss_window = saved_window = 0.0
    n_window_missed = n_saved = 0
    leak_total = leak_cnt = 0
    for i, l in enumerate(cur):
        pol = policies[l.oem]
        ent = entitlement(_as_core(lives[i]), PARTS[l.part_no], pol)
        ok_now = l.ship_day is not None and l.ship_day <= l.deadline
        ok_manual = lives[i].ship_day is not None and lives[i].ship_day <= lives[i].deadline
        if not ok_now:
            loss_window += ent
            n_window_missed += 1
        elif not ok_manual:
            saved_window += ent
            n_saved += 1
        if ok_now and l.leak in CREDIT_KINDS:
            leak_cnt += 1
            if l.credit_amount is None:
                leak_total += ent
            else:
                leak_total += max(0.0, ent - l.credit_amount)
    detected = [i for i in flagged if cur[i].leak in CREDIT_KINDS]
    fp = [i for i in flagged if cur[i].leak not in CREDIT_KINDS]
    cash = sum(a for a, d in recovered.values() if d <= params.horizon)
    detected_value = sum(a for i, (d, k) in flagged.items() if cur[i].leak in CREDIT_KINDS
                         for a in [_shortfall(cur[i], lives[i], policies)])
    loss_credit = max(0.0, leak_total - cash)
    staff_min = sum(minutes.values())
    staff_cost = staff_min / 60.0 * params.wage_per_hour
    software = (params.horizon / 30.0) * params.software_cost_per_month if spec.automated else 0.0
    verified = cash + saved_window
    return {
        "policy": spec.name,
        "loss_window": loss_window, "n_window_missed": n_window_missed,
        "saved_window_value": saved_window, "n_window_saved": n_saved,
        "credit_leaks": leak_cnt, "credit_leak_value": leak_total,
        "detected": len(detected), "detected_value": detected_value,
        "missed_or_late": leak_cnt - len(detected),
        "disputes_submitted": len(submitted),
        "disputes_submitted_real": sum(1 for i in submitted if cur[i].leak in CREDIT_KINDS),
        "approved": len(recovered),
        "cash_received": cash,
        "loss_credit_unrecovered": loss_credit,
        "false_positive_credit_alerts": len(fp),
        "ship_alerts": st["ship_alerts"], "ship_alerts_unnecessary": st["ship_alerts_unnecessary"],
        "ship_acted": st["ship_acted"], "ship_events": len(interventions),
        "staff_minutes": staff_min,
        "staff_minutes_audit": minutes["audit_review"] + minutes["triage"],
        "staff_cost": staff_cost, "freight_cost": freight, "software_cost": software,
        "total_loss": loss_window + loss_credit,
        "verified_recovery": verified,
        "operating_cost": staff_cost + freight + software,
        "net_benefit": verified - (staff_cost + freight + software),
        "flag_days": {i: flagged[i][0] for i in detected},
    }


def _as_core(life):
    return observe(life, 10**6)


def _shortfall(cur_life, orig_life, policies):
    ent = entitlement(_as_core(orig_life), PARTS[cur_life.part_no], policies[cur_life.oem])
    if cur_life.credit_amount is None:
        return ent
    return max(0.0, ent - cur_life.credit_amount)
