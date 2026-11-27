# Audit-frequency experiment: results

**SYNTHETIC data. Every parameter is an assumption** (see `audit_frequency_methodology.md`). 200 seeds x 600 cores x 5 policies on identical ledgers; 95% CIs are across seeds.

## 1. Per-policy means (per 600-core ledger, about 180 days of removals)

| Metric | N: no auditing (reference) | A: every 90 days | B: every 30 days | C: every 7 days | D: event-driven continuous |
|---|---|---|---|---|---|
| Total loss ($) = expired return windows + unrecovered credit shortfall | 31,553 +-541 | 26,051 +-536 | 11,784 +-390 | 4,296 +-206 | 4,410 +-208 |
|   of which expired return windows ($) | 18,752 +-431 | 16,543 +-414 | 7,546 +-320 | 92 +-34 | 206 +-46 |
|   of which unrecovered credit shortfall ($) | 12,800 +-331 | 9,508 +-328 | 4,238 +-203 | 4,204 +-200 | 4,204 +-200 |
| True credit discrepancies (count) | 58.3 +-1.0 | 58.3 +-1.0 | 58.3 +-1.0 | 58.3 +-1.0 | 58.3 +-1.0 |
| Discrepancies detected before deadline | 0.0 +-0.0 | 24.2 +-1.0 | 58.1 +-1.0 | 58.3 +-1.0 | 58.3 +-1.0 |
| Discovered too late or never | 58.3 +-1.0 | 34.1 +-1.1 | 0.2 +-0.1 | 0.0 +-0.0 | 0.0 +-0.0 |
| Disputes submitted | 0.0 +-0.0 | 20.9 +-0.9 | 50.0 +-0.9 | 50.2 +-0.9 | 51.2 +-0.9 |
| Disputes approved | 0.0 +-0.0 | 14.9 +-0.7 | 36.6 +-0.7 | 36.7 +-0.7 | 36.7 +-0.7 |
| Cash actually received ($) | 0 +-0 | 3,292 +-193 | 8,562 +-264 | 8,596 +-264 | 8,596 +-264 |
| Core value saved by shipping in time ($) | 0 +-0 | 2,209 +-171 | 11,207 +-365 | 18,660 +-429 | 18,546 +-429 |
| False-positive credit alerts | 0.00 +-0.00 | 0.59 +-0.12 | 0.80 +-0.12 | 0.89 +-0.14 | 1.97 +-0.23 |
| Unnecessary ship alerts (would have shipped anyway) | 0.0 +-0.0 | 9.8 +-1.9 | 53.7 +-2.1 | 70.9 +-5.6 | 29.8 +-0.6 |
| Intervention shipments | 0.0 +-0.0 | 3.5 +-0.1 | 16.4 +-0.2 | 44.8 +-0.2 | 32.5 +-0.2 |
| Staff hours | 0.0 +-0.0 | 17.5 +-0.3 | 45.5 +-0.3 | 134.8 +-0.3 | 30.2 +-0.3 |
| Operating cost ($): staff + freight + software | 0 +-0 | 779 +-17 | 2,361 +-17 | 6,701 +-16 | 5,180 +-14 |
| Verified simulated recovery ($) | 0 +-0 | 5,501 +-268 | 19,769 +-423 | 27,257 +-499 | 27,142 +-501 |
| **Net benefit ($)** | 0 +-0 | 4,722 +-259 | 17,408 +-418 | 20,556 +-495 | 21,962 +-498 |
| Detection delay vs D (days, when both flag) | n/a | 22.9 | 10.9 | 1.3 | 0.0 |

## 2. Preventable loss and net benefit (paired across seeds)

`Preventable Loss = Loss under periodic auditing - Loss under continuous monitoring`

| Quantity | mean | 95% CI |
|---|---|---|
| Loss(A) - Loss(D) | 21,641 | +-502 |
| Loss(B) - Loss(D) | 7,373 | +-322 |
| Loss(C) - Loss(D) | -114 | +-53 |
| Net(D) - Net(A) | 17,240 | +-494 |
| Net(D) - Net(B) | 4,554 | +-317 |
| Net(D) - Net(C) | 1,406 | +-52 |
| Staff minutes: C - D | 6,278 | +-9 |

`Net Benefit = Verified Simulated Recovery - Monitoring Cost - Incremental Operational Cost`; verified recovery = cash from approved disputes + value of cores saved by timely shipping.

## 3. Sensitivity (60 disjoint seeds per scenario; losses in $ per ledger)

| Scenario | Loss A (90d) | Loss B (30d) | Loss C (7d) | Loss D | A-D | C-D (95% CI) | Net D-C (95% CI) |
|---|---|---|---|---|---|---|---|
| base case | 25,237 | 11,675 | 4,123 | 4,331 | 20,906 | -208 +-103 | 1,325 +-99 |
| staff follow-through 60% | 26,219 | 14,116 | 6,916 | 7,547 | 18,672 | -631 +-212 | 869 +-195 |
| staff follow-through 100% | 24,724 | 10,133 | 2,537 | 2,487 | 22,237 | 50 +-42 | 1,570 +-43 |
| return windows x0.5 (tighter) | 26,853 | 18,388 | 5,789 | 4,036 | 22,817 | 1,753 +-368 | 746 +-331 |
| return windows x2 | 22,289 | 5,538 | 3,985 | 4,190 | 18,100 | -205 +-97 | 1,099 +-94 |
| return windows x4 (like long retail policies) | 16,128 | 3,851 | 3,959 | 4,060 | 12,067 | -102 +-65 | 1,594 +-66 |
| leak rates x0.5 | 12,985 | 5,891 | 2,075 | 2,165 | 10,820 | -89 +-83 | 1,519 +-88 |
| leak rates x2 | 50,797 | 22,878 | 8,170 | 8,350 | 42,447 | -180 +-116 | 1,195 +-113 |
| no slow-posting credits | 25,206 | 11,627 | 4,024 | 4,211 | 20,995 | -187 +-116 | 1,336 +-114 |
| slow-posting credits 10% (vs 3%) | 25,305 | 11,696 | 3,996 | 4,131 | 21,174 | -135 +-99 | 1,415 +-95 |
| dispute win probability x0.5 | 26,899 | 16,096 | 8,550 | 8,758 | 18,141 | -208 +-103 | 1,325 +-99 |
| human audits only happen 70% of the time | 26,705 | 17,259 | 6,011 | 4,331 | 22,374 | 1,680 +-338 | 1,685 +-318 |
| human audits only happen 50% of the time | 27,911 | 21,231 | 9,091 | 4,331 | 23,580 | 4,759 +-576 | 3,623 +-499 |
| each human audit takes 30 min total | 25,237 | 11,675 | 4,123 | 4,331 | 20,906 | -208 +-103 | -1,331 +-99 |
| monitoring software $0 / month | 25,237 | 11,675 | 4,123 | 4,331 | 20,906 | -208 +-103 | 3,992 +-99 |
| monitoring software $1,000 / month | 25,237 | 11,675 | 4,123 | 4,331 | 20,906 | -208 +-103 | -9,342 +-99 |
| staff wage $70 / hour | 25,237 | 11,675 | 4,123 | 4,331 | 20,906 | -208 +-103 | 4,995 +-101 |
| freight x2 | 25,237 | 11,675 | 4,123 | 4,331 | 20,906 | -208 +-103 | 1,854 +-100 |
