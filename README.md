# CoreLoop

Deadline-aware core returns for dealership parts departments. Built for Tekion Tek-Qubit: Women of Impact 2026 (ideation round).
**All data is synthetic**: OEM rules, leak rates and costs are invented, documented assumptions (`docs/ASSUMPTIONS.md`).

**Question the project answers:** can proactive, deadline-aware monitoring demonstrably prevent loss of recoverable value from core returns?
**Honest answer:** yes against infrequent audits (90 and 30 days); against a disciplined weekly audit it ties on dollars lost and wins on staff time and robustness to skipped audits.

## Run it
```
pip install -r requirements.txt
python -m pytest -q                                   # 67 tests, about 17 s
streamlit run ui/app.py                               # the 7-screen demo app (SQLite in data/)
python benchmark/audit_frequency_experiment.py 200 60 # audit-frequency experiment (a few minutes)
python audit/independent_validation.py 30             # classifier validation on a second generator
python shipping/shipping_benchmark.py 100 40          # freight and shipping benchmark
python presentation/build_deck.py                     # rebuild the 6-slide deck
python scripts/batch_eval.py                          # original v0 benchmark (200 seeds)
```

## Layout
| Path | What |
|---|---|
| `coreloop/` | Original engine (kept): models, catalog, lifecycle, generator, audit v0, shipping planner, dispute queue |
| `audit/` | Temporal credit classifier, independent generator, 29 hand-built cases, validation harness and results |
| `simulation/` | Day-by-day policy simulator (A 90d, B 30d, C 7d, D event-driven, N reference) |
| `shipping/` | Freight cost model and shipping benchmark |
| `ledger/operations.py` | All app business logic (world state, plans, queue, counterfactual) |
| `data/store.py` | SQLite persistence of decisions and audit trail |
| `ui/app.py` | Streamlit rendering only |
| `benchmark/` | Experiment code, methodology, results (.md and .json) |
| `research/` | Baseline audit, Tekion landscape, competitors, theme fit, strategy, source register, organiser question (draft, not sent) |
| `tests/` | Regression, parity, adversarial, app tests; `test_strategy.md`, `adversarial_results.md` |
| `presentation/` | Deck, demo script and data, speaker notes, 20 judge Q&As, screenshots, demo video |

## Key results (synthetic)
- Total loss per 600-core ledger: 90-day audit $26.1k, 30-day $11.8k, 7-day $4.3k, event-driven $4.4k. Continuous vs weekly: -$114 +/-$53 (a tie). Staff hours 30.2 vs 134.8.
- Classifier on held-out independent data: recall 99.8%, precision 84.6%, false-positive rate 2.5% (naive overdue rule: 20.1% precision). Its first version scored 49.7%; see `audit/validation_results.md`.
- Shipping vs weekly Friday: 48-58% fewer shipment events, 15-19% lower simulated freight; net benefit break-even to slightly positive.

## Limits
Synthetic data only. No Tekion integration exists or is claimed; whether Tekion already covers parts of this is unknown (`research/tekion_product_landscape.md`). Validation generator shares an author with the classifier. The net benefit versus a weekly audit flips sign under cheap audits or expensive software. CoreLoop is not a marketplace. An LLM is deliberately not used.

Start with `docs/HANDOFF.md`, then `docs/ASSUMPTIONS.md`, then `research/final_product_strategy.md`.
