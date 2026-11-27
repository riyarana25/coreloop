"""Hand-constructed classifier cases (no generator involved). Used by tests and by validation.

Policy used: OEM-A (window 21, transit 3, posting 14, grace 3, damage cap 30%, dispute window 60).
Removed day 0 => ship-by day 18. Shipped day 10 => received day 13 => credit due day 27.
"""
from audit.independent_generator import IND_PARTS, IND_POLICIES
from audit.temporal_credit_classifier import PostingHistory
from coreloop.catalog import PARTS, POLICIES
from coreloop.models import Core


def core(part="A-1204", cond="good", ship=None, recv=None, credit=None, cpart=None, cday=None, removed=0):
    cpart = cpart if cpart is not None else (part if credit is not None else None)
    return Core(1, 5000, part, PARTS[part].oem if part in PARTS else IND_PARTS[part].oem, removed, cond,
                ship, recv, credit, cpart, cday)


def hist(delays=()):
    h = PostingHistory(mature_days=0, patient=False)   # hand-built: prior of grace+7 unless delays given
    for d in delays:
        h.add("OEM-A", d)
    return h


# name, core, t, next_check_day, history, expected (state, kind)
CASES = [
    ("unshipped, far from ship-by", core(), 3, 4, hist(), ("pending", "ship_by")),
    ("unshipped, 6 days left", core(), 12, 13, hist(), ("at_risk", "ship_by")),
    ("unshipped, 4 days left: ship now", core(), 14, 15, hist(), ("action_required", "ship_by")),
    ("unshipped past ship-by", core(), 19, 20, hist(), ("closed", "window_missed")),
    ("periodic audit cannot wait for next look", core(), 3, 93, hist(), ("action_required", "ship_by")),
    ("shipped after ship-by day", core(ship=20, recv=23), 25, 26, hist(), ("closed", "window_missed")),
    ("in transit, not yet expected", core(ship=10), 11, 12, hist(), ("pending", "ok")),
    ("receipt unconfirmed 5 days after expected", core(ship=10), 18, 19, hist(), ("at_risk", "transit_unconfirmed")),
    ("receipt unconfirmed 11 days after expected", core(ship=10), 24, 25, hist(), ("action_required", "transit_unconfirmed")),
    ("credit not yet due", core(ship=10, recv=13), 20, 21, hist(), ("pending", "ok")),
    ("credit inside grace period", core(ship=10, recv=13), 30, 31, hist(), ("pending", "ok")),
    ("credit overdue, inside slow tail, can wait", core(ship=10, recv=13), 33, 34, hist(), ("at_risk", "credit_missing")),
    ("credit overdue beyond any delay seen", core(ship=10, recv=13), 38, 39, hist(), ("action_required", "credit_missing")),
    ("credit overdue, next look would be too late", core(ship=10, recv=13), 33, 123, hist(), ("action_required", "credit_missing")),
    ("learned tail (12 days) extends the wait", core(ship=10, recv=13), 38, 39, hist([0, 1, 2, 3] * 15 + [12] * 3),
     ("at_risk", "credit_missing")),
    ("missing credit after dispute window closed", core(ship=10, recv=13), 91, 92, hist(), ("closed", "credit_missing")),
    ("correct credit", core(ship=10, recv=13, credit=140.0, cday=27), 40, 41, hist(), ("closed", "ok")),
    ("slight overpayment", core(ship=10, recv=13, credit=150.0, cday=27), 40, 41, hist(), ("closed", "ok")),
    ("short by $0.80 (inside $1 tolerance)", core(ship=10, recv=13, credit=139.2, cday=27), 40, 41, hist(), ("closed", "ok")),
    ("short by $1.50 on a $60 core: below materiality, not worth a dispute", core("A-3050", ship=10, recv=13, credit=58.5, cday=27),
     40, 41, hist(), ("closed", "ok")),
    ("short by $12 on a $60 core: material", core("A-3050", ship=10, recv=13, credit=48.0, cday=27),
     40, 41, hist(), ("action_required", "excess_deduction")),
    ("$0 credit on a damaged core: likely legitimate rejection, review only", core(cond="damaged", ship=10, recv=13, credit=0.0, cday=27),
     40, 41, hist(), ("at_risk", "excess_deduction")),
    ("$0 credit on a good-condition core: dispute", core(ship=10, recv=13, credit=0.0, cday=27),
     40, 41, hist(), ("action_required", "excess_deduction")),
    ("legitimate 20% damage deduction", core(cond="damaged", ship=10, recv=13, credit=112.0, cday=27), 40, 41, hist(),
     ("closed", "ok")),
    ("damage deduction of 50% exceeds the 30% cap", core(cond="damaged", ship=10, recv=13, credit=70.0, cday=27), 40, 41,
     hist(), ("action_required", "excess_deduction")),
    ("good core deducted 20%", core(ship=10, recv=13, credit=112.0, cday=27), 40, 41, hist(),
     ("action_required", "excess_deduction")),
    ("credit at superseded part number", core("A-2310", ship=10, recv=13, credit=410.0, cpart="A-2301", cday=27), 40, 41,
     hist(), ("action_required", "wrong_number")),
    ("right part number, wrong amount", core("A-2310", ship=10, recv=13, credit=410.0, cpart="A-2310", cday=27), 40, 41,
     hist(), ("action_required", "excess_deduction")),
]

# Documented LIMITATION: only one supersession hop is followed.
TWO_HOP_LIMITATION = ("two-hop supersession is labelled excess_deduction, not wrong_number",
                      core("W-100", ship=5, recv=7, credit=150.0, cpart="W-090", cday=20), 40, 41, ("action_required", "excess_deduction"))


def run_all():
    from audit.temporal_credit_classifier import assess
    results = []
    for name, c, t, nxt, h, exp in CASES:
        a = assess(c, t, PARTS, POLICIES, h, nxt)
        results.append((name, (a.state, a.kind), exp, (a.state, a.kind) == exp))
    name, c, t, nxt, exp = TWO_HOP_LIMITATION
    h = PostingHistory(mature_days=0, patient=False)
    a = assess(c, t, IND_PARTS, IND_POLICIES, h, nxt)
    results.append((name, (a.state, a.kind), exp, (a.state, a.kind) == exp))
    return results
