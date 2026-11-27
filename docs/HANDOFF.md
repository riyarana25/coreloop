# CoreLoop handoff (for the teammate picking this up)

**One line:** every removed part with a core charge is money with a clock on it. CoreLoop ships each core on
time at the lowest freight cost, audits every credit that comes back, and works the dispute queue.

Tekion angle: repair order, parts, vendor credit and ledger live on one platform, so the agent can read all four
without the stitching third-party reconciliation tools need. Frame it as an extension of Parts + AP AI.
Not verified: whether AP AI already reads vendor credit memos. Check before claiming it is missing.

## Status (all numbers synthetic; `outputs/eval_200seeds.md` has the full tables)
| Piece | State | Honest result |
|---|---|---|
| Synthetic ledger + hidden leaks | Done, tested | 300 cores / 90 days / 3 invented OEMs per seed |
| Audit engine (rules, never reads truth) | Done, tested | Recall ~1.0 is **circular** (rules mirror generator). Credit-missing precision 0.949 because slow credits look identical to missing ones |
| Deadline-aware shipment batching | Done, **optimal vs brute force** | 17-22 shipments vs 41.6 for a weekly-Friday cadence: 48-58% fewer shipment events (17.4-21.6 vs 41.6); the earlier '50-60% less freight' came from a flat per-shipment fee, not a freight model. No core misses its window if carriers are on time; with the assumed delay odds, buffer 0 expects 5.6 misses per ledger, buffer 3 expects 0. Buffer slider trades freight for that risk |
| Dispute queue (CP-SAT) | Done, optimal vs brute force | Lift over simple baselines is small: +2.7% at 20 min/day, ~0 at 60+. **Do not headline it** |
| At-risk alerts | Done (rule) | Not scored; alerts are cheap, precision is not meaningful |
| Streamlit UI, LLM layer, routing | Not started | see tasks |

Where the money is in this synthetic world (mean per ledger): $7.4k of cores lose their window (preventable by
shipping on time) vs $3.2k of credit shortfalls still disputable, plus $1.1k already past the dispute deadline when
audited once at day 90. **Prevention beats recovery**, so lead with batching + alerts, not disputes.

## Prioritized next tasks
1. **Streamlit "leak board"**: cores sorted by ship-by deadline with $ at risk; shipment plan with a buffer slider;
   dispute queue with a minutes-per-day slider; one-click dispute draft; scenario seed picker.
2. **Audit-cadence experiment**: audit weekly vs once per 90 days and measure dollars lost to expiry. This is the
   honest case for a continuously running agent.
3. **Harder detection**: add credit memos with a missing or wrong RO reference (fuzzy matching) so recall is not trivially 1.0.
4. **LLM layer**: parse a pasted vendor credit memo into strict JSON; polish dispute drafts from `draft_dispute`
   facts only. The LLM never decides amounts or deadlines.
5. **Stretch, maybe cut**: routing each core among return / reman exchange / reuse / scrap. Not built. One use case
   is enough; only add it if everything above is done.
6. **Slides (6 max) + demo video** (about 100 s, fixed seed, recorded fallback).
7. **Verify before claiming**: Tekion's existing core features; AP AI scope; organizer confirmation that a
   decision-engine reading of "Circular Parts Marketplace" is acceptable.

## Storyboard (100 s)
1. 0-15 s: the leak board, $ at risk in red. 2. 15-40 s: "ship plan" collapses 141 one-off shipments to ~19
with a visible safety buffer. 3. 40-65 s: audit finds a wrong-number credit; show expected vs received.
4. 65-85 s: dispute queue under a 30-minute budget. 5. 85-100 s: sustainability line: recovered cores feed
remanufacturing, so the money incentive and the circular-economy goal point the same way.

## Judge Q&A
- *Doesn't Tekion already track cores?* Tracking and reports exist. We add shipping decisions, credit audit and a
  dispute queue on the same ledger. Say "as far as we found".
- *Data is synthetic.* Yes. Every number is an editable assumption; leaks are injected so detection can be scored
  against known truth.
- *Perfect recall?* Circular by construction. The informative numbers are precision on slow credits and dollars lost to expiry.
- *Why not ship weekly?* Weekly is a fine baseline and is safe, but costs about twice the freight. We ship on the last
  safe day minus a buffer you choose.
- *What stops the LLM inventing a number?* It never computes one. Rules and the solver produce every amount and date.
- *Is the dispute queue worth it?* Only when staff time is scarce; the data says so (small lift). It is a minor feature.

## Known limitations
Slow credits are indistinguishable from missing ones at audit time (accepted, counted as false positives).
Single audit day. No partial shipments, no multi-OEM consolidation, no weight-based freight, no condition
inspection at the OEM, no OEM-specific rules beyond the invented table.
