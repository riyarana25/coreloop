# Product differentiation

| Dimension | Typical shop/DMS core tracking (public descriptions) | CoreLoop |
|---|---|---|
| Unit of record | Core line and return order | Core lifecycle with a deadline and an expected credit |
| Credit check | Credit memo marked complete by a person | Credit compared with the entitled amount (rate, damage cap, supersession) |
| Time | Overdue reports | Three states; a slow credit is not flagged until the OEM's own settled posting history says it is overdue |
| Shipping | Not found | Minimum-shipment planner with buffer days, brute-force verified |
| Counterfactual | Not found | "What happens if we wait a day" per shipment |
| Evidence standard | Not applicable | Reproducible synthetic benchmark; hidden truth never reaches the policy; tests for information gating |

What is NOT different: tracking and posting credits (commodity), reconciliation per se (offered by at least one vendor).

What would change the answer: real OEM posting data. The classifier learns each OEM's posting-delay tail from settled history, so real data would replace the invented distribution without code changes.
