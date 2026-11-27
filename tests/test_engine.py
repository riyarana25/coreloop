import itertools
import random
import subprocess
import sys

import pytest

from coreloop.audit import CREDIT_KINDS, Finding, audit
from coreloop.catalog import ACTIVE_PARTS, PARTS, POLICIES
from coreloop.disputes import (DISPUTE_PARAMS, draft_dispute, effort, expected_value,
                               greedy_queue, plan_queue)
from coreloop.generator import TOL, make_ledger
from coreloop.metrics import score
from coreloop.models import entitlement, is_business_day, next_business_day, ship_by
from coreloop.shipping import compare, min_ship_days, run_policy


# ---------- generator ----------
def test_same_seed_same_ledger():
    a, b = make_ledger(3), make_ledger(3)
    assert [c.__dict__ for c in a.cores] == [c.__dict__ for c in b.cores]


def test_different_seed_differs():
    assert [c.__dict__ for c in make_ledger(1).cores] != [c.__dict__ for c in make_ledger(2).cores]


def test_nothing_visible_after_audit_day():
    for seed in range(10):
        L = make_ledger(seed)
        for c in L.cores:
            for d in (c.shipped_day, c.received_day, c.credit_day):
                assert d is None or d <= L.audit_day
            assert c.removed_day < L.audit_day


def test_leak_shortfalls_exceed_tolerance():
    """Injected credit leaks must be real shortfalls, otherwise detection is ill-posed."""
    for seed in range(30):
        L = make_ledger(seed, leak_scale=3.0)
        for c in L.cores:
            if c.truth in ("wrong_number", "excess_deduction"):
                ent = entitlement(c, PARTS[c.part_no], POLICIES[c.oem])
                assert ent - c.credit_amount > TOL + 0.5


# ---------- audit ----------
def test_audit_never_reads_truth():
    L = make_ledger(5)
    base = audit(L)
    for c in L.cores:
        c.truth = "SCRAMBLED"
    assert [f.__dict__ for f in audit(L)] == [f.__dict__ for f in base]


def test_audit_scores_high_on_synthetic_but_not_by_magic():
    # Rules mirror the generator, so recall on injected leaks is expected to be ~1.
    # The confounders (slow credits) must be the only source of false positives.
    fp_cm = tp_cm = 0
    for seed in range(40):
        L = make_ledger(seed)
        s = score(L, audit(L))
        for cls in ("window_missed", "wrong_number", "excess_deduction"):
            assert s[cls]["fp"] == 0
            assert s[cls]["fn"] == 0
        assert s["credit_missing"]["fn"] == 0
        fp_cm += s["credit_missing"]["fp"]
        tp_cm += s["credit_missing"]["tp"]
    n_slow = sum(1 for seed in range(40) for c in make_ledger(seed).cores if c.truth == "slow_credit")
    assert fp_cm == n_slow  # every false positive is a slow credit, nothing else
    assert fp_cm > 0        # the confounder actually bites


def test_clean_ledger_has_no_credit_findings():
    L = make_ledger(0, leak_scale=0.0)
    assert not [f for f in audit(L) if f.kind in CREDIT_KINDS]
    assert not [f for f in audit(L) if f.kind == "window_missed"]


def test_legit_damage_deduction_not_flagged():
    L = make_ledger(0, leak_scale=0.0, damaged_share=1.0)
    assert not [f for f in audit(L) if f.kind in CREDIT_KINDS]


def test_wrong_number_detected_via_supersession():
    found = [f for seed in range(40) for f in audit(make_ledger(seed)) if f.kind == "wrong_number"]
    assert found
    for f in found:
        assert PARTS[f.evidence["credit_part_no"]].core_value < f.evidence["expected"]


# ---------- shipping: optimality ----------
def _brute_min_points(intervals, days):
    for k in range(1, len(days) + 1):
        for pts in itertools.combinations(days, k):
            if all(any(lo <= p <= hi for p in pts) for lo, hi, _ in intervals):
                return k
    return 0


def test_stabbing_matches_brute_force():
    rng = random.Random(11)
    days = [d for d in range(0, 22) if is_business_day(d)]
    for _ in range(60):
        n = rng.randint(1, 7)
        ivs = []
        for i in range(n):
            lo = rng.choice(days[:-2])
            hi = rng.choice([d for d in days if d >= lo])
            ivs.append((lo, hi, i))
        got = min_ship_days(ivs)
        assert len(got) == _brute_min_points(ivs, days)
        # every interval is covered by the point it was assigned
        for day, keys in got.items():
            for k in keys:
                lo, hi, _ = ivs[k]
                assert lo <= day <= hi


