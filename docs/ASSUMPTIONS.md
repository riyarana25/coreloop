# Assumptions (everything is synthetic and editable)

Nothing here is real OEM policy, real price data or a measured industry rate. Change values in
`coreloop/catalog.py` and `coreloop/generator.py`, then re-run `scripts/batch_eval.py`.

## OEM policy table (`catalog.py`, invented)
| OEM | return window | transit | credit posts after receipt | grace | max damage deduction | dispute window | freight per shipment |
|---|---|---|---|---|---|---|---|
| OEM-A | 21 d | 3 d | 14 d | 3 d | 30% | 60 d | $45 |
| OEM-B | 30 d | 4 d | 21 d | 5 d | 25% | 45 d | $55 |
| OEM-C | 14 d | 2 d | 10 d | 3 d | 30% | 30 d | $40 |

Ship-by day = removal day + window - transit. Shipments leave on business days only (day 0 is a Monday).

## Parts
14 invented part numbers, core values $60-$900. Three have a superseded predecessor with a lower core value
(this models the "credit issued at the old part number" failure seen in dealer-forum anecdotes).

## Leak rates per core (`generator.py`)
never shipped 4%, shipped late 6%, credit never posts 5%, wrong-number credit 3% (only parts with a
predecessor), excess deduction 4%, slow credit 3% (not a real leak; a confounder). 15% of cores are
recorded as damaged and carry a legitimate 10%-to-max deduction. Credit amounts carry +-$0.50 rounding noise;
the audit tolerance is $1.00.

**No reliable industry-wide leakage figure was found.** One vendor blog quotes $8,000-$22,000 of unclaimed
credits per rooftop per year; that is marketing, do not cite it as fact. One trade-press anecdote has a dealer
getting credit for about 30% of cores in the past; that is one store, not a rate.

## Dispute economics (`disputes.py`)
| Kind | staff minutes | chance dispute succeeds |
|---|---|---|
| credit_missing | 10 | 85% |
| wrong_number | 15 | 80% |
| excess_deduction | 20 | 60% |

## Carrier delay (`shipping.py`)
Extra transit days: 0 (80%), 1 (12%), 2 (6%), 3 (2%).

## Impact formula to show on a slide (editable, never a claim)
recovered $ = sum over disputes (amount x win probability) + core value saved by shipping inside the window
- freight spent - staff minutes x $/minute.
