"""Adversarial and regression tests. Each test is an attack on one claim; see tests/test_strategy.md."""
import dataclasses
import os
import random
import tempfile
import time

import pytest

from audit.temporal_credit_classifier import ACTION, AT_RISK, CLOSED, PENDING, PostingHistory, assess
from coreloop.catalog import PARTS, POLICIES
from coreloop.lifecycle import make_lives, observe, reship
from coreloop.models import Core, is_business_day, ship_by
from data.store import Store
from ledger import operations as ops
from shipping.freight_cost_model import FreightParams, plan_freight, shipment_cost

PART = "A-1100"          # OEM-A, no supersession
POL = POLICIES["OEM-A"]
VAL = PARTS[PART].core_value


def core(**kw):
    base = dict(core_id=1, ro_id=1, part_no=PART, oem="OEM-A", removed_day=0, condition="good", shipped_day=None,
                received_day=None, credit_amount=None, credit_part_no=None, credit_day=None)
    base.update(kw)
    return Core(**base)


def hist(delays=()):
    h = PostingHistory(mature_days=0, patient=False)
    for i, d in enumerate(delays):
        h.add("OEM-A", d, i)
    return h


def run(c, t, nxt=None, h=None):
    return assess(c, t, PARTS, POLICIES, h or hist(), nxt if nxt is not None else t + 1)


# ---------- A. leakage ------------------------------------------------------------------
def test_A1_latent_draws_cannot_change_any_assessment():
    lives = make_lives(3, n_cores=120)
    rng = random.Random(1)
    t = 90
    base = [run_obs(observe(l, t), t) for l in lives]
    for l in lives:
        l.u_win, l.u_submit, l.u_ship, l.cash_lag, l.clean_delay = rng.random(), rng.random(), rng.random(), 99, 99
    assert base == [run_obs(observe(l, t), t) for l in lives]


def run_obs(c, t):
    a = assess(c, t, PARTS, POLICIES, PostingHistory(0, False), t + 1)
    return (a.core_id, a.state, a.kind, a.amount)


def test_A2_observe_hides_everything_after_t():
    for l in make_lives(4, n_cores=200):
        for t in (30, 90, 150):
            o = observe(l, t)
            assert o.truth == ""
            for day in (o.shipped_day, o.received_day, o.credit_day):
                assert day is None or day <= t
            if o.credit_day is None:
                assert o.credit_amount is None and o.credit_part_no is None


# ---------- B. boundaries ---------------------------------------------------------------
def test_B1_ship_by_boundary():
    sb = ship_by(core(), POL)
    assert run(core(shipped_day=sb, received_day=sb + POL.transit_days), sb + 1).kind != "window_missed"
    assert run(core(shipped_day=sb + 1, received_day=sb + 1 + POL.transit_days), sb + 5).kind == "window_missed"


def test_B2_window_shorter_than_transit_is_lost_immediately():
    pols = {"OEM-A": dataclasses.replace(POL, window_days=2, transit_days=3)}
    a = assess(core(), 1, PARTS, pols, hist(), 2)
    assert a.kind == "window_missed" and a.state == CLOSED


def test_B3_credit_exactly_at_entitlement_and_within_tolerance():
    c = core(shipped_day=5, received_day=8, credit_amount=VAL, credit_part_no=PART, credit_day=25)
    assert run(c, 40).state == CLOSED
    c2 = dataclasses.replace(c, credit_amount=VAL - 0.99)
    assert run(c2, 40).state == CLOSED


def test_B4_credit_larger_than_entitlement_is_not_a_dispute():
    c = core(shipped_day=5, received_day=8, credit_amount=VAL + 50, credit_part_no=PART, credit_day=25)
    assert run(c, 40).state == CLOSED


def test_B5_dispute_window_closing_exactly():
    c = core(shipped_day=5, received_day=8)                                 # due = 8 + 14
    due = 8 + POL.posting_days
    last = due + POL.grace_days + POL.dispute_window_days
    assert run(c, last, h=hist([0] * 60)).state == ACTION
    assert run(c, last + 1, h=hist([0] * 60)).state == CLOSED


