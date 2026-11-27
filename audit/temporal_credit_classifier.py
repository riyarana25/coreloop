"""Temporal credit + return-deadline classifier.

Every open core is in exactly one of three states on a given day:

  pending          nothing is wrong yet, or waiting is still safe (the normal posting window has
                   not expired, or the ship-by day is far away)
  at_risk          something is overdue or abnormal, but waiting a little longer is still safe
  action_required  evidence supports a real discrepancy (or the cost of waiting is now too high);
                   a human should act today

The key idea: a slow-posting credit and a missing credit look identical on the day the credit
becomes overdue. We resolve that ambiguity with TIME, not with a bigger rulebook. We keep a
`pending/at_risk` verdict while (a) the delay is still inside the posting delays this ledger has
actually shown for that OEM (empirical high quantile, learned only from credits visible so far)
and (b) the NEXT time anyone will look is still early enough to dispute before the deadline.
Only when waiting stops being safe does the case become `action_required`.

`next_check_day` is the single difference between audit policies: a monthly audit cannot wait
because it will not look again for 30 days; continuous monitoring can wait until the last safe day.

The classifier reads observable ledger fields only. It never sees `Core.truth` or any latent field.
"""
import bisect
import math
from dataclasses import dataclass, field
from typing import Optional

from coreloop.lifecycle import TOL
from coreloop.models import entitlement, ship_by

PENDING, AT_RISK, ACTION, CLOSED = "pending", "at_risk", "action_required", "closed"

# Assumptions (documented in benchmark/audit_frequency_methodology.md)
SHIP_MARGIN = 4        # days of slack we want left when we finally ship (business days + carrier delay)
SHIP_LOOKAHEAD = 7     # unshipped cores inside this many days of ship-by are shown as at_risk
URGENT_MARGIN = 5      # days of dispute-window slack we refuse to go below before acting
DELAY_QUANTILE = 0.995 # "normal" posting delay = this quantile of delays seen so far for the OEM
MIN_HISTORY = 50       # credits needed before the empirical quantile is trusted
PRIOR_EXTRA_DAYS = 7   # before enough history: wait one week beyond the grace period
TRANSIT_GRACE = 3      # days after expected arrival before an unconfirmed receipt is flagged
TRANSIT_ESCALATE = 10  # days after expected arrival before it becomes action_required (trace / claim)


@dataclass
class Assessment:
    core_id: int
    track: str                   # shipping | transit | credit | done
    state: str                   # pending | at_risk | action_required | closed
    kind: str                    # ship_by | transit_unconfirmed | credit_missing | wrong_number |
                                 # excess_deduction | window_missed | data_error | ok
    amount: float                # dollars at stake
    days_left: Optional[int]     # ship: days to ship-by; credit: days to dispute deadline
    reason: str
    evidence: dict = field(default_factory=dict)
    expired: bool = False


@dataclass
class ClassifierConfig:
    """v1 = defaults. V0 reproduces the first version evaluated (kept for honest before/after numbers)."""
    materiality: bool = True       # ignore shortfalls smaller than max($5, 2% of entitlement)
    zero_credit_rule: bool = True  # a $0 credit on a DAMAGED core is a likely legitimate rejection
    materiality_abs: float = 5.0
    materiality_rel: float = 0.02


V1 = ClassifierConfig()
V0 = ClassifierConfig(materiality=False, zero_credit_rule=False)


class PostingHistory:
    """Posting delays (credit day minus nominal due day) seen so far, per OEM.

    Only credits already visible on the current day are added by the caller, so the learned tail can
    never include the future. Two safeguards against a statistical trap, RIGHT-CENSORING: on any day the
    credits we have seen are biased toward short delays (slow ones have not posted yet). So:
      mature_days > 0: only credits whose nominal due day is at least that many days old are used
      patient = True : with too little mature history we do not guess a tail; we wait as long as it is
                       safe (until the dispute deadline gets close) instead of using a fixed prior
    V0 behaviour (first version): mature_days=0, patient=False."""

    def __init__(self, mature_days=40, patient=True):
        self.mature_days, self.patient = mature_days, patient
        self.pending = {}      # oem -> list of (due, delay) not yet mature
        self.delays = {}       # oem -> sorted delays of mature credits

    def add(self, oem, delay, due=None):
        due = -10**9 if due is None else due
        if self.mature_days <= 0:
            bisect.insort(self.delays.setdefault(oem, []), delay)
        else:
            self.pending.setdefault(oem, []).append((due, delay))

    def _mature(self, oem, t):
        if self.mature_days <= 0 or t is None:
            return
        keep = []
        for due, delay in self.pending.get(oem, []):
            if due <= t - self.mature_days:
                bisect.insort(self.delays.setdefault(oem, []), delay)
            else:
                keep.append((due, delay))
        self.pending[oem] = keep

    def normal_delay(self, oem, grace, t=None, q=DELAY_QUANTILE):
        """Largest posting delay we still call normal, or None = no evidence yet (wait if safe)."""
        self._mature(oem, t)
        d = self.delays.get(oem, [])
        if len(d) < MIN_HISTORY:
            return None if self.patient else grace + PRIOR_EXTRA_DAYS
        idx = min(len(d) - 1, max(0, math.ceil(q * len(d)) - 1))
        return max(grace, d[idx])

    def n(self, oem):
        return len(self.delays.get(oem, []))


