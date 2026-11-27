"""The lifecycle refactor must not change a single byte of the original synthetic ledgers."""
import hashlib
import json
from pathlib import Path

from coreloop.generator import make_ledger

SAVED = json.loads((Path(__file__).parent / "legacy_ledger_hashes.json").read_text())


def _h(L):
    return hashlib.sha256(json.dumps([c.__dict__ for c in L.cores], sort_keys=True, default=str).encode()).hexdigest()


def test_ledgers_identical_to_pre_refactor():
    for s in range(6):
        assert _h(make_ledger(s)) == SAVED[str(s)]
        assert _h(make_ledger(s, leak_scale=2.0, audit_day=120)) == SAVED[f"{s}b"]
