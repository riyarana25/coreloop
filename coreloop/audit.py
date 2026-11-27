"""Rule-based audit. Reads only observable ledger fields, never `Core.truth`.

For every core it decides one of:
  at_risk          not shipped yet, ship-by day is close (act now)
  window_missed    return window already lost (preventable earlier, not recoverable)
  credit_missing   shipped on time, credit overdue past grace
  wrong_number     credit issued at the superseded part number's value
  excess_deduction credit lower than the policy-allowed minimum
Nothing is reported for cores that are fine or legitimately still pending.
"""
from dataclasses import dataclass, field
from typing import Optional

from .generator import TOL
from .models import entitlement, ship_by

CREDIT_KINDS = ("credit_missing", "wrong_number", "excess_deduction")


@dataclass
class Finding:
    core_id: int
    kind: str
    amount: float                 # $ at stake: shortfall for credit kinds, entitlement otherwise
    days_left: Optional[int]      # at_risk: days to ship-by; credit kinds: days to dispute deadline
    recoverable: bool             # credit kinds still inside the dispute window
    expired: bool                 # credit kinds past the dispute deadline
    evidence: dict = field(default_factory=dict)


def audit(ledger, at_risk_days=5):
    T = ledger.audit_day
    out = []
    for c in ledger.cores:
        part = ledger.parts[c.part_no]
        pol = ledger.policies[c.oem]
        deadline = ship_by(c, pol)
        ent = entitlement(c, part, pol)

        if c.shipped_day is None:
            if T > deadline:
                out.append(Finding(c.core_id, "window_missed", ent, None, False, False,
                                   {"ship_by": deadline}))
            elif deadline - T <= at_risk_days:
                out.append(Finding(c.core_id, "at_risk", ent, deadline - T, True, False,
                                   {"ship_by": deadline}))
            continue

        if c.shipped_day > deadline:
            out.append(Finding(c.core_id, "window_missed", ent, None, False, False,
                               {"ship_by": deadline, "shipped_day": c.shipped_day}))
            continue

        if c.received_day is None:
            continue  # in transit
        due = c.received_day + pol.posting_days
        dispute_deadline = due + pol.grace_days + pol.dispute_window_days
        days_left = dispute_deadline - T

        if c.credit_amount is None:
            if T > due + pol.grace_days:
                out.append(Finding(c.core_id, "credit_missing", ent, days_left, days_left >= 0,
                                   days_left < 0,
                                   {"credit_due": due, "expected": ent, "received": 0.0}))
            continue

        if c.credit_amount + TOL >= ent:
            continue  # credit is fine (or higher than entitled)
        shortfall = round(ent - c.credit_amount, 2)
        wrong = c.credit_part_no != c.part_no and c.credit_part_no == part.supersedes
        kind = "wrong_number" if wrong else "excess_deduction"
        out.append(Finding(c.core_id, kind, shortfall, days_left, days_left >= 0, days_left < 0,
                           {"credit_due": due, "expected": ent, "received": c.credit_amount,
                            "credit_part_no": c.credit_part_no, "condition": c.condition}))
    return out
