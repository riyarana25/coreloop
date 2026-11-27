# Baseline benchmark (reproduced in this session; SYNTHETIC data, invented policies and rates)

Source: `python scripts/batch_eval.py` (200 seeds, 300 cores per ledger, audit on day 90). Output matched the earlier file exactly.

| Claim in the brief | Reproduced? | Value |
|---|---|---|
| Shipment events 17-22 vs 42 weekly | Yes | coreloop buffer 0..3: 17.4 / 18.5 / 19.4 / 21.6 vs weekly_friday 41.6 (ship_each 141.3) |
| No expected miss at 3-day buffer | Yes, under the assumed delay odds only | expected misses per ledger: buffer 0 = 5.55, 1 = 2.05, 2 = 0.44, 3 = 0.00 |
| ~$7.4k missed-window loss / ledger | Yes | $7,389 |
| ~$3.2k disputable credit shortfall / ledger | Yes | $3,215 (+$1,087 already past the dispute deadline) |
| 100% injected-leak detection | Yes, but **circular** | rules and generator share assumptions |
| Credit-missing precision ~0.949 | Yes | 0.949 mean, 0.667 worst seed, 104 false positives in 200 seeds, all from slow credits |
| Dispute queue lift <= ~2.7% | Yes | +2.7% at 20 min/day, +1.1% at 30, ~0 at 60+ |

## Correction to earlier wording
Earlier I wrote "about 50-60% less freight". That figure came from `shipments x flat per-OEM fee` ($782-$965 vs $1,943), not from an independent freight model. The defensible wording until Phase 6 is **"48-58% fewer shipment events"** (17.4-21.6 vs 41.6).

## Why these numbers are preliminary
1. One audit instant per ledger: no timing information, so nothing here says whether continuous monitoring beats periodic audits.
2. Audit rules were written alongside the generator, so recall of 1.0 is expected.
3. Return windows (14-30 days) are invented and on the short side of public retail policies (21 days to 6 months).
4. Flat freight fee, no weight, distance or capacity.
