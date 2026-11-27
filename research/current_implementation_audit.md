# Current implementation audit (commit 2b9e29b, inspected and run in this session)

## What exists (910 lines of Python, 20 tests)
| Module | Lines | Role | State |
|---|---|---|---|
| `coreloop/models.py` | 90 | OEMPolicy, Part, Core, Ledger; ship-by day; entitlement | working |
| `coreloop/catalog.py` | 35 | 3 invented OEM policies, 14 invented parts (3 with a superseded predecessor) | working, invented values |
| `coreloop/generator.py` | 125 | Ledger as seen on one audit day T; hidden `Core.truth` labels; six leak types + confounders | working |
| `coreloop/audit.py` | 75 | Rule-based audit; never reads `Core.truth` (tested by scrambling truth) | working |
| `coreloop/shipping.py` | 109 | Min point-stabbing batching; ship_each / weekly_friday baselines; buffer; expected misses under assumed carrier delay | working, optimal vs brute force on 60 small cases |
| `coreloop/disputes.py` | 103 | CP-SAT multi-day dispute queue; two greedy baselines; deterministic dispute text | working, optimal vs brute force on 25 small cases |
| `coreloop/metrics.py` | 40 | precision/recall/dollars vs hidden truth | working |
| `scripts/batch_eval.py` | 100 | 200-seed evaluation | working, ~1 min |
| `tests/test_engine.py` | 233 | 20 tests incl. determinism across processes | all pass |

## Verified in this session
- `python -m pytest -q`: **20 passed in 5.23 s** (run before any change in this phase).
- `python scripts/batch_eval.py`: output **identical** to the previously delivered `outputs/eval_200seeds.md` (compared with `diff`, blank lines ignored). Numbers below in `baseline_benchmark.md`.

## Architecture
Single flat package. `make_ledger(seed)` simulates each core's life, then **masks everything after audit day T**, so there is exactly one observation instant per ledger. The audit, planner and queue consume that single snapshot. There is no event timeline, no notion of "what was knowable on day t", and no persistence or UI.

## Not implemented (matches the brief)
Streamlit UI; LLM extraction; routing among return / reman / reuse / scrap; any experiment on audit cadence; any independent validation; any freight model beyond `shipments x flat fee per OEM`.

## Reproduce
`pip install -r requirements.txt && python -m pytest -q && python scripts/batch_eval.py`
