# Test strategy

Principle: each test attacks a specific claim the pitch makes. A claim without an attack is not tested.

| Claim | Attack | Test file |
|---|---|---|
| The classifier never uses hidden ground truth or future information | Scramble the truth label; overwrite every latent draw; change credit fields dated after day t; check `observe` hides everything after t | `test_classifier.py`, `test_adversarial.py` A1-A2 |
| Classification rules behave at the edges | Ship-by day +/-1, dispute deadline exactly, credit == entitlement, credit above entitlement, tolerance, materiality threshold, $0 credit on good vs damaged core | B1-B5, C5-C6, 29 hand-built cases in `audit/manual_cases.py` |
| Hostile or broken records cannot crash it or create a bogus dispute | Unknown part, unknown OEM, shipped before removal, received before shipped, credit before receipt, negative credit | C1 |
| Statistical learning cannot be fooled by outliers or thin history | A 300-day outlier in history; history of only instant credits; thin history while it is still safe to wait | C2-C4 |
| The planner meets deadlines and only uses business days | Start days on weekends; empty ledger; waiting never saves cores; late reship forfeits | D1-D4 and the brute-force check in `test_engine.py` |
| Freight model is sane | Capacity overflow adds a load; costs positive and monotone in weight and distance | D5, `test_classifier.py` |
| The dispute queue respects staff time and deadlines | 400-item flood under a 120-minute budget; CP-SAT matches brute force on small cases | E1, `test_engine.py` |
| Operator actions change state, persist and cannot double-fire | Restart from SQLite; future-dated decisions ignored; defer expiry; double click; SQL metacharacters | `test_app.py`, E2-E3 |
| Experiments are fair and reproducible | Results of policy D independent of which other policies ran; simulator does not mutate inputs; no-audit reference recovers nothing; byte-for-byte parity with the pre-refactor generator | F1-F4, `test_refactor_parity.py` |
| Every screen renders | Streamlit AppTest on all 7 screens | `test_app.py` |

Not covered, and said so: real OEM data (none available), visual layout beyond rendering without exceptions, load/performance beyond the dispute-queue flood, and any statistical claim about real dealerships.
