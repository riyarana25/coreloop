"""Compare shipping policies under the explicit freight cost model. ALL DATA SYNTHETIC.

    python shipping/shipping_benchmark.py [n_seeds=100] [n_sens_seeds=40]
Writes benchmark/shipping_results.md and benchmark/shipping_results.json
"""
import json
import statistics as stats
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from coreloop.generator import make_ledger  # noqa: E402
from coreloop.models import entitlement  # noqa: E402
from coreloop.shipping import run_policy  # noqa: E402
from shipping.freight_cost_model import FreightParams, plan_freight  # noqa: E402

DELAY_SETS = {
    "low delay risk": {0: 0.92, 1: 0.06, 2: 0.02},
    "base delay risk": {0: 0.80, 1: 0.12, 2: 0.06, 3: 0.02},
    "high delay risk": {0: 0.60, 1: 0.20, 2: 0.12, 3: 0.08},
    "severe delay risk": {0: 0.50, 1: 0.20, 2: 0.15, 3: 0.10, 5: 0.05},
}
POLICY_LABELS = [("weekly_friday", 0, "1. Weekly Friday"),
                 ("last_safe_day", 0, "2. Basic deadline rule (each core on its last safe day)"),
                 ("coreloop", 0, "3. Optimised planner, buffer 0"),
                 ("coreloop", 1, "4a. Optimised, buffer 1"),
                 ("coreloop", 2, "4b. Optimised, buffer 2"),
                 ("coreloop", 3, "4c. Optimised, buffer 3")]


def p_miss(core, pol, ship_day, probs):
    margin = (core.removed_day + pol.window_days) - (ship_day + pol.transit_days)
    if margin < 0:
        return 1.0
    return sum(p for extra, p in probs.items() if extra > margin)


def evaluate_ledger(ledger, fp, probs, only=None):
    cores = ledger.cores
    by_id = {c.core_id: c for c in cores}
    rows = {}
    for name, buf, label in POLICY_LABELS:
        if only and label not in only:
            continue
        res = run_policy(name, cores, ledger, buffer_days=buf)
        fr = plan_freight(res.schedule, by_id, fp)
        day_of = {cid: d for (_o, d), ids in res.schedule.items() for cid in ids}
        pm, value, exp_loss = [], 0.0, 0.0
        for c in cores:
            pol = ledger.policies[c.oem]
            ent = entitlement(c, ledger.parts[c.part_no], pol)
            p = p_miss(c, pol, day_of[c.core_id], probs)
            pm.append(p)
            value += ent * (1 - p)
            exp_loss += ent * p
        rows[label] = {"shipment_events": len(res.schedule), "loads": fr["loads"], "freight": fr["freight"],
                       "cost_per_core": fr["freight"] / len(cores), "missed_planned": res.missed,
                       "on_time_rate": 1 - stats.fmean(pm), "expected_loss": exp_loss,
                       "utilisation": fr["utilisation"], "net_benefit": value - fr["freight"]}
    return rows


def run(seeds, fp=FreightParams(), probs=DELAY_SETS["base delay risk"], only=None):
    agg = {}
    for s in seeds:
        for label, r in evaluate_ledger(make_ledger(s), fp, probs, only).items():
            for k, v in r.items():
                agg.setdefault(label, {}).setdefault(k, []).append(v)
    return agg


