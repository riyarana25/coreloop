"""Does continuous auditing prevent more financial loss than periodic manual auditing?

Runs policies N (reference), A (90 d), B (30 d), C (7 d), D (event-driven) on IDENTICAL simulated
ledgers (same seeds, same latent draws), reports mean and 95% CI of paired differences, and a
sensitivity grid. ALL DATA IS SYNTHETIC; every parameter is an assumption.

    python benchmark/audit_frequency_experiment.py [n_seeds=200] [n_sens_seeds=60]
"""
import json
import statistics as stats
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from coreloop.catalog import POLICIES  # noqa: E402
from coreloop.lifecycle import LEAK_RATES, make_lives, scale_windows  # noqa: E402
from simulation.engine import POLICIES_UNDER_TEST, Params, simulate  # noqa: E402

OUT = ROOT / "benchmark"
KEYS = ["total_loss", "loss_window", "loss_credit_unrecovered", "cash_received", "saved_window_value",
        "credit_leaks", "detected", "missed_or_late", "disputes_submitted", "approved",
        "false_positive_credit_alerts", "ship_alerts", "ship_alerts_unnecessary", "ship_events",
        "staff_minutes", "staff_cost", "freight_cost", "software_cost", "operating_cost",
        "verified_recovery", "net_benefit"]


def run_scenario(seeds, params=None, window_k=1.0, leak_scale=1.0, rates=None):
    params = params or Params()
    pol = scale_windows(POLICIES, window_k) if window_k != 1.0 else POLICIES
    per = {s.name: [] for s in POLICIES_UNDER_TEST}
    for seed in seeds:
        lives = make_lives(seed, leak_scale=leak_scale, policies=pol, rates=rates)
        for spec in POLICIES_UNDER_TEST:
            per[spec.name].append(simulate(lives, pol, spec, params, seed=seed))
    return per


def mean_ci(xs):
    m = stats.fmean(xs)
    if len(xs) < 2:
        return m, 0.0
    return m, 1.96 * stats.stdev(xs) / len(xs) ** 0.5


def summarize(per):
    out = {}
    for name, rs in per.items():
        out[name] = {k: dict(zip(("mean", "ci95"), mean_ci([r[k] for r in rs]))) for k in KEYS}
        # detection delay relative to policy D, for leaks both flagged
    dname = [n for n in per if n.startswith("D")][0]
    for name, rs in per.items():
        delays = []
        for r, rd in zip(rs, per[dname]):
            common = set(r["flag_days"]) & set(rd["flag_days"])
            delays += [r["flag_days"][i] - rd["flag_days"][i] for i in common]
        out[name]["detection_delay_vs_D_days"] = {
            "mean": stats.fmean(delays) if delays else None, "n": len(delays)}
    return out


def paired(per, a, b, key):
    """mean and CI of key(a) - key(b) across seeds."""
    diffs = [x[key] - y[key] for x, y in zip(per[a], per[b])]
    return dict(zip(("mean", "ci95"), mean_ci(diffs)))


def preventable(per):
    names = {n[0]: n for n in per}
    res = {}
    for base in "ABC":
        res[f"Loss({base}) - Loss(D)"] = paired(per, names[base], names["D"], "total_loss")
    res["Net(D) - Net(A)"] = paired(per, names["D"], names["A"], "net_benefit")
    res["Net(D) - Net(B)"] = paired(per, names["D"], names["B"], "net_benefit")
    res["Net(D) - Net(C)"] = paired(per, names["D"], names["C"], "net_benefit")
    res["Staff minutes: C - D"] = paired(per, names["C"], names["D"], "staff_minutes")
    return res


def sensitivity(n):
    seeds = range(1000, 1000 + n)          # disjoint from the main seeds
    base = Params()
    slow_off = {**LEAK_RATES, "slow_credit": 0.0}
    slow_hi = {**LEAK_RATES, "slow_credit": 0.10}
    grid = [
        ("base case", {}),
        ("staff follow-through 60%", {"params": replace(base, follow_ship=0.6, follow_dispute=0.6)}),
        ("staff follow-through 100%", {"params": replace(base, follow_ship=1.0, follow_dispute=1.0)}),
        ("return windows x0.5 (tighter)", {"window_k": 0.5}),
        ("return windows x2", {"window_k": 2.0}),
        ("return windows x4 (like long retail policies)", {"window_k": 4.0}),
        ("leak rates x0.5", {"leak_scale": 0.5}),
        ("leak rates x2", {"leak_scale": 2.0}),
        ("no slow-posting credits", {"rates": slow_off}),
        ("slow-posting credits 10% (vs 3%)", {"rates": slow_hi}),
        ("dispute win probability x0.5", {"params": replace(base, p_win_scale=0.5)}),
        ("human audits only happen 70% of the time", {"params": replace(base, audit_adherence=0.7)}),
        ("human audits only happen 50% of the time", {"params": replace(base, audit_adherence=0.5)}),
        ("each human audit takes 30 min total", {"params": replace(base, audit_base_min=30, audit_per_open_min=0.1)}),
        ("monitoring software $0 / month", {"params": replace(base, software_cost_per_month=0.0)}),
        ("monitoring software $1,000 / month", {"params": replace(base, software_cost_per_month=1000.0)}),
        ("staff wage $70 / hour", {"params": replace(base, wage_per_hour=70.0)}),
        ("freight x2", {"params": replace(base, freight_scale=2.0)}),
    ]
    rows = []
    for label, kw in grid:
        per = run_scenario(seeds, **kw)
        names = {n[0]: n for n in per}
        row = {"scenario": label}
        for pol in "NABCD":
            row[f"loss_{pol}"] = stats.fmean(r["total_loss"] for r in per[names[pol]])
            row[f"net_{pol}"] = stats.fmean(r["net_benefit"] for r in per[names[pol]])
        row["preventable_A_minus_D"] = paired(per, names["A"], names["D"], "total_loss")["mean"]
        row["preventable_C_minus_D"] = paired(per, names["C"], names["D"], "total_loss")
        row["net_D_minus_C"] = paired(per, names["D"], names["C"], "net_benefit")
        rows.append(row)
    return rows


