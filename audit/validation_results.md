# Credit classifier validation

**SYNTHETIC data.** The independent generator differs in design (other OEM tables, statement-cycle heavy-tailed posting, two-hop supersession, lost cores, legitimate rejections, bigger rounding noise) but has the **same author** as the classifier, so it is independent in construction, not in authorship. 30 seeds x 500 cores per dataset; values are mean (min-max across seeds). Each method sees only information visible on the current day.

**Process, in order.** (1) First version (v0) measured on independent seeds 0-29: precision fell from 94% to 49%. (2) Diagnosed on seeds 0-9 only: most false positives were clean credits flagged missing because the learned delay history was right-censored (slow credits had not posted yet), plus rounding noise and zero-dollar rejections. (3) Fixed on principle (settled-history cohort, patience when history is thin, materiality threshold, zero-credit-on-damaged review rule), not by tuning constants. (4) **Re-scored on held-out seeds 200+ that were never used for diagnosis.**

Positives = recoverable discrepancies (missing credit, wrong part number, over-deduction, lost-in-transit core). Negatives = clean credits, slow-posting credits and (independent set) legitimate OEM rejections. Window-missed cores are excluded.

| Dataset | Method | Recall | Precision | False-positive rate | Detected before dispute deadline | Detection delay vs earliest naive flag (days) |
|---|---|---|---|---|---|---|
| original generator, new seeds | first version (v0) | 100.0% (100-100) | 94.0% (90-98) | 0.8% (0-1) | 100.0% (100-100) | 3.8 |
| original generator, new seeds | improved (v1) | 100.0% (100-100) | 97.0% (90-100) | 0.4% (0-1) | 100.0% (100-100) | 10.9 |
| original generator, new seeds | naive overdue rule | 100.0% (100-100) | 78.3% (71-91) | 3.4% (1-5) | 100.0% (100-100) | 0.0 |
| INDEPENDENT generator, held-out seeds | first version (v0) | 99.9% (98-100) | 49.7% (42-58) | 14.2% (12-19) | 99.9% (98-100) | 9.5 |
| INDEPENDENT generator, held-out seeds | improved (v1) | 99.8% (98-100) | 84.6% (77-93) | 2.5% (1-4) | 99.8% (98-100) | 20.0 |
| INDEPENDENT generator, held-out seeds | naive overdue rule | 99.9% (98-100) | 20.1% (14-24) | 55.9% (50-63) | 99.9% (98-100) | -1.4 |

## Where the classifier fails (independent generator, temporal classifier, pooled over seeds)

| Truth class | positives | detected | missed (FN) | false positives (negatives flagged) |
|---|---|---|---|---|
| credit_missing | 756 | 756 | 0 | - |
| wrong_number | 186 | 182 | 4 | - |
| excess_deduction | 453 | 453 | 0 | - |
| lost_in_transit | 309 | 309 | 0 | - |
| clean (negative) | - | - | - | 8 |
| slow_credit (negative) | - | - | - | 80 |
| legit_rejection (negative) | - | - | - | 221 |

Wrong-part-number cases labelled with the right kind: 70% (two-hop chains are flagged as discrepancies but labelled `excess_deduction`; this is a known limitation).

## Hand-built cases (no generator)

29 of 29 pass.

| Case | got | expected | pass |
|---|---|---|---|
| unshipped, far from ship-by | pending / ship_by | pending / ship_by | yes |
| unshipped, 6 days left | at_risk / ship_by | at_risk / ship_by | yes |
| unshipped, 4 days left: ship now | action_required / ship_by | action_required / ship_by | yes |
| unshipped past ship-by | closed / window_missed | closed / window_missed | yes |
| periodic audit cannot wait for next look | action_required / ship_by | action_required / ship_by | yes |
| shipped after ship-by day | closed / window_missed | closed / window_missed | yes |
| in transit, not yet expected | pending / ok | pending / ok | yes |
| receipt unconfirmed 5 days after expected | at_risk / transit_unconfirmed | at_risk / transit_unconfirmed | yes |
| receipt unconfirmed 11 days after expected | action_required / transit_unconfirmed | action_required / transit_unconfirmed | yes |
| credit not yet due | pending / ok | pending / ok | yes |
| credit inside grace period | pending / ok | pending / ok | yes |
| credit overdue, inside slow tail, can wait | at_risk / credit_missing | at_risk / credit_missing | yes |
| credit overdue beyond any delay seen | action_required / credit_missing | action_required / credit_missing | yes |
| credit overdue, next look would be too late | action_required / credit_missing | action_required / credit_missing | yes |
| learned tail (12 days) extends the wait | at_risk / credit_missing | at_risk / credit_missing | yes |
| missing credit after dispute window closed | closed / credit_missing | closed / credit_missing | yes |
| correct credit | closed / ok | closed / ok | yes |
| slight overpayment | closed / ok | closed / ok | yes |
| short by $0.80 (inside $1 tolerance) | closed / ok | closed / ok | yes |
| short by $1.50 on a $60 core: below materiality, not worth a dispute | closed / ok | closed / ok | yes |
| short by $12 on a $60 core: material | action_required / excess_deduction | action_required / excess_deduction | yes |
| $0 credit on a damaged core: likely legitimate rejection, review only | at_risk / excess_deduction | at_risk / excess_deduction | yes |
| $0 credit on a good-condition core: dispute | action_required / excess_deduction | action_required / excess_deduction | yes |
| legitimate 20% damage deduction | closed / ok | closed / ok | yes |
| damage deduction of 50% exceeds the 30% cap | action_required / excess_deduction | action_required / excess_deduction | yes |
| good core deducted 20% | action_required / excess_deduction | action_required / excess_deduction | yes |
| credit at superseded part number | action_required / wrong_number | action_required / wrong_number | yes |
| right part number, wrong amount | action_required / excess_deduction | action_required / excess_deduction | yes |
| two-hop supersession is labelled excess_deduction, not wrong_number | action_required / excess_deduction | action_required / excess_deduction | yes |

The expected outcomes were written from the intended rules while looking at the classifier, so passing all of them shows internal consistency, not independence.

## Reading the numbers honestly

- Compare the temporal classifier against the naive overdue rule on the same days: the difference is what the temporal states buy.
- A classifier that is much worse on the independent set than on the original set is over-fitted to its own generator; see the table.
- Legitimate rejections and statement-cycle posting are cases where ground truth is genuinely ambiguous; flagging them costs a dispute attempt, not a confirmed loss.
- Flagged != disputed != approved != cash. These are classification metrics only.
