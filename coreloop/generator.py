"""Synthetic ledger generator with HIDDEN ground-truth leaks.

Since the refactor the heavy lifting lives in lifecycle.py: each core gets a full lifecycle
(`Life`), and make_ledger() observes all lives on one audit day T, hiding everything later.
`Core.truth` records what is actually wrong at day T; the audit never reads it.

Leak types (rates are assumptions, see docs/ASSUMPTIONS.md): never_shipped, shipped_late,
credit_missing, wrong_number, excess_deduction, and slow_credit (not a real leak: a confounder).
Other confounders: legitimate damage deductions, rounding noise, credits not yet due, cores in transit.
"""
import random

from .catalog import PARTS, POLICIES
from .lifecycle import LEAK_RATES, TOL, make_life, observe  # noqa: F401  (re-exported)
from .models import Ledger


def make_ledger(seed, n_cores=300, audit_day=90, leak_scale=1.0, damaged_share=0.15):
    rng = random.Random(seed)
    cores = []
    for cid in range(n_cores):
        life = make_life(rng, cid, audit_day, damaged_share, leak_scale)
        cores.append(observe(life, audit_day, with_truth=True))
    return Ledger(audit_day=audit_day, cores=cores, parts=PARTS, policies=POLICIES)