# ---------- C. hostile / broken data ----------------------------------------------------
@pytest.mark.parametrize("kw", [
    dict(part_no="ZZZ-999"),
    dict(oem="OEM-Q"),
    dict(shipped_day=-5),
    dict(shipped_day=10, received_day=5),
    dict(received_day=9),
    dict(shipped_day=5, received_day=8, credit_amount=10.0, credit_day=3),
    dict(shipped_day=5, received_day=8, credit_amount=-40.0, credit_part_no=PART, credit_day=30),
])
def test_C1_bad_records_never_crash_and_never_become_disputes(kw):
    a = run(core(**kw), 50)
    assert a.kind == "data_error" and a.state == AT_RISK


def test_C2_extreme_outlier_in_history_cannot_make_us_wait_past_the_deadline():
    c = core(shipped_day=5, received_day=8)
    due = 8 + POL.posting_days
    t = due + POL.grace_days + POL.dispute_window_days - 2
    a = run(c, t, nxt=t + 7, h=hist([0] * 60 + [300]))
    assert a.state == ACTION                                           # cannot wait for the next look


def test_C3_history_of_only_instant_posting_does_not_flag_inside_grace():
    c = core(shipped_day=5, received_day=8)
    due = 8 + POL.posting_days
    assert run(c, due + POL.grace_days, h=hist([0] * 100)).state == PENDING


def test_C4_thin_history_waits_instead_of_guessing_when_safe():
    pats = PostingHistory(mature_days=40, patient=True)
    c = core(shipped_day=5, received_day=8)
    due = 8 + POL.posting_days
    a = assess(c, due + POL.grace_days + 3, PARTS, POLICIES, pats, due + POL.grace_days + 4)
    assert a.state == AT_RISK


def test_C5_materiality_boundary():
    thr = max(5.0, 0.02 * VAL)
    c = core(shipped_day=5, received_day=8, credit_amount=VAL - (thr - 0.01), credit_part_no=PART, credit_day=25)
    if thr - 0.01 > 1.0:
        assert run(c, 40).state == CLOSED
    c2 = dataclasses.replace(c, credit_amount=VAL - (thr + 1))
    assert run(c2, 40).state == ACTION


def test_C6_zero_credit_good_condition_is_disputed_but_damaged_is_reviewed():
    base = dict(shipped_day=5, received_day=8, credit_amount=0.0, credit_part_no=PART, credit_day=25)
    assert run(core(**base), 40).state == ACTION
    assert run(core(condition="damaged", **base), 40).state == AT_RISK


# ---------- D. shipping -----------------------------------------------------------------
@pytest.fixture()
def db(monkeypatch):
    path = os.path.join(tempfile.mkdtemp(), "t.sqlite")
    monkeypatch.setenv("CORELOOP_DB", path)
    return path


def world(s):
    return ops.build_world(s.get("seed"), s.get("n_cores"), s.get("today"), s.decisions())


def test_D1_planned_days_are_business_days_and_meet_deadlines(db):
    s = Store(db)
    for today in (100, 130, 131, 132, 133):          # includes weekend start days
        s.set("today", today)
        w = world(s)
        plan = ops.plan_shipments(w, 1)
        for (oem, day), ids in plan["schedule"].items():
            assert is_business_day(day) and day >= today
            for cid in ids:
                c = plan["cores_by_id"][cid]
                assert day <= ship_by(c, POLICIES[oem])


def test_D2_empty_ledger_plans_nothing(db):
    s = Store(db)
    s.set("today", -1)
    plan = ops.plan_shipments(world(s), 1)
    assert plan["events"] == 0 and plan["freight"] == 0.0


def test_D3_waiting_longer_never_saves_cores(db):
    s = Store(db)
    w = world(s)
    lost = [ops.counterfactual_wait(w, d, 1)["wait"]["cores_lost"] for d in (1, 2, 3, 5, 7)]
    assert lost == sorted(lost)


