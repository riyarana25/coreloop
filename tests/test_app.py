"""App smoke tests: every screen renders without an exception, and decisions really change state."""
import os
import tempfile
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from data.store import Store
from ledger import operations as ops

PAGES = ["Operations overview", "Core inventory & deadlines", "Shipment optimisation", "Credit monitoring",
         "Dispute queue", "Audit-frequency simulator", "Audit trail"]


@pytest.fixture()
def db(monkeypatch):
    path = os.path.join(tempfile.mkdtemp(), "t.sqlite")
    monkeypatch.setenv("CORELOOP_DB", path)
    return path


@pytest.mark.parametrize("page", PAGES)
def test_every_screen_renders(db, page):
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "ui" / "app.py"), default_timeout=90).run()
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception, [e.value for e in at.exception]


def _world(s):
    return ops.build_world(s.get("seed"), s.get("n_cores"), s.get("today"), s.decisions())


def test_ship_decision_changes_state_and_persists(db):
    s = Store(db)
    w = _world(s)
    alert = ops.ship_today_alerts(w)[0]
    before = w.assessments[alert.core_id]
    ops.decide(s, w, alert.core_id, "ship_by", "approve")
    s2 = Store(db)                        # new connection = persisted
    w2 = _world(s2)
    after = w2.assessments[alert.core_id]
    assert before.state == "action_required"
    assert after.track != "shipping" or after.state != "action_required"
    assert w2.cores[alert.core_id].shipped_day is not None


def test_dispute_decisions_remove_from_queue_and_defer_expires(db):
    s = Store(db)
    w = _world(s)
    q, _ = ops.dispute_queue(w)
    a, b = q[0]["core_id"], q[1]["core_id"]
    ops.decide(s, w, a, q[0]["kind"], "approve")
    ops.decide(s, w, b, q[1]["kind"], "defer", 3)
    w = _world(s)
    ids = {r["core_id"] for r in ops.dispute_queue(w)[0]}
    assert a not in ids and b not in ids
    ops.advance(s, 4)
    w = _world(s)
    assert b in {r["core_id"] for r in ops.dispute_queue(w)[0]} or w.assessments[b].state != "action_required"
    assert any(o["core_id"] == a for o in ops.dispute_outcomes(w))


def test_counterfactual_wait_never_improves_saved_cores(db):
    s = Store(db)
    w = _world(s)
    cf = ops.counterfactual_wait(w, 3, 1)
    assert cf["wait"]["cores_lost"] >= cf["base"]["cores_lost"]


def test_world_ignores_future_decisions(db):
    s = Store(db)
    w = _world(s)
    a = ops.ship_today_alerts(w)[0]
    s.add_decision(a.core_id, "ship_by", "approve", w.today + 5)       # a decision dated in the future
    w2 = _world(s)
    assert w2.cores[a.core_id].shipped_day == w.cores[a.core_id].shipped_day
