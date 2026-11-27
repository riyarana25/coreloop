"""Temporal credit classifier: hand-built cases, information gating, truth isolation, freight model."""
import copy
import dataclasses

from audit.manual_cases import run_all
from audit.temporal_credit_classifier import PostingHistory, assess
from coreloop.catalog import PARTS, POLICIES
from coreloop.lifecycle import make_lives, observe
from shipping.freight_cost_model import FreightParams, shipment_cost, split_loads


def test_manual_cases_all_pass():
    bad = [r for r in run_all() if not r[3]]
    assert not bad, bad


def _states(lives, t, mutate=None):
    out = []
    for l in lives:
        l2 = mutate(l) if mutate else l
        a = assess(observe(l2, t), t, PARTS, POLICIES, PostingHistory(0, False), t + 1)
        out.append((a.core_id, a.state, a.kind, round(a.amount, 2)))
    return out


def test_information_gating_future_fields_do_not_change_assessment():
    """Changing anything that happens AFTER day t must not change what the classifier says on day t."""
    lives = make_lives(11, n_cores=150)
    t = 60

    def scramble_future(l):
        l2 = copy.copy(l)
        if l2.credit_day is not None and l2.credit_day > t:
            l2 = dataclasses.replace(l2, credit_amount=l2.credit_amount + 999.0, credit_day=l2.credit_day + 40)
        return l2

    assert _states(lives, t) == _states(lives, t, scramble_future)


def test_truth_label_is_never_used():
    """Scrambling the hidden truth label cannot change any assessment."""
    lives = make_lives(12, n_cores=150)

    def scramble_label(l):
        return dataclasses.replace(l, leak="clean") if hasattr(l, "leak") else l

    assert _states(lives, 80) == _states(lives, 80, scramble_label)


def test_freight_split_respects_capacity_and_cost_monotone():
    fp = FreightParams()
    loads = split_loads([300, 300, 300, 100], fp.capacity_lb)
    assert all(sum(l) <= fp.capacity_lb for l in loads)
    c1, n1, _ = shipment_cost("OEM-B", [20, 20], fp)
    c2, n2, _ = shipment_cost("OEM-B", [20, 20, 20], fp)
    assert n1 == n2 == 1 and c2 > c1          # more weight and packaging never cost less
    far, _, _ = shipment_cost("OEM-B", [50], fp)
    near, _, _ = shipment_cost("OEM-C", [50], fp)
    assert far > near
