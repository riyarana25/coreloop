# CoreLoop 200-seed evaluation (SYNTHETIC data, invented policies and rates)

Each seed is a 90-day ledger of 300 cores across 3 invented OEMs, audited on day 90.

## 1. Audit vs hidden ground truth

| Leak class | mean precision | min precision | mean recall | min recall | $ found / $ true | false positives (200 seeds) |
|---|---|---|---|---|---|---|
| window_missed | 1.000 | 1.000 | 1.000 | 1.000 | 100.0% | 0 |
| credit_missing | 0.949 | 0.667 | 1.000 | 1.000 | 100.0% | 104 |
| wrong_number | 1.000 | 1.000 | 1.000 | 1.000 | 100.0% | 0 |
| excess_deduction | 1.000 | 1.000 | 1.000 | 1.000 | 100.0% | 0 |

Caveat: the audit rules and the generator are written by the same people, so near-perfect recall on injected leaks is expected, not impressive. The honest signals are (a) false positives from slow-posting credits that look identical to missing ones at audit time, and (b) the dollars that are already past the dispute deadline when a once-per-90-days audit finds them.

Mean per ledger: $3,215 of credit shortfalls still disputable; $1,087 already expired.

## 2. Core shipment batching (same 300 cores per ledger)

| Policy | shipments | freight $ | cores that cannot make the window | expected misses with carrier delay |
|---|---|---|---|---|
| ship_each | 141.3 | 6,633 | 0.00 | 0.00 |
| weekly_friday | 41.6 | 1,943 | 0.00 | 0.00 |
| coreloop(buffer=0) | 17.4 | 782 | 0.00 | 5.55 |
| coreloop(buffer=1) | 18.5 | 830 | 0.00 | 2.05 |
| coreloop(buffer=2) | 19.4 | 865 | 0.00 | 0.44 |
| coreloop(buffer=3) | 21.6 | 965 | 0.00 | 0.00 |

Freight cost per shipment (45/55/40 by OEM) and the carrier-delay distribution are assumptions. `buffer` = days earlier than the last safe ship day.

## 3. Dispute work-queue (expected recovered $ per ledger, higher is better)

| Staff minutes per day | CP-SAT optimal | soonest-deadline-first | biggest-dollar-first | lift vs best baseline |
|---|---|---|---|---|
| 20 | 2,520 | 2,206 | 2,453 | +2.7% |
| 30 | 2,567 | 2,539 | 2,522 | +1.1% |
| 60 | 2,571 | 2,571 | 2,557 | +0.0% |
| 120 | 2,571 | 2,571 | 2,568 | +0.0% |

Win probabilities (85% / 80% / 60%) and effort minutes (10 / 15 / 20) are assumptions. At generous budgets every method ties because nothing is scarce.

## 4. Sensitivity to leak rate

| leak rate multiplier | disputable $ per ledger | credit-missing precision |
|---|---|---|
| x0.5 | 1,640 | 0.947 |
| x1.0 | 3,215 | 0.949 |
| x2.0 | 6,491 | 0.954 |
