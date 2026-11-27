"""Validate the temporal classifier on data it was not built around.

Daily monitoring harness: for every day, every open core is assessed with ONLY the information visible
that day (observe(life, t)) and a posting-delay history learned from credits visible so far.
Compared: the temporal classifier vs a NAIVE rule (flag the moment a credit passes its grace period).

Datasets: (1) the original generator (different seeds), (2) the independent generator
(audit/independent_generator.py): other OEM tables, statement-cycle heavy-tailed posting, two-hop
supersession, lost cores, legitimate rejections. Plus 26 hand-built cases (audit/manual_cases.py).

    python audit/independent_validation.py [n_seeds=30]
"""
import statistics as stats
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from audit.independent_generator import (IND_PARTS, IND_POLICIES, RECOVERABLE,  # noqa: E402
                                         make_independent_lives)
from audit.manual_cases import run_all  # noqa: E402
from audit.temporal_credit_classifier import (ACTION, CLOSED, V0, V1, NaiveHistory, PostingHistory,  # noqa: E402
                                              TRANSIT_ESCALATE, assess)
from coreloop.catalog import PARTS, POLICIES  # noqa: E402
from coreloop.lifecycle import make_lives, observe  # noqa: E402

FLAG_KINDS = ("credit_missing", "wrong_number", "excess_deduction", "transit_unconfirmed")


def monitor(lives, parts, policies, history_cls, cfg=V1, horizon=420):
    """Return {core_id: (first_action_day, kind)} for credit/transit actions (daily, next look = tomorrow)."""
    by_day = defaultdict(list)
    for l in lives:
        if l.credit_day is not None and l.due is not None:
            by_day[l.credit_day].append(l)
    order = sorted(lives, key=lambda l: l.removed_day)
    hist, ptr, active, first = history_cls(), 0, [], {}
    for t in range(horizon + 1):
        for l in by_day.pop(t, ()):
            hist.add(l.oem, t - l.due, l.due)
        while ptr < len(order) and order[ptr].removed_day <= t:
            active.append(order[ptr])
            ptr += 1
        keep = []
        for l in active:
            a = assess(observe(l, t), t, parts, policies, hist, t + 1, cfg)
            if a.state == CLOSED:
                continue
            if a.state == ACTION and a.kind in FLAG_KINDS:
                first[l.core_id] = (t, a.kind)
                continue
            keep.append(l)
        active = keep
    return first


def earliest_observable(l, policies):
    pol = policies[l.oem]
    if l.leak == "credit_missing":
        return l.due + pol.grace_days + 1
    if l.leak == "lost_in_transit":
        return l.ship_day + pol.transit_days + TRANSIT_ESCALATE + 1
    return l.credit_day


def evaluate(lives, parts, policies, positives, history_cls, cfg=V1):
    first = monitor(lives, parts, policies, history_cls, cfg)
    pos = [l for l in lives if l.leak in positives]
    neg = [l for l in lives if l.leak not in positives and l.leak not in ("never_shipped", "shipped_late")]
    res = {"n_pos": len(pos), "n_neg": len(neg)}
    tp = [l for l in pos if l.core_id in first]
    fp = [l for l in neg if l.core_id in first]
    pol_dead = lambda l: l.due + policies[l.oem].grace_days + policies[l.oem].dispute_window_days if l.due else None  # noqa: E731
    res["recall"] = len(tp) / len(pos) if pos else None
    res["fpr"] = len(fp) / len(neg) if neg else None
    res["precision"] = len(tp) / (len(tp) + len(fp)) if (tp or fp) else None
    on_time = [l for l in tp if l.leak == "lost_in_transit" or first[l.core_id][0] <= pol_dead(l)]
    res["before_deadline"] = len(on_time) / len(pos) if pos else None
    delays = [first[l.core_id][0] - earliest_observable(l, policies) for l in tp]
    res["delay_mean"] = stats.fmean(delays) if delays else None
    res["fn_by_class"] = Counter(l.leak for l in pos if l.core_id not in first)
    res["fp_by_class"] = Counter(l.leak for l in fp)
    res["tp_by_class"] = Counter(l.leak for l in tp)
    res["pos_by_class"] = Counter(l.leak for l in pos)
    wn = [l for l in tp if l.leak == "wrong_number"]
    res["wrong_number_kind_acc"] = (sum(first[l.core_id][1] == "wrong_number" for l in wn) / len(wn)) if wn else None
    return res


def pool(rs):
    out = {}
    for k in ("recall", "fpr", "precision", "before_deadline", "delay_mean", "wrong_number_kind_acc"):
        vals = [r[k] for r in rs if r[k] is not None]
        out[k] = (stats.fmean(vals), min(vals), max(vals)) if vals else None
    for k in ("fn_by_class", "fp_by_class", "tp_by_class", "pos_by_class"):
        c = Counter()
        for r in rs:
            c.update(r[k])
        out[k] = c
    out["n_pos"] = sum(r["n_pos"] for r in rs)
    out["n_neg"] = sum(r["n_neg"] for r in rs)
    return out


