"""200-seed evaluation. Writes outputs/eval_200seeds.md. ALL DATA IS SYNTHETIC."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from coreloop.audit import audit  # noqa: E402
from coreloop.disputes import greedy_queue, plan_queue  # noqa: E402
from coreloop.generator import make_ledger  # noqa: E402
from coreloop.metrics import CLASSES, score  # noqa: E402
from coreloop.shipping import compare  # noqa: E402

SEEDS = range(200)
OUT = Path(__file__).resolve().parents[1] / "outputs" / "eval_200seeds.md"


def audit_section(leak_scale=1.0):
    per = {c: {"p": [], "r": [], "dt": 0.0, "dh": 0.0, "fp": 0} for c in CLASSES}
    exp_dollars, rec_dollars = [], []
    for s in SEEDS:
        L = make_ledger(s, leak_scale=leak_scale)
        F = audit(L)
        sc = score(L, F)
        for c in CLASSES:
            r = sc[c]
            if r["precision"] is not None:
                per[c]["p"].append(r["precision"])
            if r["recall"] is not None:
                per[c]["r"].append(r["recall"])
            per[c]["dt"] += r["dollars_true"]
            per[c]["dh"] += r["dollars_found"]
            per[c]["fp"] += r["fp"]
        exp_dollars.append(sum(f.amount for f in F if f.expired))
        rec_dollars.append(sum(f.amount for f in F if f.recoverable and f.kind in
                               ("credit_missing", "wrong_number", "excess_deduction")))
    return per, np.mean(exp_dollars), np.mean(rec_dollars)


def main():
    lines = ["# CoreLoop 200-seed evaluation (SYNTHETIC data, invented policies and rates)", ""]
    lines += ["Each seed is a 90-day ledger of 300 cores across 3 invented OEMs, audited on day 90.", ""]

    per, exp_d, rec_d = audit_section()
    lines += ["## 1. Audit vs hidden ground truth", "",
              "| Leak class | mean precision | min precision | mean recall | min recall | $ found / $ true | false positives (200 seeds) |",
              "|---|---|---|---|---|---|---|"]
    for c in CLASSES:
        p, r = per[c]["p"], per[c]["r"]
        lines.append(f"| {c} | {np.mean(p):.3f} | {np.min(p):.3f} | {np.mean(r):.3f} | {np.min(r):.3f} | "
                     f"{per[c]['dh']/per[c]['dt']:.1%} | {per[c]['fp']} |")
    lines += ["",
              "Caveat: the audit rules and the generator are written by the same people, so near-perfect recall "
              "on injected leaks is expected, not impressive. The honest signals are (a) false positives from "
              "slow-posting credits that look identical to missing ones at audit time, and (b) the dollars "
              "that are already past the dispute deadline when a once-per-90-days audit finds them.", "",
              f"Mean per ledger: ${rec_d:,.0f} of credit shortfalls still disputable; ${exp_d:,.0f} already expired.", ""]

    ship = {}
    for s in SEEDS:
        for r in compare(make_ledger(s)):
            ship.setdefault(r.policy, []).append((r.shipments, r.freight, r.missed, r.expected_missed))
    lines += ["## 2. Core shipment batching (same 300 cores per ledger)", "",
              "| Policy | shipments | freight $ | cores that cannot make the window | expected misses with carrier delay |",
              "|---|---|---|---|---|"]
    for k, v in ship.items():
        a = np.array(v)
        lines.append(f"| {k} | {a[:,0].mean():.1f} | {a[:,1].mean():,.0f} | {a[:,2].mean():.2f} | {a[:,3].mean():.2f} |")
    lines += ["", "Freight cost per shipment (45/55/40 by OEM) and the carrier-delay distribution are assumptions. "
              "`buffer` = days earlier than the last safe ship day.", ""]

    lines += ["## 3. Dispute work-queue (expected recovered $ per ledger, higher is better)", "",
              "| Staff minutes per day | CP-SAT optimal | soonest-deadline-first | biggest-dollar-first | lift vs best baseline |",
              "|---|---|---|---|---|"]
    for minutes in (20, 30, 60, 120):
        opt, edf, amt = [], [], []
        for s in SEEDS:
            F = audit(make_ledger(s))
            opt.append(plan_queue(F, minutes, 10)[1])
            edf.append(greedy_queue(F, minutes, 10, "expiry")[1])
            amt.append(greedy_queue(F, minutes, 10, "amount")[1])
        best = max(np.mean(edf), np.mean(amt))
        lines.append(f"| {minutes} | {np.mean(opt):,.0f} | {np.mean(edf):,.0f} | {np.mean(amt):,.0f} | "
                     f"{(np.mean(opt)/best-1):+.1%} |")
    lines += ["", "Win probabilities (85% / 80% / 60%) and effort minutes (10 / 15 / 20) are assumptions. "
              "At generous budgets every method ties because nothing is scarce.", ""]

    lines += ["## 4. Sensitivity to leak rate", "",
              "| leak rate multiplier | disputable $ per ledger | credit-missing precision |", "|---|---|---|"]
    for sc_ in (0.5, 1.0, 2.0):
        pr, _, rec = audit_section(sc_)
        lines.append(f"| x{sc_} | {rec:,.0f} | {np.mean(pr['credit_missing']['p']):.3f} |")
    lines.append("")

    OUT.write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