def mean(agg, label, k):
    return stats.fmean(agg[label][k])


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    ns = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    fp = FreightParams()
    agg = run(range(n), fp)
    W = POLICY_LABELS[0][2]
    L = ["# Shipping economics (SYNTHETIC; freight model values are illustrative assumptions)", "",
         f"{n} ledgers x 300 cores. Freight = base fee + linehaul ($0.10 per 100 lb per mile, 20% discount above 200 lb) "
         "+ packaging $4 per core, minimum charge $45, 500 lb capacity per load; distances OEM-A 350 mi, OEM-B 900 mi, OEM-C 150 mi. "
         "On-time rate and expected loss use the base carrier-delay odds (80% on time, 12% +1 day, 6% +2, 2% +3).", "",
         "| Policy | shipment events | loads | freight $ | $ per core | planned misses | on-time rate | expected window loss $ | capacity utilisation | net benefit $ |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for _n, _b, label in POLICY_LABELS:
        L.append(f"| {label} | {mean(agg,label,'shipment_events'):.1f} | {mean(agg,label,'loads'):.1f} | "
                 f"{mean(agg,label,'freight'):,.0f} | {mean(agg,label,'cost_per_core'):.2f} | {mean(agg,label,'missed_planned'):.2f} | "
                 f"{100*mean(agg,label,'on_time_rate'):.2f}% | {mean(agg,label,'expected_loss'):,.0f} | "
                 f"{100*mean(agg,label,'utilisation'):.1f}% | {mean(agg,label,'net_benefit'):,.0f} |")
    base_e, base_f = mean(agg, W, "shipment_events"), mean(agg, W, "freight")
    L += ["", "## Claims this model supports (vs weekly Friday)", ""]
    for _n, _b, label in POLICY_LABELS[2:]:
        e, f = mean(agg, label, "shipment_events"), mean(agg, label, "freight")
        L.append(f"- {label}: **{100*(1-e/base_e):.0f}% fewer shipment events**, **{100*(1-f/base_f):.0f}% lower simulated freight expenditure**, "
                 f"net benefit {mean(agg,label,'net_benefit')-mean(agg,W,'net_benefit'):+,.0f} $ per ledger.")
    L += ["", "Shipment count and freight spend differ because heavy consolidated loads still pay for weight and distance, and "
          "overflow loads pay a second base fee. The earlier '50-60% less freight' figure used a flat fee per shipment and is superseded by this table.", ""]

    sens = []
    nB = POLICY_LABELS[3][2]   # buffer 1 as the middle case
    only = {W, POLICY_LABELS[1][2], POLICY_LABELS[2][2], POLICY_LABELS[3][2], POLICY_LABELS[4][2], POLICY_LABELS[5][2]}
    scenarios = []
    for dn, probs in DELAY_SETS.items():
        scenarios.append((f"carrier delay: {dn}", fp, probs))
    scenarios += [("freight rate x0.5", replace(fp, rate_per_cwt_mile=0.05), DELAY_SETS["base delay risk"]),
                  ("freight rate x2", replace(fp, rate_per_cwt_mile=0.20), DELAY_SETS["base delay risk"]),
                  ("base fee x0.5", replace(fp, base_fee=14.0, min_charge=22.0), DELAY_SETS["base delay risk"]),
                  ("base fee x2", replace(fp, base_fee=56.0, min_charge=90.0), DELAY_SETS["base delay risk"]),
                  ("capacity 150 lb per load", replace(fp, capacity_lb=150.0), DELAY_SETS["base delay risk"]),
                  ("capacity 1000 lb per load", replace(fp, capacity_lb=1000.0), DELAY_SETS["base delay risk"])]
    L += [f"## Sensitivity ({ns} disjoint ledgers per scenario)", "",
          "Net benefit ($ per ledger) = core value expected to arrive in time - freight. Best policy per scenario in bold.", "",
          "| Scenario | " + " | ".join(l.split(". ", 1)[1] if ". " in l else l for _n, _b, l in POLICY_LABELS) + " | best |",
          "|---|" + "---|" * (len(POLICY_LABELS) + 1)]
    for label, fpar, probs in scenarios:
        a = run(range(2000, 2000 + ns), fpar, probs)
        nets = {l: mean(a, l, "net_benefit") for _n, _b, l in POLICY_LABELS}
        best = max(nets, key=nets.get)
        cells = [f"**{v:,.0f}**" if l == best else f"{v:,.0f}" for l, v in nets.items()]
        L.append(f"| {label} | " + " | ".join(cells) + f" | {best.split('. ',1)[1]} |")
        sens.append({"scenario": label, "net_benefit": nets})
    out = ROOT / "benchmark"
    (out / "shipping_results.md").write_text("\n".join(L) + "\n")
    (out / "shipping_results.json").write_text(json.dumps(
        {"n": n, "policies": {l: {k: mean(agg, l, k) for k in agg[l]} for l in agg}, "sensitivity": sens}, indent=1))
    print("\n".join(L))


if __name__ == "__main__":
    main()