def _data_error(core, t, parts, policies):
    """Return a reason string if the record cannot be classified safely, else None."""
    if core.part_no not in parts:
        return f"unknown part number {core.part_no}"
    if core.oem not in policies:
        return f"no return policy on file for {core.oem}"
    if core.shipped_day is not None and core.shipped_day < core.removed_day:
        return "shipped before it was removed"
    if core.received_day is not None and (core.shipped_day is None or core.received_day < core.shipped_day):
        return "received before it was shipped (or receipt with no shipment)"
    if core.credit_day is not None and (core.received_day is None or core.credit_day < core.received_day):
        return "credit posted before the OEM received the core"
    if core.credit_amount is not None and core.credit_amount < 0:
        return "negative credit amount"
    return None


def assess(core, t, parts, policies, history, next_check_day, cfg=V1):
    bad = _data_error(core, t, parts, policies)
    if bad:
        # never crash and never invent a dispute: route to a human with the reason
        return Assessment(core.core_id, "done", AT_RISK, "data_error", 0.0, None,
                          f"cannot classify: {bad}; review the record", {})
    part, pol = parts[core.part_no], policies[core.oem]
    deadline = ship_by(core, pol)
    ent = entitlement(core, part, pol)

    # ---- return-window track -------------------------------------------------
    if core.shipped_day is None:
        left = deadline - t
        if left < 0:
            return Assessment(core.core_id, "done", CLOSED, "window_missed", ent, left,
                              f"not shipped by ship-by day {deadline}; return window lost",
                              {"ship_by": deadline})
        if deadline - next_check_day < SHIP_MARGIN:
            return Assessment(core.core_id, "shipping", ACTION, "ship_by", ent, left,
                              f"ship now: next look is day {next_check_day}, leaving under "
                              f"{SHIP_MARGIN} days of slack before ship-by day {deadline}",
                              {"ship_by": deadline, "next_check": next_check_day})
        state = AT_RISK if left <= SHIP_LOOKAHEAD else PENDING
        return Assessment(core.core_id, "shipping", state, "ship_by", ent, left,
                          f"{left} days to ship-by day {deadline}; still safe to wait",
                          {"ship_by": deadline})
    if core.shipped_day > deadline:
        return Assessment(core.core_id, "done", CLOSED, "window_missed", ent, None,
                          f"shipped day {core.shipped_day}, after ship-by day {deadline}",
                          {"ship_by": deadline, "shipped_day": core.shipped_day})

    # ---- receipt (carrier) track --------------------------------------------
    if core.received_day is None:
        expected = core.shipped_day + pol.transit_days
        if t > expected + TRANSIT_ESCALATE:
            return Assessment(core.core_id, "transit", ACTION, "transit_unconfirmed", ent, None,
                              f"no receipt confirmation {t - expected} days after expected arrival "
                              f"(day {expected}); open a carrier trace / OEM inquiry now",
                              {"expected_arrival": expected})
        if t > expected + TRANSIT_GRACE:
            return Assessment(core.core_id, "transit", AT_RISK, "transit_unconfirmed", ent, None,
                              f"no receipt confirmation {t - expected} days after expected arrival "
                              f"(day {expected}); a lost core looks like a slow credit, so trace it now",
                              {"expected_arrival": expected})
        return Assessment(core.core_id, "transit", PENDING, "ok", ent, None,
                          "in transit", {"expected_arrival": expected})

    # ---- credit track ---------------------------------------------------------
    due = core.received_day + pol.posting_days
    dispute_deadline = due + pol.grace_days + pol.dispute_window_days
    left = dispute_deadline - t
    ev = {"credit_due": due, "grace_until": due + pol.grace_days, "dispute_deadline": dispute_deadline,
          "expected_credit": ent, "condition_recorded": core.condition,
          "received_day": core.received_day}

    if core.credit_amount is None:
        if t <= due + pol.grace_days:
            return Assessment(core.core_id, "credit", PENDING, "ok", ent, left,
                              f"credit due day {due} (+{pol.grace_days} grace); not overdue yet", ev)
        overdue = t - (due + pol.grace_days)
        normal = history.normal_delay(core.oem, pol.grace_days, t)
        tail = None if normal is None else normal - pol.grace_days
        ev.update({"overdue_days": overdue, "normal_slow_tail_days": tail,
                   "history_n": history.n(core.oem)})
        if left < 0:
            return Assessment(core.core_id, "credit", CLOSED, "credit_missing", ent, left,
                              "dispute window has closed", ev, expired=True)
        cannot_wait = dispute_deadline - next_check_day < URGENT_MARGIN
        if tail is not None and overdue > tail:
            return Assessment(core.core_id, "credit", ACTION, "credit_missing", ent, left,
                              f"credit {overdue} days past grace, longer than any delay seen for "
                              f"{core.oem} (normal tail {tail} days)", ev)
        if cannot_wait:
            return Assessment(core.core_id, "credit", ACTION, "credit_missing", ent, left,
                              f"credit {overdue} days overdue and the next look (day {next_check_day}) "
                              f"would leave under {URGENT_MARGIN} days to dispute", ev)
        if tail is None:
            return Assessment(core.core_id, "credit", AT_RISK, "credit_missing", ent, left,
                              f"credit {overdue} days past grace; not enough settled history for {core.oem} "
                              f"to know what is normal, so waiting while it is still safe", ev)
        return Assessment(core.core_id, "credit", AT_RISK, "credit_missing", ent, left,
                          f"credit {overdue} days past grace but inside the normal slow-posting tail "
                          f"({tail} days); waiting is still safe", ev)

    if core.credit_amount + TOL >= ent:
        return Assessment(core.core_id, "done", CLOSED, "ok", 0.0, None,
                          "credit matches or exceeds the entitled amount", ev)

    shortfall = round(ent - core.credit_amount, 2)
    if cfg.materiality and shortfall < max(cfg.materiality_abs, cfg.materiality_rel * ent):
        return Assessment(core.core_id, "done", CLOSED, "ok", 0.0, None,
                          f"shortfall ${shortfall:.2f} is below the materiality threshold; not worth a dispute", ev)
    ev.update({"received_credit": core.credit_amount, "credit_part_no": core.credit_part_no,
               "shortfall": shortfall})
    expired = left < 0
    wrong = core.credit_part_no != core.part_no and core.credit_part_no == part.supersedes
    kind = "wrong_number" if wrong else "excess_deduction"
    if wrong:
        why = (f"credit posted against superseded part {core.credit_part_no}; part returned was "
               f"{core.part_no}; shortfall ${shortfall:.2f}")
    elif core.condition == "damaged":
        why = (f"deduction exceeds the {pol.max_damage_deduction:.0%} damage allowance; "
               f"shortfall ${shortfall:.2f}")
    else:
        why = f"core recorded as good but credit is ${shortfall:.2f} short"
    if expired:
        return Assessment(core.core_id, "credit", CLOSED, kind, shortfall, left, why + "; window closed",
                          ev, expired=True)
    if cfg.zero_credit_rule and core.credit_amount < TOL and core.condition == "damaged":
        return Assessment(core.core_id, "credit", AT_RISK, kind, shortfall, left,
                          "$0 credit on a core recorded as damaged: likely an OEM rejection; review the "
                          "inspection evidence before disputing", ev)
    return Assessment(core.core_id, "credit", ACTION, kind, shortfall, left, why, ev)


class NaiveHistory(PostingHistory):
    """Baseline for experiments: no learned tail, so any credit past grace is immediately overdue."""

    def __init__(self):
        super().__init__(mature_days=0, patient=False)

    def normal_delay(self, oem, grace, t=None, q=DELAY_QUANTILE):
        return grace
