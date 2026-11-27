# Shipping economics (SYNTHETIC; freight model values are illustrative assumptions)

100 ledgers x 300 cores. Freight = base fee + linehaul ($0.10 per 100 lb per mile, 20% discount above 200 lb) + packaging $4 per core, minimum charge $45, 500 lb capacity per load; distances OEM-A 350 mi, OEM-B 900 mi, OEM-C 150 mi. On-time rate and expected loss use the base carrier-delay odds (80% on time, 12% +1 day, 6% +2, 2% +3).

| Policy | shipment events | loads | freight $ | $ per core | planned misses | on-time rate | expected window loss $ | capacity utilisation | net benefit $ |
|---|---|---|---|---|---|---|---|---|---|
| 1. Weekly Friday | 41.6 | 41.6 | 4,814 | 16.05 | 0.00 | 100.00% | 0 | 18.3% | 87,979 |
| 2. Basic deadline rule (each core on its last safe day) | 141.1 | 141.1 | 8,886 | 29.62 | 0.00 | 84.31% | 14,566 | 5.4% | 69,342 |
| 3. Optimised planner, buffer 0 | 17.4 | 20.1 | 3,899 | 13.00 | 0.00 | 98.15% | 1,774 | 37.8% | 87,121 |
| 4a. Optimised, buffer 1 | 18.5 | 21.3 | 3,947 | 13.16 | 0.00 | 99.31% | 639 | 35.6% | 88,208 |
| 4b. Optimised, buffer 2 | 19.3 | 22.1 | 3,987 | 13.29 | 0.00 | 99.85% | 143 | 34.3% | 88,664 |
| 4c. Optimised, buffer 3 | 21.6 | 24.5 | 4,091 | 13.64 | 0.00 | 100.00% | 0 | 31.1% | 88,703 |

## Claims this model supports (vs weekly Friday)

- 3. Optimised planner, buffer 0: **58% fewer shipment events**, **19% lower simulated freight expenditure**, net benefit -859 $ per ledger.
- 4a. Optimised, buffer 1: **55% fewer shipment events**, **18% lower simulated freight expenditure**, net benefit +229 $ per ledger.
- 4b. Optimised, buffer 2: **54% fewer shipment events**, **17% lower simulated freight expenditure**, net benefit +684 $ per ledger.
- 4c. Optimised, buffer 3: **48% fewer shipment events**, **15% lower simulated freight expenditure**, net benefit +723 $ per ledger.

Shipment count and freight spend differ because heavy consolidated loads still pay for weight and distance, and overflow loads pay a second base fee. The earlier '50-60% less freight' figure used a flat fee per shipment and is superseded by this table.

## Sensitivity (40 disjoint ledgers per scenario)

Net benefit ($ per ledger) = core value expected to arrive in time - freight. Best policy per scenario in bold.

| Scenario | Weekly Friday | Basic deadline rule (each core on its last safe day) | Optimised planner, buffer 0 | Optimised, buffer 1 | Optimised, buffer 2 | Optimised, buffer 3 | best |
|---|---|---|---|---|---|---|---|
| carrier delay: low delay risk | 87,637 | 78,041 | 87,972 | 88,394 | **88,478** | 88,368 | Optimised, buffer 2 |
| carrier delay: base delay risk | 87,637 | 69,098 | 86,773 | 87,845 | 88,329 | **88,368** | Optimised, buffer 3 |
| carrier delay: high delay risk | 87,637 | 53,566 | 84,481 | 86,623 | 87,880 | **88,368** | Optimised, buffer 3 |
| carrier delay: severe delay risk | 87,637 | 44,729 | 82,248 | 84,844 | 86,718 | **87,791** | Optimised, buffer 3 |
| freight rate x0.5 | 88,682 | 70,043 | 87,773 | 88,842 | 89,335 | **89,377** | Optimised, buffer 3 |
| freight rate x2 | 85,429 | 66,946 | 84,724 | 85,807 | 86,276 | **86,317** | Optimised, buffer 3 |
| base fee x0.5 | 88,361 | 71,926 | 87,108 | 88,202 | 88,707 | **88,803** | Optimised, buffer 3 |
| base fee x2 | 86,082 | 63,265 | 86,056 | 87,090 | **87,538** | 87,471 | Optimised, buffer 2 |
| capacity 150 lb per load | 87,182 | 69,064 | 85,922 | 86,999 | 87,512 | **87,568** | Optimised, buffer 3 |
| capacity 1000 lb per load | 87,637 | 69,098 | 86,876 | 87,949 | 88,443 | **88,485** | Optimised, buffer 3 |
