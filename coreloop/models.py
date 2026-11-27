"""Data model for CoreLoop.

Everything here is SYNTHETIC. OEM policies, part numbers, core values and
probabilities are invented, editable assumptions (see docs/ASSUMPTIONS.md).
They are not real OEM rules.
"""
from dataclasses import dataclass
from typing import Dict, Optional

# Day numbering: day 0 is a Monday. Days with day % 7 in (5, 6) are weekends.
WEEKEND = (5, 6)


def is_business_day(day: int) -> bool:
    return day % 7 not in WEEKEND


def next_business_day(day: int) -> int:
    """First business day >= day."""
    while not is_business_day(day):
        day += 1
    return day


def prev_business_day(day: int) -> int:
    """Last business day <= day."""
    while not is_business_day(day):
        day -= 1
    return day


@dataclass(frozen=True)
class OEMPolicy:
    name: str
    window_days: int            # core must REACH the OEM within this many days of removal
    transit_days: int           # so the ship-by day is removed_day + window - transit
    posting_days: int           # OEM should post the credit this many days after receipt
    grace_days: int             # extra days before we call a missing credit "missing"
    max_damage_deduction: float # largest legitimate deduction (fraction of core value)
    dispute_window_days: int    # days after (credit due + grace) in which a dispute is accepted
    freight_cost: float         # fixed cost of one shipment to this OEM (assumption)


@dataclass(frozen=True)
class Part:
    part_no: str
    oem: str
    core_value: float
    supersedes: Optional[str] = None  # older part number this one replaced


@dataclass
class Core:
    """One removed part with a refundable core charge, as seen in the ledger at audit day T.

    Fields before `truth` are what a real system would hold. `truth` is hidden
    ground truth used ONLY to score the audit; the audit never reads it.
    """
    core_id: int
    ro_id: int
    part_no: str
    oem: str
    removed_day: int
    condition: str                       # "good" | "damaged", recorded by the dealer at removal
    shipped_day: Optional[int]           # None = not shipped by audit day
    received_day: Optional[int]          # OEM receipt day, None = not received by audit day
    credit_amount: Optional[float]       # None = no credit visible by audit day
    credit_part_no: Optional[str]        # part number printed on the credit memo
    credit_day: Optional[int]
    truth: str = "clean"                 # hidden label, see generator.py


@dataclass
class Ledger:
    audit_day: int
    cores: list
    parts: Dict[str, Part]
    policies: Dict[str, OEMPolicy]


def ship_by(core: Core, policy: OEMPolicy) -> int:
    """Last day the core may leave the dealership and still arrive inside the window."""
    return core.removed_day + policy.window_days - policy.transit_days


def entitlement(core: Core, part: Part, policy: OEMPolicy) -> float:
    """Minimum credit the dealer is entitled to for an on-time core."""
    if core.condition == "damaged":
        return round(part.core_value * (1.0 - policy.max_damage_deduction), 2)
    return round(part.core_value, 2)
