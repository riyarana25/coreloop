"""CoreLoop demo UI (Streamlit). Rendering only: every number comes from ledger/operations.py,
which wraps the audited engine. ALL DATA IS SYNTHETIC. Run:  streamlit run ui/app.py
Deep link for a screen: ?page=<name> (used for screenshots)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from data.store import Store  # noqa: E402
from ledger import operations as ops  # noqa: E402

PAGES = ["Operations overview", "Core inventory & deadlines", "Shipment optimisation", "Credit monitoring",
         "Dispute queue", "Audit-frequency simulator", "Audit trail"]
SLUG = {p: p.lower().split(" &")[0].replace(" ", "-") for p in PAGES}
STATE_COLOR = {"pending": "#8fa3b8", "at_risk": "#e0a030", "action_required": "#c8452d", "closed": "#cfd6dd"}
BENCH = ROOT / "benchmark" / "audit_frequency_results.json"

st.set_page_config(page_title="CoreLoop", layout="wide", page_icon="🔁")


@st.cache_resource
def store():
    return Store()


S = store()


def world():
    return ops.build_world(S.get("seed"), S.get("n_cores"), S.get("today"), S.decisions())


def usd(x):
    return f"${x:,.0f}"


# ------------------------------------------------------------------ sidebar
qp = st.query_params
default = next((p for p in PAGES if SLUG[p] == qp.get("page")), PAGES[0])
with st.sidebar:
    st.title("🔁 CoreLoop")
    st.caption("Deadline-aware core returns. **Synthetic data only.**")
    if "screen" not in st.session_state:
        st.session_state["screen"] = default
    page = st.radio("Screen", PAGES, key="screen")
    st.divider()
    st.metric("Simulated day", S.get("today"))
    c1, c2, c3 = st.columns(3)
    for col, d in zip((c1, c2, c3), (1, 3, 7)):
        if col.button(f"+{d}d", key=f"adv{d}"):
            ops.advance(S, d)
            st.rerun()
    with st.expander("Scenario"):
        seed = st.number_input("Seed", 1, 9999, int(S.get("seed")))
        n = st.number_input("Cores", 100, 1000, int(S.get("n_cores")), step=100)
        day = st.number_input("Start day", 60, 300, 130)
        if st.button("Reset scenario (clears decisions)"):
            S.reset(int(seed), int(n), int(day))
            st.rerun()

w = world()
ops.reconcile_audit_events(S, w)
if qp.get("page") != SLUG[page]:
    st.query_params["page"] = SLUG[page]


def alert_buttons(core_id, kind, key, defer_days=3, approve_label="Approve"):
    a, b, c = st.columns(3)
    if a.button(approve_label, key=f"ap{key}"):
        ops.decide(S, w, core_id, kind, "approve")
        st.rerun()
    if b.button(f"Defer {defer_days}d", key=f"df{key}"):
        ops.decide(S, w, core_id, kind, "defer", defer_days)
        st.rerun()
    if c.button("Dismiss", key=f"di{key}"):
        ops.decide(S, w, core_id, kind, "dismiss")
        st.rerun()


# ------------------------------------------------------------------ 1 overview
if page == PAGES[0]:
    o = ops.overview(w)
    st.header("Operations overview")
    st.caption(f"Day {o['today']} · {o['cores_in_system']} cores removed so far · synthetic dealership, three invented OEMs")
    k = st.columns(5)
    k[0].metric("Open cores", o["open_cores"])
    k[1].metric("Action required", o["action_required"], usd(o["deposits_action"]) + " at stake", delta_color="off")
    k[2].metric("At risk", o["at_risk"], usd(o["deposits_at_risk"]) + " at stake", delta_color="off")
    k[3].metric("Windows already missed", o["windows_missed"], usd(o["deposits_forfeited"]) + " forfeited", delta_color="off")
    k[4].metric("Disputes submitted", o["disputes_submitted"])
    inv = pd.DataFrame(ops.inventory_rows(w))
    open_ = inv[inv.state != "closed"]
    left, right = st.columns(2)
    by = open_.groupby(["oem", "state"], as_index=False)["amount"].sum()
    fig = px.bar(by, x="oem", y="amount", color="state", color_discrete_map=STATE_COLOR,
                 labels={"amount": "Deposit $ at stake", "oem": ""}, title="Open deposits by OEM and state")
    left.plotly_chart(fig, use_container_width=True)
    ship = open_[open_.shipped_day.isna()]
    fig2 = px.histogram(ship, x="days_to_ship_by", nbins=20, color="state", color_discrete_map=STATE_COLOR,
                        labels={"days_to_ship_by": "Days until ship-by"}, title="Unshipped cores: time left to ship")
    right.plotly_chart(fig2, use_container_width=True)
    st.info("Every state is computed by the temporal classifier from what is visible **today**. "
            "Nothing here reads hidden ground truth.")

# ------------------------------------------------------------------ 2 inventory
elif page == PAGES[1]:
    st.header("Core inventory & deadlines")
    inv = pd.DataFrame(ops.inventory_rows(w))
    f1, f2, f3 = st.columns(3)
    st_sel = f1.multiselect("State", ["action_required", "at_risk", "pending", "closed"], ["action_required", "at_risk", "pending"])
    oem_sel = f2.multiselect("OEM", sorted(inv.oem.unique()), sorted(inv.oem.unique()))
    max_days = f3.slider("Ship-by within (days)", -60, 60, 60)
    v = inv[inv.state.isin(st_sel) & inv.oem.isin(oem_sel) & (inv.days_to_ship_by <= max_days)]
    st.dataframe(v.sort_values("days_to_ship_by")[["core_id", "part", "oem", "condition", "removed_day", "ship_by_day",
                 "days_to_ship_by", "shipped_day", "received_day", "credit", "state", "kind", "amount", "why"]],
                 use_container_width=True, hide_index=True, height=520)
    st.caption("`ship_by_day` = removal + OEM window − transit days. Negative `days_to_ship_by` on an unshipped core means the window is gone.")

# ------------------------------------------------------------------ 3 shipments
elif page == PAGES[2]:
    st.header("Shipment optimisation")
    buf = st.slider("Safety buffer (days before the last safe ship day)", 0, 3, 1)
    plan = ops.plan_shipments(w, buf)
    k = st.columns(4)
    k[0].metric("Unshipped cores", plan["cores_planned"] + plan["cores_lost"])
    k[1].metric("Planned shipment events", plan["events"])
    k[2].metric("Simulated freight", usd(plan["freight"]))
    k[3].metric("Expected loss from carrier delay", usd(plan["expected_delay_loss"]))
    rows = [{"OEM": oem, "ship on day": day, "cores": len(ids), "core ids": ", ".join(map(str, ids))}
            for (oem, day), ids in sorted(plan["schedule"].items(), key=lambda x: x[0][1])]
    st.subheader("Plan (minimum number of shipments that still meets every deadline)")
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    st.subheader("Counterfactual: what if we wait?")
    wait = st.select_slider("Wait this many days before shipping", [1, 2, 3, 5, 7], 1)
    cf = ops.counterfactual_wait(w, wait, buf)
    d = cf["delta"]
    c = st.columns(4)
    c[0].metric("Shipment events", cf["wait"]["events"], f"{d['events']:+.0f}", delta_color="inverse")
    c[1].metric("Freight", usd(cf["wait"]["freight"]), f"{d['freight']:+,.0f}", delta_color="inverse")
    c[2].metric("Cores that can no longer be saved", cf["wait"]["cores_lost"], f"{d['cores_lost']:+.0f}", delta_color="inverse")
    c[3].metric("Deposit value lost", usd(cf["wait"]["value_lost"]), f"{d['value_lost']:+,.0f}", delta_color="inverse")
    if cf["newly_lost"]:
        st.error(f"Waiting {wait} day(s) forfeits cores {cf['newly_lost']}. The freight saving is "
                 f"{usd(-d['freight']) if d['freight'] < 0 else '$0'}; the deposits lost are {usd(d['value_lost'])}.")
    else:
        st.success(f"Waiting {wait} day(s) costs no cores under this buffer.")
    st.subheader("Ship-now alerts")
    alerts = ops.ship_today_alerts(w)
    if not alerts:
        st.write("None today.")
    for a in alerts[:12]:
        col1, col2 = st.columns([3, 2])
        col1.write(f"Core **{a.core_id}** · {usd(a.amount)} · {a.days_left} days to ship-by — {a.reason}")
        with col2:
            alert_buttons(a.core_id, "ship_by", f"s{a.core_id}", 1, "Ship today")

# ------------------------------------------------------------------ 4 credit monitoring
elif page == PAGES[3]:
    st.header("Credit monitoring")
    rows = pd.DataFrame(ops.credit_rows(w))
    if rows.empty:
        st.write("No credit or transit cases are open.")
    else:
        cnt = rows.groupby(["kind", "state"], as_index=False).size()
        st.plotly_chart(px.bar(cnt, x="kind", y="size", color="state", color_discrete_map=STATE_COLOR,
                               labels={"size": "cores"}, title="Credit and transit cases by kind and state"),
                        use_container_width=True)
        st.dataframe(rows.sort_values(["state", "days_left"]), hide_index=True, use_container_width=True, height=360)
    st.subheader("What the system has learned about posting delays")
    h = pd.DataFrame(ops.posting_history_summary(w))
    h["normal_delay_days"] = h["normal_delay_days"].map(lambda x: "not enough settled history yet" if x is None else x)
    st.dataframe(h, hide_index=True, use_container_width=True)
    st.caption("A credit is not called missing until it is later than the OEM's own settled posting delays "
               "(or waiting any longer would leave too little time to dispute). Only credits already posted are used.")

# ------------------------------------------------------------------ 5 disputes
elif page == PAGES[4]:
    st.header("Dispute queue")
    q, total = ops.dispute_queue(w)
    st.caption(f"{len(q)} cases need a decision. Expected value of the suggested 10-day plan: {usd(total)} "
               f"(win probabilities and effort minutes are assumptions).")
    for r in q[:15]:
        with st.container(border=True):
            a, b = st.columns([4, 2])
            a.markdown(f"**Core {r['core_id']}** · `{r['kind']}` · **{usd(r['amount'])}** · "
                       f"{r['days_left']} days to deadline · ~{r['effort_min']} min · expected {usd(r['expected_value'])}")
            a.caption(r["why"])
            with a.expander("Draft dispute text"):
                st.code(ops.draft_dispute(w, r["core_id"]))
            with b:
                alert_buttons(r["core_id"], r["kind"], f"d{r['core_id']}", 3, "Submit")
    st.subheader("Submitted disputes (outcomes are simulated)")
    outs = [{k: v for k, v in o.items() if not k.startswith("_")} for o in ops.dispute_outcomes(w)]
    st.dataframe(pd.DataFrame(outs), hide_index=True, use_container_width=True)

# ------------------------------------------------------------------ 6 audit frequency
elif page == PAGES[5]:
    st.header("Audit-frequency simulator")
    st.caption("A: every 90 days · B: every 30 days · C: every 7 days · D: event-driven continuous. All policies run on the SAME "
               "synthetic ledgers with the same classifier; they differ only in when they look.")
    tab1, tab2 = st.tabs(["Saved benchmark (200 seeds)", "Run it live (small)"])
    with tab1:
        if BENCH.exists():
            b = ops.load_benchmark(BENCH)
            pol = b["policies"]
            names = [n for n in pol if not n.startswith("N")]
            loss = [pol[n]["total_loss"]["mean"] if isinstance(pol[n]["total_loss"], dict) else pol[n]["total_loss"] for n in names]
            hrs = [pol[n]["staff_minutes"]["mean"] / 60.0 for n in names]
            from plotly.subplots import make_subplots
            colors = ["#8fa3b8", "#8fa3b8", "#8fa3b8", "#2e7d6b"]
            short = [n.split(":")[0] + ": " + n.split(": ")[1].replace("every ", "").replace("event-driven continuous", "continuous") for n in names]
            fig = make_subplots(rows=1, cols=2, subplot_titles=("Total loss per 600-core ledger ($), lower is better",
                                                               "Staff hours per ledger, lower is better"))
            fig.add_trace(go.Bar(x=short, y=loss, marker_color=colors, showlegend=False), 1, 1)
            fig.add_trace(go.Bar(x=short, y=hrs, marker_color=colors, showlegend=False), 1, 2)
            fig.update_layout(height=430, margin=dict(t=60, b=30))
            st.plotly_chart(fig, use_container_width=True)
            st.markdown("**Honest reading:** event-driven monitoring clearly beats 90- and 30-day audits. Versus a disciplined 7-day "
                        "audit the dollar loss is about the same; the difference is staff time and robustness when audits are skipped. "
                        "See `benchmark/audit_frequency_results.md`.")
        else:
            st.warning("Run `python benchmark/audit_frequency_experiment.py` to create the saved benchmark.")
    with tab2:
        c = st.columns(4)
        seeds = c[0].slider("Seeds", 2, 20, 6)
        wk = c[1].select_slider("Return-window scale", [0.5, 1.0, 2.0, 4.0], 1.0)
        adh = c[2].select_slider("Human audits that really happen", [0.5, 0.7, 1.0], 1.0)
        fd = c[3].select_slider("Staff follow-through", [0.6, 0.85, 1.0], 0.85)
        if st.button("Run simulation"):
            with st.spinner("Simulating…"):
                res = ops.frequency_experiment(seeds, wk, adh, fd)
            df = pd.DataFrame(res).T[["total_loss", "staff_hours", "operating_cost", "net_benefit"]].round(0)
            st.dataframe(df, use_container_width=True)
            st.caption(f"Mean of {seeds} fresh synthetic ledgers (300 cores each). Small runs are noisy; the saved benchmark has the confidence intervals.")

# ------------------------------------------------------------------ 7 audit trail
else:
    st.header("Audit trail")
    tr = pd.DataFrame(S.trail())
    if tr.empty:
        st.write("No events yet. Approve, defer or dismiss an alert, or advance the clock.")
    else:
        st.dataframe(tr, hide_index=True, use_container_width=True, height=560)
    st.caption("Append-only SQLite log of operator decisions and simulated outcomes. Decisions persist across restarts.")