def pct(v):
    return "n/a" if v is None else f"{100 * v[0]:.1f}% ({100 * v[1]:.0f}-{100 * v[2]:.0f})"


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    orig_pos = ("credit_missing", "wrong_number", "excess_deduction")
    runs = {}
    variants = [("first version (v0)", lambda: PostingHistory(0, False), V0),
                ("improved (v1)", PostingHistory, V1),
                ("naive overdue rule", NaiveHistory, V0)]
    for label, make, parts, pol, positives in [
        ("original generator, new seeds", lambda s: make_lives(5000 + s, n_cores=500), PARTS, POLICIES, orig_pos),
        ("INDEPENDENT generator, held-out seeds", lambda s: make_independent_lives(200 + s), IND_PARTS, IND_POLICIES, RECOVERABLE),
    ]:
        for hname, hf, cfg in variants:
            rs = [evaluate(make(s), parts, pol, positives, hf, cfg) for s in range(n)]
            runs[(label, hname)] = pool(rs)

    cases = run_all()
    L = ["# Credit classifier validation", "",
         "**SYNTHETIC data.** The independent generator differs in design (other OEM tables, statement-cycle heavy-tailed "
         "posting, two-hop supersession, lost cores, legitimate rejections, bigger rounding noise) but has the **same author** "
         f"as the classifier, so it is independent in construction, not in authorship. {n} seeds x 500 cores per dataset; "
         "values are mean (min-max across seeds). Each method sees only information visible on the current day.", "",
         "**Process, in order.** (1) First version (v0) measured on independent seeds 0-29: precision fell from 94% to 49%. "
         "(2) Diagnosed on seeds 0-9 only: most false positives were clean credits flagged missing because the learned delay "
         "history was right-censored (slow credits had not posted yet), plus rounding noise and zero-dollar rejections. "
         "(3) Fixed on principle (settled-history cohort, patience when history is thin, materiality threshold, zero-credit-on-damaged "
         "review rule), not by tuning constants. (4) **Re-scored on held-out seeds 200+ that were never used for diagnosis.**", "",
         "Positives = recoverable discrepancies (missing credit, wrong part number, over-deduction, lost-in-transit core). "
         "Negatives = clean credits, slow-posting credits and (independent set) legitimate OEM rejections. Window-missed cores are excluded.", "",
         "| Dataset | Method | Recall | Precision | False-positive rate | Detected before dispute deadline | Detection delay vs earliest naive flag (days) |",
         "|---|---|---|---|---|---|---|"]
    for (label, h), r in runs.items():
        dl = "n/a" if r["delay_mean"] is None else f"{r['delay_mean'][0]:.1f}"
        L.append(f"| {label} | {h} | {pct(r['recall'])} | {pct(r['precision'])} | {pct(r['fpr'])} | {pct(r['before_deadline'])} | {dl} |")
    ind_t = runs[("INDEPENDENT generator, held-out seeds", "improved (v1)")]
    L += ["", "## Where the classifier fails (independent generator, temporal classifier, pooled over seeds)", "",
          "| Truth class | positives | detected | missed (FN) | false positives (negatives flagged) |", "|---|---|---|---|---|"]
    for cls in RECOVERABLE:
        L.append(f"| {cls} | {ind_t['pos_by_class'][cls]} | {ind_t['tp_by_class'][cls]} | {ind_t['fn_by_class'][cls]} | - |")
    for cls in ("clean", "slow_credit", "legit_rejection"):
        L.append(f"| {cls} (negative) | - | - | - | {ind_t['fp_by_class'][cls]} |")
    wn = ind_t["wrong_number_kind_acc"]
    L += ["", f"Wrong-part-number cases labelled with the right kind: {'n/a' if wn is None else f'{100*wn[0]:.0f}%'} "
          "(two-hop chains are flagged as discrepancies but labelled `excess_deduction`; this is a known limitation).", "",
          "## Hand-built cases (no generator)", "",
          f"{sum(1 for c in cases if c[3])} of {len(cases)} pass.", "",
          "| Case | got | expected | pass |", "|---|---|---|---|"]
    for name, got, exp, ok in cases:
        L.append(f"| {name} | {got[0]} / {got[1]} | {exp[0]} / {exp[1]} | {'yes' if ok else '**NO**'} |")
    L += ["", "The expected outcomes were written from the intended rules while looking at the classifier, so passing all of them "
          "shows internal consistency, not independence.", "",
          "## Reading the numbers honestly", "",
          "- Compare the temporal classifier against the naive overdue rule on the same days: the difference is what the temporal states buy.",
          "- A classifier that is much worse on the independent set than on the original set is over-fitted to its own generator; see the table.",
          "- Legitimate rejections and statement-cycle posting are cases where ground truth is genuinely ambiguous; flagging them costs a "
          "dispute attempt, not a confirmed loss.",
          "- Flagged != disputed != approved != cash. These are classification metrics only."]
    out = ROOT / "audit" / "validation_results.md"
    out.write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
