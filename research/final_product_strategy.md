# CoreLoop: final product strategy

## One use case (the slide limit is six)
A dealership's parts department sells parts that carry a refundable core deposit. The removed core must be shipped inside the OEM's window, the OEM must credit the correct amount, and the credit must post. Money leaks at four places: window missed, credit missing, credit at a superseded part number, and over-deduction.

## Two pillars (everything else is supporting)
1. **Deadline-aware shipping.** Plan shipments as late as is safe, share boxes per OEM, hold a buffer for carrier delay, and show the counterfactual "what if we wait another day".
2. **Continuous credit monitoring.** Classify each core as pending, at risk or action required, using information visible that day only. The ambiguity between a slow credit and a missing one is resolved with time and the OEM's own posting history.

Supporting: a dispute queue (approve, defer, dismiss) and an audit trail. Deferred: routing, any LLM extraction, any marketplace.

## What the evidence says (all synthetic; every parameter is an assumption)
- **Against infrequent audits, the case is strong.** Total loss per 600-core ledger: 90-day audit about $26.1k, 30-day about $11.8k, event-driven about $4.4k (`benchmark/audit_frequency_results.md`).
- **Against a disciplined weekly audit, it is a near tie on dollars lost** (difference about $114 per ledger, in weekly's favour, with a confidence interval of +-$53). Where event-driven monitoring wins is staff time (about 22% of the weekly audit's hours), robustness when human audits are skipped (the weekly audit's loss rises sharply at 50% adherence) and tight return windows.
- **Credit classifier**: on held-out independent data, recall about 99.8%, precision about 85%, false-positive rate about 2.5%, versus 20% precision for a naive overdue rule (`audit/validation_results.md`). A first version scored 49.7% precision; the fixes and the re-test on unseen seeds are documented there.
- **Shipping**: 48-58% fewer shipment events and 15-19% lower simulated freight spend versus weekly Friday, under an explicit freight model; the net benefit after expected window losses depends on the buffer and is roughly break-even to slightly positive (`benchmark/shipping_results.md`). Claims use that wording, not "less freight".

The net-benefit sign versus a weekly audit is positive in 16 of 18 sensitivity scenarios but flips negative if a human audit takes only 30 minutes or the software costs $1,000 per month; those costs are invented.

## Honest pitch line
"We do not claim to beat a perfect weekly audit on recovered dollars. We claim the same recovery at about a quarter of the staff time, which does not degrade when people skip the audit, plus a shipping planner that cuts shipments without raising missed windows."

## Risks
- Tekion may already do part of this internally (Q1-Q3 are "not found", not "absent").
- Return windows and leak rates are invented. Window-length sensitivity is included because real windows range from 6 months (GM) to 90 days (a supplier) per public policies.
- The marketplace reading of Theme 4 is unverified.