def fmt(x, d=0):
    return f"{x:,.{d}f}"


def write_md(main, prevent, sens, n, ns, params):
    L = ["# Audit-frequency experiment: results", "",
         "**SYNTHETIC data. Every parameter is an assumption** (see `audit_frequency_methodology.md`). "
         f"{n} seeds x 600 cores x 5 policies on identical ledgers; 95% CIs are across seeds.", "",
         "## 1. Per-policy means (per 600-core ledger, about 180 days of removals)", "",
         "| Metric | " + " | ".join(main.keys()) + " |", "|---|" + "---|" * len(main)]
    rows = [("Total loss ($) = expired return windows + unrecovered credit shortfall", "total_loss", 0),
            ("  of which expired return windows ($)", "loss_window", 0),
            ("  of which unrecovered credit shortfall ($)", "loss_credit_unrecovered", 0),
            ("True credit discrepancies (count)", "credit_leaks", 1),
            ("Discrepancies detected before deadline", "detected", 1),
            ("Discovered too late or never", "missed_or_late", 1),
            ("Disputes submitted", "disputes_submitted", 1),
            ("Disputes approved", "approved", 1),
            ("Cash actually received ($)", "cash_received", 0),
            ("Core value saved by shipping in time ($)", "saved_window_value", 0),
            ("False-positive credit alerts", "false_positive_credit_alerts", 2),
            ("Unnecessary ship alerts (would have shipped anyway)", "ship_alerts_unnecessary", 1),
            ("Intervention shipments", "ship_events", 1),
            ("Staff hours", "staff_minutes", 1),
            ("Operating cost ($): staff + freight + software", "operating_cost", 0),
            ("Verified simulated recovery ($)", "verified_recovery", 0),
            ("**Net benefit ($)**", "net_benefit", 0)]
    for label, k, d in rows:
        cells = []
        for name, m in main.items():
            v, ci = m[k]["mean"], m[k]["ci95"]
            if k == "staff_minutes":
                v, ci = v / 60, ci / 60
            cells.append(f"{fmt(v, d)} +-{fmt(ci, d)}")
        L.append(f"| {label} | " + " | ".join(cells) + " |")
    L.append("| Detection delay vs D (days, when both flag) | " + " | ".join(
        "n/a" if m["detection_delay_vs_D_days"]["mean"] is None else f"{m['detection_delay_vs_D_days']['mean']:.1f}"
        for m in main.values()) + " |")
    L += ["", "## 2. Preventable loss and net benefit (paired across seeds)", "",
          "`Preventable Loss = Loss under periodic auditing - Loss under continuous monitoring`", "",
          "| Quantity | mean | 95% CI |", "|---|---|---|"]
    for k, v in prevent.items():
        L.append(f"| {k} | {fmt(v['mean'])} | +-{fmt(v['ci95'])} |")
    L += ["", "`Net Benefit = Verified Simulated Recovery - Monitoring Cost - Incremental Operational Cost`; "
          "verified recovery = cash from approved disputes + value of cores saved by timely shipping.", "",
          f"## 3. Sensitivity ({ns} disjoint seeds per scenario; losses in $ per ledger)", "",
          "| Scenario | Loss A (90d) | Loss B (30d) | Loss C (7d) | Loss D | A-D | C-D (95% CI) | Net D-C (95% CI) |",
          "|---|---|---|---|---|---|---|---|"]
    for r in sens:
        c, nd = r["preventable_C_minus_D"], r["net_D_minus_C"]
        L.append(f"| {r['scenario']} | {fmt(r['loss_A'])} | {fmt(r['loss_B'])} | {fmt(r['loss_C'])} | "
                 f"{fmt(r['loss_D'])} | {fmt(r['preventable_A_minus_D'])} | "
                 f"{fmt(c['mean'])} +-{fmt(c['ci95'])} | {fmt(nd['mean'])} +-{fmt(nd['ci95'])} |")
    return "\n".join(L) + "\n"


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    ns = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    t0 = time.time()
    per = run_scenario(range(n))
    main_summary = summarize(per)
    prevent = preventable(per)
    sens = sensitivity(ns)
    params = asdict(Params())
    (OUT / "audit_frequency_results.json").write_text(json.dumps(
        {"n_seeds": n, "n_sensitivity_seeds": ns, "params": params, "policies": main_summary,
         "paired": prevent, "sensitivity": sens}, indent=1, default=float))
    (OUT / "audit_frequency_results.md").write_text(write_md(main_summary, prevent, sens, n, ns, params))
    print((OUT / "audit_frequency_results.md").read_text())
    print(f"[done in {time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()
