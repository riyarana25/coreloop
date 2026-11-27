# Audit-frequency experiment: methodology

**Question.** Does continuous, deadline-aware monitoring prevent more financial loss than periodic manual auditing?

**Hypothesis (stated before running):** policy D has lower total loss than A (90 d), B (30 d) and C (7 d).
**Verdict:** supported against A and B; **not supported against C** (see results). D beats C only when return windows are tight or human audits are skipped.

## Design
- **Identical worlds.** For each seed one set of 600 core lifecycles (`coreloop/lifecycle.py`) is generated and every policy runs on that same set, with the same latent random draws (does staff act, does a dispute win, cash lag). Paired differences use common random numbers.
- **Information gating.** A policy only ever sees `observe(life, t)`: shipping, receipt and credit events dated on or before day t. The classifier's "normal slow-posting tail" is learned only from credits already visible on day t. Latent fields (`leak`, win draws) are never passed to the classifier. Tested in `tests/test_strategy.md` / `tests/test_audit_and_gating.py`.
- **Same brain, different looking schedule.** Every policy uses the same temporal classifier (`audit/temporal_credit_classifier.py`). The only per-policy inputs are `period` (how often it looks) and `automated`. A monthly audit cannot wait out an ambiguous overdue credit because it will not look again soon; continuous monitoring can wait until the last safe day.
- **Policies.** N: never audits (reference only). A: every 90 days. B: every 30 days. C: every 7 days. D: event-driven continuous (scans every open core every day; humans only triage alerts). Human audits start at a random phase offset per seed.
- **Horizon.** Removals on days 0-179, simulation runs to day 400 so every core's lifecycle resolves and audits keep running (no end-of-horizon penalty).
- **Ordinary process.** Without intervention: ~10% of cores are never shipped or shipped late, ~12% have credit problems (rates are assumptions), the rest ship at a random time inside the window.

## Stages are modelled separately
flagged -> submitted (staff follow-through, default 85%) -> approved (win probability by kind: 85% / 80% / 60%) -> cash received (10-30 day lag). A false positive (a slow credit that posts anyway) can be flagged and submitted but recovers nothing. Verified recovery counts only cash received plus the value of cores saved by shipping inside the window.

## Actions
- **Ship alert** (`action_required`, kind `ship_by`): ship on the next business day if still inside the window. One box per OEM: every unshipped core of that OEM in the bin goes with it. This rule applies equally to all policies.
- **Credit discrepancy** (`action_required`): dispute if the dispute window is still open.

## Cost model (assumptions)
Staff wage $35/h. Human audit = 90 min + 0.5 min per open core. Automated triage = 4 min per alert. Dispute effort 10/15/20 min by kind. Intervention shipment = 10 min + 1 min per core. Freight = the invented flat per-OEM fee x intervention shipments (the richer freight model is in Phase 6). Monitoring software $200/month for D only.
`Net Benefit = Verified Simulated Recovery - staff cost - freight - software cost`.

## Metrics requested -> where
1 expired-window loss; 2 detected; 3 disputes submitted; 4 discovered too late or never; 5 value recoverable at discovery (= `detected` before the deadline, by construction); 6 staff hours; 7 false positives; 8 detection delay vs D; 9 net benefit; 10 operating cost: all in `audit_frequency_results.md/json`.

## Statistics
200 main seeds (0-199); 18 sensitivity scenarios x 60 disjoint seeds (1000-1059). Means with 95% CIs (1.96 x SE) across seeds; differences are paired.

## Known limitations and biases
1. All rates, windows and costs are invented; absolute dollars mean nothing, relative ordering and sensitivity are the point.
2. Staff follow-through is a fixed per-core draw (common across policies), and there is no daily staff capacity limit.
3. The classifier and the generator were written by the same author. This experiment does not validate the classifier (see Phase 5 independent validation).
4. Bulk shipping side effect: because a shipment sweeps the whole OEM bin, a weekly audit rescues some cores whose staff would otherwise forget. That slightly favours frequent human audits (C) over D on window loss; it is not tuned toward D.
5. Event-driven monitoring is implemented as a daily scan, which is outcome-equivalent but not an engineering claim about event streams.
6. No time value of money, no partial recoveries, no OEM appeal rules, no weekends in staff availability for audits.
7. D has more false-positive credit alerts than C because it looks more often (more chances to flag a slow credit before it posts).