def test_all_policies_cover_every_core_and_coreloop_never_ships_late():
    for seed in range(10):
        L = make_ledger(seed)
        for res in compare(L):
            assert sum(len(v) for v in res.schedule.values()) == len(L.cores)
        cl = run_policy("coreloop", L.cores, L)
        assert cl.missed == 0


def test_coreloop_beats_naive_policies_on_freight_without_missing():
    for seed in range(10):
        L = make_ledger(seed)
        each = run_policy("ship_each", L.cores, L)
        weekly = run_policy("weekly_friday", L.cores, L)
        cl = run_policy("coreloop", L.cores, L)
        assert cl.freight < weekly.freight < each.freight
        assert cl.missed == 0


def test_buffer_reduces_expected_misses_and_costs_shipments():
    L = make_ledger(0)
    r0 = run_policy("coreloop", L.cores, L, buffer_days=0)
    r3 = run_policy("coreloop", L.cores, L, buffer_days=3)
    assert r3.expected_missed < r0.expected_missed
    assert r3.shipments >= r0.shipments


def test_ship_days_are_business_days_and_after_removal():
    L = make_ledger(2)
    res = run_policy("coreloop", L.cores, L, buffer_days=1)
    by_id = {c.core_id: c for c in L.cores}
    for (oem, day), ids in res.schedule.items():
        assert is_business_day(day)
        for i in ids:
            assert day >= by_id[i].removed_day + 1


# ---------- dispute queue ----------
def _mk(kind, amount, days_left, cid):
    return Finding(cid, kind, amount, days_left, True, False, {})


def _brute_queue(items, minutes, horizon):
    best = 0.0
    opts = [[None] + [t for t in range(min(horizon, f.days_left + 1))] for f in items]
    for assign in itertools.product(*opts):
        used = [0] * horizon
        ok, val = True, 0.0
        for f, t in zip(items, assign):
            if t is None:
                continue
            used[t] += effort(f)
            if used[t] > minutes:
                ok = False
                break
            val += expected_value(f)
        if ok:
            best = max(best, val)
    return best


def test_queue_matches_brute_force():
    rng = random.Random(4)
    kinds = list(DISPUTE_PARAMS)
    for _ in range(25):
        items = [_mk(rng.choice(kinds), rng.choice([40, 120, 300, 700]), rng.randint(0, 3), i)
                 for i in range(rng.randint(2, 6))]
        _, total = plan_queue(items, daily_minutes=25, horizon=4)
        assert total == pytest.approx(_brute_queue(items, 25, 4), abs=0.02)


def test_queue_respects_capacity_and_deadlines():
    L = make_ledger(0)
    F = audit(L)
    plan, _ = plan_queue(F, daily_minutes=30, horizon=10)
    for t, fs in plan.items():
        assert sum(effort(f) for f in fs) <= 30
        for f in fs:
            assert t <= f.days_left


def test_queue_never_worse_than_greedy_baselines():
    for seed in range(15):
        F = audit(make_ledger(seed))
        _, opt = plan_queue(F, daily_minutes=30, horizon=10)
        for order in ("amount", "expiry"):
            assert opt >= greedy_queue(F, 30, 10, order)[1] - 0.01


def test_expired_findings_are_not_queued():
    F = audit(make_ledger(0))
    plan, _ = plan_queue(F)
    queued = {f.core_id for fs in plan.values() for f in fs}
    assert not [f for f in F if f.expired and f.core_id in queued]


def test_dispute_draft_uses_only_ledger_facts():
    L = make_ledger(0)
    F = [f for f in audit(L) if f.kind in CREDIT_KINDS]
    assert F
    for f in F:
        text = draft_dispute(f, L)
        c = next(c for c in L.cores if c.core_id == f.core_id)
        assert str(c.ro_id) in text and c.part_no in text


# ---------- determinism across processes ----------
def test_cross_process_determinism():
    code = ("from coreloop.generator import make_ledger;from coreloop.audit import audit;"
            "from coreloop.disputes import plan_queue;"
            "L=make_ledger(1);F=audit(L);print(plan_queue(F,30,10)[1], len(F))")
    outs = {subprocess.run([sys.executable, "-c", code], capture_output=True, text=True).stdout
            for _ in range(3)}
    assert len(outs) == 1 and outs != {""}