def test_D4_late_reship_forfeits_and_on_time_reship_recovers():
    l = next(x for x in make_lives(11, n_cores=300) if x.leak == "never_shipped")
    late = reship(l, l.deadline + 2, POLICIES)
    assert late.credit_amount is None
    ok = reship(l, l.removed_day + 1, POLICIES)
    assert ok.credit_amount is not None


def test_D5_freight_is_never_negative_and_capacity_overflow_adds_a_load():
    fp = FreightParams()
    c1, n1, _ = shipment_cost("OEM-A", [100], fp)
    c2, n2, _ = shipment_cost("OEM-A", [300, 300], fp)
    assert c1 > 0 and n1 == 1 and n2 == 2


# ---------- E. dispute queue ------------------------------------------------------------
def test_E1_queue_respects_daily_minutes_and_runs_fast_under_flood(db):
    from types import SimpleNamespace
    from coreloop.disputes import plan_queue
    rng = random.Random(5)
    kinds = ["credit_missing", "wrong_number", "excess_deduction"]
    flood = [SimpleNamespace(core_id=i, kind=rng.choice(kinds), amount=rng.uniform(10, 500), days_left=rng.randint(0, 40),
                             recoverable=True) for i in range(400)]
    t0 = time.time()
    plan, _ = plan_queue(flood, daily_minutes=120, horizon=10, time_limit=5.0)
    assert time.time() - t0 < 15
    from coreloop.disputes import effort
    for t, fs in plan.items():
        assert sum(effort(f) for f in fs) <= 120
        assert all(t <= f.days_left for f in fs)


def test_E2_double_click_submits_once(db):
    s = Store(db)
    w = world(s)
    q, _ = ops.dispute_queue(w)
    for _ in range(3):
        ops.decide(s, w, q[0]["core_id"], q[0]["kind"], "approve")
    assert sum(1 for d in s.decisions() if d["action"] == "approve") == 1


def test_E3_sql_metacharacters_in_notes_are_stored_literally(db):
    s = Store(db)
    w = world(s)
    q, _ = ops.dispute_queue(w)
    nasty = "x'); DROP TABLE decisions; --"
    ops.decide(s, w, q[0]["core_id"], q[0]["kind"], "dismiss", note=nasty)
    assert s.decisions()[-1]["note"] == nasty and len(s.decisions()) == 1


# ---------- F. determinism and reproducibility ------------------------------------------
def test_F1_same_seed_same_world(db):
    s = Store(db)
    a, b = world(s), world(s)
    assert [(k, v.state, v.kind, v.amount) for k, v in a.assessments.items()] == \
           [(k, v.state, v.kind, v.amount) for k, v in b.assessments.items()]


def test_F2_policy_results_do_not_depend_on_which_other_policies_ran():
    from simulation.engine import POLICIES_UNDER_TEST, Params, simulate
    lives = make_lives(21, n_cores=200)
    D = POLICIES_UNDER_TEST[4]
    alone = simulate(lives, POLICIES, D, Params(), seed=3)
    for spec in POLICIES_UNDER_TEST[:4]:
        simulate(lives, POLICIES, spec, Params(), seed=3)
    after = simulate(lives, POLICIES, D, Params(), seed=3)
    assert alone["total_loss"] == after["total_loss"] and alone["net_benefit"] == after["net_benefit"]


def test_F3_simulator_does_not_mutate_the_input_lives():
    from simulation.engine import POLICIES_UNDER_TEST, Params, simulate
    lives = make_lives(22, n_cores=150)
    snap = [dataclasses.astuple(l) for l in lives]
    for spec in POLICIES_UNDER_TEST:
        simulate(lives, POLICIES, spec, Params(), seed=1)
    assert snap == [dataclasses.astuple(l) for l in lives]


def test_F4_no_audit_reference_recovers_nothing():
    from simulation.engine import POLICIES_UNDER_TEST, Params, simulate
    r = simulate(make_lives(23, n_cores=200), POLICIES, POLICIES_UNDER_TEST[0], Params(), seed=1)
    assert r["cash_received"] == 0 and r["net_benefit"] == 0
