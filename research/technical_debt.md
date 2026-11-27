# Technical debt and risks (prioritised)

| # | Issue | Why it matters | Planned fix |
|---|---|---|---|
| 1 | Single observation instant; no event timeline | Cannot test continuous vs periodic auditing, the central claim | `simulation/` day-by-day engine with information gating (Phase 4) |
| 2 | Audit rules mirror the generator | 100% recall proves nothing | Temporal classifier + independent generator + hand-built cases (Phase 5) |
| 3 | `Core.truth` sits on the same object as observable fields | One careless line could leak labels | Separate truth store; keep the scramble test; add a test that observations are built from a truth-free view |
| 4 | Freight = shipments x flat fee | Shipment count is not freight cost | Distance, weight, capacity, packaging model (Phase 6) |
| 5 | Invented 14-30 day windows | Longer real windows shrink the benefit of batching and of frequent audits | Sensitivity on window length (x1, x2, x4) |
| 6 | Staff follow-through is implicit (100%) | Flagged != disputed != approved != cash | Explicit funnel with probabilities (Phase 4) |
| 7 | Single-hop supersession, 14 parts | Real chains are longer | Document; add two-hop test case |
| 8 | No persistence, no UI | Cannot demo state changes | SQLite + Streamlit (Phase 8) |
| 9 | No adversarial tests | Failure modes unknown | Phase 10 suite |
| 10 | Dispute queue adds little | Risk of over-claiming | Keep as supporting feature only |
| 11 | Business days only Mon-Fri, no holidays | Minor timing error | Documented limitation |
