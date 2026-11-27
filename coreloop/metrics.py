"""Score the audit against hidden ground truth."""
from .models import entitlement

CLASSES = ("window_missed", "credit_missing", "wrong_number", "excess_deduction")


def _true_dollars(core, ledger):
    part = ledger.parts[core.part_no]
    pol = ledger.policies[core.oem]
    ent = entitlement(core, part, pol)
    if core.truth in ("window_missed", "credit_missing"):
        return ent
    if core.truth in ("wrong_number", "excess_deduction"):
        return round(ent - core.credit_amount, 2)
    return 0.0


def score(ledger, findings):
    """Per-class precision/recall plus dollar recall, using Core.truth."""
    found = {}
    for f in findings:
        if f.kind in CLASSES:
            found[f.core_id] = f
    out = {}
    for cls in CLASSES:
        truth_ids = {c.core_id for c in ledger.cores if c.truth == cls}
        pred_ids = {cid for cid, f in found.items() if f.kind == cls}
        tp = len(truth_ids & pred_ids)
        fp = len(pred_ids - truth_ids)
        fn = len(truth_ids - pred_ids)
        by_id = {c.core_id: c for c in ledger.cores}
        d_true = sum(_true_dollars(by_id[i], ledger) for i in truth_ids)
        d_hit = sum(_true_dollars(by_id[i], ledger) for i in truth_ids & pred_ids)
        out[cls] = {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "dollars_true": round(d_true, 2), "dollars_found": round(d_hit, 2),
        }
    return out
