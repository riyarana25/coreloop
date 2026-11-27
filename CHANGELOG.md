# Changelog

## v1 (competition build)
Preserved from v0 (unchanged logic, parity-tested byte-for-byte): ledger models, catalog, generator output, shipping planner, CP-SAT dispute queue, 20 original tests.

Changed
- `coreloop/generator.py` is now a thin wrapper over full lifecycles (`coreloop/lifecycle.py`, `observe(life, t)` information gating).
- `coreloop/shipping.py`: added the `last_safe_day` baseline policy.

Added
- `audit/temporal_credit_classifier.py`: pending / at-risk / action-required states; settled-history delay tail (right-censoring fix), materiality threshold, zero-credit-on-damaged review rule, data-error guard.
- `audit/independent_generator.py`, `audit/manual_cases.py` (29 cases), `audit/independent_validation.py`, `audit/validation_results.md`.
- `simulation/engine.py`, `benchmark/audit_frequency_*` (200 seeds + 18 sensitivity scenarios).
- `shipping/freight_cost_model.py`, `shipping/shipping_benchmark.py`, `benchmark/shipping_results.*`.
- `ledger/operations.py`, `data/store.py`, `ui/app.py` (7 screens, SQLite persistence).
- `tests/test_classifier.py`, `test_adversarial.py`, `test_app.py`, `test_strategy.md`, `adversarial_results.md` (67 tests total).
- `research/*` (baseline, Tekion landscape, competitors, theme fit, strategy, sources, draft organiser question).
- `presentation/*`: 6-slide deck, demo script and data, speaker notes, judge Q&A, screenshots.

Corrected
- "50-60% less freight" (flat fee artefact) replaced by "48-58% fewer shipment events" and a modelled "15-19% lower simulated freight".

Fixed during build
- App: the screen selector stalled in a real browser after a decision followed by two navigations (radio `index` changed between reruns). It is now keyed in session state; found while recording the demo, not by the AppTest suite, which did not reproduce it.
- Classifier: unknown parts or OEMs, impossible date orderings and negative credits are routed to a `data_error` review state instead of raising.
- Double-clicking a dispute approval no longer records two submissions.

Demo video: `presentation/CoreLoop_demo.mp4` (about 94 s, captioned screen recording of the app, no voice-over).

## Deck redesign (Rasmalai, 8 slides)
- `presentation/build_deck.py` rebuilt: intro, six evidence slides (problem, prototype with real optimiser plan, two replayed cases, architecture plus "what we deliberately did not automate", benchmark charts, fit and next steps) and an embedded demo video.
- Charts are native and read from `benchmark/*.json`; case studies and the shipment plan are computed live from the engine.
- Corrected staff-hour figures in docs to match the benchmark (30.2 vs 134.8 h; 50% adherence loss $9,091).

## Deck wording pass
- Rewrote all slide headlines and body text in a plain, first-person voice (problem-led headlines, jargon explained first, technical detail kept as small supporting text).
- Slide 1 opens with the story; slide 2 reconciles the $31,553 no-checks baseline with the $26,051 90-day figure (added a "No checks" bar to the slide 6 chart); slide 5 is now a decision-flow diagram with people-vs-automation colouring; slide 8 has a step-by-step explanation of the video and the closing statement.
- Removed the "not a marketplace" sentence from the deck; the theme-fit question stays an open item for the organisers.
